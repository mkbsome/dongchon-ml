# 동촌에프에스 절임 공정 최적화 시스템

AI 기반 김치 절임 공정 모니터링 및 최적화 데스크톱 애플리케이션

## 프로젝트 구조

```
dongchon-ml/
├── src/                    # React 프론트엔드
│   ├── components/         # UI 컴포넌트
│   ├── pages/              # 페이지 (Dashboard, Optimize, History)
│   ├── services/           # API 연동
│   ├── stores/             # Zustand 상태관리
│   └── types/              # TypeScript 타입
├── src-tauri/              # Tauri 데스크톱 래퍼
├── backend/                # FastAPI 백엔드
│   ├── app/
│   │   ├── api/            # API 엔드포인트
│   │   ├── ml/             # ML 모델 (Gradient Boosting)
│   │   ├── models/         # SQLAlchemy 모델
│   │   └── schemas/        # Pydantic 스키마
│   ├── scripts/            # 더미 데이터 생성
│   └── sql/                # DB 스키마
└── package.json
```

## 기술 스택

### 프론트엔드
- React 19 + TypeScript
- Tauri 2.0 (데스크톱)
- Tailwind CSS
- Zustand (상태관리)
- Recharts (차트)

### 백엔드
- FastAPI
- SQLite / PostgreSQL
- SQLAlchemy

### ML 모델
- Gradient Boosting (scikit-learn)
- 3개 예측 모델:
  - 염도 예측 (R² = 0.925)
  - 품질 분류 (F1 = 0.852)
  - 시간 예측 (R² = 0.913)

## 설치 및 실행

### 1. 백엔드 설정

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에서 ANTHROPIC_API_KEY 설정

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

### 2. 프론트엔드 설정

```bash
npm install

# 개발 서버
npm run dev

# Tauri 데스크톱 앱
npm run tauri:dev
```

## API 엔드포인트

### ML API
| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/ml/optimize` | 최적 공정 조건 추천 |
| `POST /api/ml/predict/time` | 잔여 시간 예측 |
| `POST /api/ml/predict/quality` | 품질 등급 예측 |
| `GET /api/ml/status` | 모델 상태 조회 |
| `POST /api/ml/completion-decision` | 완료 시점 결정 |
| `POST /api/ml/anomaly-check` | 이상 감지 |

### 데이터 API
| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/tanks/` | 절임조 목록 |
| `GET /api/batches/` | 배치 목록 |
| `POST /api/insight/chat` | Claude 채팅 |

## ML 모델 정보

학습된 모델은 `backend/app/ml/saved_models/v1/`에 저장:
- `optimizer_salinity.pkl`: 염도 최적화 모델
- `optimizer_duration.pkl`: 시간 최적화 모델
- `quality_classifier.pkl`: 품질 분류 모델
- `time_predictor.pkl`: 시간 예측 모델

## 라이선스

Private - 충북TP AI 파일럿 프로젝트
