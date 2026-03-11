# 동촌에프에스 절임배추 공정 최적화 시스템 - 기능정의서

## 문서 정보

| 항목 | 내용 |
|------|------|
| **버전** | v1.0 |
| **작성일** | 2026-03-11 |
| **API 버전** | /api |
| **백엔드** | FastAPI + Python 3.11 |
| **프론트엔드** | React 19 + TypeScript |

---

## 1. 시스템 개요

### 1.1 기능 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            프론트엔드 (React)                                │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│  대시보드     │   최적화     │   이력조회    │   설정       │  AI 채팅       │
│  Dashboard   │  Optimize    │   History    │  Settings   │  ChatSidebar   │
├──────────────┴──────────────┴──────────────┴──────────────┴────────────────┤
│                          API 서비스 레이어 (api.ts)                          │
│  tanksApi | batchesApi | mlApi | insightApi | chatApi                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                            백엔드 (FastAPI)                                  │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│  /tanks      │  /batches    │  /ml         │ /measurements│  /insight      │
│  절임조 관리  │  배치 관리    │  ML 예측     │  측정 기록    │  AI 인사이트   │
├──────────────┴──────────────┴──────────────┴──────────────┴────────────────┤
│                            ML 모델 레이어                                    │
│  ProcessOptimizer | TimePredictor | QualityClassifier | PhysicsModel       │
├─────────────────────────────────────────────────────────────────────────────┤
│                           데이터 레이어 (SQLite)                             │
│  Tank | Batch | Measurement | PredictionLog | InsightLog                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 주요 기능 목록

| 기능 영역 | 핵심 기능 | 설명 |
|----------|----------|------|
| **대시보드** | 탱크 모니터링 | 7개 절임조 실시간 상태 표시 |
| | ML 예측 표시 | 잔여 시간, 예상 품질 표시 |
| | 이상 감지 | 비정상 진행 배치 경고 |
| **최적화** | 배치 시작 추천 | 최적 초기 염도/절임 시간 추천 |
| | 완료 시점 결정 | 시나리오별 품질 예측 |
| | 염도-시간 연동 | 염도 조정 시 시간 자동 재계산 |
| **이력조회** | 배치 이력 검색 | 필터링, 정렬, 비교 |
| | 성공 요인 분석 | 등급별 조건 분석 |
| | 절임조별 성과 | 탱크별 A등급률 비교 |
| **AI 채팅** | 자연어 질의 | Claude 기반 대화형 상담 |
| | 컨텍스트 분석 | 현재 페이지/탱크 정보 활용 |

---

## 2. 대시보드 기능

### 2.1 탱크 현황 조회

#### 2.1.1 API: 전체 탱크 조회

```http
GET /api/tanks/
```

**응답**:
```json
[
  {
    "id": 1,
    "name": "절임조 1",
    "capacity": 2000,
    "is_active": true
  },
  ...
]
```

**프론트엔드 처리**:
- `tanksApi.getAll()` 호출
- 자동 갱신: 30초 간격 (설정 가능)
- 연결 실패 시 더미 데이터 표시

#### 2.1.2 API: 활성 배치 조회

```http
GET /api/batches/?status=active
```

**응답**:
```json
[
  {
    "id": 1,
    "tank_id": 1,
    "status": "active",
    "start_time": "2026-03-11T08:00:00",
    "cultivar": "해남",
    "avg_weight": 3.2,
    "initial_salinity": 12.5,
    "season": "겨울",
    "measurements": [...]
  },
  ...
]
```

### 2.2 ML 예측 표시 (TankCard)

#### 2.2.1 잔여 시간 예측

```http
POST /api/ml/predict/time
```

**요청**:
```json
{
  "batch_id": 1
}
```

**응답**:
```json
{
  "remaining_hours": 18.5,
  "predicted_end_time": "2026-03-12T02:30:00",
  "confidence": 0.92,
  "current_progress": 45
}
```

**계산 로직** (`TimePredictor`):
1. 배치 시작 시간에서 경과 시간 계산
2. 현재 염도와 초기 염도의 차이 분석
3. 수온, 적산 온도 기반 잔여 시간 예측
4. 모델 R² = 0.978, MAE = 0.97h

#### 2.2.2 품질 예측

```http
POST /api/ml/predict/quality
```

**요청**:
```json
{
  "batch_id": 1,
  "final_salinity": 1.8,
  "bend_test": 85
}
```

**응답**:
```json
{
  "predicted_grade": "A",
  "probabilities": {
    "A": 0.87,
    "B": 0.10,
    "C": 0.03
  },
  "confidence": 0.92,
  "risk_factors": []
}
```

**품질 기준**:
| 등급 | 최종 염도 | 휘어짐 점수 |
|------|----------|-----------|
| A | 1.5-2.0% | 85+ |
| B | 1.2-1.5% 또는 2.0-2.5% | 70-84 |
| C | <1.2% 또는 >2.5% | <70 |

#### 2.2.3 이상 감지

```http
POST /api/ml/anomaly-check
```

**요청**:
```json
{
  "batch_id": 1
}
```

**응답**:
```json
{
  "batch_id": 1,
  "is_anomaly": true,
  "anomaly_score": 0.75,
  "current_vs_expected": {
    "salinity_diff": 1.2,
    "temp_diff": 2.5
  },
  "similar_batches": [
    {
      "batch_id": 45,
      "similarity_score": 0.89,
      "quality_grade": "A"
    }
  ],
  "alerts": [
    "염도 침투 속도가 예상보다 느림",
    "유사 배치 대비 수온이 낮음"
  ],
  "generated_at": "2026-03-11T14:30:00"
}
```

### 2.3 탱크 상세 모달

#### 2.3.1 측정 이력 조회

```http
GET /api/batches/{batch_id}/
```

**응답 (BatchWithMeasurements)**:
```json
{
  "id": 1,
  "tank_id": 1,
  ...
  "measurements": [
    {
      "id": 1,
      "timestamp": "2026-03-11T10:00:00",
      "top_salinity": 8.5,
      "bottom_salinity": 9.2,
      "water_temp": 14.2,
      "salinity_avg": 8.85,
      "salinity_diff": -0.7,
      "accumulated_temp": 28.4
    },
    ...
  ]
}
```

#### 2.3.2 인터랙티브 차트 렌더링

**데이터 처리**:
```typescript
// SVG 좌표 계산
const pointsArray = data.map((val, i) => ({
  x: padding + (i / (data.length - 1)) * (width - 2 * padding),
  y: height - padding - ((val - min) / range) * (height - 2 * padding),
  value: val
}));
```

**표시 항목**:
- 상단 염도 추이 (파란색)
- 하단 염도 추이 (녹색)
- 수온 추이 (주황색)

#### 2.3.3 AI 분석 요청

**프롬프트 생성** (`handleAIAnalysis`):
```typescript
const prompt = `[${tank.name}] 절임 상태 분석을 요청합니다.

현재 상태:
- 품종: ${batch.cultivar}
- 평균 무게: ${batch.avg_weight}kg
- 초기 염도: ${batch.initial_salinity}%
- 진행률: ${progress}%
- 경과 시간: ${elapsedHours}시간

현재 측정값:
- 상단 염도: ${topSalinity.toFixed(1)}%
- 하단 염도: ${bottomSalinity.toFixed(1)}%
- 평균 염도: ${currentSalinity.toFixed(1)}%
- 수온: ${waterTemp.toFixed(1)}°C

위 정보를 바탕으로 현재 절임 상태를 분석하고,
최적의 완료 시점과 권장 조치사항을 알려주세요.`;

sendAnalysisRequest(prompt, measurementContext);
```

---

## 3. 최적화 기능

### 3.1 배치 시작 최적화 (Start Tab)

#### 3.1.1 API: 공정 최적화

```http
POST /api/ml/optimize
```

**요청**:
```json
{
  "cultivar": "해남",
  "avg_weight": 3.2,
  "firmness": 15,
  "leaf_thickness": 3.0,
  "season": "겨울",
  "room_temp": 18,
  "water_temp": 14,
  "target_quality": "A"
}
```

**응답**:
```json
{
  "recommended_salinity": 11.5,
  "recommended_duration": 36.2,
  "predicted_quality": "A",
  "quality_probability": {
    "A": 0.72,
    "B": 0.25,
    "C": 0.03
  },
  "confidence": 0.91,
  "reasoning": "겨울철 저온(14°C) 조건에서 해남 품종 3.2kg 배추의 경우...",
  "expected_final_salinity": 1.85,
  "is_optimal": true
}
```

#### 3.1.2 물리 모델 기반 역최적화

**ProcessOptimizer.predict() 로직**:

```python
# 1. 계절별 기본 수온
season_temp = {'봄': 14, '여름': 22, '가을': 16, '겨울': 10}
water_temp = water_temp or season_temp.get(season, 15)

# 2. 염도 후보 탐색 (0.1% 단위)
for sal_candidate in np.arange(9.0, 15.01, 0.1):
    for dur_candidate in np.arange(dur_min, dur_max, 1.0):

        # 3. 배추 특성 효과 계산
        weight_effect = max(0.75, min(1.25, 1.0 - (avg_weight - 3.0) * 0.12))
        firmness_effect = max(0.75, min(1.25, 1.0 - (firmness - 15) * 0.015))
        thickness_effect = max(0.85, min(1.15, 1.0 - (leaf_thickness - 3) * 0.04))

        total_effect = weight_effect * firmness_effect * thickness_effect

        # 4. 삼투 평형 계산 (Van't Hoff 방정식)
        base_absorption = 0.17
        equilibrium = sal_candidate * base_absorption * total_effect

        # 5. 침투 속도 계산 (Fick's Law)
        temp_factor = math.exp((water_temp - 15) * 0.05)
        k = 0.035 * temp_factor / (weight_effect * firmness_effect * thickness_effect)
        penetration = 1 - math.exp(-k * dur_candidate)

        # 6. 최종 염도 예측
        final_salinity = 0.2 + (equilibrium - 0.2) * penetration

        # 7. 목표 범위(1.5-2.0%) 내 최적 조합 선택
        if 1.5 <= final_salinity <= 2.0:
            candidates.append((sal_candidate, dur_candidate, final_salinity))
```

#### 3.1.3 염도 조정 시 시간 재계산

```http
GET /api/ml/recalculate-duration?salinity=12.0&season=겨울&water_temp=10&avg_weight=3.2
```

**응답**:
```json
{
  "adjusted_salinity": 12.0,
  "recalculated_duration": 38.5,
  "base_duration": 46.0,
  "duration_change": -7.5,
  "direction": "높은 염도로 인해 절임 시간 단축",
  "water_temp": 10,
  "season": "겨울"
}
```

**프론트엔드 처리** (`handleSalinityAdjust`):
```typescript
const handleSalinityAdjust = async (newSalinity: number) => {
  setAdjustedSalinity(newSalinity);
  setIsRecalculating(true);

  try {
    const response = await mlApi.recalculateDuration({
      salinity: newSalinity,
      season: formData.season,
      water_temp: formData.water_temp,
      avg_weight: formData.avg_weight,
      base_duration: result.recommended_duration
    });
    setAdjustedDuration(response.recalculated_duration);
  } finally {
    setIsRecalculating(false);
  }
};
```

### 3.2 완료 시점 결정 (Completion Tab)

#### 3.2.1 API: 완료 시점 분석

```http
POST /api/ml/completion-decision
```

**요청**:
```json
{
  "batch_id": 1
}
```

**응답**:
```json
{
  "batch_id": 1,
  "current_status": {
    "elapsed_hours": 18.5,
    "current_salinity": 3.2,
    "initial_salinity": 12.5,
    "water_temp": 14.5,
    "cultivar": "해남",
    "season": "겨울"
  },
  "scenarios": [
    {
      "hours_from_now": 0,
      "predicted_salinity": 3.20,
      "predicted_grade": "B",
      "grade_probabilities": {"A": 0.65, "B": 0.30, "C": 0.05},
      "confidence": 0.88,
      "is_recommended": false
    },
    {
      "hours_from_now": 2,
      "predicted_salinity": 2.80,
      "predicted_grade": "A",
      "grade_probabilities": {"A": 0.80, "B": 0.17, "C": 0.03},
      "confidence": 0.91,
      "is_recommended": false
    },
    {
      "hours_from_now": 4,
      "predicted_salinity": 2.40,
      "predicted_grade": "A",
      "grade_probabilities": {"A": 0.87, "B": 0.11, "C": 0.02},
      "confidence": 0.93,
      "is_recommended": true
    },
    {
      "hours_from_now": 6,
      "predicted_salinity": 2.10,
      "predicted_grade": "A",
      "grade_probabilities": {"A": 0.82, "B": 0.15, "C": 0.03},
      "confidence": 0.90,
      "is_recommended": false
    }
  ],
  "recommendation": "4시간 후 완료를 추천합니다. A등급 확률 87%로 최적의 결과가 예상됩니다.",
  "optimal_scenario_index": 2,
  "generated_at": "2026-03-11T14:30:00"
}
```

#### 3.2.2 시나리오 생성 로직

```python
# 시나리오 생성 (0h, +2h, +4h, +6h)
scenario_hours = [0, 2, 4, 6]

for add_hours in scenario_hours:
    # 예상 시점의 총 경과 시간
    total_hours = elapsed_hours + add_hours

    # 예상 염도 (선형 감소 추정)
    predicted_salinity = max(1.5, current_salinity - salinity_drop_rate * add_hours)

    # 휘어짐 점수 추정 (시간이 지날수록 향상)
    predicted_bend = min(90, bend_test + add_hours * 2)

    # 품질 예측
    quality_result = quality_classifier.predict(
        final_salinity=predicted_salinity,
        bend_test=predicted_bend,
        elapsed_hours=total_hours,
        cultivar=batch.cultivar,
        season=batch.season
    )

    # 최고 A등급 확률 시나리오 선택
    if quality_result.probabilities['A'] > best_a_prob:
        best_index = i
```

---

## 4. 이력조회 기능

### 4.1 배치 이력 검색

#### 4.1.1 API: 완료 배치 조회

```http
GET /api/batches/?status=completed&limit=500
```

**응답**:
```json
[
  {
    "id": 1,
    "tank_id": 1,
    "status": "completed",
    "start_time": "2026-03-10T08:00:00",
    "end_time": "2026-03-11T06:00:00",
    "cultivar": "해남",
    "avg_weight": 3.2,
    "initial_salinity": 12.5,
    "final_cabbage_salinity": 1.85,
    "bend_test": 87,
    "quality_grade": "A",
    "season": "겨울"
  },
  ...
]
```

#### 4.1.2 프론트엔드 필터링

```typescript
const filteredBatches = useMemo(() => {
  let result = batches.filter((batch) => {
    // 검색어 매칭
    const matchesSearch =
      batch.cultivar?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      batch.tank_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      batch.batch_code?.toLowerCase().includes(searchTerm.toLowerCase());

    // 등급 필터
    const matchesGrade = gradeFilter === 'all' || batch.quality_grade === gradeFilter;

    return matchesSearch && matchesGrade;
  });

  // 정렬
  result.sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case 'start_time':
        comparison = new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
        break;
      case 'tank_id':
        comparison = a.tank_id - b.tank_id;
        break;
      case 'quality_grade':
        comparison = (a.quality_grade || '').localeCompare(b.quality_grade || '');
        break;
    }
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  return result;
}, [batches, searchTerm, gradeFilter, sortField, sortOrder]);
```

### 4.2 통계 계산

#### 4.2.1 전체 통계

```typescript
const stats = useMemo(() => {
  const gradeA = batches.filter((b) => b.quality_grade === 'A').length;
  const gradeB = batches.filter((b) => b.quality_grade === 'B').length;
  const gradeC = batches.filter((b) => b.quality_grade === 'C').length;
  const avgDuration = batches.reduce((acc, b) => acc + b.duration_hours, 0) / batches.length;

  const salinityDrops = batches
    .filter((b) => b.initial_salinity && b.final_salinity)
    .map((b) => b.initial_salinity - b.final_salinity);
  const avgSalinityDrop = salinityDrops.reduce((a, b) => a + b, 0) / salinityDrops.length;

  return {
    total: batches.length,
    gradeA,
    gradeB,
    gradeC,
    avgDuration,
    avgSalinityDrop,
    predictionAccuracy: 87  // ML 모델 검증 결과
  };
}, [batches]);
```

#### 4.2.2 조건별 분석

```typescript
// 초기 염도별 A등급 비율
const salinityStats = salinityRanges.map((range) => {
  const filtered = batches.filter(
    (b) => b.initial_salinity >= range.min && b.initial_salinity < range.max
  );
  const gradeA = filtered.filter((b) => b.quality_grade === 'A').length;
  return {
    label: range.label,
    total: filtered.length,
    rate: Math.round((gradeA / filtered.length) * 100)
  };
});

// 시즌 × 품종 분석
const seasonCultivarAnalysis = cultivars.map(cultivar => {
  return seasons.map(season => {
    const filtered = batches.filter(
      b => b.cultivar === cultivar && b.season === season
    );
    const gradeA = filtered.filter(b => b.quality_grade === 'A').length;
    return {
      total: filtered.length,
      rate: filtered.length > 0 ? Math.round(gradeA / filtered.length * 100) : 0
    };
  });
});
```

### 4.3 배치 비교 기능

```typescript
// 최대 3개 배치 선택
const toggleBatchSelection = (batchId: number) => {
  setSelectedBatches((prev) => {
    if (prev.includes(batchId)) {
      return prev.filter((id) => id !== batchId);
    }
    if (prev.length >= 3) {
      return [...prev.slice(1), batchId];  // FIFO
    }
    return [...prev, batchId];
  });
};

// 선택된 배치 데이터
const selectedBatchData = useMemo(() => {
  return batches.filter((b) => selectedBatches.includes(b.id));
}, [batches, selectedBatches]);
```

---

## 5. 배치 관리 기능

### 5.1 새 배치 생성

```http
POST /api/batches/
```

**요청**:
```json
{
  "tank_id": 1,
  "cultivar": "해남",
  "avg_weight": 3.2,
  "firmness": 15,
  "leaf_thickness": 3.0,
  "total_quantity": 2000,
  "room_temp": 18,
  "season": "겨울",
  "initial_salinity": 12.5,
  "initial_water_temp": 14
}
```

**자동 처리**:
- 해당 탱크의 기존 활성 배치 자동 종료
- 계절 미입력 시 현재 월 기준 자동 판단
- `start_time` 현재 시각으로 설정

### 5.2 배치 종료

```http
PUT /api/batches/{tank_id}/finish
```

**요청**:
```json
{
  "final_cabbage_salinity": 1.85,
  "bend_test": 87,
  "output_quantity": 1850,
  "quality_grade": "A",
  "notes": "정상 완료",
  "wash1_top_salinity": 1.2,
  "wash1_bottom_salinity": 1.5,
  "wash1_water_temp": 12,
  "wash2_top_salinity": 0.8,
  "wash2_bottom_salinity": 1.0,
  "wash2_water_temp": 12,
  "wash3_top_salinity": 0.5,
  "wash3_bottom_salinity": 0.6,
  "wash3_water_temp": 12
}
```

---

## 6. 측정 기록 관리

### 6.1 측정 기록 추가

```http
POST /api/measurements/tank/{tank_id}
```

**요청**:
```json
{
  "top_salinity": 8.5,
  "bottom_salinity": 9.2,
  "water_temp": 14.2,
  "ph": 6.8,
  "memo": "정상 진행 중"
}
```

**자동 계산 필드**:
```python
# 평균 염도
salinity_avg = (top_salinity + bottom_salinity) / 2

# 염도 차이 (상단 - 하단)
salinity_diff = top_salinity - bottom_salinity

# 삼투압 지수
osmotic_pressure_index = salinity_avg * (1 + water_temp / 100)

# 적산 온도 (이전 측정 기록 기반)
time_diff = (now - last_measurement.timestamp).total_seconds() / 60
accumulated_temp = last_accumulated + (water_temp * time_diff / 60)
```

### 6.2 측정 기록 조회

```http
GET /api/measurements/batch/{batch_id}
```

```http
GET /api/measurements/tank/{tank_id}/active
```

---

## 7. AI 인사이트 기능

### 7.1 종합 인사이트 생성

```http
POST /api/insight/
```

**요청**:
```json
{
  "batch_id": 1,
  "include_optimization": true,
  "include_time_prediction": true,
  "include_quality_prediction": true
}
```

**응답**:
```json
{
  "batch_id": 1,
  "summary": "절임조 1번의 해남 배추 배치입니다. 현재 18.5시간 경과했습니다. 진행률 67%, 약 8.5시간 후 완료 예상입니다. 현재 상태로는 A등급이 예상됩니다 (신뢰도 91%).",
  "optimization": {
    "recommended_salinity": 12.5,
    "recommended_duration": 26,
    "predicted_quality": "A"
  },
  "time_prediction": {
    "remaining_hours": 8.5,
    "current_progress": 67
  },
  "quality_prediction": {
    "predicted_grade": "A",
    "probabilities": {"A": 0.87, "B": 0.10, "C": 0.03}
  },
  "recommendations": [
    "현재 정상적으로 진행 중입니다. 계속 모니터링해주세요."
  ],
  "generated_at": "2026-03-11T14:30:00"
}
```

### 7.2 AI 채팅

```http
POST /api/insight/chat
```

**요청**:
```json
{
  "message": "현재 진행 상황은?",
  "context": {
    "current_page": "dashboard",
    "active_tanks": [
      {
        "name": "절임조 1",
        "cultivar": "해남",
        "progress": 67,
        "salinity": 3.2
      }
    ]
  }
}
```

**응답**:
```json
{
  "response": "현재 절임조 1번에서 해남 배추 배치가 진행 중입니다. 진행률 67%로, 약 8시간 후 완료 예정입니다. 현재 염도는 3.2%로 정상 범위입니다.",
  "tokens_used": 150
}
```

---

## 8. ML 모델 상태 조회

### 8.1 API: 모델 상태

```http
GET /api/ml/status
```

**응답**:
```json
{
  "models": {
    "optimizer": {
      "type": "GradientBoostingRegressor",
      "status": "trained",
      "version": "v3",
      "is_trained": true,
      "metrics": {
        "duration_mae": 1.32,
        "duration_r2": 0.961,
        "duration_features": [
          "cultivar_encoded", "avg_weight", "firmness", "leaf_thickness",
          "season_encoded", "room_temp", "initial_water_temp", "initial_salinity",
          "outdoor_temp", "added_salt_amount", "vant_hoff_osmotic", "weight_firmness"
        ]
      }
    },
    "time_predictor": {
      "type": "GradientBoostingRegressor",
      "status": "trained",
      "version": "v3",
      "is_trained": true,
      "metrics": {
        "mae": 0.97,
        "r2": 0.978,
        "features": [
          "elapsed_hours", "salinity_avg", "initial_salinity", "water_temp",
          "accumulated_temp", "salinity_diff", "osmotic_index"
        ]
      }
    },
    "quality_classifier": {
      "type": "GradientBoostingClassifier",
      "status": "trained",
      "version": "v3",
      "is_trained": true,
      "metrics": {
        "accuracy": 0.971,
        "f1_weighted": 0.971,
        "features": [
          "final_salinity", "quality_bending", "duration_hours", "cultivar_encoded",
          "season_encoded", "avg_weight", "initial_salinity", "initial_water_temp"
        ]
      }
    }
  },
  "message": "v3 학습 모델 사용 중",
  "version": "v3",
  "changes": [
    "물리 모델 기반 역최적화 적용",
    "배추 특성 반영 강화 (무게, 경도, 잎두께)",
    "염도 추천 0.1% 단위 세분화"
  ]
}
```

### 8.2 예측 로그 조회

```http
GET /api/ml/logs?model_type=optimizer&days=30&limit=100
```

```http
GET /api/ml/logs/batch/{batch_id}/history
```

```http
GET /api/ml/logs/summary/stats
```

---

## 9. 데이터 모델 상세

### 9.1 Batch 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| tank_id | Integer | FK → Tank |
| status | String | active/completed |
| start_time | DateTime | 배치 시작 시각 |
| end_time | DateTime | 배치 종료 시각 |
| cultivar | String | 품종 (해남, 괴산, 강원, 월동, 일반) |
| avg_weight | Float | 평균 무게 (kg) |
| firmness | Float | 경도 (5-22) |
| leaf_thickness | Float | 잎 두께 (mm) |
| total_quantity | Float | 총 물량 (kg) |
| room_temp | Float | 실내 온도 (°C) |
| season | String | 계절 (봄, 여름, 가을, 겨울) |
| initial_salinity | Float | 초기 염도 (%) |
| initial_water_temp | Float | 초기 염수 온도 (°C) |
| final_cabbage_salinity | Float | 최종 배추 염도 (%) |
| bend_test | Float | 휘어짐 점수 (0-100) |
| output_quantity | Float | 출고 물량 (kg) |
| quality_grade | String | 품질 등급 (A/B/C) |
| notes | Text | 비고 |
| wash1/2/3_* | Float | 세척 데이터 |

### 9.2 Measurement 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| batch_id | Integer | FK → Batch |
| timestamp | DateTime | 측정 시각 |
| top_salinity | Float | 상단 염도 (%) |
| bottom_salinity | Float | 하단 염도 (%) |
| water_temp | Float | 수온 (°C) |
| ph | Float | pH |
| salinity_avg | Float | 평균 염도 (계산) |
| salinity_diff | Float | 염도 차이 (계산) |
| accumulated_temp | Float | 적산 온도 (°C·h) |
| osmotic_pressure_index | Float | 삼투압 지수 (계산) |
| memo | Text | 메모 |

### 9.3 PredictionLog 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| batch_id | Integer | FK → Batch (nullable) |
| model_type | String | optimizer/time_predictor/quality_classifier |
| model_version | String | v3 |
| input_data | JSON | 입력 데이터 |
| prediction | JSON | 예측 결과 |
| confidence | Float | 신뢰도 |
| created_at | DateTime | 생성 시각 |

---

## 10. 에러 처리

### 10.1 HTTP 에러 코드

| 코드 | 상황 | 처리 |
|------|------|------|
| 400 | 필수 파라미터 누락 | 에러 메시지 표시 |
| 404 | 리소스 없음 (배치, 탱크) | 에러 메시지 표시 |
| 500 | 서버 에러 | 재시도 버튼 표시 |
| 503 | 서비스 불가 (Claude API 미설정) | 대체 응답 표시 |

### 10.2 프론트엔드 에러 핸들링

```typescript
// API 인터셉터
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// 컴포넌트 레벨
try {
  const data = await tanksApi.getAll();
  setTanks(data);
  setIsConnected(true);
} catch (error) {
  setApiError(error.message || 'API 연결 실패');
  setIsConnected(false);
  setTanks(dummyTanks);  // 더미 데이터로 폴백
}
```

---

## 11. 성능 지표

### 11.1 ML 모델 성능

| 모델 | 지표 | 값 |
|------|------|-----|
| **Optimizer (Duration)** | R² | 0.961 |
| | MAE | 1.32h |
| **Time Predictor** | R² | 0.978 |
| | MAE | 0.97h |
| **Quality Classifier** | Accuracy | 97.1% |
| | F1 Score | 0.971 |

### 11.2 API 응답 시간 목표

| 엔드포인트 | 목표 | 비고 |
|-----------|------|------|
| GET /tanks | < 100ms | 캐싱 가능 |
| GET /batches | < 200ms | - |
| POST /ml/optimize | < 500ms | 물리 모델 계산 포함 |
| POST /ml/predict/* | < 300ms | - |
| POST /ml/completion-decision | < 800ms | 4개 시나리오 계산 |

---

## 부록 A. 품종 매핑

```python
CULTIVAR_MAP = {
    '해남': '불암플러스',
    '괴산': '불암3호',
    '강원': '청명',
    '충북': '휘파람골드',
}
```

## 부록 B. UI Firmness/Thickness 변환

```python
def convert_ui_firmness(ui_firmness: float) -> float:
    """UI firmness (0-100) → 학습 데이터 firmness (5-22)"""
    return 5.0 + (ui_firmness / 100.0) * 17.0

def convert_ui_leaf_thickness(ui_thickness: float) -> int:
    """UI leaf_thickness (0.2-1.0 mm) → 학습 데이터 (1-5 mm)"""
    if ui_thickness < 1.5:
        return max(1, min(5, int(ui_thickness * 5)))
    else:
        return max(1, min(5, int(ui_thickness)))
```

## 부록 C. 계절별 기본값

| 계절 | 기본 수온 | 기본 초기 염도 | 예상 절임 시간 |
|------|----------|--------------|--------------|
| 봄 | 14°C | 12.0% | 24-28h |
| 여름 | 22°C | 13.0% | 18-22h |
| 가을 | 16°C | 12.0% | 22-26h |
| 겨울 | 10°C | 10.5% | 36-42h |
