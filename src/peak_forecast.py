"""피크 전용 예측: (1) 일 최대수요전력 예측(일 단위 모델 + 직전 가동일 규칙 앙상블), (2) 15분 피크위험 경보(분위수)."""
import numpy as np
import pandas as pd
import lightgbm as lgb

from .config import SEED

DAY_FEATS = ["day_prod", "day_prod_hours", "first_prod_hour", "restart_day", "days_since_workday",
             "full_workday", "dow", "holiday", "month", "temp_max", "temp_mean", "prev_day_prod"]


def day_frame(X):
    agg = {c: (c, "first") for c in DAY_FEATS + ["last_workday_max", "last_same_dow_max"]}
    agg["ymax"] = ("kw", "max")
    agg["n_obs"] = ("kw", "count")
    D = X.groupby("date").agg(**agg)
    D.loc[D["n_obs"] < 80, "ymax"] = np.nan    # 결측이 많은 날은 일 피크 목표에서 제외
    return D


class DailyPeakModel:
    """일 최대 15분 수요전력 = 0.5*LightGBM(일 단위 계획·달력·기상) + 0.5*규칙(가동일: 직전 가동일 최대값)."""

    def __init__(self, w_rule=0.5):
        self.w_rule = w_rule
        self.m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=8, min_child_samples=10,
                                   subsample=0.8, subsample_freq=1, random_state=SEED, verbose=-1, n_jobs=4)

    def fit(self, D):
        t = D.dropna(subset=["ymax"])
        self.m.fit(t[DAY_FEATS], t["ymax"])
        return self

    def predict(self, D):
        pm = self.m.predict(D[DAY_FEATS])
        rule = np.where(D["full_workday"] == 1, D["last_workday_max"], D["last_same_dow_max"])
        rule = np.where(np.isnan(rule), pm, rule)
        return pd.DataFrame({"dmax_model": pm, "dmax_rule": rule,
                             "dmax_pred": (1 - self.w_rule) * pm + self.w_rule * rule}, index=D.index)
