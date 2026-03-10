"""
ML 모델 학습 모듈
- 더미 데이터 또는 실제 데이터로 모델 학습
- 학습된 모델 저장/로드
"""

import json
import pickle
import os
from datetime import datetime
from typing import Tuple, Optional
import numpy as np
from pathlib import Path

# ML 라이브러리
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


# 모델 저장 경로
MODEL_DIR = Path(__file__).parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)


class ModelTrainer:
    """ML 모델 학습 및 관리 클래스"""

    def __init__(self):
        self.label_encoders = {}
        self.scalers = {}
        self.models = {}
        self.metrics = {}

    def load_dummy_data(self, json_path: str) -> Tuple[list, list]:
        """더미 데이터 JSON 로드"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['batches'], data['measurements']

    def prepare_optimizer_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        공정 최적화 모델용 데이터 준비
        입력: 배추 특성 + 환경
        출력: 최적 염도, 절임 시간
        """
        X = []
        y_salinity = []
        y_duration = []

        # 라벨 인코더 초기화
        if 'cultivar' not in self.label_encoders:
            self.label_encoders['cultivar'] = LabelEncoder()
            self.label_encoders['season'] = LabelEncoder()
            self.label_encoders['pickling_type'] = LabelEncoder()

            # 모든 품종과 계절 학습
            all_cultivars = list(set(b.get('cultivar', b.get('cultivar_label', '기타')) for b in batches))
            all_seasons = list(set(b['season'] for b in batches))
            all_pickling_types = list(set(b.get('pickling_type', '하루절임') for b in batches))
            self.label_encoders['cultivar'].fit(all_cultivars)
            self.label_encoders['season'].fit(all_seasons)
            self.label_encoders['pickling_type'].fit(all_pickling_types)

        for b in batches:
            # '좋음' 등급 데이터만 사용 (최적 조건)
            if b['quality_grade'] == '좋음':
                cultivar = b.get('cultivar', b.get('cultivar_label', '기타'))
                features = [
                    self.label_encoders['cultivar'].transform([cultivar])[0],
                    b['avg_weight'],
                    b['firmness'],
                    b['leaf_thickness'],
                    self.label_encoders['season'].transform([b['season']])[0],
                    b['room_temp'],
                    b.get('initial_water_temp', b.get('water_temp', 15)),
                    self.label_encoders['pickling_type'].transform([b.get('pickling_type', '하루절임')])[0],
                ]
                X.append(features)
                y_salinity.append(b['initial_salinity'])

                # 절임 시간 (분 -> 시간)
                duration = b.get('total_duration_minutes', 0) / 60
                if duration == 0:
                    start = datetime.fromisoformat(b['start_time'])
                    end = datetime.fromisoformat(b['end_time'])
                    duration = (end - start).total_seconds() / 3600
                y_duration.append(duration)

        return np.array(X), np.array(y_salinity), np.array(y_duration)

    def prepare_time_predictor_data(self, batches: list, measurements: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        시간 예측 모델용 데이터 준비
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

            # 각 측정 시점에서의 특성과 남은 시간
            for m in meas_list[:-1]:  # 마지막 측정 제외
                elapsed = m.get('elapsed_minutes', 0) / 60
                remaining = total_duration - elapsed

                if remaining > 0:
                    features = [
                        elapsed,
                        m.get('salinity_avg', (m.get('salinity_top', 0) + m.get('salinity_bottom', 0)) / 2),
                        b['initial_salinity'],
                        m.get('water_temp', 15),
                        elapsed * m.get('water_temp', 15),  # 적산온도 근사
                        m.get('salinity_diff', abs(m.get('salinity_top', 0) - m.get('salinity_bottom', 0))),
                        m.get('salinity_avg', 10) * 0.1,  # 삼투압 근사
                    ]
                    X.append(features)
                    y.append(remaining)

        return np.array(X), np.array(y)

    def prepare_quality_classifier_data(self, batches: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        품질 분류 모델용 데이터 준비
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

            features = [
                b.get('final_salinity', b.get('final_cabbage_salinity', 1.7)),
                b.get('quality_bending', b.get('bend_test', 3)),
                duration,
                self.label_encoders['cultivar'].transform([cultivar])[0],
                self.label_encoders['season'].transform([b['season']])[0],
                b['avg_weight'],
                b['initial_salinity'],
                b.get('initial_water_temp', 15),
            ]
            X.append(features)
            y.append(self.label_encoders['quality'].transform([b['quality_grade']])[0])

        return np.array(X), np.array(y)

    def train_optimizer(self, X: np.ndarray, y_salinity: np.ndarray, y_duration: np.ndarray):
        """공정 최적화 모델 학습"""
        print("\n[학습] 공정 최적화 모델...")

        # 스케일러
        self.scalers['optimizer'] = StandardScaler()
        X_scaled = self.scalers['optimizer'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_sal_train, y_sal_test, y_dur_train, y_dur_test = train_test_split(
            X_scaled, y_salinity, y_duration, test_size=0.2, random_state=42
        )

        # 염도 예측 모델
        if HAS_XGBOOST:
            self.models['optimizer_salinity'] = xgb.XGBRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
            )
        else:
            self.models['optimizer_salinity'] = RandomForestRegressor(
                n_estimators=100, max_depth=10, random_state=42
            )

        self.models['optimizer_salinity'].fit(X_train, y_sal_train)
        y_sal_pred = self.models['optimizer_salinity'].predict(X_test)

        # 시간 예측 모델
        if HAS_XGBOOST:
            self.models['optimizer_duration'] = xgb.XGBRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
            )
        else:
            self.models['optimizer_duration'] = RandomForestRegressor(
                n_estimators=100, max_depth=10, random_state=42
            )

        self.models['optimizer_duration'].fit(X_train, y_dur_train)
        y_dur_pred = self.models['optimizer_duration'].predict(X_test)

        # 메트릭 저장
        self.metrics['optimizer'] = {
            'salinity_mae': mean_absolute_error(y_sal_test, y_sal_pred),
            'salinity_r2': r2_score(y_sal_test, y_sal_pred),
            'duration_mae': mean_absolute_error(y_dur_test, y_dur_pred),
            'duration_r2': r2_score(y_dur_test, y_dur_pred),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
        }

        print(f"  염도 MAE: {self.metrics['optimizer']['salinity_mae']:.3f}")
        print(f"  염도 R2: {self.metrics['optimizer']['salinity_r2']:.3f}")
        print(f"  시간 MAE: {self.metrics['optimizer']['duration_mae']:.3f}h")
        print(f"  시간 R2: {self.metrics['optimizer']['duration_r2']:.3f}")

    def train_time_predictor(self, X: np.ndarray, y: np.ndarray):
        """시간 예측 모델 학습"""
        print("\n[학습] 시간 예측 모델...")

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
            self.models['time_predictor'] = RandomForestRegressor(
                n_estimators=150, max_depth=12, random_state=42
            )

        self.models['time_predictor'].fit(X_train, y_train)
        y_pred = self.models['time_predictor'].predict(X_test)

        # 메트릭
        self.metrics['time_predictor'] = {
            'mae': mean_absolute_error(y_test, y_pred),
            'r2': r2_score(y_test, y_pred),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
        }

        print(f"  MAE: {self.metrics['time_predictor']['mae']:.3f}h")
        print(f"  R2: {self.metrics['time_predictor']['r2']:.3f}")

    def train_quality_classifier(self, X: np.ndarray, y: np.ndarray):
        """품질 분류 모델 학습"""
        print("\n[학습] 품질 분류 모델...")

        # 스케일러
        self.scalers['quality_classifier'] = StandardScaler()
        X_scaled = self.scalers['quality_classifier'].fit_transform(X)

        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )

        # 모델 학습
        if HAS_XGBOOST:
            self.models['quality_classifier'] = xgb.XGBClassifier(
                n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
            )
        else:
            self.models['quality_classifier'] = RandomForestClassifier(
                n_estimators=100, max_depth=10, random_state=42
            )

        self.models['quality_classifier'].fit(X_train, y_train)
        y_pred = self.models['quality_classifier'].predict(X_test)

        # 메트릭
        self.metrics['quality_classifier'] = {
            'accuracy': accuracy_score(y_test, y_pred),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
        }

        print(f"  Accuracy: {self.metrics['quality_classifier']['accuracy']:.3f}")

    def save_models(self, version: str = "v1"):
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

        # 메트릭 저장
        with open(save_path / "metrics.json", 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)

        print(f"\n[저장] 모델 저장 완료: {save_path}")
        return str(save_path)

    def load_models(self, version: str = "v1") -> bool:
        """저장된 모델 로드"""
        load_path = MODEL_DIR / version

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

            # 메트릭 로드
            metrics_file = load_path / "metrics.json"
            if metrics_file.exists():
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    self.metrics = json.load(f)

            print(f"[로드] 모델 로드 완료: {load_path}")
            return True

        except Exception as e:
            print(f"[오류] 모델 로드 실패: {e}")
            return False

    def train_all(self, json_path: str, version: str = "v1"):
        """전체 모델 학습"""
        print("="*60)
        print("[시작] ML 모델 학습")
        print("="*60)

        # 데이터 로드
        batches, measurements = self.load_dummy_data(json_path)
        print(f"\n데이터 로드: 배치 {len(batches)}개, 측정 {len(measurements)}개")

        # 1. 공정 최적화 모델
        X_opt, y_sal, y_dur = self.prepare_optimizer_data(batches)
        self.train_optimizer(X_opt, y_sal, y_dur)

        # 2. 시간 예측 모델
        X_time, y_time = self.prepare_time_predictor_data(batches, measurements)
        self.train_time_predictor(X_time, y_time)

        # 3. 품질 분류 모델
        X_qual, y_qual = self.prepare_quality_classifier_data(batches)
        self.train_quality_classifier(X_qual, y_qual)

        # 모델 저장
        self.save_models(version)

        print("\n" + "="*60)
        print("[완료] 모델 학습 완료")
        print("="*60)

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
        trainer.train_all(str(data_path), version="v1")
    else:
        print(f"[오류] 데이터 파일 없음: {data_path}")
        print("먼저 generate_realistic_data.py를 실행하세요.")
