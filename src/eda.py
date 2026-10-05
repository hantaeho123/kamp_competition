"""데이터 이해·진단 그림/표."""
import numpy as np
import pandas as pd

from .config import S0, QUARTER_COLS, TEST_START, CV_FOLD_STARTS, CV_FOLD_DAYS
from .data import diagnose
from .plotting import plt, save, C


def run(raw, hourly, L):
    # 품질 진단표
    rep = diagnose(raw)
    pd.Series(rep, name="값").to_csv(S0 / "data_quality.csv", encoding="utf-8-sig")
    actions = pd.DataFrame([
        ["시간 컬럼 손상·행 정렬 오류", "07-13, 07-15 (48행)", "'시간'에 70~188 값, 손상값 기준 정렬로 실제 시각 불명", "전력 목표값 제외, 생산계획은 직전 4주 동요일 중앙값으로 대체"],
        ["전력 0 연속 구간", "08-28 18시~08-29 10시 (17행)", "4개 15분 값 모두 0, 공장인원도 결측 -> 계측 누락/정전", "목표값 결측 처리(학습·평가 제외)"],
        ["증강 복사일", f"{int((hourly.groupby('date').aug_size.first() > 1).sum())}일 / 45개 그룹", "하루 96개 15분 전력 패턴이 다른 날과 완전 동일, 1~6월에 집중(요일 불일치 포함)", "그룹 단위 집계 가중치(1/n), 지연변수 배제 근거"],
        ["15분 단발 0값", "6개 슬롯(08-28, 08-29, 09-08)", "대기전력(약 21kW)보다 낮은 0kW가 정상 부하 사이에 1~2슬롯 출현", "계측 누락으로 결측 처리"],
        ["강수량 누적값", "전 기간", "1시에 초기화되는 일 누적값, 0시 행에 전일 합계", "시간 강수량으로 차분 변환"],
        ["결측", "풍속 3, 강수량 1, 공장인원 17", "산발 결측", "선형보간 / 0(비가동)"],
        ["(날짜,시간) 중복 키", "5건", "손상된 '시간' 값끼리 우연히 같음", "시간 재구성으로 해소"],
        ["계획-실적 불일치", "일요일 특근 등", "생산계획 0인데 설비 가동(최대 130kW)", "오차분석의 별도 조건으로 분리"],
    ], columns=["항목", "범위", "근거", "처리"])
    actions.to_csv(S0 / "data_cleaning_actions.csv", index=False, encoding="utf-8-sig")

    day = hourly.groupby("date").agg(pmax=("avg", "max"), pmean=("avg", "mean"), prod=("prod", "sum"),
                                     aug=("aug_size", "first"), dow=("dow", "first"))
    q = hourly.groupby("date")[QUARTER_COLS].max().max(axis=1)
    day["qmax"] = q

    # 그림1: 일별 최대·평균 + 증강일 표시
    fig, ax = plt.subplots(2, 1, figsize=(13, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(day.index, day["qmax"], color=C["peak"], lw=1, label="일 최대 15분 수요전력")
    ax[0].plot(day.index, day["pmean"], color=C["actual"], lw=1, label="일 평균")
    aug = day[day.aug > 1]
    ax[0].scatter(aug.index, aug["qmax"], s=8, color=C["accent"], zorder=3, label="증강 복사일")
    ax[0].axvspan(pd.Timestamp("2021-09-01"), pd.Timestamp("2021-09-14"), color=C["band"], alpha=.4, label="시험 구간")
    ax[0].set(ylabel="kW", title="일별 최대수요전력과 증강 복사일 분포")
    ax[0].legend(frameon=False, ncol=4, fontsize=8)
    ax[1].bar(day.index, day["prod"] / 1000, color=C["muted"])
    ax[1].set(ylabel="일 생산계획(천개)")
    save(fig, S0 / "eda_daily_overview.png")

    # 그림2: 증강 그룹 달력
    cal = day.assign(m=day.index.month, d=day.index.day).pivot(index="m", columns="d", values="aug")
    fig, ax = plt.subplots(figsize=(12, 3.4))
    im = ax.imshow(np.log2(cal.values), cmap="YlOrRd", aspect="auto")
    ax.set_yticks(range(len(cal.index)), [f"{m}월" for m in cal.index])
    ax.set_xticks(range(0, 31, 2), range(1, 32, 2))
    ax.set(xlabel="일", title="증강 복사 그룹 크기(같은 전력 패턴을 가진 날 수, log2) — 7~9월은 거의 원본")
    cb = plt.colorbar(im, ax=ax)
    cb.set_ticks([0, 1, 2, 3, 4], labels=["1", "2", "4", "8", "16"])
    save(fig, S0 / "eda_augmentation_calendar.png")

    # 그림3: 요일별 평균 15분 프로파일 + 생산계획 vs 전력
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    w = 1 / L["aug_size"]
    prof = L.assign(w=w, kww=L["kw"] * w).groupby(["dow", "slot"]).apply(lambda g: g["kww"].sum() / g.loc[g.kw.notna(), "w"].sum()).unstack(0)
    names = "월화수목금토일"
    cmap = plt.get_cmap("viridis")
    for i, dw in enumerate(prof.columns):
        ax[0].plot(prof.index / 4, prof[dw], color=cmap(i / 6), label=names[dw - 1], lw=1.3)
    ax[0].set(xlabel="시각", ylabel="kW", title="요일별 평균 15분 최대수요전력 프로파일")
    ax[0].legend(frameon=False, ncol=7, fontsize=8)
    hw = hourly[(hourly["prod"] > 0) & hourly["avg"].notna()]
    sc = ax[1].scatter(hw["prod"], hw[QUARTER_COLS].max(axis=1), c=hw["hour"], s=4, cmap="twilight", alpha=.6)
    ax[1].set(xscale="symlog", xlabel="시간당 생산계획량(개, symlog)", ylabel="시간 내 최대 15분 수요전력(kW)",
              title="생산계획량 vs 전력(색: 시각)")
    plt.colorbar(sc, ax=ax[1])
    save(fig, S0 / "eda_profiles.png")

    # 그림4: 상관행렬
    cols = ["avg", "prod", "staff", "temp", "humid", "wind", "rain", "hour", "dow", "month", "tariff_season", "labor_mult"]
    kor = ["전력평균", "생산량", "공장인원", "기온", "습도", "풍속", "강수(시간)", "시각", "요일", "월", "전기요금(계절)", "인건비"]
    cm = hourly[cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(7.5, 6))
    im = ax.imshow(cm.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)), kor, rotation=60, ha="right")
    ax.set_yticks(range(len(cols)), kor)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{cm.values[i, j]:.2f}", ha="center", va="center", fontsize=6.5)
    plt.colorbar(im, ax=ax)
    ax.set_title("변수 간 Spearman 상관")
    save(fig, S0 / "eda_corr.png")
    cm.round(3).to_csv(S0 / "eda_corr.csv", encoding="utf-8-sig")
    return rep, actions


def split_table(X):
    """시간 순 Train / Valid / Test 분할표(행 = 15분 슬롯). Valid는 롤링 원점 8개 fold."""
    rows = []
    y = X["kw"].notna()
    for i, f0 in enumerate(CV_FOLD_STARTS, 1):
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        tr = (X["ts"] < s) & y
        va = (X["ts"] >= s) & (X["ts"] < e) & y
        rows.append({"구분": f"Valid fold {i}", "학습 구간": f"2021-01-01 ~ {(s - pd.Timedelta(days=1)).date()}", "학습 슬롯 수": int(tr.sum()),
                     "평가 구간": f"{s.date()} ~ {(e - pd.Timedelta(days=1)).date()}", "평가 슬롯 수": int(va.sum()),
                     "평가 구간 내 복사일 수": int(X.loc[va & (X["aug_size"] > 1), "date"].nunique())})
    t = pd.Timestamp(TEST_START)
    tr = (X["ts"] < t) & y
    te = (X["ts"] >= t) & y
    rows.append({"구분": "Test(최종 1회)", "학습 구간": f"2021-01-01 ~ {(t - pd.Timedelta(days=1)).date()}", "학습 슬롯 수": int(tr.sum()),
                 "평가 구간": f"{t.date()} ~ {X['ts'].max().date()}", "평가 슬롯 수": int(te.sum()),
                 "평가 구간 내 복사일 수": int(X.loc[te & (X["aug_size"] > 1), "date"].nunique())})
    T = pd.DataFrame(rows)
    T.to_csv(S0 / "train_valid_test_split.csv", index=False, encoding="utf-8-sig")
    drop = pd.DataFrame([
        ["평균", "예측 대상 4개 값의 평균(목표값 그 자체)", "제거"],
        ["15분/30분/45분/60분(같은 시각)", "예측 대상", "입력에서 제거, 목표값으로만 사용"],
        ["전기요금(계절)", "월만으로 결정(값 3개)", "제거(월과 중복)"],
        ["인건비", "시각만으로 결정(9~17시 1.0, 그 외 1.5)", "제거(시각과 중복)"],
        ["시간(원본)", "07-13, 07-15에 손상", "행 순서로 재구성한 시각 사용, 두 날 전력은 제외"],
        ["전력 지연값(전일·전주 등)", "복사일이 날짜 간 연속성을 깨뜨림(백테스트 MAE 7.73 -> 11.99로 악화)", "최종 모델에서 제외"],
    ], columns=["변수", "근거", "처리"])
    drop.to_csv(S0 / "leakage_and_redundant_variables.csv", index=False, encoding="utf-8-sig")
    return T
