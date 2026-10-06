"""최대전력 피크 발생 조건 분석.

- 피크위험 이벤트: 15분 최대수요전력 >= 180kW (전체 슬롯 상위 5%)
- 증강 복사일의 중복 집계를 막기 위해 모든 집계에 1/aug_size 가중치 적용
- (1) 조건별 이벤트 발생률, (2) 설명용 분류모델 + SHAP(주효과·상호작용), (3) 의사결정나무 규칙, (4) 월별 최대피크 사례
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from .rules import fit_rules

from .config import PEAK_EVENT_KW, S5, SEED
from .plotting import plt, save, C

PEAK_FEATS = ["hour", "quarter", "dow", "restart_day", "days_since_workday", "prod", "prod_lag1h", "prod_lead1h",
              "hours_from_first_prod", "prod_start_hour", "day_prod", "temp", "humid", "month", "lunch"]
KOR = {"hour": "시각", "quarter": "15분 구간", "dow": "요일", "restart_day": "재가동일(주말·휴무 후)",
       "days_since_workday": "직전 가동일 경과일", "prod": "생산계획량(당시간)", "prod_lag1h": "직전시간 생산량",
       "prod_lead1h": "다음시간 생산량", "staff": "공장인원(환산)", "hours_from_first_prod": "첫 생산 후 경과시간",
       "prod_start_hour": "생산 시작 시간", "day_prod": "일 생산계획량", "temp": "기온", "humid": "습도",
       "month": "월", "lunch": "점심시간"}


def wrate(df, by):
    w = 1 / df["aug_size"]
    g = df.assign(w=w, ev=df["event"] * w).groupby(by)
    return (g["ev"].sum() / g["w"].sum() * 100).rename("이벤트율%")


def run(X: pd.DataFrame):
    d = X[X["kw"].notna()].copy()
    d["event"] = (d["kw"] >= PEAK_EVENT_KW).astype(int)
    d["temp_bin"] = pd.cut(d["temp"], [-20, 5, 15, 22, 26, 40], labels=["<5", "5-15", "15-22", "22-26", "26+"])
    out = {}

    # (1) 조건별 발생률
    out["by_hour_restart"] = wrate(d, ["hour", "restart_day"]).unstack()
    out["by_month"] = wrate(d, "month")
    out["by_tempbin_work"] = wrate(d[d.full_workday == 1], "temp_bin")
    out["by_quarter_work"] = wrate(d[(d.full_workday == 1) & d.hour.isin([8, 13])], ["hour", "quarter"]).unstack()
    out["by_dow"] = wrate(d, "dow")
    share = d[d.event == 1].assign(w=1 / d["aug_size"]).groupby("hour")["w"].sum()
    out["event_share_by_hour"] = (share / share.sum() * 100).rename("이벤트 비중%")
    for k, v in out.items():
        v.round(2).to_csv(S5 / f"peak_{k}.csv", encoding="utf-8-sig")

    # 그림: 시각 x 재가동일 이벤트율 / 시각별 평균 프로파일(재가동일 vs 일반 가동일)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    r = out["by_hour_restart"].fillna(0)
    ax[0].bar(r.index - 0.2, r.get(0, 0), 0.4, label="일반 가동일", color=C["muted"])
    ax[0].bar(r.index + 0.2, r.get(1, 0), 0.4, label="재가동일(주말·휴무 다음날)", color=C["peak"])
    ax[0].set(xlabel="시각", ylabel="180kW 이상 15분 슬롯 비율(%)", title="시각별 피크위험 이벤트 발생률")
    ax[0].legend(frameon=False)
    wd = d[d.full_workday == 1]
    prof = wd.groupby(["restart_day", "slot"])["kw"].mean().unstack(0)
    ax[1].plot(prof.index / 4, prof[0], color=C["muted"], label="일반 가동일")
    ax[1].plot(prof.index / 4, prof[1], color=C["peak"], label="재가동일")
    ax[1].axhline(PEAK_EVENT_KW, ls="--", color="k", lw=0.8)
    ax[1].text(0.3, PEAK_EVENT_KW + 2, "피크위험 기준 180kW", fontsize=8)
    ax[1].set(xlabel="시각", ylabel="평균 15분 최대수요전력(kW)", title="가동일 평균 부하 프로파일")
    ax[1].legend(frameon=False)
    save(fig, S5 / "peak_hour_restart.png")

    # (2) 설명용 분류모델(가동일만) + SHAP
    wd = d[d.full_workday == 1].copy()
    clf = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                             subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1, n_jobs=4)
    clf.fit(wd[PEAK_FEATS], wd["event"], sample_weight=1 / wd["aug_size"])
    expl = shap.TreeExplainer(clf)
    sv = expl.shap_values(wd[PEAK_FEATS])
    sv = sv[1] if isinstance(sv, list) else sv
    imp = pd.Series(np.abs(sv).mean(0), index=PEAK_FEATS).sort_values(ascending=False)
    imp.rename(index=KOR).round(4).to_csv(S5 / "peak_shap_importance.csv", encoding="utf-8-sig")
    out["shap_importance"] = imp
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    top = imp.head(10)[::-1]
    ax.barh([KOR[i] for i in top.index], top.values, color=C["peak"])
    ax.set(xlabel="평균 |SHAP| (log-odds)", title="피크위험 이벤트 주요 영향요인(가동일)")
    save(fig, S5 / "peak_shap_importance.png")

    # 상호작용: 시각 x 재가동일, 시각 x 기온
    inter = expl.shap_interaction_values(wd[PEAK_FEATS].sample(4000, random_state=SEED))
    inter = inter[1] if isinstance(inter, list) else inter
    Mv = np.abs(inter).mean(0).copy()
    np.fill_diagonal(Mv, 0)
    M = pd.DataFrame(Mv, index=PEAK_FEATS, columns=PEAK_FEATS)
    pairs = M.where(np.triu(np.ones(M.shape), 1).astype(bool)).stack().sort_values(ascending=False).head(10)
    pairs.index = [f"{KOR[a]} x {KOR[b]}" for a, b in pairs.index]
    pairs.round(4).to_csv(S5 / "peak_shap_interactions.csv", encoding="utf-8-sig")
    out["shap_interactions"] = pairs

    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    for i, (feat, col) in enumerate([("hour", "restart_day"), ("temp", "hour")]):
        j = PEAK_FEATS.index(feat)
        sc = ax[i].scatter(wd[feat] + (np.random.RandomState(0).uniform(-.3, .3, len(wd)) if feat == "hour" else 0),
                           sv[:, j], c=wd[col], s=3, cmap="coolwarm", alpha=0.5)
        ax[i].set(xlabel=KOR[feat], ylabel=f"SHAP({KOR[feat]})", title=f"{KOR[feat]} 효과 (색: {KOR[col]})")
        plt.colorbar(sc, ax=ax[i])
    save(fig, S5 / "peak_shap_dependence.png")

    # (3) 의사결정나무 규칙(현장 공유용)
    tf = ["hour", "restart_day", "temp", "prod", "hours_from_first_prod", "quarter"]
    rules = fit_rules(wd, wd["event"].values, tf, [KOR[f] for f in tf], w=(1 / wd["aug_size"]).values,
                      depth=3, min_leaf=150)
    rules = rules.rename(columns={"가중평균": "피크위험 이벤트율"})
    rules["피크위험 이벤트율"] = (rules["피크위험 이벤트율"] * 100).round(1)
    rules.to_csv(S5 / "peak_tree_rules.csv", index=False, encoding="utf-8-sig")
    out["tree_rules"] = rules

    # (4) 월별 최대피크 사례
    mp = d.loc[d.groupby("month")["kw"].idxmax(), ["month", "ts", "kw", "dow", "restart_day", "hour", "prod", "temp", "aug_size"]]
    mp.to_csv(S5 / "peak_monthly_max.csv", index=False, encoding="utf-8-sig")
    out["monthly_max"] = mp
    return out
