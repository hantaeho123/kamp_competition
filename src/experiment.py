"""시간 순서 기반 검증(롤링 원점 백테스트)과 최종 시험 구간 평가."""
import numpy as np
import pandas as pd

from .config import CV_FOLD_STARTS, CV_FOLD_DAYS, TEST_START
from .features import feature_list
from .models import make_model
from .metrics import all_metrics


def sample_weight(X, scheme):
    if scheme == "none":
        return np.ones(len(X))
    if scheme == "aug_inv":            # 증강 복사 그룹 크기의 역수: 같은 패턴이 n번 반복되면 각 1/n
        return 1.0 / X["aug_size"].values
    if scheme == "aug_inv_recent":     # + 최근(7월 이후 원본 구간) 2배
        return (1.0 / X["aug_size"].values) * np.where(X["ts"] >= "2021-07-01", 2.0, 1.0)
    raise ValueError(scheme)


def fit_predict(X, train_mask, pred_mask, model_name, feats, weight="aug_inv"):
    tr = X[train_mask & X["kw"].notna()]
    m = make_model(model_name)
    m.fit(tr[feats], tr["kw"].values, sample_weight(tr, weight))
    return m, m.predict(X.loc[pred_mask, feats])


def backtest(X, model_name, horizon="day_ahead", weather=True, lags=True, weight="aug_inv", folds=CV_FOLD_STARTS):
    feats = feature_list(horizon, weather, lags)
    outs = []
    for f0 in folds:
        s, e = pd.Timestamp(f0), pd.Timestamp(f0) + pd.Timedelta(days=CV_FOLD_DAYS)
        trm = X["ts"] < s
        pm = (X["ts"] >= s) & (X["ts"] < e)
        _, p = fit_predict(X, trm, pm, model_name, feats, weight)
        o = X.loc[pm].copy()
        o["pred"] = np.clip(p, 0, None)
        o["fold"] = f0
        outs.append(o)
    return pd.concat(outs)


def test_eval(X, model_name, horizon="day_ahead", weather=True, lags=True, weight="aug_inv"):
    feats = feature_list(horizon, weather, lags)
    trm = X["ts"] < TEST_START
    pm = X["ts"] >= TEST_START
    m, p = fit_predict(X, trm, pm, model_name, feats, weight)
    o = X.loc[pm].copy()
    o["pred"] = np.clip(p, 0, None)
    return m, o


def summarize(df):
    return pd.Series(all_metrics(df))
