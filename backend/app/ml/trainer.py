"""
ML 모델 학습 모듈 (v2 - 2026.03.11 재설계)

변경사항:
- pickling_type 피처 제거 (데이터 누수 문제 해결)
- initial_salinity를 시간 예측 피처로 추가 (r=-0.81)
- 물리화학적 파생변수 추가 (vant_hoff_osmotic 등)
- 피처 메타데이터 저장

모델 구성:
1. optimizer_duration: 절임 시간 예측 (12개 피처)
2. optimizer_salinity: 초기 염도 추천 (8개 피처)
3. quality_classifier: 품질 등급 분류 (8개 피처)
4. time_predictor: 남은 시간 예측 (7개 피처)
"""

import json
import pickle
import os
from datetime import datetime
from typing import Tuple, Optional, Dict, List
import numpy as np
from pathlib import Path

# ML 라이브러리
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score, f1_score

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


# 모델 저장 경로
MODEL_DIR = Path(__file__).parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)


# ============================================================
# 피처 정의 (v2)
# ============================================================

# 모델1: 시간 예측 (optimizer_duration) - 12개 피처
DURATION_FEATURES = [
    'cultivar_encoded',      # 품종 (인코딩)
    'avg_weight',            # 배추 평균 무게 (kg)
    'firmness',              # 경도
    'leaf_thickness',        # 잎 두께 (mm)
    'season_encoded',        # 계절 (인코딩)
    'room_temp',             # 실내 온도 (°C)
    'initial_water_temp',    # 지하수 온도 (°C) - 핵심!
    'initial_salinity',      # 초기 염도 (%) - 핵심! r=-0.81
    'outdoor_temp',          # 외부 온도 (°C) - r=-0.69
    'added_salt_amount',     # 웃소금량 (kg) - r=+0.69
    'vant_hoff_osmotic',     # Van't Hoff 삼투압 - r=-0.87 (파생)
    'weight_firmness',       # 무게x경도 상호작용 - r=+0.70 (파생)
]

# 모델2: 염도 추천 (optimizer_salinity) - 8개 피처
SALINITY_FEATURES = [
    'cultivar_encoded',
    'avg_weight',
    'firmness',
    'leaf_thickness',
    'season_encoded',
    'room_temp',
    'initial_water_temp',
    'outdoor_temp',
]

# 모델3: 품질 분류 (quality_classifier) - 8개 피처 (기존 유지)
QUALITY_FEATURES = [
    'final_salinity',
    'quality_bending',
    'duration_hours',
    'cultivar_encoded',
    'season_encoded',
    'avg_weight',
    'initial_salinity',
    'initial_water_temp',
]

# 모델4: 시간 예측기 (time_predictor) - 7개 피처 (기존 유지)
TIME_PREDICTOR_FEATURES = [
    'elapsed_hours',
    'salinity_avg',
    'initial_salinity',
    'water_temp',
    'accumulated_temp',
    'salinity_diff',
    'osmotic_index',
]

# 모델5: 최종 염도 예측기 (final_salinity_predictor) - 핵심 모델
# 이 모델로 역최적화: 목표 final_salinity(1.5~2.0%)를 달성하는 (초기염도, 시간) 찾기
FINAL_SALINITY_FEATURES = [
    'initial_salinity',      # 초기 염도 (%)
    'duration_hours',        # 절임 시간 (hours)
    'initial_water_temp',    # 수온 (°C)
    'avg_weight',            # 배추 무게 (kg)
    'firmness',              # 경도
    'leaf_thickness',        # 잎 두께
    'vant_hoff_osmotic',     # Van't Hoff 삼투압
    'cultivar_encoded',      # 품종
    'season_encoded',        # 계절
]


class ModelTrainer:
    """ML 모델 학습 및 관리 클래스 (v2)"""

    def __init__(self):
        self.label_encoders = {}
        self.scalers = {}
        self.models = {}
        self.metrics = {}
        self.feature_names = {}  # 피처 이름 저장

    def load_dummy_data(self, json_path: str) -> Tuple[list, list]:
        """더미 데이터 JSON 로드"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['batches'], data['measurements']

    def _compute_derived_features(self, initial_salinity: float, water_temp: float,
                                   avg_weight: float, firmness: float) -> Dict[str, float]:
        """물리화학적 파생변수 계산"""
        return {
            'vant_hoff_osmotic': initial_salinity * (water_temp + 273.15) / 100,
            'osmotic_index': initial_salinity * water_temp,
            'weight_firmness': avg_weight * firmness,
        }

    def prepare_duration_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        시간 예측 모델용 데이터 준비 (v2)
        - pickling_type 제거
        - initial_salinity, outdoor_temp, added_salt_amount 추가
        - 물리화학적 파생변수 추가

        입력: 배추 특성 + 환경 + 공정 조건
        출력: 절임 시간 (hours)
        """
        X = []
        y = []

        # 라벨 인코더 초기화
        if 'cultivar' not in self.label_encoders:
            self.label_encoders['cultivar'] = LabelEncoder()
            self.label_encoders['season'] = LabelEncoder()

            all_cultivars = list(set(b.get('cultivar', b.get('cultivar_label', '기타')) for b in batches))
            all_seasons = list(set(b['season'] for b in batches))
            self.label_encoders['cultivar'].fit(all_cultivars)
            self.label_encoders['season'].fit(all_seasons)

        for b in batches:
            # 모든 데이터 사용 (좋음 등급만 사용하면 편향 발생)
            cultivar = b.get('cultivar', b.get('cultivar_label', '기타'))
            water_temp = b.get('initial_water_temp', b.get('water_temp', 15))
            initial_salinity = b.get('initial_salinity', 12.0)
            avg_weight = b.get('avg_weight', 3.0)
            firmness = b.get('firmness', 15.0)

            # 파생변수 계산
            derived = self._compute_derived_features(initial_salinity, water_temp, avg_weight, firmness)

            features = [
                self.label_encoders['cultivar'].transform([cultivar])[0],
                avg_weight,
                firmness,
                b.get('leaf_thickness', 3),
                self.label_encoders['season'].transform([b['season']])[0],
                b.get('room_temp', 22.0),
                water_temp,
                initial_salinity,
                b.get('outdoor_temp', 15.0),
                b.get('added_salt_amount', 20),
                derived['vant_hoff_osmotic'],
                derived['weight_firmness'],
            ]
            X.append(features)

            # 타겟: 절임 시간 (분 -> 시간)
            duration = b.get('total_duration_minutes', 0) / 60
            if duration == 0:
                start = datetime.fromisoformat(b['start_time'])
                end = datetime.fromisoformat(b['end_time'])
                duration = (end - start).total_seconds() / 3600
            y.append(duration)

        self.feature_names['optimizer_duration'] = DURATION_FEATURES
        return np.array(X), np.array(y)

    def prepare_salinity_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        염도 추천 모델용 데이터 준비 (v2)
        - pickling_type 제거

        입력: 배추 특성 + 환경
        출력: 권장 초기 염도 (%)
        """
        X = []
        y = []

        for b in batches:
            # '좋음' 등급 데이터만 사용 (최적 조건 학습)
            if b['quality_grade'] == '좋음':
                cultivar = b.get('cultivar', b.get('cultivar_label', '기타'))
                water_temp = b.get('initial_water_temp', b.get('water_temp', 15))

                features = [
                    self.label_encoders['cultivar'].transform([cultivar])[0],
                    b.get('avg_weight', 3.0),
                    b.get('firmness', 15.0),
                    b.get('leaf_thickness', 3),
                    self.label_encoders['season'].transform([b['season']])[0],
                    b.get('room_temp', 22.0),
                    water_temp,
                    b.get('outdoor_temp', 15.0),
                ]
                X.append(features)
                y.append(b['initial_salinity'])

        self.feature_names['optimizer_salinity'] = SALINITY_FEATURES
        return np.array(X), np.array(y)

    def prepare_time_predictor_data(self, batches: list, measurements: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        실시간 시간 예측 모델용 데이터 준비
        입력: 현재 상태 (경과시간, 염도, 온도 등)
        출력: 남은 시간
        """
        # 배치별 측정 데이터 그룹화
        batch_measurements = {}
        for m in measurements:
            bid = m['batch_id']
            if bid not in batch_measurements:
                batch_measurements[bid] = []
            batch_measurements[bid].append(m)

        # 배치 ID로 빠른 검색
        batch_dict = {b['id']: b for b in batches}

        X = []
        y = []

        for bid, meas_list in batch_measurements.items():
            if bid not in batch_dict:
                continue

            b = batch_dict[bid]
            meas_list = sorted(meas_list, key=lambda x: x['timestamp'])

            # 총 절임 시간 (분 -> 시간)
            total_duration = b.get('total_duration_minutes', 0) / 60
            if total_duration == 0:
                start = datetime.fromisoformat(b['start_time'])
                end = datetime.fromisoformat(b['end_time'])
                total_duration = (end - start).total_seconds() / 3600

            initial_salinity = b.get('initial_salinity', 12.0)

            # 각 측정 시점에서의 특성과 남은 시간
            for m in meas_list[:-1]:  # 마지막 측정 제외
                elapsed = m.get('elapsed_minutes', 0) / 60
                remaining = total_duration - elapsed

                if remaining > 0:
                    water_temp = m.get('water_temp', 15)
                    salinity_avg = m.get('salinity_avg', (m.get('salinity_top', 0) + m.get('salinity_bottom', 0)) / 2)

                    features = [
                        elapsed,
                        salinity_avg,
                        initial_salinity,
                        water_temp,
                        elapsed * water_temp,  # 적산온도 근사
                        m.get('salinity_diff', abs(m.get('salinity_top', 0) - m.get('salinity_bottom', 0))),
                        salinity_avg * water_temp / 100,  # 삼투압 지표
                    ]
                    X.append(features)
                    y.append(remaining)

        self.feature_names['time_predictor'] = TIME_PREDICTOR_FEATURES
        return np.array(X), np.array(y)

    def prepare_quality_classifier_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        품질 분류 모델용 데이터 준비 (기존 유지)
        입력: 최종 상태
        출력: 품질 등급 (좋음/양호/나쁨)
        """
        X = []
        y = []

        # 품질 등급 인코더
        if 'quality' not in self.label_encoders:
            self.label_encoders['quality'] = LabelEncoder()
            self.label_encoders['quality'].fit(['좋음', '양호', '나쁨'])

        for b in batches:
            # 절임 시간 (분 -> 시간)
            duration = b.get('total_duration_minutes', 0) / 60
            if duration == 0:
                start = datetime.fromisoformat(b['start_time'])
                end = datetime.fromisoformat(b['end_time'])
                duration = (end - start).total_seconds() / 3600

            cultivar = b.get('cultivar', b.get('cultivar_label', '기타'))
            water_temp = b.get('initial_water_temp', b.get('water_temp', 15))

            features = [
                b.get('final_salinity', b.get('final_cabbage_salinity', 1.7)),
                b.get('quality_bending', b.get('bend_test', 3)),
                duration,
                self.label_encoders['cultivar'].transform([cultivar])[0],
                self.label_encoders['season'].transform([b['season']])[0],
                b.get('avg_weight', 3.0),
                b.get('initial_salinity', 12.0),
                water_temp,
            ]
            X.append(features)
            y.append(self.label_encoders['quality'].transform([b['quality_grade']])[0])

        self.feature_names['quality_classifier'] = QUALITY_FEATURES
        return np.array(X), np.array(y)

    def train_duration_model(self, X: np.ndarray, y: np.ndarray):
        """시간 예측 모델 학습 (v2)"""
        print("\n[학습] 절임 시간 예측 모델 (optimizer_duration)...")
        print(f"  피처 수: {X.shape[1]}개")
        print(f"  피처: {DURATION_FEATURES}")

        # 스케일러
        self.scalers['optimizer_duration'] = StandardScaler()
        X_scaled = self.scalers['optimizer_duration'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        # Gradient Boosting (더 나은 성능)
        self.models['optimizer_duration'] = GradientBoostingRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            min_samples_split=10, min_samples_leaf=5, random_state=42
        )

        self.models['optimizer_duration'].fit(X_train, y_train)
        y_pred = self.models['optimizer_duration'].predict(X_test)

        # 메트릭 저장
        self.metrics['optimizer_duration'] = {
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': DURATION_FEATURES,
        }

        print(f"  MAE: {self.metrics['optimizer_duration']['mae']:.3f}h")
        print(f"  R2: {self.metrics['optimizer_duration']['r2']:.3f}")

        # 피처 중요도 출력
        importances = self.models['optimizer_duration'].feature_importances_
        feature_importance = sorted(zip(DURATION_FEATURES, importances), key=lambda x: x[1], reverse=True)
        print("\n  [피처 중요도]")
        for feat, imp in feature_importance[:5]:
            print(f"    {feat}: {imp:.3f}")

    def train_salinity_model(self, X: np.ndarray, y: np.ndarray):
        """염도 추천 모델 학습 (v2)"""
        print("\n[학습] 염도 추천 모델 (optimizer_salinity)...")
        print(f"  피처 수: {X.shape[1]}개")
        print(f"  피처: {SALINITY_FEATURES}")

        # 스케일러
        self.scalers['optimizer_salinity'] = StandardScaler()
        X_scaled = self.scalers['optimizer_salinity'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        # Gradient Boosting
        self.models['optimizer_salinity'] = GradientBoostingRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
        )

        self.models['optimizer_salinity'].fit(X_train, y_train)
        y_pred = self.models['optimizer_salinity'].predict(X_test)

        # 메트릭 저장
        self.metrics['optimizer_salinity'] = {
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': SALINITY_FEATURES,
        }

        print(f"  MAE: {self.metrics['optimizer_salinity']['mae']:.3f}%")
        print(f"  R2: {self.metrics['optimizer_salinity']['r2']:.3f}")

    def train_time_predictor(self, X: np.ndarray, y: np.ndarray):
        """실시간 시간 예측 모델 학습"""
        print("\n[학습] 실시간 시간 예측 모델 (time_predictor)...")
        print(f"  피처 수: {X.shape[1]}개")

        # 스케일러
        self.scalers['time_predictor'] = StandardScaler()
        X_scaled = self.scalers['time_predictor'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        # 모델 학습
        if HAS_XGBOOST:
            self.models['time_predictor'] = xgb.XGBRegressor(
                n_estimators=150, max_depth=6, learning_rate=0.1, random_state=42
            )
        else:
            self.models['time_predictor'] = GradientBoostingRegressor(
                n_estimators=150, max_depth=6, learning_rate=0.1, random_state=42
            )

        self.models['time_predictor'].fit(X_train, y_train)
        y_pred = self.models['time_predictor'].predict(X_test)

        # 메트릭
        self.metrics['time_predictor'] = {
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': TIME_PREDICTOR_FEATURES,
        }

        print(f"  MAE: {self.metrics['time_predictor']['mae']:.3f}h")
        print(f"  R2: {self.metrics['time_predictor']['r2']:.3f}")

    def prepare_final_salinity_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        최종 염도 예측 모델용 데이터 준비 (v3 핵심)

        입력: 초기염도, 시간, 수온, 배추특성
        출력: 최종 배추 염도 (final_salinity)

        이 모델을 역최적화하여:
        "final_salinity = 1.75%가 되려면 초기염도/시간이 얼마여야 하는가?" 계산
        """
        X = []
        y = []

        for b in batches:
            final_sal = b.get('final_salinity')
            if final_sal is None:
                continue

            cultivar = b.get('cultivar', b.get('cultivar_label', '기타'))
            water_temp = b.get('initial_water_temp', b.get('water_temp', 15))
            initial_salinity = b.get('initial_salinity', 12.0)
            avg_weight = b.get('avg_weight', 3.0)
            firmness = b.get('firmness', 15.0)

            # 시간 계산
            duration = b.get('total_duration_minutes', 0) / 60
            if duration == 0:
                start = datetime.fromisoformat(b['start_time'])
                end = datetime.fromisoformat(b['end_time'])
                duration = (end - start).total_seconds() / 3600

            # 파생변수
            derived = self._compute_derived_features(initial_salinity, water_temp, avg_weight, firmness)

            features = [
                initial_salinity,
                duration,
                water_temp,
                avg_weight,
                firmness,
                b.get('leaf_thickness', 3),
                derived['vant_hoff_osmotic'],
                self.label_encoders['cultivar'].transform([cultivar])[0],
                self.label_encoders['season'].transform([b['season']])[0],
            ]
            X.append(features)
            y.append(final_sal)

        self.feature_names['final_salinity_predictor'] = FINAL_SALINITY_FEATURES
        return np.array(X), np.array(y)

    def train_final_salinity_model(self, X: np.ndarray, y: np.ndarray):
        """최종 염도 예측 모델 학습 (v3 핵심)"""
        print("\n[학습] 최종 염도 예측 모델 (final_salinity_predictor)...")
        print(f"  피처 수: {X.shape[1]}개")
        print(f"  피처: {FINAL_SALINITY_FEATURES}")

        # 스케일러
        self.scalers['final_salinity_predictor'] = StandardScaler()
        X_scaled = self.scalers['final_salinity_predictor'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        # Gradient Boosting
        self.models['final_salinity_predictor'] = GradientBoostingRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            min_samples_split=10, min_samples_leaf=5, random_state=42
        )

        self.models['final_salinity_predictor'].fit(X_train, y_train)
        y_pred = self.models['final_salinity_predictor'].predict(X_test)

        # 메트릭 저장
        self.metrics['final_salinity_predictor'] = {
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred)),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': FINAL_SALINITY_FEATURES,
        }

        print(f"  MAE: {self.metrics['final_salinity_predictor']['mae']:.4f}%")
        print(f"  R2: {self.metrics['final_salinity_predictor']['r2']:.3f}")

        # 피처 중요도 출력
        importances = self.models['final_salinity_predictor'].feature_importances_
        feature_importance = sorted(zip(FINAL_SALINITY_FEATURES, importances), key=lambda x: x[1], reverse=True)
        print("\n  [피처 중요도]")
        for feat, imp in feature_importance[:5]:
            print(f"    {feat}: {imp:.3f}")

    def train_quality_classifier(self, X: np.ndarray, y: np.ndarray):
        """품질 분류 모델 학습"""
        print("\n[학습] 품질 분류 모델 (quality_classifier)...")
        print(f"  피처 수: {X.shape[1]}개")

        # 스케일러
        self.scalers['quality_classifier'] = StandardScaler()
        X_scaled = self.scalers['quality_classifier'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )

        # Gradient Boosting Classifier
        self.models['quality_classifier'] = GradientBoostingClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )

        self.models['quality_classifier'].fit(X_train, y_train)
        y_pred = self.models['quality_classifier'].predict(X_test)

        # 메트릭
        self.metrics['quality_classifier'] = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'f1_weighted': float(f1_score(y_test, y_pred, average='weighted')),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': QUALITY_FEATURES,
        }

        print(f"  Accuracy: {self.metrics['quality_classifier']['accuracy']:.3f}")
        print(f"  F1 (weighted): {self.metrics['quality_classifier']['f1_weighted']:.3f}")

    def save_models(self, version: str = "v2"):
        """학습된 모델 저장"""
        save_path = MODEL_DIR / version
        save_path.mkdir(exist_ok=True)

        # 모델 저장
        for name, model in self.models.items():
            with open(save_path / f"{name}.pkl", 'wb') as f:
                pickle.dump(model, f)

        # 스케일러 저장
        with open(save_path / "scalers.pkl", 'wb') as f:
            pickle.dump(self.scalers, f)

        # 라벨 인코더 저장
        with open(save_path / "label_encoders.pkl", 'wb') as f:
            pickle.dump(self.label_encoders, f)

        # 메트릭 및 피처 정보 저장
        metadata = {
            'version': version,
            'created_at': datetime.now().isoformat(),
            'metrics': self.metrics,
            'feature_names': self.feature_names,
            'changes': [
                'pickling_type 피처 제거 (데이터 누수 해결)',
                'initial_salinity를 시간 예측 피처로 추가',
                'vant_hoff_osmotic 파생변수 추가',
                'weight_firmness 파생변수 추가',
                'Gradient Boosting 모델 적용',
            ]
        }
        with open(save_path / "metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"\n[저장] 모델 저장 완료: {save_path}")
        return str(save_path)

    def load_models(self, version: str = "v2") -> bool:
        """저장된 모델 로드"""
        load_path = MODEL_DIR / version

        # v2가 없으면 v1 시도
        if not load_path.exists():
            load_path = MODEL_DIR / "v1"

        if not load_path.exists():
            print(f"[오류] 모델 경로 없음: {load_path}")
            return False

        try:
            # 모델 로드
            for model_file in load_path.glob("*.pkl"):
                if model_file.name == "scalers.pkl":
                    with open(model_file, 'rb') as f:
                        self.scalers = pickle.load(f)
                elif model_file.name == "label_encoders.pkl":
                    with open(model_file, 'rb') as f:
                        self.label_encoders = pickle.load(f)
                else:
                    name = model_file.stem
                    with open(model_file, 'rb') as f:
                        self.models[name] = pickle.load(f)

            # 메타데이터 로드
            metadata_file = load_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    self.metrics = metadata.get('metrics', {})
                    self.feature_names = metadata.get('feature_names', {})

            print(f"[로드] 모델 로드 완료: {load_path}")
            return True

        except Exception as e:
            print(f"[오류] 모델 로드 실패: {e}")
            return False

    def train_all(self, json_path: str, version: str = "v2"):
        """전체 모델 학습 (v2)"""
        print("="*70)
        print("[시작] ML 모델 학습 (v2 - pickling_type 제거)")
        print("="*70)

        # 데이터 로드
        batches, measurements = self.load_dummy_data(json_path)
        print(f"\n데이터 로드: 배치 {len(batches)}개, 측정 {len(measurements)}개")

        # 1. 시간 예측 모델 (핵심 수정)
        X_dur, y_dur = self.prepare_duration_data(batches)
        print(f"\n시간 예측 데이터: {len(X_dur)}개 샘플")
        self.train_duration_model(X_dur, y_dur)

        # 2. 염도 추천 모델
        X_sal, y_sal = self.prepare_salinity_data(batches)
        print(f"\n염도 추천 데이터: {len(X_sal)}개 샘플 (좋음 등급만)")
        self.train_salinity_model(X_sal, y_sal)

        # 3. 실시간 시간 예측 모델
        X_time, y_time = self.prepare_time_predictor_data(batches, measurements)
        print(f"\n실시간 예측 데이터: {len(X_time)}개 샘플")
        self.train_time_predictor(X_time, y_time)

        # 4. 품질 분류 모델
        X_qual, y_qual = self.prepare_quality_classifier_data(batches)
        print(f"\n품질 분류 데이터: {len(X_qual)}개 샘플")
        self.train_quality_classifier(X_qual, y_qual)

        # 5. 최종 염도 예측 모델 (v3 핵심 - 역최적화용)
        X_final, y_final = self.prepare_final_salinity_data(batches)
        print(f"\n최종 염도 예측 데이터: {len(X_final)}개 샘플")
        self.train_final_salinity_model(X_final, y_final)

        # 모델 저장
        self.save_models(version)

        print("\n" + "="*70)
        print("[완료] 모델 학습 완료")
        print("="*70)

        # 결과 요약
        print("\n[결과 요약]")
        print(f"  시간 예측 R2: {self.metrics['optimizer_duration']['r2']:.3f}")
        print(f"  염도 추천 R2: {self.metrics['optimizer_salinity']['r2']:.3f}")
        print(f"  실시간 예측 R2: {self.metrics['time_predictor']['r2']:.3f}")
        print(f"  품질 분류 Accuracy: {self.metrics['quality_classifier']['accuracy']:.3f}")
        print(f"  최종 염도 예측 R2: {self.metrics['final_salinity_predictor']['r2']:.3f} ★ 핵심 모델")

        return self.metrics


# 학습 스크립트로 실행
if __name__ == "__main__":
    trainer = ModelTrainer()

    # 새 현실적 데이터 경로
    data_path = Path(__file__).parent.parent.parent / "scripts" / "realistic_data_2024_2025.json"

    # 기존 경로 대체
    if not data_path.exists():
        data_path = Path(__file__).parent.parent.parent / "scripts" / "dummy_data_2024.json"

    if data_path.exists():
        trainer.train_all(str(data_path), version="v2")
    else:
        print(f"[오류] 데이터 파일 없음: {data_path}")
        print("먼저 generate_realistic_data.py를 실행하세요.")
