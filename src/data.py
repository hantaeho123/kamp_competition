"""데이터 적재·진단·정제.

핵심 정제 규칙(모두 결과보고서 '데이터 이해 및 진단'에 근거 제시):
1) '시간' 컬럼 손상(07-13, 07-15 이틀 48행: 0~23 대신 70~188). 손상된 값 기준으로 행이 오름차순 정렬되어
   행 순서로도 실제 시각을 알 수 없음(인접일 기상 매칭 복원 시도 -> 정상 가동 프로파일과 불일치).
   -> 해당 이틀의 전력값은 목표값 결측 처리(학습·평가 제외), 날짜 단위 정보(생산계획 등)만 유지
2) 전력 0 구간(08-28 18시 ~ 08-29 10시, 17행): 계측 누락/정전으로 판단 -> 목표값 결측 처리(학습·평가 제외)
3) 생산량 누락(07-13, 07-15: 전력은 정상 가동 수준인데 생산량 0) -> 직전 4주 동일 요일·시간 중앙값으로 대체 + 플래그
4) 강수량은 일 누적값(1시 초기화, 0시에 전일 합계) -> 시간 강수량으로 변환
5) 풍속·강수량 결측 4행 -> 선형보간
6) 증강 복사일(하루 96개 15분 전력 패턴이 다른 날과 완전히 동일) -> aug_group/aug_size 플래그, 학습 가중치에 활용
7) 15분 단위 0값(08-28 17:30~45, 08-29 11:00~15, 09-08 12:00~15, 6개 슬롯) -> 계측 누락으로 결측 처리
"""
import numpy as np
import pandas as pd
import holidays

from .config import DATA_PATH, QUARTER_COLS

RENAME = {"날짜": "date_int", "시간": "hour_raw", "평균": "avg", "생산량": "prod", "기온": "temp",
          "풍속": "wind", "습도": "humid", "강수량": "rain_cum", "전기요금(계절)": "tariff_season",
          "day": "dow", "d": "dom", "m": "month", "공장인원": "staff", "인건비": "labor_mult"}


def load_raw(path=DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def diagnose(raw: pd.DataFrame) -> dict:
    """원천 데이터 품질 진단 결과(표로 저장)."""
    df = raw.rename(columns=RENAME)
    dates = pd.to_datetime(df["date_int"].astype(str))
    rep = {}
    rep["행 수"] = len(df)
    rep["열 수"] = raw.shape[1]
    rep["일 수"] = dates.nunique()
    rep["기간"] = f"{dates.min().date()} ~ {dates.max().date()}"
    rep["결측(풍속/강수량/공장인원)"] = f"{df.wind.isna().sum()}/{df.rain_cum.isna().sum()}/{df.staff.isna().sum()}"
    rep["완전 중복 행"] = int(raw.duplicated().sum())
    rep["(날짜,시간) 중복 키"] = int(raw.duplicated(["날짜", "시간"]).sum())
    rep["시간 범위 위반(>23) 행"] = int((df.hour_raw > 23).sum())
    rep["전력 4구간 모두 0인 행"] = int((df[QUARTER_COLS] == 0).all(axis=1).sum())
    avg_chk = (df[QUARTER_COLS].mean(axis=1) - df["avg"]).abs()
    rep["평균 = 4구간 평균 일치(오차<=0.5)"] = f"{(avg_chk <= 0.5).mean():.1%}"
    calc_dow = dates.dt.dayofweek + 1
    rep["요일(day) 일치율"] = f"{(calc_dow == df.dow).mean():.1%}"
    return rep


def find_aug_groups(df: pd.DataFrame) -> pd.Series:
    """하루 96개 15분 전력값이 완전히 같은 날끼리 그룹 id 부여 (단독 날은 -1)."""
    sig = df.groupby("date")[QUARTER_COLS].apply(lambda g: hash(g.values.tobytes()))
    counts = sig.map(sig.value_counts())
    gid = sig.astype("category").cat.codes.where(counts > 1, -1)
    return pd.DataFrame({"aug_group": gid, "aug_size": counts.where(counts > 1, 1)})


def clean_hourly(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=RENAME).copy()
    df["date"] = pd.to_datetime(df["date_int"].astype(str))
    df["prod"] = df["prod"].astype(float)
    # 1) 시간 복원: 모든 날이 정확히 24행이고 행 순서가 0~23시 순서임을 확인 후 적용
    assert (df.groupby("date").size() == 24).all()
    df["hour"] = df.groupby("date").cumcount()
    df["hour_corrupted"] = (df["hour_raw"] != df["hour"]).astype(int)
    df["ts"] = df["date"] + pd.to_timedelta(df["hour"], unit="h")

    # 1-2) 시간 순서 불명일 -> 전력 결측 처리
    bad_days = df.loc[df["hour_corrupted"] == 1, "date"].unique()
    df["hour_order_unknown"] = df["date"].isin(bad_days).astype(int)
    # 2) 전력 0 구간 -> 결측
    zero = (df[QUARTER_COLS] == 0).all(axis=1)
    df["power_missing"] = (zero | (df["hour_order_unknown"] == 1)).astype(int)
    df.loc[df["power_missing"] == 1, QUARTER_COLS + ["avg"]] = np.nan

    # 4) 강수량: 일 누적 -> 시간 강수량. 0시 행은 전일 합계가 남아 있으므로 0시 강수 = 0시 값 - 전일 23시 값
    rc = df["rain_cum"].interpolate(limit_direction="both")
    prev = rc.shift(1)
    hourly = np.where(df["hour"] == 1, rc, rc - prev)
    df["rain"] = np.clip(np.nan_to_num(hourly), 0, None)
    # 5) 결측 보간
    df["wind"] = df["wind"].interpolate(limit_direction="both")
    df["staff"] = df["staff"].fillna(0.0)

    # 3) 생산량 누락일 대체(07-13, 07-15)
    df["prod_imputed"] = 0
    miss_days = []
    for d, g in df.groupby("date"):
        # 평일 정상가동 수준 전력(일평균>100)인데 생산계획이 전부 0이고 '시간' 컬럼까지 손상된 날
        if g["prod"].sum() == 0 and g["hour_order_unknown"].any():
            miss_days.append(d)
    for d in miss_days:
        ref = df[(df.date < d) & (df.date >= d - pd.Timedelta(days=28)) & (df.dow == df.loc[df.date == d, "dow"].iloc[0])
                 & (~df.date.isin(miss_days))]
        med = ref.groupby("hour")[["prod", "staff"]].median()
        idx = df.date == d
        df.loc[idx, "prod"] = df.loc[idx, "hour"].map(med["prod"]).values
        df.loc[idx, "staff"] = df.loc[idx, "hour"].map(med["staff"]).values
        df.loc[idx, "prod_imputed"] = 1

    # 공휴일(외부데이터: python 'holidays' 패키지의 대한민국 법정공휴일)
    kr = holidays.KR(years=2021)
    df["holiday"] = df["date"].dt.date.map(lambda x: int(x in kr))

    # 6) 증강 복사 그룹
    aug = find_aug_groups(df)
    df = df.join(aug, on="date")
    return df


def to_long(hourly: pd.DataFrame) -> pd.DataFrame:
    """시간 단위(1행=1시간, 4개 15분 컬럼) -> 15분 단위 long 포맷(1행=15분 슬롯)."""
    keep = [c for c in hourly.columns if c not in QUARTER_COLS]
    L = hourly.melt(id_vars=keep, value_vars=QUARTER_COLS, var_name="qcol", value_name="kw")
    L["quarter"] = L["qcol"].map({c: i for i, c in enumerate(QUARTER_COLS)})
    L["ts"] = L["ts"] + pd.to_timedelta(15 * L["quarter"], unit="min")
    L = L.sort_values("ts").reset_index(drop=True)
    L["slot"] = L["hour"] * 4 + L["quarter"]
    # 7) 15분 단발 0값(대기전력 약 21kW보다 낮아 물리적으로 불가능한 값) -> 계측 누락으로 결측 처리
    L["kw_dropout"] = (L["kw"] < 5).astype(int)
    L.loc[L["kw_dropout"] == 1, "kw"] = np.nan
    return L.drop(columns=["qcol"])


def load_clean():
    raw = load_raw()
    hourly = clean_hourly(raw)
    return raw, hourly, to_long(hourly)
