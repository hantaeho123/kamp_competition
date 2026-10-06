"""3~5단계: 실제 피크 구간 추출 -> 두 유형 구분 -> 유형별 발생조건.

3단계 피크 구간: 15분 최대수요전력이 기준(180kW, 이 값 이상인 슬롯이 전체의 5.0%) 이상인 연속 구간.
                 사이에 1슬롯(15분)만 기준 아래로 내려간 경우는 한 구간으로 합침.
4단계 유형 구분: 구간마다 (상승폭, 지속시간, 직전 1시간 부하 수준)을 계산해 K-means로 묶음.
                 묶음 수는 실루엣 점수로 정함(2개가 최고). 복사일 중복을 막기 위해 '고유한 날'의 구간으로만 학습.
5단계 발생조건: 유형별 시작 시각, 생산계획량, 생산계획 변화, 운영상태(재가동일·시간대), 기온 비교 + 순위합 검정.
"""
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import PEAK_EVENT_KW, S3, S4, S5, SEED
from .features import clock_state
from .plotting import plt, save, C

TYPE_NAME = {1: "유형1: 가동 시작·재개 직후 크게 오르는 피크", 2: "유형2: 가동 중 잠깐 더 오르는 피크"}
TYPE_SHORT = {1: "유형1(시작·재개 직후)", 2: "유형2(가동 중)"}
TYPE_COLOR = {1: C["peak"], 2: C["pred"]}


def unique_days(X):
    """복사 그룹마다 가장 이른 하루만 남긴 '고유한 날' 집합."""
    d = X.groupby("date")["aug_group"].first().reset_index()
    d["key"] = np.where(d["aug_group"] >= 0, d["aug_group"].astype(str), d["date"].astype(str))
    return set(d.drop_duplicates("key")["date"])


def extract_episodes(X, thr=PEAK_EVENT_KW):
    rows = []
    for d, g in X.groupby("date"):
        g = g.sort_values("slot")
        kw = g["kw"].interpolate(limit=2).values
        if np.isnan(kw).mean() > 0.2:
            continue
        hi = np.nan_to_num(kw) >= thr
        for i in range(1, 95):                      # 15분 한 칸짜리 끊김은 이어 붙임
            if not hi[i] and hi[i - 1] and hi[i + 1]:
                hi[i] = True
        i = 0
        while i < 96:
            if not hi[i]:
                i += 1
                continue
            j = i
            while j + 1 < 96 and hi[j + 1]:
                j += 1
            pre = np.nanmean(kw[max(0, i - 4):i]) if i > 0 else np.nan
            post = np.nanmean(kw[j + 1:j + 5]) if j < 95 else np.nan
            peak = np.nanmax(kw[i:j + 1])
            r = g.iloc[i]
            rows.append({
                "date": d, "start_slot": i, "end_slot": j, "start_hour": i // 4,
                "시작시각": f"{i // 4:02d}:{(i % 4) * 15:02d}", "지속시간(분)": (j - i + 1) * 15, "최대(kW)": peak,
                "직전1시간 평균(kW)": pre, "직후1시간 평균(kW)": post, "상승폭(kW)": peak - pre,
                "직전30분 상승(kW)": kw[i] - kw[max(i - 2, 0)],
                "생산계획량(시작 시간)": r["prod"], "직전 시간 생산계획량": r["prod_lag1h"],
                "생산계획 변화(개/h)": r["prod"] - (r["prod_lag1h"] if pd.notna(r["prod_lag1h"]) else 0),
                "일 생산계획량": r["day_prod"], "재가동일": r["restart_day"], "기온": r["temp"],
                "요일": r["dow"], "월": r["month"], "운영상태": clock_state(i // 4), "복사그룹크기": r["aug_size"],
            })
            i = j + 1
    return pd.DataFrame(rows)


def step3_extract(X):
    """3단계: 피크 구간 추출 + 기준값 근거."""
    y = X["kw"].dropna()
    rows = []
    for thr in (160, 170, 175, 180, 185, 190, 200):
        e = extract_episodes(X, thr)
        rows.append({"기준(kW)": thr, "기준 이상 슬롯 비율%": 100 * (y >= thr).mean(), "피크 구간 수": len(e),
                     "피크 발생일 수": e["date"].nunique() if len(e) else 0,
                     "구간 평균 지속(분)": e["지속시간(분)"].mean() if len(e) else np.nan})
    T = pd.DataFrame(rows)
    T.round(2).to_csv(S3 / "threshold_sensitivity.csv", index=False, encoding="utf-8-sig")
    E = extract_episodes(X, PEAK_EVENT_KW)
    E["고유일"] = E["date"].isin(unique_days(X)).astype(int)
    work_days = X[X["full_workday"] == 1].groupby("date")["kw"].count()
    work_days = set(work_days[work_days >= 77].index)
    summ = pd.Series({
        "기준(kW)": PEAK_EVENT_KW, "기준의 근거": "180kW 이상 슬롯이 전체 15분 슬롯의 5.0%(상위 5%)",
        "전체 피크 구간 수": len(E), "고유일 기준 피크 구간 수": int(E["고유일"].sum()),
        "피크 발생일 수(고유일)": E.loc[E["고유일"] == 1, "date"].nunique(),
        "7~9월 정상 가동일 수": len([d for d in work_days if d >= pd.Timestamp("2021-07-01")]),
        "7~9월 피크 발생일 수": E.loc[E["date"] >= "2021-07-01", "date"].nunique(),
        "구간 지속시간 중앙값(분)": E["지속시간(분)"].median(), "구간 최대값 평균(kW)": round(E["최대(kW)"].mean(), 1),
    }, name="값")
    summ.to_csv(S3 / "peak_extraction_summary.csv", encoding="utf-8-sig")

    # 그림: 7~9월 일 최대와 피크 구간 수, 예시일
    fig, ax = plt.subplots(1, 2, figsize=(13, 4), gridspec_kw={"width_ratios": [1.3, 1]})
    d0 = E[E["date"] >= "2021-07-01"].groupby("date").size().idxmax()
    g = X[X["date"] == d0].sort_values("slot")
    ax[0].plot(g["slot"] / 4, g["kw"], color=C["actual"], lw=1.2)
    for _, e in E[E["date"] == d0].iterrows():
        ax[0].axvspan(e["start_slot"] / 4, (e["end_slot"] + 1) / 4, color=C["peak"], alpha=.25)
    ax[0].axhline(PEAK_EVENT_KW, ls="--", color=C["peak"], lw=.8)
    ax[0].set(xlabel="시각", ylabel="kW", title=f"피크 구간 추출 예시({pd.Timestamp(d0):%m-%d}): 180kW 이상 연속 구간(붉은 띠)")
    ax[1].bar(T["기준(kW)"].astype(str), T["피크 구간 수"], color=[C["peak"] if t == PEAK_EVENT_KW else C["muted"] for t in T["기준(kW)"]])
    ax[1].set(xlabel="기준(kW)", ylabel="피크 구간 수", title="기준값에 따른 피크 구간 수(채택: 180kW)")
    save(fig, S3 / "peak_extraction.png")
    return E, T, summ


CL_FEATS = ["상승폭(kW)", "지속시간(분)", "직전1시간 평균(kW)"]


def _design(E):
    F = E[CL_FEATS].copy()
    F["지속시간(분)"] = np.log(F["지속시간(분)"])      # 15~240분으로 치우친 분포 -> 로그
    return F.fillna(F.median())


def step4_types(E, X):
    """4단계: 두 유형 구분."""
    U = E[E["고유일"] == 1]
    sc = StandardScaler().fit(_design(U))
    Z = sc.transform(_design(U))
    sil = []
    for k in (2, 3, 4, 5, 6):
        km = KMeans(k, n_init=20, random_state=SEED).fit(Z)
        sil.append({"묶음 수": k, "실루엣 점수": silhouette_score(Z, km.labels_), "묶음별 구간 수": str(sorted(np.bincount(km.labels_), reverse=True))})
    SIL = pd.DataFrame(sil)
    SIL.round(3).to_csv(S4 / "cluster_count_selection.csv", index=False, encoding="utf-8-sig")
    km = KMeans(2, n_init=20, random_state=SEED).fit(Z)
    lab = km.predict(sc.transform(_design(E)))
    big = int(np.argmax(sc.inverse_transform(km.cluster_centers_)[:, 0]))   # 상승폭이 큰 묶음 = 유형1
    E = E.copy()
    E["유형"] = np.where(lab == big, 1, 2)
    E.to_csv(S4 / "peak_episodes_typed.csv", index=False, encoding="utf-8-sig")

    U = E[E["고유일"] == 1]
    cols = ["지속시간(분)", "최대(kW)", "상승폭(kW)", "직전30분 상승(kW)", "직전1시간 평균(kW)", "직후1시간 평균(kW)"]
    prof = U.groupby("유형")[cols].agg(["mean", "median"]).round(1)
    prof.columns = [f"{a} {'평균' if b == 'mean' else '중앙값'}" for a, b in prof.columns]
    prof.insert(0, "구간 수", U.groupby("유형").size())
    prof.index = [TYPE_NAME[i] for i in prof.index]
    prof.T.to_csv(S4 / "type_profile.csv", encoding="utf-8-sig")
    # 유형 간 차이 검정
    tests = []
    for c in cols:
        a, b = U.loc[U["유형"] == 1, c].dropna(), U.loc[U["유형"] == 2, c].dropna()
        tests.append({"특성": c, "유형1 중앙값": a.median(), "유형2 중앙값": b.median(), "순위합 검정 p값": mannwhitneyu(a, b).pvalue})
    pd.DataFrame(tests).to_csv(S4 / "type_difference_tests.csv", index=False, encoding="utf-8-sig")

    # 그림1: 상승폭 x 직전 부하 산점도 / 그림2: 구간 시작 기준 정렬 평균 프로파일(전후 패턴)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for t in (1, 2):
        u = U[U["유형"] == t]
        ax[0].scatter(u["직전1시간 평균(kW)"], u["상승폭(kW)"], s=8 + u["지속시간(분)"] / 3, color=TYPE_COLOR[t], alpha=.55, label=TYPE_SHORT[t])
    ax[0].set(xlabel="피크 직전 1시간 평균 부하(kW)", ylabel="상승폭(kW)", title="피크 구간의 상승폭과 직전 부하(점 크기=지속시간)")
    ax[0].legend(frameon=False, fontsize=8)
    daily = X.pivot_table(index="date", columns="slot", values="kw")
    rel = np.arange(-8, 13)
    for t in (1, 2):
        M = []
        for _, e in U[U["유형"] == t].iterrows():
            row = daily.loc[e["date"]].values
            M.append([row[e["start_slot"] + r] if 0 <= e["start_slot"] + r < 96 else np.nan for r in rel])
        M = np.array(M, float)
        ax[1].plot(rel * 15, np.nanmean(M, 0), color=TYPE_COLOR[t], lw=1.8, label=TYPE_SHORT[t])
        ax[1].fill_between(rel * 15, np.nanpercentile(M, 25, 0), np.nanpercentile(M, 75, 0), color=TYPE_COLOR[t], alpha=.15)
    ax[1].axvline(0, color="k", lw=.6, ls=":")
    ax[1].axhline(PEAK_EVENT_KW, color="k", lw=.6, ls="--")
    ax[1].set(xlabel="피크 구간 시작 기준 경과(분)", ylabel="kW", title="피크 전후 평균 부하(띠: 25~75%)")
    ax[1].legend(frameon=False, fontsize=8)
    bins = [15, 30, 45, 60, 90, 120, 180, 241]
    lbl = ["15", "30", "45", "60~75", "90~105", "120~165", "180+"]
    for k, t in enumerate((1, 2)):
        h = pd.cut(U.loc[U["유형"] == t, "지속시간(분)"], bins=bins, right=False, labels=lbl).value_counts().reindex(lbl)
        ax[2].bar(np.arange(len(lbl)) + (k - .5) * .4, h.values, .4, color=TYPE_COLOR[t], label=TYPE_SHORT[t])
    ax[2].set_xticks(range(len(lbl)), lbl, fontsize=8)
    ax[2].set(xlabel="지속시간(분)", ylabel="구간 수", title="유형별 지속시간 분포")
    ax[2].legend(frameon=False, fontsize=8)
    save(fig, S4 / "peak_types.png")
    return E, SIL, prof


def step5_conditions(E, X):
    """5단계: 유형별 발생조건."""
    U = E[E["고유일"] == 1]
    out = {}
    out["by_hour"] = pd.crosstab(U["start_hour"], U["유형"]).rename(columns=TYPE_SHORT)
    st = pd.crosstab(U["운영상태"], U["유형"]).rename(columns=TYPE_SHORT)
    st_pct = (st / st.sum() * 100).round(1).add_suffix(" 비중%")
    out["by_state"] = st.join(st_pct)
    num = ["생산계획량(시작 시간)", "직전 시간 생산계획량", "생산계획 변화(개/h)", "일 생산계획량", "기온", "재가동일"]
    rows = []
    for c in num:
        a, b = U.loc[U["유형"] == 1, c].dropna(), U.loc[U["유형"] == 2, c].dropna()
        rows.append({"조건": c, "유형1 평균": a.mean(), "유형1 중앙값": a.median(), "유형2 평균": b.mean(), "유형2 중앙값": b.median(),
                     "순위합 검정 p값": mannwhitneyu(a, b).pvalue})
    out["numeric"] = pd.DataFrame(rows).round(3)
    U2 = U.assign(변화구간=pd.cut(U["생산계획 변화(개/h)"], [-1e9, -300, 300, 1e9], labels=["300개 이상 감소", "변화 작음(±300개)", "300개 이상 증가"]),
                  기온구간=pd.cut(U["기온"], [-30, 15, 22, 26, 50], labels=["15도 미만", "15~22도", "22~26도", "26도 이상"]))
    out["by_prod_change"] = pd.crosstab(U2["변화구간"], U2["유형"]).rename(columns=TYPE_SHORT)
    out["by_temp"] = pd.crosstab(U2["기온구간"], U2["유형"]).rename(columns=TYPE_SHORT)

    # 가동일당 발생 빈도: 재가동일 여부 x 유형, 일 최고기온 구간 x 유형 (고유한 정상 가동일 기준)
    days = X[(X["full_workday"] == 1) & X["date"].isin(unique_days(X))].groupby("date").agg(
        restart=("restart_day", "first"), tmax=("temp_max", "first"), n=("kw", "count"))
    days = days[days["n"] >= 77]
    cnt = U.groupby(["date", "유형"]).size().unstack(fill_value=0).reindex(days.index, fill_value=0)
    for t in (1, 2):
        if t not in cnt:
            cnt[t] = 0
    days = days.join(cnt)
    days["재가동일 여부"] = np.where(days["restart"] == 1, "재가동일", "일반 가동일")
    days["일 최고기온"] = pd.cut(days["tmax"], [-30, 20, 27, 50], labels=["20도 미만", "20~27도", "27도 이상"])

    def rate(by):
        g = days.groupby(by, observed=True)
        return pd.DataFrame({"가동일 수": g.size(), "유형1 발생일 비율%": g[1].apply(lambda s: 100 * (s > 0).mean()),
                             "유형1 일평균 구간 수": g[1].mean(), "유형2 발생일 비율%": g[2].apply(lambda s: 100 * (s > 0).mean()),
                             "유형2 일평균 구간 수": g[2].mean()}).round(2)
    out["rate_by_restart"] = rate("재가동일 여부")
    out["rate_by_tmax"] = rate("일 최고기온")
    for k, v in out.items():
        v.to_csv(S5 / f"type_conditions_{k}.csv", index=(k != "numeric"), encoding="utf-8-sig")

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    hh = out["by_hour"].reindex(range(7, 20), fill_value=0)
    for k, t in enumerate((1, 2)):
        ax[0].bar(hh.index + (k - .5) * .4, hh[TYPE_SHORT[t]], .4, color=TYPE_COLOR[t], label=TYPE_SHORT[t])
    ax[0].set(xlabel="피크 구간 시작 시각", ylabel="구간 수", title="유형별 시작 시각")
    ax[0].legend(frameon=False, fontsize=8)
    for t in (1, 2):
        u = U[U["유형"] == t]
        ax[1].scatter(u["직전 시간 생산계획량"] + 1, u["생산계획량(시작 시간)"] + 1, s=10, color=TYPE_COLOR[t], alpha=.5, label=TYPE_SHORT[t])
    ax[1].plot([1, 1e4], [1, 1e4], color="k", lw=.5, ls=":")
    ax[1].set(xscale="log", yscale="log", xlabel="직전 시간 생산계획량(개)", ylabel="피크 시작 시간 생산계획량(개)",
              title="생산계획 변화(대각선 위 = 증가)")
    ax[1].legend(frameon=False, fontsize=8)
    r = out["rate_by_tmax"]
    xx = np.arange(len(r))
    ax[2].bar(xx - .2, r["유형1 일평균 구간 수"], .4, color=TYPE_COLOR[1], label=TYPE_SHORT[1])
    ax[2].bar(xx + .2, r["유형2 일평균 구간 수"], .4, color=TYPE_COLOR[2], label=TYPE_SHORT[2])
    ax[2].set_xticks(xx, r.index)
    ax[2].set(xlabel="일 최고기온", ylabel="가동일당 평균 피크 구간 수", title="기온과 유형별 발생 빈도")
    ax[2].legend(frameon=False, fontsize=8)
    save(fig, S5 / "type_conditions.png")
    return out
