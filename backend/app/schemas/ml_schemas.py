from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# ============ Optimization Schemas ============
class OptimizeRequest(BaseModel):
    """공정 최적화 요청"""
    cultivar: str                           # 품종 (해남, 괴산 등)
    avg_weight: float                       # 평균 무게 (kg)
    firmness: Optional[float] = 50.0        # 경도 (UI: 0-100)
    leaf_thickness: Optional[float] = 3.0   # 잎 두께 (mm)
    season: str                             # 계절
    room_temp: Optional[float] = 18.0       # 실내 온도
    water_temp: Optional[float] = None      # 염수 온도 (None이면 계절 기본값)
    target_quality: Optional[str] = "A"     # 목표 품질


class QualityProbability(BaseModel):
    """품질 등급별 확률"""
    A: float = 0.0
    B: float = 0.0
    C: float = 0.0


class OptimizeResponse(BaseModel):
    """공정 최적화 응답 (v4 확장)"""
    recommended_salinity: float     # 추천 초기 염도 (%)
    recommended_duration: float     # 추천 절임 시간 (hours)
    predicted_quality: str          # 예상 품질 등급 (A/B/C)
    quality_probability: Optional[QualityProbability] = None  # 등급별 확률
    confidence: float               # 신뢰도
    reasoning: str                  # 추천 이유
    expected_final_salinity: Optional[float] = None  # 예상 최종 염도
    is_optimal: bool = False        # 최적 범위 여부


# ============ Time Prediction Schemas ============
class TimePredictRequest(BaseModel):
    """시간 예측 요청"""
    batch_id: Optional[int] = None          # 배치 ID (있으면 자동으로 데이터 조회)
    elapsed_hours: Optional[float] = None   # 경과 시간
    current_salinity_avg: Optional[float] = None  # 현재 평균 염도
    initial_salinity: Optional[float] = None      # 초기 염도
    water_temp: Optional[float] = 15.0      # 현재 수온
    accumulated_temp: Optional[float] = 0.0 # 적산 온도


class TimePredictResponse(BaseModel):
    """시간 예측 응답"""
    remaining_hours: float          # 남은 시간
    predicted_end_time: str         # 예상 종료 시각
    confidence: float               # 신뢰도
    current_progress: float         # 현재 진행률 (%)


# ============ Quality Prediction Schemas ============
class QualityPredictRequest(BaseModel):
    """품질 예측 요청"""
    batch_id: Optional[int] = None          # 배치 ID
    final_salinity: Optional[float] = None  # 최종 염도
    bend_test: Optional[float] = None       # 휘어짐 점수
    elapsed_hours: Optional[float] = None   # 경과 시간
    cultivar: Optional[str] = None          # 품종
    season: Optional[str] = None            # 계절


class QualityPredictResponse(BaseModel):
    """품질 예측 응답"""
    predicted_grade: str            # 예측 등급 (A/B/C)
    probabilities: dict             # 각 등급별 확률
    confidence: float               # 신뢰도
    risk_factors: list              # 위험 요소


# ============ Insight Schemas ============
class InsightRequest(BaseModel):
    """AI 인사이트 요청"""
    batch_id: int                           # 배치 ID
    include_optimization: bool = True       # 최적화 결과 포함
    include_time_prediction: bool = True    # 시간 예측 포함
    include_quality_prediction: bool = True # 품질 예측 포함


class InsightResponse(BaseModel):
    """AI 인사이트 응답"""
    batch_id: int
    summary: str                    # 종합 요약
    optimization: Optional[dict] = None
    time_prediction: Optional[dict] = None
    quality_prediction: Optional[dict] = None
    recommendations: list           # 권장 사항
    generated_at: str               # 생성 시각


# ============ Prediction Log Schemas ============
class PredictionLogResponse(BaseModel):
    """예측 로그 응답"""
    id: int
    batch_id: Optional[int] = None
    model_type: str                 # optimizer, time_predictor, quality_classifier
    model_version: Optional[str] = None
    input_data: dict                # 입력 데이터
    prediction: dict                # 예측 결과
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionLogListResponse(BaseModel):
    """예측 로그 목록 응답"""
    total: int                      # 총 개수
    logs: List[PredictionLogResponse]


# ============ Completion Decision Schemas ============
class CompletionScenario(BaseModel):
    """완료 시점 시나리오"""
    hours_from_now: float           # 현재 시점 대비 추가 시간
    predicted_salinity: float       # 예상 최종 염도
    predicted_grade: str            # 예상 품질 등급 (A/B/C)
    grade_probabilities: dict       # 등급별 확률
    confidence: float               # 신뢰도
    is_recommended: bool = False    # 추천 시점 여부


class CompletionDecisionRequest(BaseModel):
    """완료 시점 결정 요청"""
    batch_id: int                   # 배치 ID


class CompletionDecisionResponse(BaseModel):
    """완료 시점 결정 응답"""
    batch_id: int
    current_status: dict            # 현재 배치 상태
    scenarios: List[CompletionScenario]  # 시나리오별 예측
    recommendation: str             # 추천 사항
    optimal_scenario_index: int     # 최적 시나리오 인덱스 (0-based)
    generated_at: str
