"""전역 설정: 경로, 기간, 외부 기준값(요금), 난수 시드."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "okm_augumented_2021.csv"
OUT = ROOT / "outputs"
# 분석 단계별 결과 폴더(표 CSV와 그림 PNG를 단계별로 함께 저장)
S0 = OUT / "step0_preprocess_split"      # 0. 데이터 전처리 및 분할
S1 = OUT / "step1_forecast"              # 1. 전력 예측
S2 = OUT / "step2_error_analysis"        # 2. 예측오차 분석
S3 = OUT / "step3_peak_extraction"       # 3. 실제 피크 추출
S4 = OUT / "step4_peak_types"            # 4. 피크 두 유형 구분
S5 = OUT / "step5_peak_conditions"       # 5. 유형별 발생조건
S6 = OUT / "step6_mitigation"            # 6. 저감방안
PRED = OUT / "predictions"               # 시험 구간 예측 결과 파일
for _p in (S0, S1, S2, S3, S4, S5, S6, PRED):
    _p.mkdir(parents=True, exist_ok=True)

SEED = 42
SLOTS_PER_DAY = 96          # 15분 x 96 = 24시간
QUARTER_COLS = ["15분", "30분", "45분", "60분"]

# 최종 시험(Test) 구간: 가이드북 실습과 동일한 2021-09-01 ~ 09-14 (336시간 = 1,344개 15분 슬롯)
TEST_START = "2021-09-01"
# 롤링 원점 백테스트(모델 선택용) 주 단위 fold 시작일: 7~8월(증강 복사가 거의 없는 원본 구간)
CV_FOLD_STARTS = ["2021-07-05", "2021-07-12", "2021-07-19", "2021-07-26",
                  "2021-08-09", "2021-08-16", "2021-08-23", "2021-08-30"]
CV_FOLD_DAYS = 7

# 피크 위험 이벤트 정의: 15분 최대수요전력이 이 값 이상(전체 15분 슬롯의 상위 5%)
PEAK_EVENT_KW = 180.0

# ---- 외부 데이터 (출처: 한국전력공사 전기요금표 종합, 2023.05.16 시행) ----
# 데이터의 최대 15분 수요전력이 약 222kW로 계약전력 300kW 미만 -> 산업용전력(갑)Ⅱ(시간대별) 고압A 선택Ⅱ 적용 가정
# 기본요금은 '요금적용전력(kW)'에 부과. 요금적용전력 = 검침 당월 포함 직전 12개월 중 12·1·2·7·8·9월 및 당월의
# 최대수요전력 중 가장 큰 값(한전 기본공급약관, 최대수요전력계 설치 고객). 단가는 설정값이므로 계약종별에 맞게 변경 가능.
TARIFF_NAME = "산업용전력(갑)Ⅱ 고압A 선택Ⅱ"
BASIC_CHARGE_KRW_PER_KW = 7470
BILLING_MONTHS = [12, 1, 2, 7, 8, 9]
# 전력량요금(원/kWh): 계절별 x 시간대별
ENERGY_RATE = {
    "summer": {"off": 82.3, "mid": 108.1, "peak": 141.6},       # 6~8월
    "springfall": {"off": 82.3, "mid": 87.1, "peak": 106.3},   # 3~5월, 9~10월
    "winter": {"off": 89.7, "mid": 106.6, "peak": 136.0},      # 11~2월
}
# 시간대 구분(시작 시각 기준): 경부하 22~08시 공통
TOU_PEAK_HOURS = {"summer": [11, 13, 14, 15, 16, 17], "springfall": [11, 13, 14, 15, 16, 17],
                  "winter": [9, 10, 11, 16, 17, 18]}
TOU_OFF_HOURS = [22, 23, 0, 1, 2, 3, 4, 5, 6, 7]


def season_of(month: int) -> str:
    if month in (6, 7, 8):
        return "summer"
    if month in (3, 4, 5, 9, 10):
        return "springfall"
    return "winter"


def tou_band(month: int, hour: int) -> str:
    if hour in TOU_OFF_HOURS:
        return "off"
    if hour in TOU_PEAK_HOURS[season_of(month)]:
        return "peak"
    return "mid"
