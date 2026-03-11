# 동촌에프에스 절임배추 공정 최적화 시스템 - 파일 매니페스트

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | 동촌에프에스 절임배추 ML 공정 최적화 시스템 |
| **목적** | 절임배추 공정의 최적 조건 추천 및 품질 예측 |
| **버전** | v3 (2026-03-11) |
| **기술스택** | React + TypeScript (프론트), FastAPI + Python (백엔드), Tauri (데스크톱) |

---

## 2. 디렉토리 구조

```
dongchon-ml/
├── src/                          # 프론트엔드 (React + TypeScript)
│   ├── pages/                    # 페이지 컴포넌트
│   ├── components/               # 공통 컴포넌트
│   ├── services/                 # API 서비스
│   ├── stores/                   # 상태 관리
│   └── types/                    # TypeScript 타입 정의
├── backend/                      # 백엔드 (FastAPI + Python)
│   ├── app/
│   │   ├── api/                  # API 엔드포인트
│   │   ├── ml/                   # ML 모델
│   │   ├── models/               # DB 모델
│   │   ├── schemas/              # Pydantic 스키마
│   │   └── services/             # 비즈니스 로직
│   └── scripts/                  # 데이터 생성/시뮬레이션
├── src-tauri/                    # 데스크톱 앱 (Tauri)
└── docs/                         # 문서
```

---

## 3. 프론트엔드 파일 목록

### 3.1 페이지 (src/pages/)

| 파일 | 라인수 | 역할 | 주요 의존성 |
|------|--------|------|-------------|
| `Dashboard.tsx` | 250 | 메인 대시보드 - 탱크 현황 모니터링 | TankCard, TankDetailModal, tanksApi |
| `Optimize.tsx` | 713 | 공정 최적화 - 배치 시작/완료 시점 결정 | mlApi, batchesApi |
| `History.tsx` | 1178 | 이력 조회 - 과거 배치 검색/분석 | batchesApi, Recharts |
| `Settings.tsx` | 199 | 설정 - 시스템 설정 관리 | - |

### 3.2 컴포넌트 (src/components/)

| 파일 | 라인수 | 역할 | Props |
|------|--------|------|-------|
| `Layout.tsx` | 65 | 전체 레이아웃 - 네비게이션, 사이드바 | children |
| `TankCard.tsx` | 336 | 탱크 카드 - 개별 탱크 상태 표시 | tank, onSelect |
| `TankDetailModal.tsx` | 410 | 탱크 상세 모달 - 상세정보, ML 예측, 차트 | batch, onClose |
| `ChatPanel.tsx` | 188 | 채팅 패널 - Claude AI 채팅 | - |
| `ChatSidebar.tsx` | 224 | 채팅 사이드바 - 채팅 UI | - |
| `InsightPanel.tsx` | 108 | 인사이트 패널 - AI 분석 결과 표시 | insight |

### 3.3 서비스/유틸 (src/)

| 파일 | 역할 |
|------|------|
| `services/api.ts` | API 클라이언트 (tanksApi, batchesApi, mlApi, insightApi) |
| `stores/useStore.ts` | Zustand 전역 상태 관리 |
| `types/index.ts` | TypeScript 인터페이스 정의 |
| `App.tsx` | 앱 진입점, 라우팅 |
| `main.tsx` | React 렌더링 |

---

## 4. 백엔드 파일 목록

### 4.1 API 엔드포인트 (backend/app/api/)

| 파일 | 라인수 | 역할 | 주요 엔드포인트 |
|------|--------|------|-----------------|
| `ml.py` | 676 | ML 예측 API | /ml/optimize, /ml/predict-time, /ml/predict-quality, /ml/completion-decision |
| `batches.py` | 141 | 배치 CRUD | /batches (GET, POST, PUT) |
| `tanks.py` | 77 | 탱크 조회 | /tanks (GET) |
| `measurements.py` | 113 | 측정 기록 | /measurements (GET, POST) |
| `insight.py` | 433 | AI 인사이트 | /insight, /chat |

### 4.2 ML 모델 (backend/app/ml/)

| 파일 | 라인수 | 역할 |
|------|--------|------|
| `models.py` | 1103 | ML 모델 클래스 (ProcessOptimizer, TimePredictor, QualityClassifier) |
| `trainer.py` | 725 | 모델 학습 스크립트 |

### 4.3 DB 모델/스키마 (backend/app/)

| 파일 | 역할 |
|------|------|
| `models/models.py` | SQLAlchemy ORM 모델 (Batch, Measurement, Tank, PredictionLog) |
| `schemas/schemas.py` | Pydantic 스키마 (요청/응답 검증) |
| `schemas/ml_schemas.py` | ML API 전용 스키마 |
| `database.py` | DB 연결 설정 |
| `config.py` | 환경 설정 |
| `main.py` | FastAPI 앱 진입점 |

### 4.4 스크립트 (backend/scripts/)

| 파일 | 역할 |
|------|------|
| `generate_realistic_data.py` | 물리 모델 기반 학습 데이터 생성 |
| `live_simulator.py` | 실시간 절임 시뮬레이터 |
| `seed_history.py` | DB 초기 데이터 시딩 |
| `realistic_data_2024_2025.json` | 생성된 학습 데이터 (520 배치) |

---

## 5. ML 모델 파일 (backend/app/ml/saved_models/v3/)

| 파일 | 용도 | 성능 지표 |
|------|------|-----------|
| `optimizer_duration.pkl` | 절임 시간 예측 모델 | R² = 0.961, MAE = 1.32h |
| `optimizer_salinity.pkl` | 염도 추천 (폴백용) | R² = -0.43 (미사용, 물리모델 대체) |
| `time_predictor.pkl` | 실시간 잔여 시간 예측 | R² = 0.978, MAE = 0.97h |
| `quality_classifier.pkl` | 품질 등급 분류 | Accuracy = 0.971, F1 = 0.971 |
| `final_salinity_predictor.pkl` | 최종 염도 예측 | R² = 0.377 |
| `scalers.pkl` | 피처 정규화 (StandardScaler) | - |
| `label_encoders.pkl` | 라벨 인코딩 (품종, 계절) | - |
| `metadata.json` | 모델 메타데이터 (버전, 피처, 성능) | - |

### 5.1 모델별 피처 목록

#### optimizer_duration (12개 피처)
```
cultivar_encoded, avg_weight, firmness, leaf_thickness, season_encoded,
room_temp, initial_water_temp, initial_salinity, outdoor_temp,
added_salt_amount, vant_hoff_osmotic, weight_firmness
```

#### time_predictor (7개 피처)
```
elapsed_hours, salinity_avg, initial_salinity, water_temp,
accumulated_temp, salinity_diff, osmotic_index
```

#### quality_classifier (8개 피처)
```
final_salinity, quality_bending, duration_hours, cultivar_encoded,
season_encoded, avg_weight, initial_salinity, initial_water_temp
```

#### final_salinity_predictor (9개 피처)
```
initial_salinity, duration_hours, initial_water_temp, avg_weight,
firmness, leaf_thickness, vant_hoff_osmotic, cultivar_encoded, season_encoded
```

---

## 6. 설정 파일

### 6.1 프론트엔드

| 파일 | 역할 |
|------|------|
| `package.json` | npm 의존성, 스크립트 |
| `tsconfig.json` | TypeScript 설정 |
| `vite.config.ts` | Vite 빌드 설정 |
| `tailwind.config.js` | Tailwind CSS 설정 |

### 6.2 백엔드

| 파일 | 역할 |
|------|------|
| `requirements.txt` | Python 의존성 |
| `dongchon.db` | SQLite 데이터베이스 |

### 6.3 데스크톱 앱

| 파일 | 역할 |
|------|------|
| `src-tauri/tauri.conf.json` | Tauri 앱 설정 (창 크기, 타이틀 등) |
| `src-tauri/Cargo.toml` | Rust 의존성 |

---

## 7. 주요 의존성

### 7.1 프론트엔드 (package.json)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| react | 19.x | UI 프레임워크 |
| react-router-dom | 7.x | 라우팅 |
| @tanstack/react-query | 6.x | 서버 상태 관리 |
| zustand | 5.x | 클라이언트 상태 관리 |
| recharts | 2.x | 차트 |
| lucide-react | - | 아이콘 |
| tailwindcss | 4.x | 스타일링 |
| @tauri-apps/api | 2.x | Tauri 연동 |

### 7.2 백엔드 (requirements.txt)

| 패키지 | 용도 |
|--------|------|
| fastapi | 웹 프레임워크 |
| uvicorn | ASGI 서버 |
| sqlalchemy | ORM |
| pydantic | 데이터 검증 |
| scikit-learn | ML 모델 |
| pandas | 데이터 처리 |
| numpy | 수치 연산 |
| joblib | 모델 직렬화 |

---

## 8. 실행 방법

### 8.1 백엔드 실행
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 8.2 프론트엔드 실행
```bash
npm install
npm run dev
```

### 8.3 데스크톱 앱 실행
```bash
npm run tauri dev
```

### 8.4 모델 재학습
```bash
cd backend
python -m scripts.generate_realistic_data  # 데이터 생성
python -c "from app.ml.trainer import ModelTrainer; t = ModelTrainer(); t.train_all('scripts/realistic_data_2024_2025.json', 'v3')"
```

---

## 9. 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| v1 | 2026-03-10 | 초기 버전, 규칙 기반 추천 |
| v2 | 2026-03-10 | ML 모델 학습, pickling_type 제거 |
| v3 | 2026-03-11 | 물리 모델 기반 역최적화, 배추 특성 반영 강화 |
