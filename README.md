# 제조 생산데이터 기반 전력사용량 예측 및 최대피크 위험조건 분석

제6회 K-인공지능 제조데이터 분석 경진대회, 과제 ⑤ (자원 최적화 AI 데이터셋)

## 한 줄 요약
생산계획(ERP)·달력·기상만으로 **하루 전에 다음 날 96개 15분 최대수요전력**을 예측하고,
피크 전용 예측(일 최대 앙상블 + 분위수 경보)과 **전력량 보존 선형계획 시뮬레이션**으로
생산일정·설비가동 시점 조정에 따른 피크 저감 효과와 기본요금 절감액을 산출합니다.

## 실행 방법
```bash
# 1) 환경 (Python 3.11)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 2) 전처리 -> 학습 -> 추론 -> 분석 -> 결과 생성 (10코어 CPU 기준 약 6~17분, 대부분 MLP 학습 시간 차이)
python run_all.py
# (개발용) 모델 비교 백테스트 캐시를 재사용해 뒷단만 다시 실행
python run_all.py --reuse-cv
```
난수 시드 42, 스레드 4개, 라이브러리 버전을 고정했습니다(`src/config.py`, `src/models.py`, `requirements.txt`).

## 핵심 결과
| 항목 | 값 |
|---|---|
| 시험(2021-09-01~14) 15분 예측 MAE / CV(RMSE) | 6.36 kW / 8.5% |
| 롤링 백테스트(7~8월 8주) MAE | 7.73 kW (Naive 19.88 kW) |
| 일 최대수요전력 예측 MAE(가동일, 시험) | 5.29 kW (MAPE 2.7%) |
| 80% 예측구간 포함률(컨포멀 보정, 시험) | 83.0% |
| 피크위험(180kW 이상) 경보 F1(시험) | 0.57 |
| 예측 연동 생산일정 조정 시 최대수요전력 | 204 → 189 kW |

## 폴더 구성
| 경로 | 내용 |
|---|---|
| `data/okm_augumented_2021.csv` | 학습용 데이터(KAMP 제공 원본) |
| `run_all.py` | 전 과정 자동 실행 진입점 |
| `src/config.py` | 경로·기간·시험구간·외부 요금 기준 설정 |
| `src/data.py` | 적재·품질 진단·정제(시간 손상, 전력 0 구간, 강수 누적값, 증강 복사일 탐지) |
| `src/features.py` | 하루 전/1시간 전 예측 시점별 피처(누수 방지 원칙 주석) |
| `src/models.py` | 베이스라인 2종, Ridge, RandomForest(가이드북), MLP, XGBoost, CatBoost, LightGBM |
| `src/experiment.py`, `src/metrics.py` | 롤링 원점 백테스트, 점·피크·이벤트(F1) 지표 |
| `src/peak_forecast.py` | 일 최대수요전력 예측(일 단위 모델 + 직전 가동일 규칙 앙상블) |
| `src/error_analysis.py` | 오차 집중 생산조건, 피크경보 FN/FP 집중 조건, 규칙 추출 |
| `src/peak_analysis.py` | 피크 발생 조건(발생률, SHAP 주효과·상호작용, 규칙) |
| `src/peak_shaving.py` | 부하 이동 선형계획(순차 기동/점심 교대/저녁 이전/±2h 최적) + 요금 환산 |
| `src/pipeline.py` | 단계별 실행·표/그림 저장 |
| `outputs/predictions/` | **시험 구간 예측 결과 파일** |
| `outputs/tables/`, `outputs/figures/` | 보고서용 표(CSV)·그림(PNG) |
| `outputs/summary.json` | 핵심 수치 요약 |

## 예측 과제 정의
- 예측 대상: 15분 단위 최대수요전력(원천 컬럼 `15분/30분/45분/60분`), 하루 96개
- 예측 시점: D-1일 24:00에 D일 전체(하루 전). 1시간 전 예측은 비교 실험으로 포함
- 시험 구간: **2021-09-01 ~ 2021-09-14** (가이드북 실습과 동일, 1,344개 15분 슬롯)
- 모델 선택: 2021-07-05 ~ 08-31 사이 주 단위 8개 fold 롤링 원점 백테스트(학습은 항상 fold 이전 데이터만)

## 시험 예측 결과 파일
| 파일 | 설명 |
|---|---|
| `test_predictions_15min.csv` | 15분 슬롯별 실측·예측·P10/P90·보정된 80% 구간·피크위험 경보 |
| `test_predictions_original_format.csv` | 원본과 같은 형식(날짜, 시간, 15분, 30분, 45분, 60분, 평균) |
| `test_daily_peak_predictions.csv` | 일 최대수요전력 예측(피크 앙상블 및 구성요소) |

## 외부 데이터
| 데이터 | 출처 | 활용 사유·방법 |
|---|---|---|
| 대한민국 법정공휴일 | Python `holidays` 패키지(공개 오픈소스, 공공 달력 기반) | 공휴일 가동 여부 반영 피처(`holiday`) |
| 전기요금표(산업용(갑)Ⅱ 고압A 선택Ⅱ 기본요금·시간대별 요금, 계절·시간대 구분) | 한국전력공사 전기요금표 종합(2023.05.16 시행), cyber.kepco.co.kr | 피크 저감량의 기본요금·전력량요금 환산(`src/config.py`에서 변경 가능) |

데이터 출처 표기: 중소벤처기업부, Korea AI Manufacturing Platform(KAMP), 자원 최적화 AI 데이터셋, KAIST(울산과학기술원, ㈜유피시앤에스), 2021.12.27., www.kamp-ai.kr
