"""예측오차가 크게 발생하는 생산조건 분석 + 피크위험 이벤트 FN/FP 집중 조건.

입력: 표본 외(out-of-sample) 예측 = 롤링 백테스트(7~8월 8주) + 최종 시험(9/1~9/14)
"""
import numpy as np
import pandas as pd

from .config import PEAK_EVENT_KW, FIG, TAB
from .plotting import plt, save, C
from .rules import fit_rules


def add_conditions(df):
    d = df.copy()
    d["err"] = d["pred"] - d["kw"]
    d["abs_err"] = d["err"].abs()
    d["prod_bin"] = pd.cut(d["prod"], [-1, 0, 300, 1000, 2000, 1e9], labels=["0", "1-300", "300-1천", "1천-2천", "2천+"])
    d["temp_bin"] = pd.cut(d["temp"], [-20, 15, 22, 26, 40], labels=["<15", "15-22", "22-26", "26+"])
    day = d.groupby("date").agg(act_mean=("kw", "mean"), plan=("day_prod", "first"))
    # 사후 진단용: 생산계획은 0인데 실제로 설비가 가동된 날(계획-실적 불일치)
    day["plan_mismatch"] = ((day["plan"] == 0) & (day["act_mean"] > 60)).astype(int)
    d = d.join(day[["plan_mismatch"]], on="date")
    hf = d["hours_from_first_prod"]
    d["phase"] = np.select(
        [d["full_workday"] == 0, hf.between(-1, 1), d["hour"].isin([12, 13]), d["hour"] >= 17],
        ["비가동일", "기동구간(첫 생산 -1~+1h)", "점심 정지·재가동(12~13시)", "저녁·야간(17시~)"], "주간 정상가동")
    return d


def group_table(d, col):
    g = d.groupby(col, observed=True)
    t = pd.DataFrame({"표본수": g.size(), "MAE": g["abs_err"].mean(), "RMSE": g["err"].apply(lambda e: np.sqrt(np.mean(e ** 2))),
                      "Bias": g["err"].mean(), "평균부하": g["kw"].mean()})
    t["오차 기여%"] = 100 * g["abs_err"].sum() / d["abs_err"].sum()
    return t.round(2)


def run(oos: pd.DataFrame, tag="oos"):
    d = add_conditions(oos.dropna(subset=["kw"]).reset_index(drop=True))
    tables = {}
    for col, name in [("phase", "운전구간"), ("hour", "시각"), ("prod_bin", "생산계획량"), ("temp_bin", "기온"),
                      ("restart_day", "재가동일"), ("plan_mismatch", "계획-실적불일치일"), ("dow", "요일")]:
        t = group_table(d, col)
        t.index.name = name
        t.to_csv(TAB / f"error_by_{col}_{tag}.csv", encoding="utf-8-sig")
        tables[col] = t

    # 큰 오차(상위 10%) 규칙 추출
    thr = d["abs_err"].quantile(0.9)
    d["big_err"] = (d["abs_err"] >= thr).astype(int)
    feats = ["hours_from_first_prod", "hour", "prod", "temp", "restart_day", "quarter", "day_prod"]
    names = ["첫생산후경과h", "시각", "생산계획량", "기온", "재가동일", "15분구간", "일생산계획"]
    dd = d.copy()
    dd["hours_from_first_prod"] = dd["hours_from_first_prod"].fillna(-99)
    rules = fit_rules(dd, dd["big_err"].values, feats, names, depth=3, min_leaf=60)
    rules = rules.rename(columns={"가중평균": "큰오차 비율"})
    rules["큰오차 비율"] = (rules["큰오차 비율"] * 100).round(1)
    rules.to_csv(TAB / f"error_rules_{tag}.csv", index=False, encoding="utf-8-sig")
    tables["rules"] = rules
    tables["big_err_threshold"] = thr

    # 피크위험 이벤트 FN / FP
    d["ev_true"] = (d["kw"] >= PEAK_EVENT_KW).astype(int)
    pcol = "pred_alert" if "pred_alert" in d else "pred"
    d["ev_pred"] = (d[pcol] >= PEAK_EVENT_KW).astype(int)
    d["cm"] = np.select([(d.ev_true == 1) & (d.ev_pred == 0), (d.ev_true == 0) & (d.ev_pred == 1),
                         (d.ev_true == 1) & (d.ev_pred == 1)], ["FN", "FP", "TP"], "TN")
    cm_phase = pd.crosstab(d["phase"], d["cm"])
    cm_hour = pd.crosstab(d["hour"], d["cm"])
    cm_temp = pd.crosstab(d["temp_bin"], d["cm"])
    cm_quarter = pd.crosstab([d["hour"].where(d["hour"].isin([8, 9, 13, 14]), -1), d["quarter"]], d["cm"])
    for k, v in [("phase", cm_phase), ("hour", cm_hour), ("temp", cm_temp), ("quarter", cm_quarter)]:
        v.to_csv(TAB / f"event_cm_by_{k}_{tag}.csv", encoding="utf-8-sig")
        tables[f"cm_{k}"] = v

    # 그림: 시각 x 요일 MAE 히트맵 + 운전구간별 MAE/기여도
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1.5, 1]})
    hm = d.pivot_table(index="dow", columns="hour", values="abs_err", aggfunc="mean")
    im = ax[0].imshow(hm.values, aspect="auto", cmap="Reds")
    ax[0].set_yticks(range(len(hm.index)), ["월화수목금토일"[i - 1] for i in hm.index])
    ax[0].set_xticks(range(0, 24, 2), range(0, 24, 2))
    ax[0].set(xlabel="시각", title="시각 x 요일별 평균 절대오차(kW)")
    plt.colorbar(im, ax=ax[0])
    t = tables["phase"].sort_values("MAE")
    ax[1].barh(t.index, t["MAE"], color=C["pred"])
    for i, (m, s) in enumerate(zip(t["MAE"], t["오차 기여%"])):
        ax[1].text(m + 0.3, i, f"기여 {s:.0f}%", va="center", fontsize=8)
    ax[1].set(xlabel="MAE(kW)", title="운전구간별 오차")
    save(fig, FIG / f"error_heatmap_{tag}.png")
    return d, tables
