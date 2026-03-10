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
    공정 최적화 모델 (trainer.py에서 학습된 모델 사용)
    - 입력: 배추 특성 + 환경 조건
    - 출력: 권장 초기 염도, 절임 시간, 예상 품질
    """

    def __init__(self):
        self.model_salinity = None
        self.model_duration = None
        self.model_quality = None
        self.scalers = {}
        self.label_encoders = {}
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """학습 모델 로드 (trainer.py에서 학습된 모델)"""
        try:
            # 학습된 모델 경로 확인
            model_path = None
            if LOCAL_MODEL_DIR.exists():
                model_path = LOCAL_MODEL_DIR
            elif MODEL_DIR.exists():
                model_path = MODEL_DIR
            else:
                print(f"[ProcessOptimizer] 모델 경로 없음")
                return

            # 모델 파일 확인 (trainer.py에서 생성된 파일명)
            salinity_path = model_path / "optimizer_salinity.pkl"
            duration_path = model_path / "optimizer_duration.pkl"
            quality_path = model_path / "quality_classifier.pkl"
            scalers_path = model_path / "scalers.pkl"
            encoders_path = model_path / "label_encoders.pkl"

            if not duration_path.exists():
                print(f"[ProcessOptimizer] 모델 파일 없음: {duration_path}")
                return

            # 모델 로드
            self.model_salinity = joblib.load(salinity_path)
            self.model_duration = joblib.load(duration_path)
            self.model_quality = joblib.load(quality_path)

            # 스케일러와 인코더 로드
            if scalers_path.exists():
                self.scalers = joblib.load(scalers_path)
            if encoders_path.exists():
                self.label_encoders = joblib.load(encoders_path)

            self.is_trained = True
            self.model_version = "v1"
            print(f"[ProcessOptimizer] 학습된 모델 로드 완료 ({self.model_version})")

        except Exception as e:
            print(f"[ProcessOptimizer] 모델 로드 실패, 더미 모드 사용: {e}")
            import traceback
            traceback.print_exc()
            self.is_trained = False

    def _prepare_optimizer_features(self, cultivar: str, avg_weight: float, firmness: float,
                                      leaf_thickness: float, season: str, room_temp: float) -> np.ndarray:
        """
        공정 최적화 모델 입력 피처 준비 (trainer.py와 동일한 구조)
        6개 feature: [cultivar_encoded, avg_weight, firmness, leaf_thickness, season_encoded, room_temp]
        """
        # 품종 인코딩
        cultivar_encoded = 0
        if 'cultivar' in self.label_encoders:
            try:
                cultivar_encoded = self.label_encoders['cultivar'].transform([cultivar])[0]
            except ValueError:
                # 알 수 없는 품종은 0으로
                cultivar_encoded = 0

        # 계절 인코딩
        season_encoded = 0
        if 'season' in self.label_encoders:
            try:
                season_encoded = self.label_encoders['season'].transform([season])[0]
            except ValueError:
                season_encoded = 0

        # UI firmness(0~100) → ML firmness (그대로 사용, 학습 데이터와 동일)
        # trainer.py에서는 firmness를 그대로 사용했으므로 변환 없음
        firmness_val = firmness if firmness else 50.0
        leaf_thickness_val = leaf_thickness if leaf_thickness else 2.0
        room_temp_val = room_temp if room_temp else 20.0

        features = np.array([[
            cultivar_encoded,
            avg_weight,
            firmness_val,
            leaf_thickness_val,
            season_encoded,
            room_temp_val
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
        """ML 모델 기반 예측 (trainer.py에서 학습된 모델 사용)"""
        try:
            # 피처 준비 (6개 feature)
            features = self._prepare_optimizer_features(
                cultivar, avg_weight, firmness, leaf_thickness, season, room_temp
            )

            # 스케일링 적용
            if 'optimizer' in self.scalers:
                features_scaled = self.scalers['optimizer'].transform(features)
            else:
                features_scaled = features

            # 절임 시간 예측
            duration = self.model_duration.predict(features_scaled)[0]
            duration = float(np.clip(duration, 8, 48))

            # 초기 염도 예측
            recommended_salinity = self.model_salinity.predict(features_scaled)[0]
            recommended_salinity = float(np.clip(recommended_salinity, 8.0, 15.0))

            # 예상 최종 염도 (초기 염도 기반 추정)
            expected_final = 1.8 + (recommended_salinity - 12.0) * 0.05

            # 최적 범위 판단
            is_optimal = 1.6 <= expected_final <= 2.0

            # 품질 예측 (quality_classifier 사용 - 7개 feature 필요)
            # final_cabbage_salinity, bend_test, duration, cultivar, season, avg_weight, initial_salinity
            quality_grade = "A"  # 기본값
            if self.model_quality and 'quality_classifier' in self.scalers:
                try:
                    # 품질 분류기 피처
                    cultivar_enc = 0
                    season_enc = 0
                    if 'cultivar' in self.label_encoders:
                        try:
                            cultivar_enc = self.label_encoders['cultivar'].transform([cultivar])[0]
                        except:
                            pass
                    if 'season' in self.label_encoders:
                        try:
                            season_enc = self.label_encoders['season'].transform([season])[0]
                        except:
                            pass

                    quality_features = np.array([[
                        expected_final,      # final_cabbage_salinity
                        4.5,                 # bend_test (예상값)
                        duration,            # duration
                        cultivar_enc,        # cultivar
                        season_enc,          # season
                        avg_weight,          # avg_weight
                        recommended_salinity # initial_salinity
                    ]])
                    quality_scaled = self.scalers['quality_classifier'].transform(quality_features)
                    quality_pred = self.model_quality.predict(quality_scaled)[0]

                    # 라벨 디코딩
                    if 'quality' in self.label_encoders:
                        quality_grade = self.label_encoders['quality'].inverse_transform([quality_pred])[0]
                    else:
                        quality_grade = GRADE_MAP.get(int(quality_pred), 'B')
                except Exception as qe:
                    print(f"[ProcessOptimizer] 품질 예측 실패: {qe}")
                    quality_grade = "A" if is_optimal else "B"

            return OptimizationResult(
                recommended_salinity=round(recommended_salinity, 1),
                recommended_duration=round(duration, 1),
                predicted_quality=quality_grade,
                confidence=0.91,  # metrics.json의 duration_r2
                reasoning=f"ML 모델 예측 ({self.model_version}): {season} {cultivar} 품종, 무게 {avg_weight}kg 기준",
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
# TimePredictor - 시간 예측 모델
# ============================================================
class TimePredictor:
    """
    시간 예측 모델 (trainer.py에서 학습된 모델 사용)
    - 입력: 시계열 센서 데이터 (염도, 온도 변화)
    - 출력: 남은 절임 시간 예측
    - 7개 feature: elapsed, salinity_avg, initial_salinity, water_temp, accumulated_temp, salinity_diff, osmotic_pressure_index
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """trainer.py에서 학습된 time_predictor 모델 로드"""
        try:
            model_path = None
            scalers_path = None

            if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "time_predictor.pkl").exists():
                model_path = LOCAL_MODEL_DIR / "time_predictor.pkl"
                scalers_path = LOCAL_MODEL_DIR / "scalers.pkl"
            elif MODEL_DIR.exists() and (MODEL_DIR / "time_predictor.pkl").exists():
                model_path = MODEL_DIR / "time_predictor.pkl"
                scalers_path = MODEL_DIR / "scalers.pkl"

            if model_path:
                self.model = joblib.load(model_path)
                if scalers_path and scalers_path.exists():
                    scalers = joblib.load(scalers_path)
                    self.scaler = scalers.get('time_predictor')
                self.is_trained = True
                self.model_version = "v1"
                print(f"[TimePredictor] 학습된 모델 로드 완료: {model_path}")
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
            # 파생 변수 계산
            salinity_diff = initial_salinity - current_salinity_avg
            osmotic_pressure_index = current_salinity_avg * water_temp / 100.0

            # 피처 준비: elapsed, salinity_avg, initial_salinity, water_temp, accumulated_temp, salinity_diff, osmotic_pressure_index
            features = np.array([[
                elapsed_hours,
                current_salinity_avg,
                initial_salinity,
                water_temp,
                accumulated_temp,
                salinity_diff,
                osmotic_pressure_index
            ]])

            # 스케일링
            if self.scaler:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            # 예측 (남은 시간)
            remaining_hours = self.model.predict(features_scaled)[0]
            remaining_hours = float(max(0.5, min(remaining_hours, 24.0)))

            total_estimated = elapsed_hours + remaining_hours
            progress = (elapsed_hours / total_estimated) * 100 if total_estimated > 0 else 0

            predicted_end = datetime.now() + timedelta(hours=remaining_hours)

            return TimePredictionResult(
                remaining_hours=round(remaining_hours, 1),
                predicted_end_time=predicted_end.strftime("%Y-%m-%d %H:%M"),
                confidence=0.86,  # metrics.json의 r2
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
# QualityClassifier - 품질 분류 모델
# ============================================================
class QualityClassifier:
    """
    품질 분류 모델 (trainer.py에서 학습된 모델 사용)
    - 입력: 최종 상태 (염도, 휘어짐 점수 등)
    - 출력: 품질 등급 (A/B/C)
    - 7개 feature: final_cabbage_salinity, bend_test, duration, cultivar, season, avg_weight, initial_salinity
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.is_trained = False
        self.model_version = "dummy"
        self._load_model()

    def _load_model(self):
        """trainer.py에서 학습된 quality_classifier 모델 로드"""
        try:
            model_path = None
            scalers_path = None
            encoders_path = None

            if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "quality_classifier.pkl").exists():
                model_path = LOCAL_MODEL_DIR / "quality_classifier.pkl"
                scalers_path = LOCAL_MODEL_DIR / "scalers.pkl"
                encoders_path = LOCAL_MODEL_DIR / "label_encoders.pkl"
            elif MODEL_DIR.exists() and (MODEL_DIR / "quality_classifier.pkl").exists():
                model_path = MODEL_DIR / "quality_classifier.pkl"
                scalers_path = MODEL_DIR / "scalers.pkl"
                encoders_path = MODEL_DIR / "label_encoders.pkl"

            if model_path:
                self.model = joblib.load(model_path)
                if scalers_path and scalers_path.exists():
                    scalers = joblib.load(scalers_path)
                    self.scaler = scalers.get('quality_classifier')
                if encoders_path and encoders_path.exists():
                    self.label_encoders = joblib.load(encoders_path)

                self.is_trained = True
                self.model_version = "v1"
                print(f"[QualityClassifier] 학습된 모델 로드 완료: {model_path}")
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
        """ML 모델 기반 예측 (7개 feature)"""
        try:
            # 품종 인코딩
            cultivar_encoded = 0
            if 'cultivar' in self.label_encoders:
                try:
                    cultivar_encoded = self.label_encoders['cultivar'].transform([cultivar])[0]
                except ValueError:
                    cultivar_encoded = 0

            # 계절 인코딩
            season_encoded = 0
            if 'season' in self.label_encoders:
                try:
                    season_encoded = self.label_encoders['season'].transform([season])[0]
                except ValueError:
                    season_encoded = 0

            # 피처 준비: final_cabbage_salinity, bend_test, duration, cultivar, season, avg_weight, initial_salinity
            features = np.array([[
                final_salinity,
                bend_test,
                elapsed_hours,
                cultivar_encoded,
                season_encoded,
                3.0,   # avg_weight 기본값
                12.0   # initial_salinity 기본값
            ]])

            # 스케일링
            if self.scaler:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            # 예측
            pred_class = self.model.predict(features_scaled)[0]
            pred_proba = self.model.predict_proba(features_scaled)[0]

            # 라벨 디코딩
            if 'quality' in self.label_encoders:
                predicted_grade = self.label_encoders['quality'].inverse_transform([pred_class])[0]
            else:
                predicted_grade = GRADE_MAP.get(int(pred_class), 'B')

            # 확률 매핑 (클래스 순서: A, B, C 또는 0, 1, 2)
            probabilities = {}
            classes = self.label_encoders.get('quality', None)
            if classes and hasattr(classes, 'classes_'):
                for i, cls in enumerate(classes.classes_):
                    probabilities[cls] = round(float(pred_proba[i]), 2)
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
