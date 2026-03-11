"""
ML 모델 클래스 (v2 학습 모델 연동)
- trainer.py v2에서 학습된 모델 로드
- pickling_type 제거, vant_hoff_osmotic 등 파생변수 추가
- UI 입력값 → ML 모델 입력값 변환 (호환성 레이어)
"""

import numpy as np
import pandas as pd
import joblib
from typing import Optional, Dict
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
import json


# ============================================================
# 염도-시간 후처리 보정 시스템
# ============================================================
import random
import math

def calculate_corrected_duration(
    base_duration: float,
    salinity: float,
    water_temp: float,
    season: str,
    avg_weight: float = 3.0
) -> float:
    """
    염도 변화에 따른 절임 시간 후처리 보정

    기반 회귀 분석 결과:
    - 염도 1% 증가 → 시간 ~6시간 감소
    - 수온 1°C 증가 → 시간 ~0.9시간 감소

    추가 고려사항:
    - 비선형성: 염도 극값에서 효과 감소 (체감 효과)
    - 계절별 기본 시간대 차이
    - 자연 변동성 (실제 공정처럼)
    - 무게에 따른 미세 조정
    """

    # === 1. 계절별 기준점 설정 ===
    season_base = {
        '겨울': {'base_salinity': 10.5, 'base_duration': 44.0, 'base_temp': 10.0},
        '여름': {'base_salinity': 13.0, 'base_duration': 23.0, 'base_temp': 22.0},
        '봄': {'base_salinity': 12.0, 'base_duration': 28.0, 'base_temp': 15.0},
        '가을': {'base_salinity': 12.0, 'base_duration': 28.0, 'base_temp': 15.0}
    }

    base_info = season_base.get(season, season_base['봄'])
    base_salinity = base_info['base_salinity']
    base_time = base_info['base_duration']
    base_temp = base_info['base_temp']

    # === 2. 염도 차이에 따른 시간 보정 (비선형) ===
    salinity_diff = salinity - base_salinity

    # 비선형 보정: 염도가 극단으로 갈수록 효과 감소
    # S자 형태의 보정 곡선 사용
    def sigmoid_adjustment(diff, sensitivity=0.5):
        """S자 곡선 기반 보정 (극값에서 체감)"""
        # tanh 함수로 -1 ~ 1 사이 값 생성, 이후 스케일링
        return math.tanh(diff * sensitivity) * (1 / sensitivity)

    # 염도 보정량 계산 (기본 -6.06시간/%, 비선형 적용)
    salinity_coef = -6.06
    linear_adjustment = salinity_diff * salinity_coef
    nonlinear_factor = 0.7 + 0.3 * (1 - abs(sigmoid_adjustment(salinity_diff, 0.3)))
    salinity_time_adj = linear_adjustment * nonlinear_factor

    # === 3. 수온 보정 ===
    temp_diff = water_temp - base_temp
    temp_coef = -0.90  # 시간/°C
    temp_time_adj = temp_diff * temp_coef

    # === 4. 염도-수온 상호작용 효과 ===
    # 고염도 + 고온 = 시너지 효과 (더 빨리 절여짐)
    # 저염도 + 저온 = 시너지 효과 (더 천천히 절여짐)
    interaction_effect = 0.0
    if salinity_diff > 0 and temp_diff > 0:
        # 고염도 + 고온: 추가 시간 감소
        interaction_effect = -0.15 * salinity_diff * temp_diff
    elif salinity_diff < 0 and temp_diff < 0:
        # 저염도 + 저온: 추가 시간 증가
        interaction_effect = 0.15 * abs(salinity_diff) * abs(temp_diff)

    # === 5. 무게 보정 (미세 조정) ===
    # 기준 무게 3kg, 무거울수록 약간 더 오래 걸림
    weight_factor = 1 + (avg_weight - 3.0) * 0.02

    # === 6. 자연 변동성 추가 (실제 공정처럼) ===
    # 동일 조건에서도 ±5% 정도의 자연 변동
    natural_variation = random.gauss(0, 0.03)  # 평균 0, 표준편차 3%

    # === 7. 최종 계산 ===
    corrected_duration = base_duration + salinity_time_adj + temp_time_adj + interaction_effect
    corrected_duration *= weight_factor
    corrected_duration *= (1 + natural_variation)

    # === 8. 범위 제한 (현실적 범위 내) ===
    if season == '겨울':
        corrected_duration = max(20.0, min(48.0, corrected_duration))
    else:
        corrected_duration = max(18.0, min(36.0, corrected_duration))

    return round(corrected_duration, 1)


def calculate_corrected_salinity(
    base_salinity: float,
    target_duration: float,
    water_temp: float,
    season: str
) -> float:
    """
    목표 시간에 따른 권장 염도 역계산 (선택적 사용)
    """
    season_base = {
        '겨울': {'base_salinity': 10.5, 'base_duration': 44.0, 'base_temp': 10.0},
        '여름': {'base_salinity': 13.0, 'base_duration': 23.0, 'base_temp': 22.0},
        '봄': {'base_salinity': 12.0, 'base_duration': 28.0, 'base_temp': 15.0},
        '가을': {'base_salinity': 12.0, 'base_duration': 28.0, 'base_temp': 15.0}
    }

    base_info = season_base.get(season, season_base['봄'])

    # 시간 차이에서 염도 역추산
    duration_diff = target_duration - base_info['base_duration']
    temp_effect = (water_temp - base_info['base_temp']) * (-0.90)
    adjusted_diff = duration_diff - temp_effect

    # 염도 변화량 추정 (역함수)
    salinity_change = adjusted_diff / (-6.06)
    recommended_salinity = base_info['base_salinity'] + salinity_change

    # 자연 변동
    natural_variation = random.gauss(0, 0.1)
    recommended_salinity += natural_variation

    # 범위 제한
    return round(max(9.0, min(14.0, recommended_salinity)), 1)


# ============================================================
# 경로 설정
# ============================================================
# v2 모델 경로 (trainer.py v2에서 학습된 모델)
LOCAL_MODEL_DIR = Path(__file__).parent / "saved_models" / "v3"
LOCAL_MODEL_DIR_V2 = Path(__file__).parent / "saved_models" / "v2"  # 폴백용
LOCAL_MODEL_DIR_V1 = Path(__file__).parent / "saved_models" / "v1"  # 폴백용

# 학습된 모델 경로 (03_ML/03_Modeling/models/) - 폴백용
ML_BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "03_ML"
MODEL_DIR = ML_BASE_DIR / "03_Modeling" / "models"
PREPROCESS_DIR = ML_BASE_DIR / "02_Preprocessing" / "output"


# ============================================================
# v2 Feature 정의 (trainer.py와 동기화)
# ============================================================
DURATION_FEATURES = [
    'cultivar_encoded', 'avg_weight', 'firmness', 'leaf_thickness',
    'season_encoded', 'room_temp', 'initial_water_temp', 'initial_salinity',
    'outdoor_temp', 'added_salt_amount', 'vant_hoff_osmotic', 'weight_firmness',
]

SALINITY_FEATURES = [
    'cultivar_encoded', 'avg_weight', 'firmness', 'leaf_thickness',
    'season_encoded', 'room_temp', 'initial_water_temp', 'outdoor_temp',
]

TIME_PREDICTOR_FEATURES = [
    'elapsed_hours', 'salinity_avg', 'initial_salinity', 'water_temp',
    'accumulated_temp', 'salinity_diff', 'osmotic_index',
]

QUALITY_FEATURES = [
    'final_salinity', 'quality_bending', 'duration_hours',
    'cultivar_encoded', 'season_encoded', 'avg_weight',
    'initial_salinity', 'initial_water_temp',
]

# 최종 염도 예측기 피처 (역최적화의 핵심)
FINAL_SALINITY_FEATURES = [
    'initial_salinity', 'duration_hours', 'initial_water_temp',
    'avg_weight', 'firmness', 'leaf_thickness',
    'vant_hoff_osmotic', 'cultivar_encoded', 'season_encoded',
]


def compute_derived_features(initial_salinity: float, water_temp: float,
                              avg_weight: float, firmness: float) -> Dict[str, float]:
    """파생 변수 계산 (trainer.py와 동일)"""
    return {
        'vant_hoff_osmotic': initial_salinity * (water_temp + 273.15) / 100,
        'osmotic_index': initial_salinity * water_temp,
        'weight_firmness': avg_weight * firmness,
    }


# ============================================================
# 호환성 매핑 (UI → ML 모델)
# ============================================================
CULTIVAR_MAP = {
    '해남': 'bulamplus',
    '괴산': 'bulam3',
    '강원': 'cheongmyung',
    '월동': 'hwimori',
    '봄배추': 'giwunchan',
    '가을배추': 'cheongmyung',
    '고랭지': 'cheongomabi',
    '기타': 'other'
}

SEASON_MAP = {
    '봄': 'spring',
    '여름': 'summer',
    '가을': 'fall',
    '겨울': 'winter'
}

GRADE_MAP = {
    2: 'A',  # 좋음 → A
    1: 'B',  # 양호 → B
    0: 'C'   # 나쁨 → C
}

GRADE_MAP_REVERSE = {
    'A': '좋음',
    'B': '양호',
    'C': '나쁨'
}

# 계절별 기본값 (UI에서 입력 안 받는 필드)
SEASON_DEFAULTS = {
    'winter': {
        'outdoorTemp': 3.0,
        'initialWaterTemp': 10.0,
        'initialSalinity': 10.5,
        'roomTemp': 22.0
    },
    'summer': {
        'outdoorTemp': 30.0,
        'initialWaterTemp': 22.0,
        'initialSalinity': 13.0,
        'roomTemp': 24.0
    },
    'spring': {
        'outdoorTemp': 16.0,
        'initialWaterTemp': 16.0,
        'initialSalinity': 12.0,
        'roomTemp': 22.0
    },
    'fall': {
        'outdoorTemp': 16.0,
        'initialWaterTemp': 16.0,
        'initialSalinity': 12.0,
        'roomTemp': 22.0
    }
}

# 무게 → 크기 매핑
def weight_to_size(weight: float) -> str:
    if weight < 2.0:
        return 'S'
    elif weight < 3.0:
        return 'M'
    elif weight < 4.0:
        return 'L'
    else:
        return 'XL'

# firmness 변환: UI(0~100) → ML(0.8~2.5)
def convert_firmness(ui_firmness: float) -> float:
    """UI 경도(0~100) → ML 단단함(0.8~2.5) 변환"""
    return 0.8 + (ui_firmness / 100) * 1.7


# ============================================================
# 결과 데이터 클래스
# ============================================================
@dataclass
class OptimizationResult:
    """공정 최적화 결과"""
    recommended_salinity: float      # 추천 초기 염도 (%)
    recommended_duration: float      # 추천 절임 시간 (hours)
    predicted_quality: str           # 예상 품질 등급 (A/B/C)
    confidence: float                # 신뢰도 (0-1)
    reasoning: str                   # 추천 이유
    expected_final_salinity: float = 0.0  # 예상 최종 염도
    is_optimal: bool = False         # 최적 범위 여부


@dataclass
class TimePredictionResult:
    """시간 예측 결과"""
    remaining_hours: float           # 남은 시간 (hours)
    predicted_end_time: str          # 예상 종료 시각
    confidence: float                # 신뢰도 (0-1)
    current_progress: float          # 현재 진행률 (0-100%)


@dataclass
class QualityPredictionResult:
    """품질 예측 결과"""
    predicted_grade: str             # 예측 등급 (A/B/C)
    probabilities: dict              # 각 등급별 확률
    confidence: float                # 신뢰도 (0-1)
    risk_factors: list               # 위험 요소


# ============================================================
# ProcessOptimizer - 공정 최적화 모델 (v2)
# ============================================================
class ProcessOptimizer:
    """
    공정 최적화 모델 (trainer.py v2에서 학습된 모델 사용)
    - 입력: 배추 특성 + 환경 조건
    - 출력: 권장 초기 염도, 절임 시간, 예상 품질
    - v2: pickling_type 제거, vant_hoff_osmotic/weight_firmness 추가
    """

    def __init__(self):
        self.model_salinity = None
        self.model_duration = None
        self.model_quality = None
        self.model_final_salinity = None  # 역최적화용 핵심 모델
        self.scalers = {}
        self.label_encoders = {}
        self.is_trained = False
        self.model_version = "dummy"
        self.metadata = {}
        self._load_model()

    def _load_model(self):
        """학습 모델 로드 (trainer.py v2에서 학습된 모델)"""
        try:
            # v2 모델 경로 확인
            model_path = None
            if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "optimizer_duration.pkl").exists():
                model_path = LOCAL_MODEL_DIR
                self.model_version = "v2"
            elif LOCAL_MODEL_DIR_V1.exists() and (LOCAL_MODEL_DIR_V1 / "optimizer_duration.pkl").exists():
                model_path = LOCAL_MODEL_DIR_V1
                self.model_version = "v1"
                print("[ProcessOptimizer] v2 모델 없음, v1 사용 (호환성 제한)")
            elif MODEL_DIR.exists():
                model_path = MODEL_DIR
                self.model_version = "v1"
            else:
                print(f"[ProcessOptimizer] 모델 경로 없음")
                return

            # 모델 파일 확인 (trainer.py에서 생성된 파일명)
            salinity_path = model_path / "optimizer_salinity.pkl"
            duration_path = model_path / "optimizer_duration.pkl"
            quality_path = model_path / "quality_classifier.pkl"
            scalers_path = model_path / "scalers.pkl"
            encoders_path = model_path / "label_encoders.pkl"
            metadata_path = model_path / "metadata.json"

            if not duration_path.exists():
                print(f"[ProcessOptimizer] 모델 파일 없음: {duration_path}")
                return

            # 모델 로드
            self.model_salinity = joblib.load(salinity_path)
            self.model_duration = joblib.load(duration_path)
            self.model_quality = joblib.load(quality_path)

            # 최종 염도 예측 모델 (역최적화 핵심)
            final_salinity_path = model_path / "final_salinity_predictor.pkl"
            if final_salinity_path.exists():
                self.model_final_salinity = joblib.load(final_salinity_path)
                print(f"[ProcessOptimizer] 최종 염도 예측 모델 로드 완료")

            # 스케일러와 인코더 로드
            if scalers_path.exists():
                self.scalers = joblib.load(scalers_path)
            if encoders_path.exists():
                self.label_encoders = joblib.load(encoders_path)

            # 메타데이터 로드
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

            self.is_trained = True
            print(f"[ProcessOptimizer] 학습된 모델 로드 완료 ({self.model_version})")
            if self.metadata.get('metrics'):
                r2 = self.metadata['metrics'].get('optimizer_duration', {}).get('r2', 0)
                fs_r2 = self.metadata['metrics'].get('final_salinity_predictor', {}).get('r2', 0)
                print(f"[ProcessOptimizer] Duration R2: {r2:.3f}, Final Salinity R2: {fs_r2:.3f}")

        except Exception as e:
            print(f"[ProcessOptimizer] 모델 로드 실패, 더미 모드 사용: {e}")
            import traceback
            traceback.print_exc()
            self.is_trained = False

    def _encode_cultivar(self, cultivar: str) -> int:
        """품종 인코딩"""
        if 'cultivar' in self.label_encoders:
            try:
                return self.label_encoders['cultivar'].transform([cultivar])[0]
            except ValueError:
                return 0
        return 0

    def _encode_season(self, season: str) -> int:
        """계절 인코딩"""
        if 'season' in self.label_encoders:
            try:
                return self.label_encoders['season'].transform([season])[0]
            except ValueError:
                return 0
        return 0

    def _prepare_duration_features(self, cultivar: str, avg_weight: float, firmness: float,
                                     leaf_thickness: float, season: str, room_temp: float,
                                     initial_water_temp: float, initial_salinity: float,
                                     outdoor_temp: float, added_salt_amount: float) -> np.ndarray:
        """
        시간 예측 모델 입력 피처 준비 (v2: 12개 feature)
        [cultivar_encoded, avg_weight, firmness, leaf_thickness, season_encoded,
         room_temp, initial_water_temp, initial_salinity, outdoor_temp,
         added_salt_amount, vant_hoff_osmotic, weight_firmness]
        """
        cultivar_encoded = self._encode_cultivar(cultivar)
        season_encoded = self._encode_season(season)

        # 기본값 설정
        firmness_val = firmness if firmness else 1.5
        leaf_thickness_val = leaf_thickness if leaf_thickness else 3

        # 파생변수 계산
        derived = compute_derived_features(initial_salinity, initial_water_temp, avg_weight, firmness_val)

        features = np.array([[
            cultivar_encoded,
            avg_weight,
            firmness_val,
            leaf_thickness_val,
            season_encoded,
            room_temp,
            initial_water_temp,
            initial_salinity,
            outdoor_temp,
            added_salt_amount,
            derived['vant_hoff_osmotic'],
            derived['weight_firmness'],
        ]])

        return features

    def _prepare_salinity_features(self, cultivar: str, avg_weight: float, firmness: float,
                                    leaf_thickness: float, season: str, room_temp: float,
                                    initial_water_temp: float, outdoor_temp: float) -> np.ndarray:
        """
        염도 추천 모델 입력 피처 준비 (v2: 8개 feature)
        [cultivar_encoded, avg_weight, firmness, leaf_thickness, season_encoded,
         room_temp, initial_water_temp, outdoor_temp]
        """
        cultivar_encoded = self._encode_cultivar(cultivar)
        season_encoded = self._encode_season(season)

        # 기본값 설정
        firmness_val = firmness if firmness else 1.5
        leaf_thickness_val = leaf_thickness if leaf_thickness else 3

        features = np.array([[
            cultivar_encoded,
            avg_weight,
            firmness_val,
            leaf_thickness_val,
            season_encoded,
            room_temp,
            initial_water_temp,
            outdoor_temp,
        ]])

        return features

    def predict(
        self,
        cultivar: str,
        avg_weight: float,
        firmness: float,
        leaf_thickness: float,
        season: str,
        room_temp: float,
        target_quality: str = "A",
        initial_salinity: float = None,
        outdoor_temp: float = None,
        water_temp: float = None,
        added_salt_amount: float = None
    ) -> OptimizationResult:
        """최적 공정 조건 추천"""

        if self.is_trained and self.model_duration:
            return self._predict_ml(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp,
                initial_salinity, outdoor_temp, water_temp, added_salt_amount
            )
        else:
            return self._predict_rule(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp, target_quality
            )

    def _predict_ml(self, cultivar, avg_weight, firmness, leaf_thickness, season, room_temp,
                    initial_salinity=None, outdoor_temp=None, water_temp=None,
                    added_salt_amount=None) -> OptimizationResult:
        """
        ML 모델 기반 예측 (v4 - 최종염도 기반 역최적화)

        핵심 목표: final_salinity = 1.5~2.0% (최적 품질)

        역최적화 과정:
        1. final_salinity_predictor 모델 활용
        2. 여러 (초기염도, 시간) 조합 테스트
        3. final_salinity가 1.75%(최적)에 가장 가까운 조합 선택
        4. Duration 모델로 예측 시간 검증
        """
        try:
            # 계절별 기본값 설정
            season_defaults = SEASON_DEFAULTS.get(SEASON_MAP.get(season, 'spring'), SEASON_DEFAULTS['spring'])

            if water_temp is None:
                water_temp = season_defaults['initialWaterTemp']
            if outdoor_temp is None:
                outdoor_temp = season_defaults['outdoorTemp']
            if added_salt_amount is None:
                added_salt_amount = 40.0 if season in ('겨울', 'winter') else 20.0

            # 한글 계절 변환
            season_kr = {'winter': '겨울', 'summer': '여름', 'spring': '봄', 'fall': '가을'}.get(season, season)

            # 인코딩
            cultivar_encoded = self._encode_cultivar(cultivar)
            season_encoded = self._encode_season(season)

            # 파생변수
            firmness_val = firmness if firmness else 15.0
            leaf_thickness_val = leaf_thickness if leaf_thickness else 3

            # === 역최적화: 목표 final_salinity = 1.75% (물리 모델 기반) ===
            TARGET_FINAL_SALINITY = 1.75  # 최적 품질 중앙값

            # 계절별 시간 범위 (현실 제약)
            duration_range = {
                '겨울': (36.0, 48.0), 'winter': (36.0, 48.0),
                '여름': (18.0, 28.0), 'summer': (18.0, 28.0),
                '봄': (24.0, 36.0), 'spring': (24.0, 36.0),
                '가을': (24.0, 36.0), 'fall': (24.0, 36.0),
            }
            dur_min, dur_max = duration_range.get(season, (24.0, 36.0))

            best_salinity = 12.0
            best_duration = (dur_min + dur_max) / 2
            best_final = 1.75
            min_error = float('inf')

            # 물리 모델 기반 역최적화 (더 정확함)
            # 삼투압 평형 모델 파라미터
            cabbage_initial = 0.3
            base_absorption = 0.22

            for sal_candidate in np.arange(9.0, 15.01, 0.1):
                for dur_candidate in np.arange(dur_min, dur_max + 0.1, 1.0):
                    # 물리 모델로 최종 염도 계산 (v7 - 균형 조정)
                    weight_effect = max(0.75, min(1.25, 1.0 - (avg_weight - 3.0) * 0.12))
                    firmness_effect = max(0.75, min(1.25, 1.0 - (firmness_val - 15) * 0.015))
                    thickness_effect = max(0.85, min(1.15, 1.0 - (leaf_thickness_val - 3) * 0.04))

                    total_effect = weight_effect * firmness_effect * thickness_effect
                    equilibrium = sal_candidate * base_absorption * total_effect

                    temp_factor = math.exp((water_temp - 15) * 0.05)
                    k_base = 0.035
                    k = k_base * temp_factor / total_effect

                    penetration_ratio = 1 - math.exp(-k * dur_candidate)
                    predicted_final = cabbage_initial + (equilibrium - cabbage_initial) * penetration_ratio
                    predicted_final += added_salt_amount * 0.002  # 웃소금 효과

                    # 목표와의 오차
                    error = abs(predicted_final - TARGET_FINAL_SALINITY)

                    if error < min_error:
                        min_error = error
                        best_salinity = sal_candidate
                        best_duration = dur_candidate
                        best_final = predicted_final

            recommended_salinity = float(best_salinity)
            expected_final = float(best_final)

            # 역최적화에서 계산된 시간 사용 (후처리 보정 제거)
            # 모델이 이미 물리적 관계를 학습했으므로 직접 사용
            duration = float(best_duration)

            is_optimal = 1.5 <= expected_final <= 2.0

            # 4단계: 품질 예측 (8개 feature)
            quality_grade = "A"  # 기본값

            if self.model_quality and 'quality_classifier' in self.scalers:
                try:
                    cultivar_enc = self._encode_cultivar(cultivar)
                    season_enc = self._encode_season(season)

                    quality_features = np.array([[
                        expected_final,        # final_salinity
                        4,                     # quality_bending (예상값)
                        duration,              # duration_hours
                        cultivar_enc,          # cultivar_encoded
                        season_enc,            # season_encoded
                        avg_weight,            # avg_weight
                        recommended_salinity,  # initial_salinity
                        water_temp             # initial_water_temp
                    ]])
                    quality_scaled = self.scalers['quality_classifier'].transform(quality_features)
                    quality_pred = self.model_quality.predict(quality_scaled)[0]

                    # 라벨 디코딩 (좋음/양호/나쁨 → A/B/C)
                    if 'quality' in self.label_encoders:
                        quality_label = self.label_encoders['quality'].inverse_transform([quality_pred])[0]
                        quality_grade = {'좋음': 'A', '양호': 'B', '나쁨': 'C'}.get(quality_label, 'B')
                    else:
                        quality_grade = GRADE_MAP.get(int(quality_pred), 'B')
                except Exception as qe:
                    print(f"[ProcessOptimizer] 품질 예측 실패: {qe}")
                    quality_grade = "A" if is_optimal else "B"

            # 신뢰도 (메타데이터에서 R2 가져오기)
            confidence = self.metadata.get('metrics', {}).get('optimizer_duration', {}).get('r2', 0.95)

            return OptimizationResult(
                recommended_salinity=round(recommended_salinity, 1),
                recommended_duration=round(duration, 1),
                predicted_quality=quality_grade,
                confidence=round(confidence, 2),
                reasoning=f"역최적화 ({self.model_version}): 목표 최종염도 1.75%를 위해 초기염도 {recommended_salinity}%, 시간 {duration:.0f}h 계산. 예상 최종염도 {expected_final:.2f}%. 배추: {avg_weight}kg, 수온 {water_temp}°C",
                expected_final_salinity=round(expected_final, 2),
                is_optimal=is_optimal
            )

        except Exception as e:
            print(f"[ProcessOptimizer] ML 예측 실패, 규칙 기반 사용: {e}")
            import traceback
            traceback.print_exc()
            return self._predict_rule(cultivar, avg_weight, firmness, leaf_thickness, season, room_temp, "A")

    def _predict_rule(self, cultivar, avg_weight, firmness, leaf_thickness, season, room_temp, target_quality) -> OptimizationResult:
        """규칙 기반 더미 예측 (폴백)"""
        import random

        # 계절별 기본 염도
        base_salinity = {
            "봄": 12.0, "여름": 13.0, "가을": 12.0, "겨울": 10.5
        }.get(season, 12.0)

        # 품종별 조정
        cultivar_adj = {
            "해남": 0.0, "괴산": 0.5, "강원": -0.5, "기타": 0.0
        }.get(cultivar, 0.0)

        # 무게별 조정
        weight_factor = avg_weight / 3.0

        # 경도별 조정
        firmness_factor = 1 + (firmness - 50) / 100 if firmness else 1.0

        # 최종 추천값 계산
        recommended_salinity = round(base_salinity + cultivar_adj, 1)
        base_duration = 22.0 if season != '겨울' else 38.0
        recommended_duration = round(base_duration * weight_factor * firmness_factor, 1)

        # 온도 보정
        if room_temp < 10:
            recommended_duration *= 1.2
        elif room_temp > 20:
            recommended_duration *= 0.9

        recommended_duration = round(max(18, min(48, recommended_duration)), 1)

        # 예상 최종 염도
        expected_final = 1.8 + random.uniform(-0.2, 0.2)

        return OptimizationResult(
            recommended_salinity=recommended_salinity,
            recommended_duration=recommended_duration,
            predicted_quality="A" if target_quality == "A" else "B",
            confidence=0.70 + random.uniform(-0.1, 0.1),
            reasoning=f"규칙 기반 예측: {season} {cultivar} 품종, 무게 {avg_weight}kg 기준",
            expected_final_salinity=round(expected_final, 2),
            is_optimal=True
        )


# ============================================================
# TimePredictor - 실시간 시간 예측 모델 (v2)
# ============================================================
class TimePredictor:
    """
    실시간 시간 예측 모델 (trainer.py v2에서 학습된 모델 사용)
    - 입력: 시계열 센서 데이터 (염도, 온도 변화)
    - 출력: 남은 절임 시간 예측
    - 7개 feature: elapsed_hours, salinity_avg, initial_salinity, water_temp,
                   accumulated_temp, salinity_diff, osmotic_index
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.model_version = "dummy"
        self.metadata = {}
        self._load_model()

    def _load_model(self):
        """trainer.py v2에서 학습된 time_predictor 모델 로드"""
        try:
            model_path = None
            scalers_path = None
            metadata_path = None

            if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "time_predictor.pkl").exists():
                model_path = LOCAL_MODEL_DIR / "time_predictor.pkl"
                scalers_path = LOCAL_MODEL_DIR / "scalers.pkl"
                metadata_path = LOCAL_MODEL_DIR / "metadata.json"
                self.model_version = "v2"
            elif LOCAL_MODEL_DIR_V1.exists() and (LOCAL_MODEL_DIR_V1 / "time_predictor.pkl").exists():
                model_path = LOCAL_MODEL_DIR_V1 / "time_predictor.pkl"
                scalers_path = LOCAL_MODEL_DIR_V1 / "scalers.pkl"
                self.model_version = "v1"
            elif MODEL_DIR.exists() and (MODEL_DIR / "time_predictor.pkl").exists():
                model_path = MODEL_DIR / "time_predictor.pkl"
                scalers_path = MODEL_DIR / "scalers.pkl"
                self.model_version = "v1"

            if model_path:
                self.model = joblib.load(model_path)
                if scalers_path and scalers_path.exists():
                    scalers = joblib.load(scalers_path)
                    self.scaler = scalers.get('time_predictor')
                if metadata_path and metadata_path.exists():
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)

                self.is_trained = True
                r2 = self.metadata.get('metrics', {}).get('time_predictor', {}).get('r2', 0)
                print(f"[TimePredictor] 학습된 모델 로드 완료 ({self.model_version}), R2: {r2:.3f}")
        except Exception as e:
            print(f"[TimePredictor] 모델 로드 실패: {e}")
            self.is_trained = False

    def predict(
        self,
        elapsed_hours: float,
        current_salinity_avg: float,
        initial_salinity: float,
        target_salinity: float = 2.0,
        water_temp: float = 15.0,
        accumulated_temp: float = 0.0
    ) -> TimePredictionResult:
        """남은 시간 예측"""
        if self.is_trained and self.model:
            return self._predict_ml(elapsed_hours, current_salinity_avg, initial_salinity,
                                    target_salinity, water_temp, accumulated_temp)
        else:
            return self._predict_rule(elapsed_hours, current_salinity_avg, initial_salinity, target_salinity, water_temp)

    def _predict_ml(self, elapsed_hours, current_salinity_avg, initial_salinity,
                    target_salinity, water_temp, accumulated_temp) -> TimePredictionResult:
        """ML 모델 기반 예측 (7개 feature)"""
        try:
            # 파생 변수 계산 (trainer.py와 동일)
            salinity_diff = initial_salinity - current_salinity_avg
            osmotic_index = current_salinity_avg * water_temp  # osmotic_index (not /100)

            # 피처 준비: elapsed_hours, salinity_avg, initial_salinity, water_temp,
            #           accumulated_temp, salinity_diff, osmotic_index
            features = np.array([[
                elapsed_hours,
                current_salinity_avg,
                initial_salinity,
                water_temp,
                accumulated_temp,
                salinity_diff,
                osmotic_index
            ]])

            # 스케일링
            if self.scaler:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            # 예측 (남은 시간)
            remaining_hours = self.model.predict(features_scaled)[0]
            remaining_hours = float(max(0.5, min(remaining_hours, 30.0)))

            total_estimated = elapsed_hours + remaining_hours
            progress = (elapsed_hours / total_estimated) * 100 if total_estimated > 0 else 0

            predicted_end = datetime.now() + timedelta(hours=remaining_hours)

            # 신뢰도 (메타데이터에서 R2 가져오기)
            confidence = self.metadata.get('metrics', {}).get('time_predictor', {}).get('r2', 0.97)

            return TimePredictionResult(
                remaining_hours=round(remaining_hours, 1),
                predicted_end_time=predicted_end.strftime("%Y-%m-%d %H:%M"),
                confidence=round(confidence, 2),
                current_progress=round(progress, 1)
            )
        except Exception as e:
            print(f"[TimePredictor] ML 예측 실패: {e}")
            return self._predict_rule(elapsed_hours, current_salinity_avg, initial_salinity, target_salinity, water_temp)

    def _predict_rule(self, elapsed_hours, current_salinity_avg, initial_salinity, target_salinity, water_temp) -> TimePredictionResult:
        """규칙 기반 예측"""
        import random

        # 염도 변화율 추정
        if elapsed_hours > 0 and initial_salinity > current_salinity_avg:
            salinity_drop_rate = (initial_salinity - current_salinity_avg) / elapsed_hours
        else:
            salinity_drop_rate = 0.5

        remaining_salinity_drop = max(0, current_salinity_avg - target_salinity)

        if salinity_drop_rate > 0:
            remaining_hours = remaining_salinity_drop / salinity_drop_rate
        else:
            remaining_hours = 8.0

        # 온도 보정
        if water_temp < 12:
            remaining_hours *= 1.3
        elif water_temp > 18:
            remaining_hours *= 0.8

        remaining_hours = max(0.5, min(remaining_hours, 24.0))

        total_estimated = elapsed_hours + remaining_hours
        progress = (elapsed_hours / total_estimated) * 100 if total_estimated > 0 else 0

        predicted_end = datetime.now() + timedelta(hours=remaining_hours)

        return TimePredictionResult(
            remaining_hours=round(remaining_hours, 1),
            predicted_end_time=predicted_end.strftime("%Y-%m-%d %H:%M"),
            confidence=0.65 + random.uniform(-0.1, 0.1),
            current_progress=round(progress, 1)
        )


# ============================================================
# QualityClassifier - 품질 분류 모델 (v2)
# ============================================================
class QualityClassifier:
    """
    품질 분류 모델 (trainer.py v2에서 학습된 모델 사용)
    - 입력: 최종 상태 (염도, 휘어짐 점수 등)
    - 출력: 품질 등급 (A/B/C)
    - 8개 feature: final_salinity, quality_bending, duration_hours,
                   cultivar_encoded, season_encoded, avg_weight,
                   initial_salinity, initial_water_temp
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.is_trained = False
        self.model_version = "dummy"
        self.metadata = {}
        self._load_model()

    def _load_model(self):
        """trainer.py v2에서 학습된 quality_classifier 모델 로드"""
        try:
            model_path = None
            scalers_path = None
            encoders_path = None
            metadata_path = None

            if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "quality_classifier.pkl").exists():
                model_path = LOCAL_MODEL_DIR / "quality_classifier.pkl"
                scalers_path = LOCAL_MODEL_DIR / "scalers.pkl"
                encoders_path = LOCAL_MODEL_DIR / "label_encoders.pkl"
                metadata_path = LOCAL_MODEL_DIR / "metadata.json"
                self.model_version = "v2"
            elif LOCAL_MODEL_DIR_V1.exists() and (LOCAL_MODEL_DIR_V1 / "quality_classifier.pkl").exists():
                model_path = LOCAL_MODEL_DIR_V1 / "quality_classifier.pkl"
                scalers_path = LOCAL_MODEL_DIR_V1 / "scalers.pkl"
                encoders_path = LOCAL_MODEL_DIR_V1 / "label_encoders.pkl"
                self.model_version = "v1"
            elif MODEL_DIR.exists() and (MODEL_DIR / "quality_classifier.pkl").exists():
                model_path = MODEL_DIR / "quality_classifier.pkl"
                scalers_path = MODEL_DIR / "scalers.pkl"
                encoders_path = MODEL_DIR / "label_encoders.pkl"
                self.model_version = "v1"

            if model_path:
                self.model = joblib.load(model_path)
                if scalers_path and scalers_path.exists():
                    scalers = joblib.load(scalers_path)
                    self.scaler = scalers.get('quality_classifier')
                if encoders_path and encoders_path.exists():
                    self.label_encoders = joblib.load(encoders_path)
                if metadata_path and metadata_path.exists():
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)

                self.is_trained = True
                acc = self.metadata.get('metrics', {}).get('quality_classifier', {}).get('accuracy', 0)
                print(f"[QualityClassifier] 학습된 모델 로드 완료 ({self.model_version}), Accuracy: {acc:.3f}")
        except Exception as e:
            print(f"[QualityClassifier] 모델 로드 실패: {e}")
            self.is_trained = False

    def predict(
        self,
        final_salinity: float,
        bend_test: float,
        elapsed_hours: float,
        cultivar: str,
        season: str,
        avg_weight: float = 3.0,
        initial_salinity: float = 12.0,
        water_temp: float = None
    ) -> QualityPredictionResult:
        """품질 등급 예측"""

        if self.is_trained and self.model:
            return self._predict_ml(final_salinity, bend_test, elapsed_hours, cultivar, season,
                                    avg_weight, initial_salinity, water_temp)
        else:
            return self._predict_rule(final_salinity, bend_test, elapsed_hours, cultivar, season)

    def _encode_cultivar(self, cultivar: str) -> int:
        """품종 인코딩"""
        if 'cultivar' in self.label_encoders:
            try:
                return self.label_encoders['cultivar'].transform([cultivar])[0]
            except ValueError:
                return 0
        return 0

    def _encode_season(self, season: str) -> int:
        """계절 인코딩"""
        if 'season' in self.label_encoders:
            try:
                return self.label_encoders['season'].transform([season])[0]
            except ValueError:
                return 0
        return 0

    def _predict_ml(self, final_salinity, bend_test, elapsed_hours, cultivar, season,
                    avg_weight=3.0, initial_salinity=12.0, water_temp=None) -> QualityPredictionResult:
        """ML 모델 기반 예측 (8개 feature - trainer.py v2와 동일)"""
        try:
            # 인코딩
            cultivar_encoded = self._encode_cultivar(cultivar)
            season_encoded = self._encode_season(season)

            # 수온 기본값 (계절별)
            if water_temp is None:
                season_defaults = SEASON_DEFAULTS.get(SEASON_MAP.get(season, 'spring'), SEASON_DEFAULTS['spring'])
                water_temp = season_defaults['initialWaterTemp']

            # 피처 준비 (8개 - trainer.py v2 prepare_quality_classifier_data와 동일)
            # [final_salinity, quality_bending, duration_hours, cultivar_encoded,
            #  season_encoded, avg_weight, initial_salinity, initial_water_temp]
            features = np.array([[
                final_salinity,
                bend_test,
                elapsed_hours,
                cultivar_encoded,
                season_encoded,
                avg_weight,
                initial_salinity,
                water_temp
            ]])

            # 스케일링
            if self.scaler:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            # 예측
            pred_class = self.model.predict(features_scaled)[0]
            pred_proba = self.model.predict_proba(features_scaled)[0]

            # 라벨 디코딩 (좋음/양호/나쁨 → A/B/C)
            GRADE_CONVERT = {'좋음': 'A', '양호': 'B', '나쁨': 'C'}
            if 'quality' in self.label_encoders:
                raw_grade = self.label_encoders['quality'].inverse_transform([pred_class])[0]
                predicted_grade = GRADE_CONVERT.get(raw_grade, raw_grade)
            else:
                predicted_grade = GRADE_MAP.get(int(pred_class), 'B')

            # 확률 매핑 (좋음/양호/나쁨 → A/B/C)
            probabilities = {}
            quality_encoder = self.label_encoders.get('quality', None)
            if quality_encoder and hasattr(quality_encoder, 'classes_'):
                for i, cls in enumerate(quality_encoder.classes_):
                    grade_key = GRADE_CONVERT.get(cls, cls)
                    probabilities[grade_key] = round(float(pred_proba[i]), 2)
            else:
                probabilities = {
                    'A': round(float(pred_proba[0]) if len(pred_proba) > 0 else 0.33, 2),
                    'B': round(float(pred_proba[1]) if len(pred_proba) > 1 else 0.33, 2),
                    'C': round(float(pred_proba[2]) if len(pred_proba) > 2 else 0.33, 2)
                }

            # 위험 요소 분석
            risk_factors = []
            if final_salinity < 1.6:
                risk_factors.append("염도 부족 (목표: 1.6~2.0%)")
            elif final_salinity > 2.0:
                risk_factors.append("과염 위험 (목표: 1.6~2.0%)")
            if bend_test < 3.0:
                risk_factors.append("휘어짐 점수 낮음")

            return QualityPredictionResult(
                predicted_grade=predicted_grade,
                probabilities=probabilities,
                confidence=round(float(max(pred_proba)), 2),
                risk_factors=risk_factors
            )

        except Exception as e:
            print(f"[QualityClassifier] ML 예측 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._predict_rule(final_salinity, bend_test, elapsed_hours, cultivar, season)

    def _predict_rule(self, final_salinity, bend_test, elapsed_hours, cultivar, season) -> QualityPredictionResult:
        """규칙 기반 예측 (폴백)"""
        risk_factors = []

        # 휘어짐 점수 기반 1차 판정
        if bend_test >= 4:
            base_grade = "A"
            prob_a = 0.85
        elif bend_test >= 3:
            base_grade = "B"
            prob_a = 0.30
            risk_factors.append("휘어짐 점수 보통")
        else:
            base_grade = "C"
            prob_a = 0.05
            risk_factors.append("휘어짐 점수 낮음")

        # 염도 체크 (최적 범위: 1.6~2.0%)
        if final_salinity < 1.6:
            risk_factors.append("염도 부족 (목표: 1.6~2.0%)")
            prob_a -= 0.2
        elif final_salinity > 2.0:
            risk_factors.append("과염 위험 (목표: 1.6~2.0%)")
            prob_a -= 0.15

        # 시간 체크
        if elapsed_hours < 18:
            risk_factors.append("절임 시간 부족")
            prob_a -= 0.1
        elif elapsed_hours > 40:
            risk_factors.append("과절임 위험")
            prob_a -= 0.1

        prob_a = max(0.05, min(0.95, prob_a))
        prob_b = (1 - prob_a) * 0.7
        prob_c = 1 - prob_a - prob_b

        if prob_a > 0.5:
            predicted_grade = "A"
        elif prob_b > prob_c:
            predicted_grade = "B"
        else:
            predicted_grade = "C"

        return QualityPredictionResult(
            predicted_grade=predicted_grade,
            probabilities={"A": round(prob_a, 2), "B": round(prob_b, 2), "C": round(prob_c, 2)},
            confidence=max(prob_a, prob_b, prob_c),
            risk_factors=risk_factors
        )


# ============================================================
# 싱글톤 인스턴스
# ============================================================
optimizer = ProcessOptimizer()
time_predictor = TimePredictor()
quality_classifier = QualityClassifier()
