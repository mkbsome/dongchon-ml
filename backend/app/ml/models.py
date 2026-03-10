"""
ML 모델 클래스 (v4 학습 모델 연동)
- 03_ML/03_Modeling/models/ 에서 학습된 모델 로드
- UI 입력값 → ML 모델 입력값 변환 (호환성 레이어)
"""

import numpy as np
import pandas as pd
import joblib
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
import json


# ============================================================
# 경로 설정
# ============================================================
# 학습된 모델 경로 (03_ML/03_Modeling/models/)
ML_BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "03_ML"
MODEL_DIR = ML_BASE_DIR / "03_Modeling" / "models"
PREPROCESS_DIR = ML_BASE_DIR / "02_Preprocessing" / "output"

# 폴백용 로컬 경로
LOCAL_MODEL_DIR = Path(__file__).parent / "saved_models" / "v1"


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
# ProcessOptimizer - 공정 최적화 모델
# ============================================================
class ProcessOptimizer:
    """
    공정 최적화 모델 (v4 학습 모델 사용)
    - 입력: 배추 특성 + 환경 조건
    - 출력: 권장 초기 염도, 절임 시간, 예상 품질
    """

    def __init__(self):
        self.model_salinity = None
        self.model_duration = None
        self.model_quality = None
        self.metadata = None
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """v4 학습 모델 로드"""
        try:
            # 학습된 모델 경로 확인
            if MODEL_DIR.exists():
                model_path = MODEL_DIR
            elif LOCAL_MODEL_DIR.exists():
                model_path = LOCAL_MODEL_DIR
            else:
                print(f"[ProcessOptimizer] 모델 경로 없음: {MODEL_DIR}")
                return

            # 모델 파일 확인
            salinity_path = model_path / "salinity_model.joblib"
            duration_path = model_path / "duration_model.joblib"
            quality_path = model_path / "quality_model.joblib"
            metadata_path = model_path / "model_metadata.json"

            if not salinity_path.exists():
                print(f"[ProcessOptimizer] 염도 모델 없음: {salinity_path}")
                return

            # 모델 로드
            self.model_salinity = joblib.load(salinity_path)
            self.model_duration = joblib.load(duration_path)
            self.model_quality = joblib.load(quality_path)

            # 메타데이터 로드
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

            self.is_trained = True
            self.model_version = self.metadata.get('version', 'v4') if self.metadata else 'v4'
            print(f"[ProcessOptimizer] 학습된 모델 로드 완료 ({self.model_version})")

        except Exception as e:
            print(f"[ProcessOptimizer] 모델 로드 실패, 더미 모드 사용: {e}")
            self.is_trained = False

    def _prepare_features(self, cultivar: str, avg_weight: float, firmness: float,
                          leaf_thickness: float, season: str, room_temp: float,
                          initial_salinity: float = None, outdoor_temp: float = None,
                          water_temp: float = None) -> pd.DataFrame:
        """ML 모델 입력 피처 준비"""

        # 계절 변환 및 기본값
        season_en = SEASON_MAP.get(season, 'fall')
        defaults = SEASON_DEFAULTS.get(season_en, SEASON_DEFAULTS['fall'])

        # 값 설정 (입력값 우선, 없으면 기본값)
        initial_salinity = initial_salinity or defaults['initialSalinity']
        outdoor_temp = outdoor_temp or defaults['outdoorTemp']
        water_temp = water_temp or defaults['initialWaterTemp']
        room_temp = room_temp or defaults['roomTemp']

        # 품종 변환
        cultivar_ml = CULTIVAR_MAP.get(cultivar, 'other')

        # 단단함 변환 (UI 0~100 → ML 0.8~2.5)
        firmness_ml = convert_firmness(firmness)

        # 잎 두께 (기본값 2)
        leaf_thickness = leaf_thickness or 2

        # 크기 추정
        cabbage_size = weight_to_size(avg_weight)

        # 기본 피처
        features = {
            'avgWeight': avg_weight,
            'firmness': firmness_ml,
            'leafThickness': int(leaf_thickness),
            'roomTemp': room_temp,
            'outdoorTemp': outdoor_temp,
            'initialWaterTemp': water_temp,
            'initialSalinity': initial_salinity,
            'addedSalt': 1 if season_en == 'winter' else 0,
            'addedSaltAmount': 40 if season_en == 'winter' else 0,
        }

        # 파생 변수
        features['temp_diff'] = room_temp - outdoor_temp
        features['outdoor_water_temp_diff'] = outdoor_temp - water_temp
        features['temp_effect'] = (water_temp - 15) * 0.02
        features['penetration_factor'] = firmness_ml * leaf_thickness
        features['salinity_weight_ratio'] = initial_salinity / avg_weight
        features['absorption_potential'] = initial_salinity * 0.155
        features['weight_dilution'] = 3.0 / avg_weight

        # 세척 관련 (기본값)
        features['washTank1Salinity'] = 1.0
        features['washTank3Salinity'] = 0.3
        features['washTank1WaterTemp'] = 15.0
        features['washTank3WaterTemp'] = 15.0
        features['wash_salinity_drop'] = 0.7

        # 시간 관련 (기본값)
        features['start_hour'] = 8
        features['start_month'] = {'spring': 4, 'summer': 7, 'fall': 10, 'winter': 1}.get(season_en, 10)
        features['is_two_day'] = 1 if season_en == 'winter' else 0

        # 계절 One-Hot
        for s in ['fall', 'spring', 'summer', 'winter']:
            features[f'season_{s}'] = 1 if season_en == s else 0

        # 품종 One-Hot
        cultivars = ['bulam3', 'bulamplus', 'cheongmyung', 'cheongomabi',
                     'giwunchan', 'hwanggeumstar', 'hwimori', 'hwiparam', 'other']
        for c in cultivars:
            features[f'cultivar_{c}'] = 1 if cultivar_ml == c else 0

        # 크기 One-Hot
        sizes = ['S', 'M', 'L', 'XL']
        for size in sizes:
            features[f'cabbageSize_{size}'] = 1 if cabbage_size == size else 0

        return pd.DataFrame([features])

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
        water_temp: float = None
    ) -> OptimizationResult:
        """최적 공정 조건 추천"""

        if self.is_trained and self.model_duration:
            return self._predict_ml(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp,
                initial_salinity, outdoor_temp, water_temp
            )
        else:
            return self._predict_rule(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp, target_quality
            )

    def _predict_ml(self, cultivar, avg_weight, firmness, leaf_thickness, season, room_temp,
                    initial_salinity=None, outdoor_temp=None, water_temp=None) -> OptimizationResult:
        """v4 ML 모델 기반 예측"""
        try:
            # 피처 준비
            features_df = self._prepare_features(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp,
                initial_salinity, outdoor_temp, water_temp
            )

            # 계절 기본값
            season_en = SEASON_MAP.get(season, 'fall')
            defaults = SEASON_DEFAULTS.get(season_en, SEASON_DEFAULTS['fall'])
            initial_salinity = initial_salinity or defaults['initialSalinity']

            # 시간 예측을 위한 피처 준비
            duration_features = self.metadata['models']['duration']['features'] if self.metadata else []
            if duration_features:
                duration_df = features_df.reindex(columns=duration_features, fill_value=0)
            else:
                duration_df = features_df

            # 절임 시간 예측
            duration = self.model_duration.predict(duration_df)[0]
            duration = float(np.clip(duration, 18, 48))

            # 염도 예측을 위한 피처 준비 (duration_hours 추가)
            features_df['duration_hours'] = duration
            features_df['salinity_drop_rate'] = 0
            features_df['penetration_time'] = duration * features_df['penetration_factor'].iloc[0]

            salinity_features = self.metadata['models']['salinity']['features'] if self.metadata else []
            if salinity_features:
                salinity_df = features_df.reindex(columns=salinity_features, fill_value=0)
            else:
                salinity_df = features_df

            # 최종 염도 예측
            final_salinity = self.model_salinity.predict(salinity_df)[0]
            final_salinity = float(np.clip(final_salinity, 1.2, 2.4))

            # 품질 예측을 위한 피처 준비
            features_df['finalSalinity'] = final_salinity
            features_df['qualityBending'] = 5 if 1.6 <= final_salinity <= 2.0 else 3

            quality_features = self.metadata['models']['quality']['features'] if self.metadata else []
            if quality_features:
                quality_df = features_df.reindex(columns=quality_features, fill_value=0)
            else:
                quality_df = features_df

            # 품질 예측
            quality_pred = self.model_quality.predict(quality_df)[0]
            quality_grade = GRADE_MAP.get(int(quality_pred), 'B')

            # 최적 범위 판단
            is_optimal = 1.6 <= final_salinity <= 2.0

            # R² 점수 기반 신뢰도
            confidence = self.metadata['models']['duration']['metrics']['r2'] if self.metadata else 0.85

            return OptimizationResult(
                recommended_salinity=round(initial_salinity, 1),
                recommended_duration=round(duration, 1),
                predicted_quality=quality_grade,
                confidence=round(confidence, 2),
                reasoning=f"ML 모델 예측 ({self.model_version}): {season} {cultivar} 품종, 무게 {avg_weight}kg 기준",
                expected_final_salinity=round(final_salinity, 2),
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
# TimePredictor - 시간 예측 모델
# ============================================================
class TimePredictor:
    """
    시간 예측 모델
    - 입력: 시계열 센서 데이터 (염도, 온도 변화)
    - 출력: 남은 절임 시간 예측
    """

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """v4 학습 모델 로드"""
        try:
            if MODEL_DIR.exists():
                model_path = MODEL_DIR / "duration_model.joblib"
                if model_path.exists():
                    self.model = joblib.load(model_path)
                    self.is_trained = True
                    self.model_version = "v4"
                    print("[TimePredictor] 학습된 모델 로드 완료")
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
        # 규칙 기반 예측 (시계열은 별도 모델 필요)
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
# QualityClassifier - 품질 분류 모델
# ============================================================
class QualityClassifier:
    """
    품질 분류 모델 (v4 학습 모델 사용)
    - 입력: 최종 상태 (염도, 휘어짐 점수 등)
    - 출력: 품질 등급 (A/B/C)
    """

    def __init__(self):
        self.model = None
        self.metadata = None
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """v4 학습 모델 로드"""
        try:
            if MODEL_DIR.exists():
                model_path = MODEL_DIR / "quality_model.joblib"
                metadata_path = MODEL_DIR / "model_metadata.json"

                if model_path.exists():
                    self.model = joblib.load(model_path)

                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            self.metadata = json.load(f)

                    self.is_trained = True
                    self.model_version = "v4"
                    print("[QualityClassifier] 학습된 모델 로드 완료")
        except Exception as e:
            print(f"[QualityClassifier] 모델 로드 실패: {e}")
            self.is_trained = False

    def predict(
        self,
        final_salinity: float,
        bend_test: float,
        elapsed_hours: float,
        cultivar: str,
        season: str
    ) -> QualityPredictionResult:
        """품질 등급 예측"""

        if self.is_trained and self.model:
            return self._predict_ml(final_salinity, bend_test, elapsed_hours, cultivar, season)
        else:
            return self._predict_rule(final_salinity, bend_test, elapsed_hours, cultivar, season)

    def _predict_ml(self, final_salinity, bend_test, elapsed_hours, cultivar, season) -> QualityPredictionResult:
        """ML 모델 기반 예측"""
        try:
            # 피처 준비 (간소화 버전)
            season_en = SEASON_MAP.get(season, 'fall')
            cultivar_ml = CULTIVAR_MAP.get(cultivar, 'other')

            # 기본 피처 (ProcessOptimizer와 동일한 구조 필요)
            features = {
                'avgWeight': 3.0,
                'firmness': 1.5,
                'leafThickness': 2,
                'roomTemp': 22.0,
                'outdoorTemp': 16.0,
                'initialWaterTemp': 16.0,
                'initialSalinity': 12.0,
                'duration_hours': elapsed_hours,
                'washTank1Salinity': 1.0,
                'washTank3Salinity': 0.3,
                'washTank1WaterTemp': 15.0,
                'washTank3WaterTemp': 15.0,
                'addedSaltAmount': 0,
                'finalSalinity': final_salinity,
                'qualityBending': int(bend_test),
                'salinity_drop': 12.0 - final_salinity,
                'salinity_drop_rate': (12.0 - final_salinity) / max(elapsed_hours, 1),
                'temp_diff': 6.0,
                'wash_salinity_drop': 0.7,
                'start_hour': 8,
                'start_month': {'spring': 4, 'summer': 7, 'fall': 10, 'winter': 1}.get(season_en, 10),
                'outdoor_water_temp_diff': 0.0,
                'salinity_weight_ratio': 4.0,
                'absorption_potential': 1.86,
                'weight_dilution': 1.0,
                'temp_effect': 0.02,
                'penetration_factor': 3.0,
                'penetration_time': elapsed_hours * 3.0,
                'addedSalt': 0,
                'is_two_day': 1 if season_en == 'winter' else 0,
            }

            # 계절 One-Hot
            for s in ['fall', 'spring', 'summer', 'winter']:
                features[f'season_{s}'] = 1 if season_en == s else 0

            # 품종 One-Hot
            cultivars = ['bulam3', 'bulamplus', 'cheongmyung', 'cheongomabi',
                         'giwunchan', 'hwanggeumstar', 'hwimori', 'hwiparam', 'other']
            for c in cultivars:
                features[f'cultivar_{c}'] = 1 if cultivar_ml == c else 0

            # 크기 One-Hot
            for size in ['S', 'M', 'L', 'XL']:
                features[f'cabbageSize_{size}'] = 1 if size == 'M' else 0

            df = pd.DataFrame([features])

            # 피처 선택
            quality_features = self.metadata['models']['quality']['features'] if self.metadata else list(features.keys())
            df = df.reindex(columns=quality_features, fill_value=0)

            # 예측
            pred_class = self.model.predict(df)[0]
            pred_proba = self.model.predict_proba(df)[0]

            predicted_grade = GRADE_MAP.get(int(pred_class), 'B')

            # 확률 매핑
            probabilities = {
                'A': round(float(pred_proba[2]), 2),  # 좋음
                'B': round(float(pred_proba[1]), 2),  # 양호
                'C': round(float(pred_proba[0]), 2)   # 나쁨
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
