"""피크 발생 확률 예측(1단계 보강): 15분 슬롯마다 '최대수요전력이 180kW 이상일 확률'을 예측.

- 평가표의 '이상 확률 예측 + F1 비교'에 대응. 피크 슬롯은 전체의 약 5%뿐인 불균형 문제
- 비교 모델: 베이스라인 2종(지난주 같은 시각, 직전 가동일 프로파일), 로지스틱 회귀,
            LightGBM 분류(가중 없음), LightGBM 분류(불균형 가중), 전력량 예측값을 확률 대용으로 쓰는 방식
- 확률보정: 롤링 백테스트의 표본 외 확률에 등위 회귀(isotonic)를 맞춰 '예측 확률 = 실제 발생 비율'이 되게 함
- 판정 기준: 백테스트에서 F1이 최대인 확률 기준을 고르고 시험 구간에 그대로 적용
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import CV_FOLD_STARTS, CV_FOLD_DAYS, PEAK_EVENT_KW, S1, SEED, TEST_START
from .features import feature_list
from .plotting import plt, save, C

CLF_PARAMS = dict(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1, n_jobs=4)
PROB_MODELS = ["로지스틱 회귀(불균형 가중)", "LightGBM 분류", "LightGBM 분류(불균형 가중)"]


def _make(name, pos_ratio):
    if name == "로지스틱 회귀(불균형 가중)":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000))
    if name == "LightGBM 분류":
        return lgb.LGBMClassifier(**CLF_PARAMS)
    return lgb.LGBMClassifier(scale_pos_weight=pos_ratio, **CLF_PARAMS)      # 피크:비피크 비율만큼 피크에 가중


def _fit_predict(name, tr, te, feats):
    y = (tr["kw"] >= PEAK_EVENT_KW).astype(int)
    m = _make(name, (y == 0).sum() / max((y == 1).sum(), 1))
    m.fit(tr[feats], y)
    return m, m.predict_proba(te[feats])[:, 1]


def _scores(y, p, thr):
    hat = (p >= thr).astype(int)
    return {"F1": f1_score(y, hat, zero_division=0), "정밀도": precision_score(y, hat, zero_division=0),
            "재현율": recall_score(y, hat, zero_division=0), "PR-AUC": average_precision_score(y, p),
            "ROC-AUC": roc_auc_score(y, p), "Brier": brier_score_loss(y, np.clip(p, 0, 1))}


def _best_thr(y, p, grid):
    f = [f1_score(y, (p >= t).astype(int), zero_division=0) for t in grid]
    return float(grid[int(np.argmax(f))])


def run(X, oos_reg, Xte_reg):
    """oos_reg: 백테스트의 전력량 예측(LightGBM 회귀), Xte_reg: 시험 구간 전력량 예측 프레임."""
    feats = feature_list("day_ahead", weather=True, lags=False)
    # ---- 백테스트(표본 외) 확률 ----
    parts = []
    for f0 in CV_FOLD_STARTS:
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        tr = X[(X["ts"] < s) & X["kw"].notna()]
        te = X[(X["ts"] >= s) & (X["ts"] < e)].copy()
        for name in PROB_MODELS:
            te[name] = _fit_predict(name, tr, te, feats)[1]
        parts.append(te)
    cv = pd.concat(parts)
    cv["전력량 예측값 기준(회귀)"] = oos_reg["pred"].values
    cv["베이스라인1 지난주 같은 시각"] = cv["lag672"].fillna(cv["lag96"]).values
    b2 = pd.Series(np.where(cv["full_workday"] == 1, cv["last_workday_slot"], cv["lag672"]), index=cv.index)
    cv["베이스라인2 직전 가동일 프로파일"] = b2.fillna(cv["lag672"]).fillna(cv["same_slot_7d_mean"]).values

    # ---- 시험 구간: 9/1 이전 전체로 학습 ----
    tr = X[(X["ts"] < TEST_START) & X["kw"].notna()]
    te = X[X["ts"] >= TEST_START].copy()
    models = {}
    for name in PROB_MODELS:
        models[name], te[name] = _fit_predict(name, tr, te, feats)
    te["전력량 예측값 기준(회귀)"] = Xte_reg["pred"].values
    te["베이스라인1 지난주 같은 시각"] = te["lag672"].fillna(te["lag96"]).values
    b2 = pd.Series(np.where(te["full_workday"] == 1, te["last_workday_slot"], te["lag672"]), index=te.index)
    te["베이스라인2 직전 가동일 프로파일"] = b2.fillna(te["lag672"]).fillna(te["same_slot_7d_mean"]).values

    v, t = cv.dropna(subset=["kw"]), te.dropna(subset=["kw"])
    yv, yt = (v["kw"] >= PEAK_EVENT_KW).astype(int), (t["kw"] >= PEAK_EVENT_KW).astype(int)

    # ---- 확률보정(등위 회귀): 백테스트 표본 외 확률 -> 실제 발생 비율 ----
    iso, rows = {}, []
    for name in PROB_MODELS:
        iso[name] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(v[name], yv)
        for d in (cv, te, v, t):
            d[name + " [보정]"] = iso[name].predict(d[name])
    v, t = cv.dropna(subset=["kw"]), te.dropna(subset=["kw"])

    kw_grid = np.arange(160, 196, 1.0)
    p_grid = np.round(np.arange(0.05, 0.96, 0.01), 2)
    for name in ["베이스라인1 지난주 같은 시각", "베이스라인2 직전 가동일 프로파일", "전력량 예측값 기준(회귀)"]:
        base = name.startswith("베이스라인")
        thr = PEAK_EVENT_KW if base else _best_thr(yv, v[name].fillna(0).values, kw_grid)
        for seg, y, d in (("백테스트(7~8월)", yv, v), ("시험(9/1~14)", yt, t)):
            s = _scores(y, d[name].fillna(0).values, thr)
            s["Brier"] = np.nan                       # kW 값이라 확률 정확도(Brier)는 해당 없음
            rows.append({"모델": name, "구간": seg, "판정 기준": f"{thr:.0f}kW 이상", **s})
    for name in PROB_MODELS:
        for col, tag in ((name, name), (name + " [보정]", name + " + 확률보정")):
            thr = _best_thr(yv, v[col].values, p_grid)
            for seg, y, d in (("백테스트(7~8월)", yv, v), ("시험(9/1~14)", yt, t)):
                rows.append({"모델": tag, "구간": seg, "판정 기준": f"확률 {thr:.2f} 이상", **_scores(y, d[col].values, thr)})
    T = pd.DataFrame(rows)
    T.round(3).to_csv(S1 / "peak_probability_model_comparison.csv", index=False, encoding="utf-8-sig")

    # ---- 최종 확률 모델: 백테스트 PR-AUC가 가장 높은 분류 모델 + 확률보정 ----
    cvT = T[T["구간"] == "백테스트(7~8월)"].set_index("모델")
    best = max(PROB_MODELS, key=lambda n: cvT.loc[n, "PR-AUC"])
    final_col = best + " [보정]"
    thr = _best_thr(yv, v[final_col].values, p_grid)
    te["peak_prob"] = te[final_col]
    cv["peak_prob"] = cv[final_col]
    # 경보 규칙: '보정 확률 >= 기준'과 '전력량 예측값 >= 기준 kW' 중 백테스트 F1이 높은 쪽을 사용(시험 성적은 선택에 쓰지 않음)
    reg = "전력량 예측값 기준(회귀)"
    thr_kw = _best_thr(yv, v[reg].fillna(0).values, kw_grid)
    f1_prob = f1_score(yv, (v[final_col] >= thr).astype(int), zero_division=0)
    f1_reg = f1_score(yv, (v[reg].fillna(0) >= thr_kw).astype(int), zero_division=0)
    use_reg = f1_reg > f1_prob
    for d in (te, cv):
        d["peak_prob_alert"] = ((d[reg].fillna(0) >= thr_kw) if use_reg else (d[final_col] >= thr)).astype(int)
    alert_rule = f"전력량 예측값 {thr_kw:.0f}kW 이상" if use_reg else f"피크 확률 {thr:.2f} 이상"
    alert_test_f1 = float(f1_score(yt, te.loc[t.index, "peak_prob_alert"], zero_division=0))

    # 보정 전후 신뢰도표(시험)
    cal = []
    bins = [0, .05, .15, .3, .5, .7, 1.0001]
    for col, tag in ((best, "보정 전"), (final_col, "보정 후")):
        g = t.assign(b=pd.cut(t[col], bins, right=False), y=yt.values).groupby("b", observed=True)
        for b, x in g:
            cal.append({"구분": tag, "예측 확률 구간": f"{b.left:.2f}~{min(b.right, 1):.2f}", "슬롯 수": len(x),
                        "평균 예측 확률": x[col].mean(), "실제 피크 비율": x["y"].mean()})
    CAL = pd.DataFrame(cal)
    CAL.round(3).to_csv(S1 / "peak_probability_calibration.csv", index=False, encoding="utf-8-sig")

    # 그림: 모델별 F1(시험) / 신뢰도 곡선 / 시험 구간 확률과 실제 피크
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.3), gridspec_kw={"width_ratios": [1.1, .8, 1.5]})
    tt = T[T["구간"] == "시험(9/1~14)"].set_index("모델")["F1"].sort_values()
    ax[0].barh(tt.index, tt.values, color=[C["peak"] if i == best + " + 확률보정" else C["muted"] for i in tt.index])
    for i, val in enumerate(tt.values):
        ax[0].text(val + .01, i, f"{val:.2f}", va="center", fontsize=8)
    ax[0].set(xlabel="F1(시험 구간)", title="피크 판정 F1 비교", xlim=(0, max(tt.values) + .12))
    ax[0].tick_params(axis="y", labelsize=8)
    for tag, colr in (("보정 전", C["muted"]), ("보정 후", C["peak"])):
        q = CAL[CAL["구분"] == tag]
        ax[1].plot(q["평균 예측 확률"], q["실제 피크 비율"], "o-", color=colr, label=tag)
    ax[1].plot([0, 1], [0, 1], ls=":", color="k", lw=.7)
    ax[1].set(xlabel="예측 확률", ylabel="실제 피크 비율", title="확률보정 전후(시험 구간)")
    ax[1].legend(frameon=False)
    ax[2].fill_between(te["ts"], 0, te["peak_prob"], color=C["peak"], alpha=.45, label="피크 발생 확률(보정)")
    ax[2].axhline(thr, ls="--", color=C["peak"], lw=.7)
    ax2 = ax[2].twinx()
    ax2.plot(te["ts"], te["kw"], color=C["actual"], lw=.6)
    ax2.axhline(PEAK_EVENT_KW, ls=":", color="k", lw=.6)
    ax2.set_ylabel("실측 kW")
    ax[2].set(ylabel="확률", ylim=(0, 1.05), title="시험 구간 피크 발생 확률과 실측 전력")
    ax[2].tick_params(axis="x", labelrotation=30, labelsize=8)
    ax[2].legend(frameon=False, loc="upper left", fontsize=8)
    save(fig, S1 / "peak_probability.png")

    # 점검 우선순위: 시험 구간 날짜별 '피크 확률이 높은 시간대' 상위
    pr = te.groupby(["date", "hour"])["peak_prob"].max().reset_index()
    top = pr.sort_values(["date", "peak_prob"], ascending=[True, False]).groupby("date").head(3)
    top = top[top["peak_prob"] >= 0.2].rename(columns={"date": "날짜", "hour": "시각", "peak_prob": "피크 확률(시간 내 최대)"})
    top.round(3).to_csv(S1 / "peak_probability_priority_hours_test.csv", index=False, encoding="utf-8-sig")

    info = {"alert_rule": alert_rule, "alert_rule_cv_F1": float(max(f1_reg, f1_prob)), "alert_rule_test_F1": alert_test_f1,
            "cv_F1_regression_threshold": float(f1_reg), "cv_F1_probability": float(f1_prob),
            "final_prob_model": best + " + 확률보정", "prob_threshold": thr,
            "cv_F1": float(T[(T["모델"] == best + " + 확률보정") & (T["구간"] == "백테스트(7~8월)")]["F1"].iloc[0]),
            "test_F1": float(T[(T["모델"] == best + " + 확률보정") & (T["구간"] == "시험(9/1~14)")]["F1"].iloc[0]),
            "test_Brier_raw": float(brier_score_loss(yt, t[best])), "test_Brier_calibrated": float(brier_score_loss(yt, t[final_col]))}
    return cv, te, T, CAL, top, info
