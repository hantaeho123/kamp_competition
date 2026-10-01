"""평가지표: 점 예측 + 피크 지표 + 피크위험 이벤트 분류(F1)."""
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from .config import PEAK_EVENT_KW


def point_metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    m = ~np.isnan(y) & ~np.isnan(p)
    y, p = y[m], p[m]
    e = p - y
    rmse = np.sqrt(np.mean(e ** 2))
    return {"MAE": np.mean(np.abs(e)), "RMSE": rmse, "CV(RMSE)%": 100 * rmse / np.mean(y),
            "NMAE%": 100 * np.mean(np.abs(e)) / np.mean(y), "Bias": np.mean(e)}


def peak_metrics(df, pred_col="pred", y_col="kw"):
    """일 최대수요전력(일 피크) 크기·시각 오차, 피크위험 이벤트(>=180kW) 분류 성능."""
    d = df.dropna(subset=[y_col])
    g = d.groupby("date")
    ymax, pmax = g[y_col].max(), g[pred_col].max()
    work = g["full_workday"].first() == 1
    t_true = g.apply(lambda x: x.loc[x[y_col].idxmax(), "slot"])
    t_pred = g.apply(lambda x: x.loc[x[pred_col].idxmax(), "slot"])
    ev_true = (d[y_col] >= PEAK_EVENT_KW).astype(int)
    ev_pred = (d[pred_col] >= PEAK_EVENT_KW).astype(int)
    return {
        "DailyPeak_MAE": np.mean(np.abs(pmax - ymax)),
        "DailyPeak_MAE(가동일)": np.mean(np.abs(pmax - ymax)[work]),
        "PeakTime_within1h%": 100 * np.mean((np.abs(t_true - t_pred) <= 4)[work]),
        "PeriodPeak_err": pmax.max() - ymax.max(),
        "PeakEvent_F1": f1_score(ev_true, ev_pred, zero_division=0),
        "PeakEvent_Precision": precision_score(ev_true, ev_pred, zero_division=0),
        "PeakEvent_Recall": recall_score(ev_true, ev_pred, zero_division=0),
    }


def all_metrics(df, pred_col="pred"):
    out = point_metrics(df["kw"], df[pred_col])
    w = df["is_prod_hour"] == 1
    out["MAE(생산시간)"] = point_metrics(df.loc[w, "kw"], df.loc[w, pred_col])["MAE"]
    out.update(peak_metrics(df, pred_col))
    return out
