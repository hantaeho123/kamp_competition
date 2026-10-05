"""6단계: 피크 유형별 저감방안 시뮬레이션(전력량 보존 부하 이동 선형계획) + 예측 연동 운영 규칙.

모형(하루 단위, 15분 슬롯 t=0..95)
  P_t        : 실측 15분 최대수요전력
  base       : 당일 0~6시 중앙값(연속공정·대기전력, 이동 불가)
  F_t        : 이동 가능 부하 = alpha * max(P_t - base, 0)   (alpha: 가동 시점을 바꿀 수 있는 설비 비중)
  x_{t,s}>=0 : 슬롯 t의 부하 중 슬롯 s로 옮기는 양 (허용된 (t,s) 쌍만)
  Q_s = P_s - (t=s에서 나간 양) + (s로 들어온 양)      -> 하루 총 전력량 보존
  min  z + eps * Σ |t-s| x_{t,s}   s.t.  Q_s <= z,  Σ_s x_{t,s} <= F_t
조치(허용 이동 쌍을 피크 유형에 맞춰 정함)
  조치A 설비 가동시점 분산 : 유형1(시작·재개 직후) 구간의 처음 2시간 부하를 그 직전 2시간으로 앞당김
                            (오전 8시 시작 전 6~8시, 점심 후 13시 재개 전 11~13시에 일부 설비를 먼저 가동)
  조치B 생산일정 이동      : 유형2(가동 중) 구간과 앞뒤 15분의 부하를 같은 날 17~22시로 옮김
                            (저녁에 발생한 구간은 그 구간 1시간 뒤~24시로)
  조치A+B                  : 두 조치 동시 적용
  상한(±2h)                : 06~22시 모든 부하를 ±2시간 안에서 자유 이동(가동시점 조정으로 얻을 수 있는 최대치)
"""
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from .config import BASIC_CHARGE_KRW_PER_KW, BILLING_MONTHS, tou_band, season_of, ENERGY_RATE

MEASURES = {"A": "조치A 설비 가동시점 분산(유형1 대상)", "B": "조치B 생산일정 저녁 이동(유형2 대상)",
            "AB": "조치A+B 동시 적용", "UB": "상한: ±2시간 자유 이동"}


def moves_for(measure, episodes, W=8):
    """하루의 피크 구간 목록(episodes: start_slot, end_slot, 유형)으로 허용 이동 쌍 (from, to) 생성."""
    pairs = set()
    if measure == "UB":
        for t in range(24, 88):
            for s in range(max(24, t - W), min(88, t + W + 1)):
                if s != t:
                    pairs.add((t, s))
        return sorted(pairs)
    for e in episodes:
        st, en, ty = int(e["start_slot"]), int(e["end_slot"]), int(e["유형"])
        if ty == 1 and measure in ("A", "AB"):
            for t in range(st, min(en, st + 7) + 1):
                for s in range(max(st - 8, 0), st):
                    pairs.add((t, s))
        if ty == 2 and measure in ("B", "AB"):
            dst = range(68, 88) if en < 64 else range(min(en + 5, 95), 96)
            for t in range(max(st - 1, 0), min(en + 1, 95) + 1):
                for s in dst:
                    if s != t:
                        pairs.add((t, s))
    return sorted(pairs)


def shave_day(P, alpha, pairs, eps=1e-3):
    P = np.asarray(P, float)
    if np.isnan(P).any():
        return P.copy()
    base = np.median(P[:24])
    F = alpha * np.clip(P - base, 0, None)
    pairs = [(t, s) for t, s in pairs if F[t] > 0]
    if not pairs:
        return P.copy()
    n = len(pairs)
    c = np.r_[eps * np.array([abs(t - s) for t, s in pairs], float), 1.0]     # 변수: x_0..x_{n-1}, z
    A = lil_matrix((96 + 96, n + 1))
    b = np.zeros(96 + 96)
    for j, (t, s) in enumerate(pairs):
        A[t, j] -= 1          # Q_s <= z  ->  -(나간 양) + (들어온 양) - z <= -P_s
        A[s, j] += 1
        A[96 + t, j] = 1      # Σ_s x_{t,s} <= F_t
    A[:96, n] = -1
    b[:96] = -P
    b[96:] = F
    res = linprog(c, A_ub=A.tocsr(), b_ub=b, bounds=[(0, None)] * (n + 1), method="highs")
    if not res.success:
        return P.copy()
    Q = P.copy()
    for j, (t, s) in enumerate(pairs):
        Q[t] -= res.x[j]
        Q[s] += res.x[j]
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


def simulate(X, E, measures=("A", "B", "AB", "UB"), alphas=(0.1, 0.2, 0.3), months=(7, 8, 9)):
    """원본 구간(기본 7~9월)의 실측 프로파일에 유형별 조치를 적용. 일별 결과 R, 구간별 결과 EP, 프로파일 반환."""
    d = X[X["month"].isin(months)].copy()
    ok = d.groupby("date")["kw"].transform(lambda v: v.notna().mean() >= 0.8)   # 결측 20% 이상인 날 제외
    d = d[ok]
    ep_by_day = {k: g.to_dict("records") for k, g in E.groupby("date")}
    rows, ep_rows, profiles = [], [], {}
    for date, g in d.groupby("date"):
        g = g.sort_values("slot")
        P = pd.Series(g["kw"].values).interpolate(limit_direction="both").values   # 단발 결측 보간
        m = int(g["month"].iloc[0])
        eps_ = ep_by_day.get(date, [])
        types = {int(e["유형"]) for e in eps_}
        base = {"date": date, "month": m, "orig_peak": np.nanmax(P), "orig_cost": energy_cost(P, m, g["slot"]),
                "has_type1": int(1 in types), "has_type2": int(2 in types),
                "restart_day": int(g["restart_day"].iloc[0]), "temp_max": g["temp_max"].iloc[0],
                "full_workday": int(g["full_workday"].iloc[0])}
        for ms in measures:
            pairs = moves_for(ms, eps_)
            for a in alphas:
                Q = shave_day(P, a, pairs)
                rows.append(dict(base, measure=ms, alpha=a, new_peak=np.nanmax(Q), new_cost=energy_cost(Q, m, g["slot"])))
                profiles[(date, ms, a)] = Q
                for e in eps_:
                    sl = slice(int(e["start_slot"]), int(e["end_slot"]) + 1)
                    ep_rows.append({"date": date, "유형": int(e["유형"]), "measure": ms, "alpha": a,
                                    "구간 최대 전": np.nanmax(P[sl]), "구간 최대 후": np.nanmax(Q[sl]),
                                    "180kW 이상 슬롯 전": int((P[sl] >= 180).sum()), "180kW 이상 슬롯 후": int((Q[sl] >= 180).sum())})
    return pd.DataFrame(rows), pd.DataFrame(ep_rows), profiles


def summarize(R, EP):
    """조치 x alpha 요약: 유형별 구간 최대 변화, 일 최대 변화, 기간 최대수요전력, 요금 환산."""
    out = []
    for (ms, a), g in R.groupby(["measure", "alpha"]):
        e = EP[(EP["measure"] == ms) & (EP["alpha"] == a)]
        mo = g.groupby("month").agg(orig=("orig_peak", "max"), new=("new_peak", "max"))
        pk = g[(g["has_type1"] + g["has_type2"]) > 0]
        row = {"조치": MEASURES[ms], "measure": ms, "alpha": a}
        for t in (1, 2):
            et = e[e["유형"] == t]
            row[f"유형{t} 구간 최대 평균 전(kW)"] = et["구간 최대 전"].mean()
            row[f"유형{t} 구간 최대 평균 후(kW)"] = et["구간 최대 후"].mean()
            row[f"유형{t} 180kW 이상 시간 감소%"] = 100 * (1 - et["180kW 이상 슬롯 후"].sum() / max(et["180kW 이상 슬롯 전"].sum(), 1))
        row.update({
            "피크 발생일 일최대 평균 감소(kW)": (pk["orig_peak"] - pk["new_peak"]).mean(),
            "피크 발생일 일최대 평균 감소(%)": 100 * ((pk["orig_peak"] - pk["new_peak"]) / pk["orig_peak"]).mean(),
            "기간 최대수요전력 전(kW)": mo["orig"].max(), "기간 최대수요전력 후(kW)": mo["new"].max(),
            "연간 기본요금 절감(원)": (mo["orig"].max() - mo["new"].max()) * BASIC_CHARGE_KRW_PER_KW * 12,
            "전력량요금 변화(원/기간)": (g["new_cost"] - g["orig_cost"]).sum()})
        out.append(row)
    return pd.DataFrame(out)
