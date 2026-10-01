"""한 번에 실행: python run_all.py  (전처리 -> 학습 -> 추론 -> 분석 -> 결과 파일 생성)"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ.setdefault("PYTHONHASHSEED", "42")
os.environ.setdefault("OMP_NUM_THREADS", "4")
import sys
from src.pipeline import run_all

if __name__ == "__main__":
    # --reuse-cv : 모델 비교(백테스트) 결과 캐시 재사용(개발용). 기본은 전 과정 재실행
    run_all(reuse_cv="--reuse-cv" in sys.argv)
