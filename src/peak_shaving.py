"""피크전력 저감 시뮬레이션: 설비 가동 시점 조정(부하 이동) 선형계획.

모형(하루 단위, 15분 슬롯 t=0..95)
  P_t        : 실측 15분 최대수요전력
  base       : 당일 0~6시 중앙값(연속공정·대기전력, 이동 불가)
  F_t        : 이동 가능 부하 = alpha * max(P_t - base, 0)   (alpha: 가동 시점 조정이 가능한 설비 비중)
  x_{t,s}>=0 : 슬롯 t의 부하 중 슬롯 s로 옮기는 양 (s ∈ 허용 목적지)
  Q_s = P_s - Σ_s' x_{s,s'} + Σ_t x_{t,s}  (총 전력량 보존)
  min  z + eps * Σ |t-s| x_{t,s}   s.t.  Q_s <= z,  Σ_s x_{t,s} <= F_t
시나리오(운영 규칙 -> 허용 이동 범위)
  S1 순차 기동  : 기동구간(첫 생산 시각 ~ +2h)의 부하 일부를 첫 생산 1~2시간 전(경부하 시간대)로 앞당김
                  (예: 열처리로·컴프레서 예열/선기동을 06~08시에 분산)
  S2 점심 교대  : 점심 후 재가동(13시대) 부하 일부를 12시대로 이동(점심시간 2개 조 교대 운영)
  S3 주간->저녁 생산 이전: 주간(08~17시) 부하 일부를 같은 날 17~22시(중간부하 시간대)로 이동(생산일정 조정)
  S4 통합 최적  : 06~22시 안에서 ±2시간 이내 자유 이동(가동 시점 조정의 상한 효과)
"""
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from .config import BASIC_CHARGE_KRW_PER_KW, BILLING_MONTHS, tou_band, season_of, ENERGY_RATE


def _moves(scn, first_slot, W=8):
    """(from, to) 허용 쌍 목록."""
    pairs = []
    if first_slot is None or np.isnan(first_slot):
        return pairs
    f = int(first_slot)
    if scn == "S1":
        for t in range(f, min(f + 8, 96)):
            for s in range(max(f - 8, 24), f):
                pairs.append((t, s))
    if scn == "S2":
        for t in range(52, 56):
            for s in range(48, 52):
                pairs.append((t, s))
    if scn == "S3":
        for t in range(32, 68):
            for s in range(68, 88):
                pairs.append((t, s))
    if scn == "S4":
        for t in range(24, 88):
            for s in range(max(24, t - W), min(88, t + W + 1)):
                if s != t:
                    pairs.append((t, s))
    return pairs


def shave_day(P, alpha, scn, first_slot, eps=1e-3):
    P = np.asarray(P, float)
    if np.isnan(P).any():
        return P.copy()
    base = np.median(P[:24])
    F = alpha * np.clip(P - base, 0, None)
    pairs = [(t, s) for t, s in _moves(scn, first_slot) if F[t] > 0]
    if not pairs:
        return P.copy()
    n = len(pairs)
    # 변수: x_0..x_{n-1}, z
    c = np.r_[eps * np.array([abs(t - s) for t, s in pairs], float), 1.0]
    A = lil_matrix((96 + 96, n + 1))
    b = np.zeros(96 + 96)
    # Q_s <= z  ->  -Σout_s + Σin_s - z <= -P_s
    for j, (t, s) in enumerate(pairs):
        A[t, j] -= 1
        A[s, j] += 1
    A[:96, n] = -1
    b[:96] = -P
    # Σ_s x_{t,s} <= F_t
    for j, (t, s) in enumerate(pairs):
        A[96 + t, j] = 1
    b[96:] = F
    res = linprog(c, A_ub=A.tocsr(), b_ub=b, bounds=[(0, None)] * n + [(0, None)], method="highs")
    if not res.success:
        return P.copy()
    x = res.x[:n]
    Q = P.copy()
    for j, (t, s) in enumerate(pairs):
        Q[t] -= x[j]
        Q[s] += x[j]
    return Q


def fixed_evening_shift(P, alpha, src=(32, 68), dst=(68, 88)):
    """예측 기반 운영용 '고정 규칙'(실측 프로파일을 모르는 상태에서 적용 가능):
    주간(08~17시) 기저 초과부하의 alpha 비율을 같은 날 17~22시에 균등 배분(전력량 보존)."""
    P = np.asarray(P, float)
    if np.isnan(P).any():
        return P.copy()
    base = np.median(P[:24])
    Q = P.copy()
    take = alpha * np.clip(P[src[0]:src[1]] - base, 0, None)
    Q[src[0]:src[1]] -= take
    Q[dst[0]:dst[1]] += take.sum() / (dst[1] - dst[0])
    return Q


def planned_block_shift(P, F, delta, dmax_pred, src=(32, 68), dst=(68, 96)):
    """예측 기반 운영 규칙(실측을 모르는 상태에서 하루 전에 계획 가능):
    - 경보일에 주간(08~17시) 가동 설비 중 delta kW 상당의 블록(예: 1개 라인·보조설비)을 저녁(17~24시)으로 재배치
    - 줄이는 양은 예측 프로파일 F 기준으로 계획하고(실제 기저부하 아래로는 줄이지 않음),
      옮긴 전력량은 예측 프로파일상 여유(목표상한 C = 예측 일최대 - delta 와의 차이)에 비례해 저녁 슬롯에 배분
    - 계획을 실측 프로파일 P에 적용한 결과를 반환(전력량 보존)"""
    P, F = np.asarray(P, float), np.asarray(F, float)
    if np.isnan(P).any():
        return P.copy()
    base = np.median(P[:24])
    base_f = np.median(F[:24])
    Q = P.copy()
    s0, s1 = src
    plan = np.minimum(delta, np.clip(F[s0:s1] - base_f, 0, None))
    take = np.minimum(plan, np.clip(P[s0:s1] - base, 0, None))
    Q[s0:s1] -= take
    E = take.sum()
    C = dmax_pred - delta
    head = np.clip(C - F[dst[0]:dst[1]], 0, None)
    w = head / head.sum() if head.sum() > 0 else np.full(dst[1] - dst[0], 1 / (dst[1] - dst[0]))
    Q[dst[0]:dst[1]] += E * w
    return Q


def energy_cost(profile_kw, month, slots):
    kwh = np.asarray(profile_kw) * 0.25
    rates = np.array([ENERGY_RATE[season_of(month)][tou_band(month, s // 4)] for s in slots])
    return float(np.nansum(kwh * rates))


def simulate(X, scenarios=("S1", "S2", "S3", "S4"), alphas=(0.1, 0.2, 0.3), months=None):
    d = X.copy()
    ok = d.groupby("date")["kw"].transform(lambda v: v.notna().mean() >= 0.8)   # 결측 20% 이상인 날 제외
    d = d[ok]
    if months is not None:
        d = d[d["month"].isin(months)]
    rows, profiles = [], {}
    for date, g in d.groupby("date"):
        g = g.sort_values("slot")
        P = pd.Series(g["kw"].values).interpolate(limit_direction="both").values   # 단발 결측 보간
        fp = g["first_prod_hour"].iloc[0]
        first_slot = fp * 4 if pd.notna(fp) and g["full_workday"].iloc[0] == 1 else None
        m = int(g["month"].iloc[0])
        base_row = {"date": date, "month": m, "orig_peak": np.nanmax(P), "orig_cost": energy_cost(P, m, g["slot"])}
        for scn in scenarios:
            for a in alphas:
                Q = shave_day(P, a, scn, first_slot)
                r = dict(base_row, scenario=scn, alpha=a, new_peak=np.nanmax(Q), new_cost=energy_cost(Q, m, g["slot"]))
                rows.append(r)
                profiles[(date, scn, a)] = Q
    R = pd.DataFrame(rows)
    return R, profiles


def billing_summary(R, aug_size_by_date=None):
    """월별 최대수요전력 변화와 기본요금(요금적용전력) 절감 추정."""
    out = []
    for (scn, a), g in R.groupby(["scenario", "alpha"]):
        mo = g.groupby("month").agg(orig=("orig_peak", "max"), new=("new_peak", "max"))
        bill_o = mo.loc[mo.index.isin(BILLING_MONTHS + [mo.index.max()]), "orig"].max()
        bill_n = mo.loc[mo.index.isin(BILLING_MONTHS + [mo.index.max()]), "new"].max()
        work = g[g["orig_peak"] > 120]
        out.append({"scenario": scn, "alpha": a,
                    "가동일 일피크 평균 감소(kW)": (work["orig_peak"] - work["new_peak"]).mean(),
                    "가동일 일피크 평균 감소(%)": 100 * ((work["orig_peak"] - work["new_peak"]) / work["orig_peak"]).mean(),
                    "월최대피크 평균 감소(kW)": (mo["orig"] - mo["new"]).mean(),
                    "요금적용전력 전(kW)": bill_o, "요금적용전력 후(kW)": bill_n,
                    "연간 기본요금 절감(원)": (bill_o - bill_n) * BASIC_CHARGE_KRW_PER_KW * 12,
                    "전력량요금 변화(원/기간)": (g["new_cost"] - g["orig_cost"]).sum()})
    return pd.DataFrame(out)
