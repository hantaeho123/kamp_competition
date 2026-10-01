"""예측 모델 정의: 베이스라인 2종 + 가이드북 재현(RF) + 선형 + 부스팅 3종 + 신경망 + 앙상블."""
import numpy as np
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from .config import SEED

N_JOBS = 4   # 스레드 고정(macOS에서 OpenMP 런타임 경합으로 인한 급격한 지연 방지, 재현성 확보)

LGB_PARAMS = dict(n_estimators=900, learning_rate=0.03, num_leaves=31, min_child_samples=30,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                  random_state=SEED, verbose=-1, n_jobs=N_JOBS)


class NaiveSeasonal:
    """베이스라인1: 지난주 같은 요일·같은 15분 슬롯 값(계절성 naive)."""
    name = "Naive(지난주 동시각)"

    def fit(self, X, y, w=None):
        return self

    def predict(self, X):
        return X["lag672"].fillna(X["lag96"]).values


class LastWorkdayProfile:
    """베이스라인2: 생산계획 기반 규칙 — 가동일이면 직전 가동일 같은 슬롯, 비가동일이면 지난주 같은 슬롯."""
    name = "Rule(직전가동일 프로파일)"

    def fit(self, X, y, w=None):
        return self

    def predict(self, X):
        p = pd.Series(np.where(X["full_workday"] == 1, X["last_workday_slot"], X["lag672"]))
        for fb in ("lag672", "same_slot_7d_mean", "lag96"):      # 참조일 결측 슬롯 대체
            p = p.fillna(pd.Series(X[fb].values))
        return p.values


class SKWrap:
    def __init__(self, name, est, needs_impute=False):
        self.name, self.est, self.needs_impute = name, est, needs_impute

    def fit(self, X, y, w=None):
        kw = {}
        if w is not None:
            last = self.est.steps[-1][0] if hasattr(self.est, "steps") else None
            if last is None:
                kw["sample_weight"] = w
            elif last != "mlpregressor":
                kw[f"{last}__sample_weight"] = w
        self.est.fit(X, y, **kw)
        return self

    def predict(self, X):
        return self.est.predict(X)


def make_model(name):
    if name == "naive":
        return NaiveSeasonal()
    if name == "rule":
        return LastWorkdayProfile()
    if name == "rf":   # 가이드북 실습 모델(max_depth=20)
        return SKWrap("RandomForest(가이드북)", make_pipeline(SimpleImputer(strategy="median"),
                      RandomForestRegressor(n_estimators=300, max_depth=20, n_jobs=N_JOBS, random_state=SEED)))
    if name == "ridge":
        return SKWrap("Ridge", make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=3.0)))
    if name == "mlp":
        return SKWrap("MLP(DNN)", make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                      MLPRegressor(hidden_layer_sizes=(128, 64), alpha=1e-3, learning_rate_init=1e-3,
                                   max_iter=300, early_stopping=True, random_state=SEED)))
    if name == "lgbm":
        return SKWrap("LightGBM", lgb.LGBMRegressor(objective="regression", **LGB_PARAMS))
    if name == "lgbm_l1":
        return SKWrap("LightGBM(L1)", lgb.LGBMRegressor(objective="l1", **LGB_PARAMS))
    if name == "xgb":
        return SKWrap("XGBoost", xgb.XGBRegressor(n_estimators=800, learning_rate=0.03, max_depth=6, subsample=0.8,
                      colsample_bytree=0.8, min_child_weight=5, random_state=SEED, n_jobs=N_JOBS))
    if name == "cat":
        return SKWrap("CatBoost", CatBoostRegressor(iterations=1500, learning_rate=0.05, depth=6, loss_function="RMSE",
                      random_seed=SEED, verbose=0, allow_writing_files=False,
                                                    thread_count=N_JOBS))
    raise ValueError(name)


def make_quantile(alpha):
    p = dict(LGB_PARAMS)
    return lgb.LGBMRegressor(objective="quantile", alpha=alpha, **p)
