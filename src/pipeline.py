"""전 과정 실행: 진단 -> 피처 -> 모델 비교(롤링 백테스트) -> 최종 학습·시험 예측 -> 오차/피크 분석 -> 저감 시뮬레이션."""
import json
import time
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

from .config import (TEST_START, CV_FOLD_STARTS, CV_FOLD_DAYS, PEAK_EVENT_KW, S0, S1, S2, S3, S4, S5, S6, PRED, OUT, SEED,
                     BASIC_CHARGE_KRW_PER_KW, TARIFF_NAME)
from .data import load_clean
from .features import build_features, feature_list
from .models import make_model, LGB_PARAMS
from .experiment import sample_weight
from .metrics import all_metrics, point_metrics
from .peak_forecast import DailyPeakModel, day_frame
from . import eda, error_analysis, peak_analysis, peak_shaving, peak_types, peak_prob, tuning
from .plotting import plt, save, C

LOG = []

FEAT_KOR = {
    "hour": "시각", "quarter": "15분 구간", "slot": "하루 내 슬롯", "slot_sin": "슬롯(sin)", "slot_cos": "슬롯(cos)",
    "dow": "요일", "weekend": "주말", "holiday": "공휴일", "month": "월", "doy": "연중 일차",
    "prod": "생산계획량(당시간)", "staff": "공장인원(환산)", "prod_lag1h": "직전1h 생산계획", "prod_lag2h": "직전2h 생산계획",
    "prod_lead1h": "다음1h 생산계획", "prod_lead2h": "다음2h 생산계획", "staff_lead1h": "다음1h 공장인원",
    "is_prod_hour": "생산 시간 여부", "hours_from_first_prod": "첫 생산 후 경과h", "hours_to_last_prod": "마지막 생산까지 남은h",
    "prod_start_hour": "생산 시작 시간", "prod_share_day": "일 생산 중 비중", "lunch": "점심시간",
    "day_prod": "일 생산계획량", "day_prod_hours": "일 생산시간 수", "day_staff": "일 공장인원 합", "first_prod_hour": "첫 생산 시각",
    "last_prod_hour": "마지막 생산 시각", "workday": "생산일", "full_workday": "정상 가동일", "prev_day_prod": "전일 생산계획",
    "next_day_prod": "익일 생산계획", "days_since_workday": "직전 가동일 경과일", "restart_day": "재가동일",
    "temp": "기온", "humid": "습도", "wind": "풍속", "rain": "시간 강수량", "cdd": "냉방도(기온-24)", "hdd": "난방도(18-기온)",
    "temp_max": "일 최고기온", "temp_mean": "일 평균기온",
}


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


# --------------------------------------------------------------------------------------------
# 모델 비교 구성: (표시명, 모델키, 예측시점, 피처셋, 가중치)
#   피처셋 plan = 생산계획+달력+기상(전력 지연값 없음) / full = plan + 전력 지연값
# --------------------------------------------------------------------------------------------
COMPARE = [
    ("B1 Naive(지난주 동시각)", "naive", "day_ahead", "full", "none"),
    ("B2 규칙(직전 가동일 프로파일)", "rule", "day_ahead", "full", "none"),
    ("Ridge 회귀", "ridge", "day_ahead", "plan", "none"),
    ("RandomForest(가이드북 모델)", "rf", "day_ahead", "plan", "none"),
    ("MLP(심층신경망)", "mlp", "day_ahead", "plan", "none"),
    ("XGBoost", "xgb", "day_ahead", "plan", "none"),
    ("CatBoost", "cat", "day_ahead", "plan", "none"),
    ("LightGBM", "lgbm", "day_ahead", "plan", "none"),
    # 설계 검증(ablation)
    ("LightGBM + 전력지연값", "lgbm", "day_ahead", "full", "none"),
    ("LightGBM + 전력지연값 + 증강가중", "lgbm", "day_ahead", "full", "aug_inv"),
    ("LightGBM 1시간전(지연값 포함)", "lgbm", "hour_ahead", "full", "none"),
    ("LightGBM - 기상 제외", "lgbm", "day_ahead", "plan_noW", "none"),
    ("LightGBM + 증강가중", "lgbm", "day_ahead", "plan", "aug_inv"),
]


def feats_for(horizon, fs):
    if fs == "plan":
        return feature_list(horizon, weather=True, lags=False)
    if fs == "plan_noW":
        return feature_list(horizon, weather=False, lags=False)
    return feature_list(horizon, weather=True, lags=True)


def fit_pred(model_key, Xtr, Xte, feats, weight):
    tr = Xtr[Xtr["kw"].notna()]
    m = make_model(model_key)
    m.fit(tr[feats], tr["kw"].values, sample_weight(tr, weight))
    return m, np.clip(m.predict(Xte[feats]), 0, None)


def folds(X):
    for f0 in CV_FOLD_STARTS:
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        yield f0, X["ts"] < s, (X["ts"] >= s) & (X["ts"] < e)


def step_compare(XD, XH):
    rows, oos = [], {}
    for name, key, hz, fs, w in COMPARE:
        t = time.time()
        X = XD if hz == "day_ahead" else XH
        feats = feats_for(hz, fs)
        parts = []
        for f0, trm, pm in folds(X):
            _, p = fit_pred(key, X[trm], X[pm], feats, w)
            parts.append(X.loc[pm].assign(pred=p, fold=f0))
        o = pd.concat(parts)
        oos[name] = o
        r = all_metrics(o)
        r.update({"모델": name, "예측시점": "하루 전" if hz == "day_ahead" else "1시간 전", "피처": fs, "가중치": w,
                  "학습·예측 시간(s)": round(time.time() - t, 1)})
        rows.append(r)
        log(f"  CV {name}: MAE={r['MAE']:.2f} RMSE={r['RMSE']:.2f} ({time.time() - t:.0f}s)")
    # 앙상블: LightGBM + CatBoost 평균
    ens = oos["LightGBM"].copy()
    ens["pred"] = 0.5 * oos["LightGBM"]["pred"].values + 0.5 * oos["CatBoost"]["pred"].values
    oos["앙상블(LightGBM+CatBoost)"] = ens
    r = all_metrics(ens)
    r.update({"모델": "앙상블(LightGBM+CatBoost)", "예측시점": "하루 전", "피처": "plan", "가중치": "none"})
    rows.append(r)
    R = pd.DataFrame(rows).set_index("모델")
    R.round(3).to_csv(S1 / "model_comparison_cv.csv", encoding="utf-8-sig")
    return R, oos


def step_guidebook_replication(XD):
    """가이드북 방식(무작위 70:30 분할, 15분 전 값 입력) vs 시간 순 분할 비교 -> 누수 정량화."""
    X = XD.copy()
    X["prev_q"] = X["kw"].shift(1)
    feats = ["hour", "prod", "temp", "wind", "humid", "rain", "dow", "dom", "month", "prev_q"]
    d = X.dropna(subset=["kw", "prev_q"])
    from sklearn.ensemble import RandomForestRegressor
    rf = lambda: RandomForestRegressor(n_estimators=200, max_depth=20, random_state=42, n_jobs=4)
    tr, te = train_test_split(d, test_size=0.3, random_state=42)
    m = rf().fit(tr[feats], tr["kw"])
    mse_rand = np.mean((m.predict(te[feats]) - te["kw"]) ** 2)
    # 무작위 분할 시험셋 중, 같은 패턴의 복사본이 학습셋에 있는 표본 비율
    tr_keys = set(zip(tr["aug_group"], tr["slot"]))
    leak_share = np.mean([(g >= 0) and ((g, s) in tr_keys) for g, s in zip(te["aug_group"], te["slot"])])
    trt, tet = d[d.ts < TEST_START], d[d.ts >= TEST_START]
    m2 = rf().fit(trt[feats], trt["kw"])
    mse_time = np.mean((m2.predict(tet[feats]) - tet["kw"]) ** 2)
    res = pd.DataFrame({"검증 방식": ["가이드북: 무작위 70:30 분할", "시간 순 분할(9/1~9/14 시험)"],
                        "MSE": [mse_rand, mse_time], "RMSE": [np.sqrt(mse_rand), np.sqrt(mse_time)],
                        "시험표본 중 학습셋에 동일패턴 복사본 존재 비율%": [100 * leak_share, 0.0]})
    res.round(3).to_csv(S0 / "split_leakage_check.csv", index=False, encoding="utf-8-sig")
    return res


def step_final(XD, oos_cv, final=None):
    """최종 모델 학습(9/1 이전 전체) -> 시험 구간 예측. 예측구간은 CV 표본외 잔차로 컨포멀 보정."""
    feats = feats_for("day_ahead", "plan")
    trm, tem = XD["ts"] < TEST_START, XD["ts"] >= TEST_START
    Xtr, Xte = XD[trm & XD["kw"].notna()], XD[tem].copy()
    m_lgb = lgb.LGBMRegressor(**LGB_PARAMS).fit(Xtr[feats], Xtr["kw"])
    m_cat = make_model("cat").fit(Xtr[feats], Xtr["kw"].values)
    Xte["pred_lgb"] = np.clip(m_lgb.predict(Xte[feats]), 0, None)
    Xte["pred_cat"] = np.clip(m_cat.predict(Xte[feats]), 0, None)
    # 최종 점예측: 탐색·앙상블 비교(tuning.run)에서 선정된 앙상블. final이 없으면 LightGBM 단독
    Xte["pred"] = final["test_pred"].reindex(Xte.index).values if final is not None else Xte["pred_lgb"]
    qs = {}
    for q in (0.1, 0.5, 0.85, 0.9):
        qs[q] = lgb.LGBMRegressor(objective="quantile", alpha=q, **LGB_PARAMS).fit(Xtr[feats], Xtr["kw"])
        Xte[f"q{int(q * 100)}"] = qs[q].predict(Xte[feats])

    # --- CV에서 분위수 표본외 예측(컨포멀 보정·경보 임계값 선택용) ---
    parts = []
    for f0, trm_, pm_ in folds(XD):
        tr_ = XD[trm_ & XD["kw"].notna()]
        o = XD.loc[pm_].copy()
        for q in (0.1, 0.85, 0.9):
            o[f"q{int(q * 100)}"] = lgb.LGBMRegressor(objective="quantile", alpha=q, **LGB_PARAMS).fit(
                tr_[feats], tr_["kw"]).predict(o[feats])
        parts.append(o)
    cvq = pd.concat(parts)
    cvq["pred"] = final["cv_pred"].reindex(cvq.index).values if final is not None else oos_cv["LightGBM"]["pred"].values
    v = cvq.dropna(subset=["kw"])
    # CQR(Conformalized Quantile Regression): 80% 구간 [q10, q90]의 표본외 부적합 점수 분위수만큼 확장
    score = np.maximum(v["q10"] - v["kw"], v["kw"] - v["q90"])
    margin = float(np.quantile(score, 0.8))
    cov_raw = float(np.mean((v["kw"] >= v["q10"]) & (v["kw"] <= v["q90"])))
    Xte["lo80"] = np.clip(Xte["q10"] - margin, 0, None)
    Xte["hi80"] = Xte["q90"] + margin
    tv = Xte.dropna(subset=["kw"])
    cov_test_raw = float(np.mean((tv["kw"] >= tv["q10"]) & (tv["kw"] <= tv["q90"])))
    cov_test_cal = float(np.mean((tv["kw"] >= tv["lo80"]) & (tv["kw"] <= tv["hi80"])))

    # --- 피크위험 경보 임계값: CV에서 F1 최대가 되는 (분위수, 임계 kW) 선택 ---
    best = (None, None, -1)
    yt = (v["kw"] >= PEAK_EVENT_KW).astype(int)
    grid = []
    for qc in ("pred", "q85", "q90"):
        for thr in range(165, 196, 5):
            f1 = f1_score(yt, (v[qc] >= thr).astype(int))
            grid.append({"신호": qc, "임계kW": thr, "F1": f1})
            if f1 > best[2]:
                best = (qc, thr, f1)
    pd.DataFrame(grid).round(3).to_csv(S1 / "alert_threshold_grid_cv.csv", index=False, encoding="utf-8-sig")
    Xte["alert_signal"] = Xte[best[0]]
    Xte["pred_alert"] = np.where(Xte[best[0]] >= best[1], PEAK_EVENT_KW, 0)   # error_analysis에서 ev_pred 판단용
    Xte["peak_alert"] = (Xte[best[0]] >= best[1]).astype(int)
    v_alert = (v[best[0]] >= best[1]).astype(int)

    # --- 일 최대수요전력 예측 ---
    D = day_frame(XD)
    Dtr, Dte = D[D.index < TEST_START], D[D.index >= TEST_START]
    dpm = DailyPeakModel().fit(Dtr)
    dp = dpm.predict(Dte).join(Dte[["ymax", "full_workday"]])
    dp["slot_model_max"] = Xte.groupby("date")["pred"].max()
    dp["q90_max"] = Xte.groupby("date")["q90"].max()
    # CV 일피크 성능
    dparts = []
    for f0 in CV_FOLD_STARTS:
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        mdl = DailyPeakModel().fit(D[D.index < s])
        dparts.append(mdl.predict(D[(D.index >= s) & (D.index < e)]).join(D[["ymax", "full_workday"]]))
    dcv = pd.concat(dparts)
    dcv["slot_model_max"] = cvq.groupby("date")["pred"].max()
    dcv["q90_max"] = cvq.groupby("date")["q90"].max()

    def dscore(df, col):
        t = df.dropna(subset=["ymax"])
        w = t["full_workday"] == 1
        e = t[col] - t["ymax"]
        return {"MAE(전체일)": e.abs().mean(), "MAE(가동일)": e[w].abs().mean(), "Bias(가동일)": e[w].mean(),
                "MAPE%(가동일)": 100 * (e[w].abs() / t.loc[w, "ymax"]).mean()}

    names = {"slot_model_max": "15분 예측의 일 최대값(최종 모델)", "q90_max": "P90 분위수의 일 최대값",
             "dmax_rule": "규칙(직전 가동일 최대값)", "dmax_model": "일 단위 LightGBM", "dmax_pred": "피크 앙상블(제안)"}
    drows = []
    for col, nm in names.items():
        drows.append({"방법": nm, "구간": "CV(7~8월)", **dscore(dcv, col)})
        drows.append({"방법": nm, "구간": "시험(9/1~14)", **dscore(dp, col)})
    DP = pd.DataFrame(drows)
    DP.round(2).to_csv(S1 / "daily_peak_comparison.csv", index=False, encoding="utf-8-sig")

    # --- 시험 지표 ---
    test_rows = {}
    fname = "최종: " + final["name"] if final is not None else "LightGBM"
    if final is not None:
        test_rows[fname] = all_metrics(Xte)
    for col, nm in [("pred_lgb", "LightGBM(기본값)"), ("pred_cat", "CatBoost(기본값)")]:
        test_rows[nm] = all_metrics(Xte.assign(pred=Xte[col]))
    ens = Xte.assign(pred=0.5 * Xte["pred_lgb"] + 0.5 * Xte["pred_cat"])
    test_rows["앙상블(LightGBM+CatBoost, 기본값)"] = all_metrics(ens)
    test_rows["B1 Naive(지난주 동시각)"] = all_metrics(Xte.assign(pred=Xte["lag672"].fillna(Xte["lag96"])))
    rule = make_model("rule").predict(Xte)
    test_rows["B2 규칙(직전 가동일 프로파일)"] = all_metrics(Xte.assign(pred=rule))
    _, prf = fit_pred("rf", XD[trm], XD[tem], feats, "none")
    test_rows["RandomForest(가이드북 모델)"] = all_metrics(Xte.assign(pred=prf))
    T = pd.DataFrame(test_rows).T
    tv = Xte.dropna(subset=["kw"])
    ev = (tv["kw"] >= PEAK_EVENT_KW).astype(int)
    T["피크 판정 F1(전력량 예측값 기준선)"] = np.nan
    T.loc[T.index[0], "피크 판정 F1(전력량 예측값 기준선)"] = f1_score(ev, tv["peak_alert"])
    T.round(3).to_csv(S1 / "test_metrics.csv", encoding="utf-8-sig")

    # 특성 중요도(SHAP)
    import shap
    ex = shap.TreeExplainer(m_lgb)
    samp = Xtr[feats].sample(5000, random_state=SEED)
    sv = ex.shap_values(samp)
    imp = pd.Series(np.abs(sv).mean(0), index=feats).sort_values(ascending=False)
    imp.rename(index=FEAT_KOR).round(3).to_csv(S1 / "forecast_shap_importance.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7, 5))
    top = imp.head(15)[::-1]
    ax.barh([FEAT_KOR.get(i, i) for i in top.index], top.values, color=C["pred"])
    ax.set(xlabel="평균 |SHAP| (kW)", title="15분 전력 예측 주요 영향변수(LightGBM, 상위 15)")
    save(fig, S1 / "forecast_shap_importance.png")
    inter = ex.shap_interaction_values(samp.sample(1500, random_state=SEED))
    Mv = np.abs(inter).mean(0).copy()
    np.fill_diagonal(Mv, 0)
    M = pd.DataFrame(Mv, index=feats, columns=feats)
    pairs = M.where(np.triu(np.ones(M.shape), 1).astype(bool)).stack().sort_values(ascending=False).head(10)
    pairs.index = [f"{FEAT_KOR.get(a, a)} x {FEAT_KOR.get(b, b)}" for a, b in pairs.index]
    pairs.round(3).to_csv(S1 / "forecast_shap_interactions.csv", encoding="utf-8-sig")

    info = {"conformal_margin_kW": margin, "cv_coverage_raw_q10_q90": cov_raw,
            "test_coverage_raw": cov_test_raw, "test_coverage_conformal": cov_test_cal,
            "alert_signal": best[0], "alert_threshold_kW": best[1], "alert_cv_F1": best[2],
            "alert_test_F1": float(f1_score(ev, tv["peak_alert"]))}
    return Xte, cvq, dp, dcv, T, DP, imp, pairs, info, m_lgb


def step_probability(XD, oos, Xte, cvq):
    """피크 발생 확률 모델(peak_prob.run)을 돌리고, 최종 확률·경보를 시험/백테스트 프레임에 붙인다.
    이후 경보·놓친 피크·헛경보 분석은 모두 이 확률 경보 기준."""
    cvp, tep, PT, CAL, top, pinfo = peak_prob.run(XD, cvq, Xte)
    for d, src in ((Xte, tep), (cvq, cvp)):
        d["peak_prob"] = src["peak_prob"].values
        d["peak_alert"] = src["peak_prob_alert"].values
        d["pred_alert"] = np.where(d["peak_alert"] == 1, PEAK_EVENT_KW, 0)     # error_analysis의 경보 판정용
    return Xte, cvq, PT, CAL, top, pinfo


def step_save_predictions(Xte, dp):
    cols = {"ts": "일시(15분 시작)", "date": "날짜", "hour": "시간", "quarter": "15분구간(0~3)", "kw": "실측(kW)",
            "pred": "예측(kW)", "q10": "P10", "q90": "P90", "lo80": "80%구간 하한(보정)", "hi80": "80%구간 상한(보정)",
            "peak_prob": "피크 발생 확률(보정)", "peak_alert": "피크위험 경보(1=경보)"}
    out = Xte[list(cols)].rename(columns=cols).round(2)
    out.to_csv(PRED / "test_predictions_15min.csv", index=False, encoding="utf-8-sig")
    # 원본 포맷(1행=1시간, 15분/30분/45분/60분 + 평균)
    wide = Xte.pivot_table(index=["date", "hour"], columns="quarter", values="pred").round(2)
    wide.columns = ["15분", "30분", "45분", "60분"]
    wide["평균"] = wide.mean(axis=1).round(2)
    wide = wide.reset_index()
    wide.insert(0, "날짜", wide.pop("date").dt.strftime("%Y%m%d"))
    wide = wide.rename(columns={"hour": "시간"})
    wide.to_csv(PRED / "test_predictions_original_format.csv", index=False, encoding="utf-8-sig")
    d = dp.rename(columns={"ymax": "실측 일최대(kW)", "dmax_pred": "예측 일최대(kW, 피크앙상블)",
                           "dmax_model": "일단위모델", "dmax_rule": "규칙", "slot_model_max": "15분예측 최대",
                           "q90_max": "P90 최대"})
    d.round(2).to_csv(PRED / "test_daily_peak_predictions.csv", encoding="utf-8-sig")


def step_plots(Xte, R, dp):
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    ax[0].fill_between(Xte["ts"], Xte["lo80"], Xte["hi80"], color=C["band"], alpha=.5, label="80% 예측구간(컨포멀 보정)")
    ax[0].plot(Xte["ts"], Xte["kw"], color=C["actual"], lw=.8, label="실측")
    ax[0].plot(Xte["ts"], Xte["pred"], color=C["pred"], lw=.9, label="예측(하루 전, 최종 모델)")
    al = Xte[Xte["peak_alert"] == 1]
    ax[0].scatter(al["ts"], np.full(len(al), 228), marker="|", color=C["peak"], s=30, label="피크위험 경보")
    ax[0].axhline(PEAK_EVENT_KW, ls="--", color=C["peak"], lw=.7)
    ax[0].set(ylabel="kW", title="시험 구간(2021-09-01 ~ 09-14) 15분 최대수요전력: 실측 vs 하루 전 예측")
    ax[0].legend(frameon=False, ncol=4, fontsize=8, loc="lower left")
    ax[1].plot(Xte["ts"], Xte["pred"] - Xte["kw"], color=C["muted"], lw=.7)
    ax[1].axhline(0, color="k", lw=.5)
    ax[1].set(ylabel="오차(예측-실측, kW)")
    save(fig, S1 / "test_forecast.png")

    # 하루 확대
    day = Xte[Xte["date"] == "2021-09-06"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.fill_between(day["slot"] / 4, day["lo80"], day["hi80"], color=C["band"], alpha=.5, label="80% 구간")
    ax.plot(day["slot"] / 4, day["kw"], color=C["actual"], marker=".", ms=3, lw=1, label="실측")
    ax.plot(day["slot"] / 4, day["pred"], color=C["pred"], lw=1.2, label="예측")
    ax.axhline(PEAK_EVENT_KW, ls="--", color=C["peak"], lw=.7)
    ax.set(xlabel="시각", ylabel="kW", title="2021-09-06(월, 재가동일) 하루 전 예측 상세")
    ax.legend(frameon=False)
    save(fig, S1 / "test_forecast_day.png")

    # 모델 비교 막대
    main = R.loc[[n for n, *_ in COMPARE[:8]] + ["앙상블(LightGBM+CatBoost)"]].sort_values("MAE")
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    col = [C["pred"] if "LightGBM" == i else C["muted"] for i in main.index]
    ax[0].barh(main.index[::-1], main["MAE"][::-1], color=col[::-1])
    ax[0].set(xlabel="MAE(kW)", title="롤링 백테스트(7~8월 8주) MAE")
    ax[1].barh(main.index[::-1], main["DailyPeak_MAE(가동일)"][::-1], color=col[::-1])
    ax[1].set(xlabel="가동일 일피크 MAE(kW)", title="일 최대수요전력 오차")
    save(fig, S1 / "model_comparison.png")

    # 일 피크 예측
    t = dp.dropna(subset=["ymax"])
    fig, ax = plt.subplots(figsize=(10, 3.6))
    x = np.arange(len(t))
    ax.bar(x - 0.2, t["ymax"], 0.4, color=C["actual"], label="실측 일최대")
    ax.bar(x + 0.2, t["dmax_pred"], 0.4, color=C["peak"], label="피크 앙상블 예측")
    ax.plot(x, t["slot_model_max"], "o--", color=C["pred"], ms=3, lw=.8, label="15분 예측의 최대값")
    ax.set_xticks(x, [d.strftime("%m-%d") for d in t.index], rotation=45)
    ax.set(ylabel="kW", title="시험 구간 일 최대수요전력 예측", ylim=(0, 240))
    ax.legend(frameon=False, ncol=3, fontsize=8)
    save(fig, S1 / "test_daily_peak.png")


def step_mitigation(XD, Xte, dp, E):
    """6단계: 유형별 저감방안 시뮬레이션(7~9월 원본 구간) + 예측 연동 운영 규칙 검증(시험 구간)."""
    R, EP, prof = peak_shaving.simulate(XD, E)
    S = peak_shaving.summarize(R, EP)
    S.round(1).to_csv(S6 / "mitigation_by_type_summary.csv", index=False, encoding="utf-8-sig")
    R.round(2).to_csv(S6 / "mitigation_daily.csv", index=False, encoding="utf-8-sig")
    EP.round(2).to_csv(S6 / "mitigation_by_episode.csv", index=False, encoding="utf-8-sig")

    # 재가동일·고온일·일반 가동일별 효과(피크 발생일)
    R2 = R[(R.has_type1 + R.has_type2) > 0].copy()
    R2["day_type"] = np.select([R2.restart_day == 1, R2.temp_max >= 27], ["재가동일", "고온일(최고 27도 이상)"], "그 외 가동일")
    bytype = R2.assign(red=R2.orig_peak - R2.new_peak).groupby(["measure", "alpha", "day_type"])["red"].mean().unstack().round(2)
    bytype.to_csv(S6 / "mitigation_by_daytype.csv", encoding="utf-8-sig")

    # 예측 연동 운영(시험 구간): 피크 앙상블의 '내일 일최대 예측' >= 경보 기준인 날에만
    # 하루 전 계획 규칙(주간 delta kW 블록을 저녁 여유 슬롯으로 재배치, peak_shaving.planned_block_shift)을 세우고
    # 그 계획을 실측 부하에 적용했을 때의 결과를 평가 -> 실측을 미리 알 필요가 없는 현실적 평가
    pol_rows, day_rows = [], []
    test_days = [d for d in dp.index if not np.isnan(dp.loc[d, "ymax"])]
    act_by_day = {d: XD[XD.date == d].sort_values("slot")["kw"].interpolate(limit_direction="both").values
                  for d in test_days}
    fc_by_day = {d: Xte[Xte.date == d].sort_values("slot")["pred"].values for d in test_days}
    for delta in (10, 15, 20):
        for thr in (None, 195, 190, 185, 180):
            new_max, n_act, ecost = [], 0, 0.0
            for d in test_days:
                P = act_by_day[d]
                act = thr is not None and dp.loc[d, "dmax_pred"] >= thr
                Q = peak_shaving.planned_block_shift(P, fc_by_day[d], delta, dp.loc[d, "dmax_pred"]) if act else P
                n_act += int(act)
                new_max.append(np.nanmax(Q))
                m = pd.Timestamp(d).month
                ecost += peak_shaving.energy_cost(Q, m, range(96)) - peak_shaving.energy_cost(P, m, range(96))
                if thr == 185 and delta == 15:
                    day_rows.append({"date": d, "예측 일최대": dp.loc[d, "dmax_pred"], "실측 일최대": dp.loc[d, "ymax"],
                                     "경보(조치)": int(act), "조치 후 일최대": np.nanmax(Q)})
            pol_rows.append({"이전 블록 delta(kW)": delta, "경보 기준(kW)": "조치 없음" if thr is None else thr,
                             "조치일 수": n_act, "시험기간 최대수요전력(kW)": max(new_max),
                             "가동일 일최대 평균(kW)": np.mean([m for m in new_max if m > 120]),
                             "전력량요금 변화(원/2주)": ecost})
    P = pd.DataFrame(pol_rows)
    base_max = max(np.nanmax(v) for v in act_by_day.values())
    P["최대수요전력 감소(kW)"] = base_max - P["시험기간 최대수요전력(kW)"]
    P["연간 기본요금 절감(원, 요금적용전력 반영 가정)"] = P["최대수요전력 감소(kW)"] * BASIC_CHARGE_KRW_PER_KW * 12
    P.round(1).to_csv(S6 / "forecast_driven_policy_test.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(day_rows).round(1).to_csv(S6 / "forecast_driven_policy_days.csv", index=False, encoding="utf-8-sig")

    # 그림1: 두 유형이 모두 있는 대표일의 조치 전후
    both = R[(R.measure == "AB") & (R.alpha == 0.2) & (R.has_type1 == 1) & (R.has_type2 == 1)]
    d0 = both.assign(red=both.orig_peak - both.new_peak).sort_values("red").iloc[-1]["date"]
    g = XD[XD.date == d0].sort_values("slot")
    fig, ax = plt.subplots(1, 2, figsize=(14, 4), gridspec_kw={"width_ratios": [1.5, 1]})
    for _, e in E[E.date == d0].iterrows():
        ax[0].axvspan(e["start_slot"] / 4, (e["end_slot"] + 1) / 4, color=peak_types.TYPE_COLOR[int(e["유형"])], alpha=.12)
    ax[0].plot(g["slot"] / 4, prof[(d0, "A", 0.2)] * 0 + pd.Series(g["kw"].values).interpolate().values, color=C["actual"], lw=1.4, label="실측")
    for ms, colr in [("A", C["accent"]), ("B", C["good"]), ("AB", C["peak"])]:
        ax[0].plot(g["slot"] / 4, prof[(d0, ms, 0.2)], lw=1, color=colr, label=peak_shaving.MEASURES[ms])
    ax[0].set(xlabel="시각", ylabel="kW", xlim=(5, 24),
              title=f"유형별 조치 전후({pd.Timestamp(d0):%m-%d}, α=20%, 붉은 띠=유형1 / 파란 띠=유형2)")
    ax[0].legend(frameon=False, fontsize=7.5, loc="lower center")
    for ms, colr in [("A", C["accent"]), ("B", C["good"]), ("AB", C["peak"]), ("UB", C["muted"])]:
        q = S[S.measure == ms]
        ax[1].plot(q["alpha"] * 100, q["피크 발생일 일최대 평균 감소(kW)"], "o-", color=colr, label=peak_shaving.MEASURES[ms])
    ax[1].set(xlabel="가동 시점을 바꿀 수 있는 부하 비중 α(%)", ylabel="피크 발생일 일최대 평균 감소(kW)", title="조치별 효과(7~9월)")
    ax[1].legend(frameon=False, fontsize=7.5)
    save(fig, S6 / "mitigation_by_type.png")
    return S, bytype, P


def step_error(oos_all, E):
    """2단계: 표본 외 예측(백테스트 8주 + 시험 2주)의 조건별 오차. 피크 구간 유형을 슬롯에 붙여 '피크 시간 MAE'를 함께 계산."""
    o = oos_all.copy()
    o["peak_type"] = 0
    for _, e in E.iterrows():
        m = (o["date"] == e["date"]) & (o["slot"] >= e["start_slot"]) & (o["slot"] <= e["end_slot"])
        o.loc[m, "peak_type"] = int(e["유형"])
    return error_analysis.run(o, "oos")


def run_all(reuse_cv=False, tune=False):
    t0 = time.time()
    raw, hourly, L = load_clean()
    log("[0] 데이터 전처리 및 분할")
    rep, actions = eda.run(raw, hourly, L)
    XD = build_features(L, "day_ahead")
    XH = build_features(L, "hour_ahead")
    eda.split_table(XD)
    G = step_guidebook_replication(XD)
    log("[1] 전력 예측: 모델 비교(롤링 원점 백테스트 8주) -> 최종 학습 -> 시험 예측")
    cache = OUT / "cache_cv.pkl"
    if reuse_cv and cache.exists():
        R, oos = pd.read_pickle(cache)
        R.round(3).to_csv(S1 / "model_comparison_cv.csv", encoding="utf-8-sig")
        log("  (캐시된 백테스트 결과 사용)")
    else:
        R, oos = step_compare(XD, XH)
        pd.to_pickle((R, oos), cache)
    log("[1] 전력 예측: 탐색된 설정의 7종 모델과 앙상블 5종 비교 -> 최종 모델 선정")
    tcache = OUT / "cache_tuning.pkl"
    if tune:
        best = tuning.search(XD, log=log)
        TRES, TR, BP, W, final = tuning.run(XD, best, log=log)
        pd.to_pickle((TRES, final), tcache)
    elif reuse_cv and tcache.exists():
        TRES, final = pd.read_pickle(tcache)
        TRES.round(3).to_csv(S1 / "tuning_and_ensemble_comparison.csv", index=False, encoding="utf-8-sig")
        log("  (캐시된 앙상블 결과 사용)")
    else:
        TRES, TR, BP, W, final = tuning.run(XD, log=log)
        pd.to_pickle((TRES, final), tcache)
    Xte, cvq, dp, dcv, T, DP, imp, pairs, info, model = step_final(XD, oos, final)
    Xte, cvq, PT, CAL, top, pinfo = step_probability(XD, oos, Xte, cvq)
    info.update(pinfo)
    step_save_predictions(Xte, dp)
    step_plots(Xte, R, dp)
    log("[3] 실제 피크 구간 추출")
    E, thr_tab, ext_summ = peak_types.step3_extract(XD)
    log("[4] 피크 두 유형 구분")
    E, sil, type_prof = peak_types.step4_types(E, XD)
    log("[2] 예측오차 분석(표본 외: 백테스트 8주 + 시험 2주, 피크 유형 포함)")
    oos_all = pd.concat([cvq, Xte])
    _, et = step_error(oos_all, E)
    log("[5] 유형별 발생조건(+ 슬롯 단위 피크 조건 보조 분석)")
    cond = peak_types.step5_conditions(E, XD)
    pk = peak_analysis.run(XD)
    log("[6] 유형별 저감방안 시뮬레이션 + 예측 연동 운영 검증")
    S, bytype, P = step_mitigation(XD, Xte, dp, E)
    summary = {"data_quality": rep, "final_model": final["name"] + " (" + ", ".join(final["members"]) + ")",
               "test_metrics": T.round(3).to_dict(orient="index"), "uncertainty_alert": info,
               "peak_extraction": ext_summ.to_dict(),
               "tariff": {"name": TARIFF_NAME, "basic_krw_per_kw": BASIC_CHARGE_KRW_PER_KW},
               "runtime_sec": round(time.time() - t0, 1)}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "run_log.txt").write_text("\n".join(LOG), encoding="utf-8")
    log(f"완료: {time.time() - t0:.0f}s")
    return locals()
