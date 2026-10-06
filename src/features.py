"""피처 생성.

예측 시점(forecast origin) 정의
- day_ahead : D-1일 24:00에 D일 96개 15분 최대수요전력을 한 번에 예측(익일 생산계획 수립·피크 사전경보용)
- hour_ahead: 매 시각, 1시간(4슬롯) 뒤 15분 최대수요전력 예측(당일 실시간 피크 경보용)

사용 가능 정보 원칙(누수 방지)
- 생산량: 가이드북 정의상 '해당 시점에 생산해야 할 생산량' = ERP 생산계획 -> 사전에 알 수 있는 값으로 사용
- 공장인원: 사용하지 않음. 공장인원 = 생산량 / (15분+30분+45분+60분 전력의 합)으로 계산된 값이라
            생산량과 함께 쓰면 그 시간의 전력을 역산할 수 있는 누수 변수(data.diagnose에서 검증)
- 기상: 실측값을 '완전한 일기예보'의 대리변수로 사용(보고서에 한계 명시, 기상 제외 모델로 민감도 확인)
- 전력(목표) 지연값: 예측 시점 이전 값만 사용 (day_ahead >= 96슬롯, hour_ahead >= 4슬롯)
"""
import numpy as np
import pandas as pd


def clock_state(hour):
    """시각 기준 운영상태(가동일)."""
    if hour < 7:
        return "새벽(0~7시)"
    if hour < 9:
        return "오전 가동 시작(7~9시)"
    if hour < 12:
        return "오전 가동 중(9~12시)"
    if hour < 14:
        return "점심 정지·재개(12~14시)"
    if hour < 17:
        return "오후 가동 중(14~17시)"
    return "저녁·야간(17시~)"


HORIZON_MIN_LAG = {"day_ahead": 96, "hour_ahead": 4}


def _day_table(L: pd.DataFrame) -> pd.DataFrame:
    """일 단위 생산계획 요약 + 이전 가동일 정보."""
    h = L[L.quarter == 0]
    g = h.groupby("date")
    D = pd.DataFrame({
        "day_prod": g["prod"].sum(),
        "day_prod_hours": g["prod"].apply(lambda s: (s > 0).sum()),
        "first_prod_hour": g.apply(lambda x: x.loc[x["prod"] > 0, "hour"].min() if (x["prod"] > 0).any() else np.nan),
        "last_prod_hour": g.apply(lambda x: x.loc[x["prod"] > 0, "hour"].max() if (x["prod"] > 0).any() else np.nan),
        "temp_max": g["temp"].max(), "temp_mean": g["temp"].mean(),
        "dow": g["dow"].first(), "holiday": g["holiday"].first(),
    })
    D["workday"] = (D["day_prod"] > 0).astype(int)
    # 정상 가동일: 일 생산계획 5,000개 이상(토요일 소량 생산·특근과 구분)
    D["full_workday"] = (D["day_prod"] >= 5000).astype(int)
    D["prev_day_prod"] = D["day_prod"].shift(1)
    D["next_day_prod"] = D["day_prod"].shift(-1)
    # 직전 가동일 이후 경과일(주말·연휴 후 재가동 = 1보다 큼)
    last = None
    gap = []
    for d, w in zip(D.index, D["full_workday"]):
        gap.append((d - last).days if last is not None else np.nan)
        if w:
            last = d
    D["days_since_workday"] = gap
    D["restart_day"] = ((D["full_workday"] == 1) & (D["days_since_workday"] > 1)).astype(int)
    return D


def build_features(L: pd.DataFrame, horizon: str = "day_ahead") -> pd.DataFrame:
    H = HORIZON_MIN_LAG[horizon]
    X = L.copy()
    D = _day_table(L)
    X = X.join(D.drop(columns=["dow", "holiday"]), on="date")

    # ---- 달력 ----
    X["weekend"] = (X["dow"] >= 6).astype(int)
    X["doy"] = X["ts"].dt.dayofyear
    X["slot_sin"] = np.sin(2 * np.pi * X["slot"] / 96)
    X["slot_cos"] = np.cos(2 * np.pi * X["slot"] / 96)

    # ---- 생산계획(사전 정보) ----
    hp = L[L.quarter == 0].set_index("ts")["prod"]
    hour_ts = X["ts"].dt.floor("h")
    for k in (1, 2):
        X[f"prod_lag{k}h"] = hour_ts.map(hp.shift(k)).values
        X[f"prod_lead{k}h"] = hour_ts.map(hp.shift(-k)).values
    X["is_prod_hour"] = (X["prod"] > 0).astype(int)
    X["hours_from_first_prod"] = X["hour"] - X["first_prod_hour"]
    X["hours_to_last_prod"] = X["last_prod_hour"] - X["hour"]
    X["prod_start_hour"] = ((X["prod"] > 0) & (X["prod_lag1h"].fillna(0) == 0)).astype(int)
    X["prod_share_day"] = X["prod"] / X["day_prod"].replace(0, np.nan)
    X["lunch"] = (X["hour"] == 12).astype(int)

    # ---- 기상 ----
    X["cdd"] = (X["temp"] - 24).clip(lower=0)
    X["hdd"] = (18 - X["temp"]).clip(lower=0)

    # ---- 전력 지연값(예측 시점 이전 정보만) ----
    y = X["kw"]
    for k in (96, 192, 288, 672, 1344):
        if k >= H:
            X[f"lag{k}"] = y.shift(k)
    X["same_slot_4w_mean"] = pd.concat([y.shift(672 * i) for i in (1, 2, 3, 4)], axis=1).mean(axis=1)
    X["same_slot_7d_mean"] = pd.concat([y.shift(96 * i) for i in range(1, 8)], axis=1).mean(axis=1)
    X["roll96_mean"] = y.shift(H).rolling(96, min_periods=48).mean()
    X["roll96_max"] = y.shift(H).rolling(96, min_periods=48).max()
    X["roll672_max"] = y.shift(H).rolling(672, min_periods=300).max()
    # 직전 '가동일'의 같은 슬롯 값(월요일·연휴 후 재가동일 대응)
    daily_profile = X.pivot_table(index="date", columns="slot", values="kw").reindex(D.index)
    observed = daily_profile.notna().sum(axis=1) >= 80          # 전력 관측이 충분한 날만 참조
    wd = D["full_workday"] & observed
    last_wd = {}
    prev = None
    for d in D.index:
        last_wd[d] = prev
        if wd[d]:
            prev = d
    lw_dates = X["date"].map(last_wd)
    X["last_workday_slot"] = [daily_profile.at[d, s] if d is not None and pd.notna(d) else np.nan
                              for d, s in zip(lw_dates, X["slot"])]
    X["last_workday_max"] = lw_dates.map(daily_profile.max(axis=1)).values
    # 직전 같은 요일 같은 슬롯과 동일 요일 일 최대값
    X["last_same_dow_max"] = X["date"].map((daily_profile.max(axis=1)).shift(7, freq="D")).values

    if horizon == "hour_ahead":
        for k in (4, 5, 6, 8, 12):
            X[f"lag{k}"] = y.shift(k)
        X["roll4_mean"] = y.shift(H).rolling(4, min_periods=2).mean()
        X["diff4"] = y.shift(H) - y.shift(H + 4)
    return X


# 모델 입력 피처 목록
BASE_FEATS = [
    "hour", "quarter", "slot", "slot_sin", "slot_cos", "dow", "weekend", "holiday", "month", "doy",
    "prod", "prod_lag1h", "prod_lag2h", "prod_lead1h", "prod_lead2h",
    "is_prod_hour", "hours_from_first_prod", "hours_to_last_prod", "prod_start_hour", "prod_share_day", "lunch",
    "day_prod", "day_prod_hours", "first_prod_hour", "last_prod_hour", "workday", "full_workday",
    "prev_day_prod", "next_day_prod", "days_since_workday", "restart_day",
]
WEATHER_FEATS = ["temp", "humid", "wind", "rain", "cdd", "hdd", "temp_max", "temp_mean"]
LAG_FEATS_DA = ["lag96", "lag192", "lag288", "lag672", "lag1344", "same_slot_4w_mean", "same_slot_7d_mean",
                "roll96_mean", "roll96_max", "roll672_max", "last_workday_slot", "last_workday_max", "last_same_dow_max"]
LAG_FEATS_HA = LAG_FEATS_DA + ["lag4", "lag5", "lag6", "lag8", "lag12", "roll4_mean", "diff4"]


def feature_list(horizon="day_ahead", weather=True, lags=True):
    f = list(BASE_FEATS)
    if weather:
        f += WEATHER_FEATS
    if lags:
        f += LAG_FEATS_DA if horizon == "day_ahead" else LAG_FEATS_HA
    return f
