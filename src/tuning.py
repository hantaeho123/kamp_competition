"""1단계 보강: 하이퍼파라미터 탐색 + 추가 모델 + 다양한 앙상블.

- 탐색: Optuna(TPE, 시드 고정)로 LightGBM·XGBoost·CatBoost를, 격자로 MLP·RandomForest를 탐색.
        목적함수 = 롤링 백테스트 8개 구간의 표본 외 MAE(시험 구간은 탐색에 쓰지 않음)
- 추가 모델: ExtraTrees, HistGradientBoosting
- 앙상블: 단순 평균, 중앙값, 비음수 가중 평균(NNLS), 스태킹(Ridge 메타모델)
          가중치·메타모델은 '해당 구간을 뺀 나머지 7개 구간'으로 구해 그 구간에 적용(구간 교차 방식)하므로 백테스트 수치가 부풀지 않음
"""
import time
import numpy as np
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
import optuna
from catboost import CatBoostRegressor
from scipy.optimize import nnls
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import CV_FOLD_STARTS, CV_FOLD_DAYS, TEST_START, S1, SEED
from .features import feature_list
from .metrics import all_metrics
from .plotting import plt, save, C

optuna.logging.set_verbosity(optuna.logging.WARNING)
NJ = 4


def build(kind, p):
    if kind == "lgbm":
        return lgb.LGBMRegressor(random_state=SEED, verbose=-1, n_jobs=NJ, subsample_freq=1, **p)
    if kind == "xgb":
        return xgb.XGBRegressor(random_state=SEED, n_jobs=NJ, **p)
    if kind == "cat":
        return CatBoostRegressor(random_seed=SEED, verbose=0, allow_writing_files=False, thread_count=NJ, loss_function="RMSE", **p)
    if kind == "rf":
        return make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_jobs=NJ, random_state=SEED, **p))
    if kind == "et":
        return make_pipeline(SimpleImputer(strategy="median"), ExtraTreesRegressor(n_jobs=NJ, random_state=SEED, **p))
    if kind == "hgb":
        return HistGradientBoostingRegressor(random_state=SEED, **p)
    if kind == "mlp":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             MLPRegressor(max_iter=300, early_stopping=True, random_state=SEED, **p))
    raise ValueError(kind)


def cv_predict(X, feats, kind, p):
    """8개 구간 표본 외 예측(구간 순서대로 이어 붙인 배열)."""
    out = []
    for f0 in CV_FOLD_STARTS:
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        tr = X[(X["ts"] < s) & X["kw"].notna()]
        te = X[(X["ts"] >= s) & (X["ts"] < e)]
        out.append(np.clip(build(kind, p).fit(tr[feats], tr["kw"]).predict(te[feats]), 0, None))
    return np.concatenate(out)


def cv_frame(X):
    parts = []
    for f0 in CV_FOLD_STARTS:
        s = pd.Timestamp(f0)
        e = s + pd.Timedelta(days=CV_FOLD_DAYS)
        parts.append(X[(X["ts"] >= s) & (X["ts"] < e)].assign(fold=f0))
    return pd.concat(parts)


SPACES = {
    "lgbm": lambda t: dict(n_estimators=t.suggest_int("n_estimators", 300, 1500, step=100),
                           learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
                           num_leaves=t.suggest_int("num_leaves", 7, 63),
                           min_child_samples=t.suggest_int("min_child_samples", 10, 80),
                           subsample=t.suggest_float("subsample", 0.6, 1.0),
                           colsample_bytree=t.suggest_float("colsample_bytree", 0.5, 1.0),
                           reg_lambda=t.suggest_float("reg_lambda", 0.01, 10, log=True),
                           objective=t.suggest_categorical("objective", ["regression", "l1", "huber"])),
    "xgb": lambda t: dict(n_estimators=t.suggest_int("n_estimators", 300, 1500, step=100),
                          learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
                          max_depth=t.suggest_int("max_depth", 3, 8),
                          min_child_weight=t.suggest_int("min_child_weight", 1, 20),
                          subsample=t.suggest_float("subsample", 0.6, 1.0),
                          colsample_bytree=t.suggest_float("colsample_bytree", 0.5, 1.0),
                          reg_lambda=t.suggest_float("reg_lambda", 0.01, 10, log=True)),
    "cat": lambda t: dict(iterations=t.suggest_int("iterations", 500, 1500, step=250),
                          learning_rate=t.suggest_float("learning_rate", 0.03, 0.15, log=True),
                          depth=t.suggest_int("depth", 4, 8),
                          l2_leaf_reg=t.suggest_float("l2_leaf_reg", 1, 10, log=True)),
}
DEFAULTS = {
    "lgbm": dict(n_estimators=900, learning_rate=0.03, num_leaves=31, min_child_samples=30, subsample=0.8,
                 colsample_bytree=0.8, reg_lambda=1.0, objective="regression"),
    "xgb": dict(n_estimators=800, learning_rate=0.03, max_depth=6, subsample=0.8, colsample_bytree=0.8, min_child_weight=5),
    "cat": dict(iterations=1500, learning_rate=0.05, depth=6),
}
GRIDS = {
    "rf": [dict(n_estimators=300, max_depth=20), dict(n_estimators=300, max_depth=12, min_samples_leaf=5),
           dict(n_estimators=500, max_depth=None, min_samples_leaf=3, max_features=0.5)],
    "et": [dict(n_estimators=300, max_depth=None, min_samples_leaf=3), dict(n_estimators=500, max_depth=20, min_samples_leaf=5, max_features=0.7)],
    "hgb": [dict(max_iter=600, learning_rate=0.05, max_leaf_nodes=31), dict(max_iter=1000, learning_rate=0.03, max_leaf_nodes=15, l2_regularization=1.0)],
    "mlp": [dict(hidden_layer_sizes=(128, 64), alpha=1e-3, learning_rate_init=1e-3),
            dict(hidden_layer_sizes=(64, 32), alpha=1e-2, learning_rate_init=1e-3),
            dict(hidden_layer_sizes=(256, 128, 64), alpha=1e-3, learning_rate_init=5e-4)],
}
NAMES = {"lgbm": "LightGBM", "xgb": "XGBoost", "cat": "CatBoost", "rf": "RandomForest", "et": "ExtraTrees",
         "hgb": "HistGradientBoosting", "mlp": "MLP"}


# 아래 탐색(search)으로 찾은 최적 설정의 기록(반올림 없이 그대로: CatBoost는 학습률 소수 넷째 자리 차이에도 MAE가 0.3kW 달라짐).
# 기본 실행은 이 설정으로 학습만 하고, 탐색을 다시 하려면 search()를 호출
TUNED = {'lgbm': {'n_estimators': 300, 'learning_rate': 0.09330606024425668, 'num_leaves': 54, 'min_child_samples': 25, 'subsample': 0.6727299868828402, 'colsample_bytree': 0.5917022549267169, 'reg_lambda': 0.08179499475211674, 'objective': 'regression'}, 'xgb': {'n_estimators': 1200, 'learning_rate': 0.010530955003248244, 'max_depth': 8, 'min_child_weight': 3, 'subsample': 0.649207772328176, 'colsample_bytree': 0.7280595244346797, 'reg_lambda': 0.7202519832502359}, 'cat': {'iterations': 1250, 'learning_rate': 0.031010530712092203, 'depth': 8, 'l2_leaf_reg': 6.798962421591129}, 'rf': {'n_estimators': 500, 'max_depth': None, 'min_samples_leaf': 3, 'max_features': 0.5}, 'et': {'n_estimators': 300, 'max_depth': None, 'min_samples_leaf': 3}, 'hgb': {'max_iter': 600, 'learning_rate': 0.05, 'max_leaf_nodes': 31}, 'mlp': {'hidden_layer_sizes': (256, 128, 64), 'alpha': 0.001, 'learning_rate_init': 0.0005}}

# 최종 전력량 예측 모델은 이름을 고정하지 않고, run()에서 백테스트 MAE가 가장 낮은 후보로 자동 선정한다.


def search(X, n_trials=None, log=print):
    """하이퍼파라미터 탐색(약 30분). 부스팅 3종은 Optuna, 나머지 4종은 격자. 시도 기록을 tuning_trials.csv로 저장."""
    n_trials = n_trials or {"lgbm": 30, "xgb": 30, "cat": 15}
    feats = feature_list("day_ahead", weather=True, lags=False)
    V = cv_frame(X)
    y = V["kw"].values
    ok = ~np.isnan(y)
    mae = lambda p: float(np.mean(np.abs(p[ok] - y[ok])))
    trials, best = [], {}
    for kind in ("lgbm", "xgb", "cat"):       # 기본값을 첫 시도로 넣어 '기본값보다 나빠지는 일'을 방지
        t0 = time.time()

        def obj(t, kind=kind):
            return mae(cv_predict(X, feats, kind, SPACES[kind](t)))

        st = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=SEED))
        st.enqueue_trial({k: v for k, v in DEFAULTS[kind].items()})
        st.optimize(obj, n_trials=n_trials[kind])
        for t in st.trials:
            trials.append({"모델": NAMES[kind], "시도": t.number, "MAE": t.value, "기본값": int(t.number == 0), **{f"p_{k}": v for k, v in t.params.items()}})
        best[kind] = st.best_params
        log(f"  {NAMES[kind]}: 기본값 MAE {st.trials[0].value:.3f} -> 탐색 최적 {st.best_value:.3f} ({n_trials[kind]}회, {time.time() - t0:.0f}s)")
    for kind, grid in GRIDS.items():
        res = []
        for i, p in enumerate(grid):
            res.append((mae(cv_predict(X, feats, kind, p)), i))
            trials.append({"모델": NAMES[kind], "시도": i, "MAE": res[-1][0], "기본값": int(i == 0), "p_설정": str(p)})
        best[kind] = grid[min(res)[1]]
        log(f"  {NAMES[kind]}: 격자 {len(grid)}개 중 최적 MAE {min(res)[0]:.3f}")
    pd.DataFrame(trials).to_csv(S1 / "tuning_trials.csv", index=False, encoding="utf-8-sig")
    return best


def run(X, best=None, log=print):
    """탐색된 설정(best, 기본은 TUNED)으로 7종 모델을 백테스트·시험 평가하고 앙상블 5종을 비교."""
    best = best or TUNED
    feats = feature_list("day_ahead", weather=True, lags=False)
    V = cv_frame(X)
    y = V["kw"].values
    ok = ~np.isnan(y)
    oos = {}
    for kind in ("lgbm", "xgb", "cat"):
        oos[NAMES[kind] + "(기본값)"] = cv_predict(X, feats, kind, DEFAULTS[kind])
    for kind in best:
        t0 = time.time()
        oos[NAMES[kind] + "(탐색)"] = oos[NAMES[kind] + "(기본값)"] if best[kind] == DEFAULTS.get(kind) else cv_predict(X, feats, kind, best[kind])
        log(f"  {NAMES[kind]}(탐색 설정): 백테스트 MAE {np.mean(np.abs(oos[NAMES[kind] + '(탐색)'][ok] - y[ok])):.3f} ({time.time() - t0:.0f}s)")

    # ---- (3) 앙상블(구간 교차 방식으로 가중치·메타모델 추정) ----
    base = [n for n in oos if n.endswith("(탐색)")]
    P = np.column_stack([oos[n] for n in base])
    boost = [base.index(NAMES[k] + "(탐색)") for k in ("lgbm", "xgb", "cat")]
    fold = V["fold"].values
    ens = {"앙상블: 부스팅 3종 평균": P[:, boost].mean(1), "앙상블: 전체 7종 평균": P.mean(1), "앙상블: 전체 7종 중앙값": np.median(P, 1)}
    w_nn, st_pred = np.zeros(len(y)), np.zeros(len(y))
    for f in np.unique(fold):
        tr, te = (fold != f) & ok, fold == f
        w, _ = nnls(P[tr], y[tr])
        w = w / w.sum()
        w_nn[te] = P[te] @ w
        st_pred[te] = Ridge(alpha=10.0).fit(P[tr], y[tr]).predict(P[te])
    ens["앙상블: 비음수 가중 평균(NNLS)"] = w_nn
    ens["앙상블: 스태킹(Ridge 메타모델)"] = np.clip(st_pred, 0, None)
    w_full, _ = nnls(P[ok], y[ok])
    w_full = w_full / w_full.sum()
    meta = Ridge(alpha=10.0).fit(P[ok], y[ok])
    W = pd.Series(w_full, index=[b.replace("(탐색)", "") for b in base], name="가중치").round(3)
    W.to_csv(S1 / "ensemble_weights.csv", encoding="utf-8-sig")

    # ---- (4) 시험 구간: 9/1 이전 전체로 학습 ----
    tr = X[(X["ts"] < TEST_START) & X["kw"].notna()]
    te = X[X["ts"] >= TEST_START].copy()
    tp = {}
    for kind in ("lgbm", "xgb", "cat"):
        tp[NAMES[kind] + "(기본값)"] = np.clip(build(kind, DEFAULTS[kind]).fit(tr[feats], tr["kw"]).predict(te[feats]), 0, None)
    for kind in best:
        tp[NAMES[kind] + "(탐색)"] = np.clip(build(kind, best[kind]).fit(tr[feats], tr["kw"]).predict(te[feats]), 0, None)
    PT = np.column_stack([tp[n] for n in base])
    tp["앙상블: 부스팅 3종 평균"] = PT[:, boost].mean(1)
    tp["앙상블: 전체 7종 평균"] = PT.mean(1)
    tp["앙상블: 전체 7종 중앙값"] = np.median(PT, 1)
    tp["앙상블: 비음수 가중 평균(NNLS)"] = PT @ w_full
    tp["앙상블: 스태킹(Ridge 메타모델)"] = np.clip(meta.predict(PT), 0, None)

    # ---- (5) 결과표: 백테스트·시험, 구간별 MAE 표준편차 ----
    rows = []
    allcv = {**oos, **ens}
    for n in allcv:
        m = all_metrics(V.assign(pred=allcv[n]))
        fm = [np.mean(np.abs(allcv[n][(fold == f) & ok] - y[(fold == f) & ok])) for f in np.unique(fold)]
        mt = all_metrics(te.assign(pred=tp[n]))
        base_fm = [np.mean(np.abs(oos["LightGBM(기본값)"][(fold == f) & ok] - y[(fold == f) & ok])) for f in np.unique(fold)]
        rows.append({"모델": n, "백테스트 MAE": m["MAE"], "백테스트 RMSE": m["RMSE"], "구간별 MAE 표준편차": np.std(fm),
                     "LightGBM 기본값보다 나은 구간 수(8개 중)": int(np.sum(np.array(fm) < np.array(base_fm) - 1e-9)),
                     "백테스트 일최대 MAE(가동일)": m["DailyPeak_MAE(가동일)"], "시험 MAE": mt["MAE"], "시험 RMSE": mt["RMSE"],
                     "시험 일최대 MAE(가동일)": mt["DailyPeak_MAE(가동일)"]})
    RES = pd.DataFrame(rows).sort_values("백테스트 MAE").reset_index(drop=True)
    RES.round(3).to_csv(S1 / "tuning_and_ensemble_comparison.csv", index=False, encoding="utf-8-sig")
    FINAL_NAME = RES.iloc[0]["모델"]            # 선정 규칙: 백테스트(Valid) MAE 최저. 시험 성적은 선정에 쓰지 않음
    BP = pd.DataFrame([{"모델": NAMES[k], "최적 설정": str({a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})} for k, v in best.items()])
    BP.to_csv(S1 / "tuning_best_params.csv", index=False, encoding="utf-8-sig")

    # ---- 그림: 탐색 과정(시도 기록이 있을 때) / 모델·앙상블 비교 ----
    tfile = S1 / "tuning_trials.csv"
    fig, ax = plt.subplots(1, 2, figsize=(15, 4.8), gridspec_kw={"width_ratios": [1, 1.25]})
    if tfile.exists():
        TR = pd.read_csv(tfile)
        for kind, colr in (("lgbm", C["pred"]), ("xgb", C["good"]), ("cat", C["accent"])):
            q = TR[TR["모델"] == NAMES[kind]].sort_values("시도")
            ax[0].scatter(q["시도"], q["MAE"], s=12, color=colr, alpha=.5)
            ax[0].plot(q["시도"], q["MAE"].cummin(), color=colr, lw=1.6, label=f"{NAMES[kind]} (기본값 {q['MAE'].iloc[0]:.2f} → 최적 {q['MAE'].min():.2f})")
        ax[0].set(xlabel="탐색 시도 번호(0 = 기본값)", ylabel="백테스트 MAE(kW)", title="하이퍼파라미터 탐색 과정(선: 그때까지의 최적)")
        ax[0].set_ylim(TR[TR["모델"].isin(["LightGBM", "XGBoost", "CatBoost"])]["MAE"].min() - .1, 9.2)
        ax[0].legend(frameon=False, fontsize=8)
    else:
        TR = None
        ax[0].axis("off")
        ax[0].text(.5, .5, "탐색 시도 기록(tuning_trials.csv) 없음\nsearch()를 실행하면 생성됩니다", ha="center", va="center")
    r = RES.sort_values("백테스트 MAE", ascending=False)
    yy = np.arange(len(r))
    ax[1].barh(yy + .2, r["백테스트 MAE"], .4, color=C["muted"], label="백테스트(7~8월)")
    ax[1].barh(yy - .2, r["시험 MAE"], .4, color=[C["peak"] if n == FINAL_NAME else C["pred"] for n in r["모델"]], label="시험(9/1~14)")
    ax[1].set_yticks(yy, r["모델"], fontsize=8)
    ax[1].set(xlabel="MAE(kW)", title="탐색 모델과 앙상블 비교(붉은색: 최종 선정)", xlim=(5.5, max(r["백테스트 MAE"].max(), r["시험 MAE"].max()) + .3))
    ax[1].legend(frameon=False, fontsize=8)
    save(fig, S1 / "tuning_and_ensemble.png")
    final = {"name": FINAL_NAME, "cv_pred": pd.Series(allcv[FINAL_NAME], index=V.index), "test_pred": pd.Series(tp[FINAL_NAME], index=te.index),
             "members": [b.replace("(탐색)", "") for b in base] if FINAL_NAME.startswith("앙상블") else [FINAL_NAME.replace("(탐색)", "")]}
    return RES, TR, BP, W, final
