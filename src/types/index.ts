// 배치 타입
export interface Batch {
  id: string;
  tank_id: number;
  tank_name: string;
  batch_code?: string;
  status: 'active' | 'completed';
  start_time: string;
  end_time?: string;
  progress?: number;

  // 배추 특성
  cultivar: string;
  avg_weight: number;
  firmness?: number;
  leaf_thickness?: number;
  total_quantity?: number;

  // 환경 정보
  room_temp?: number;
  outdoor_temp?: number;
  season?: string;
  initial_salinity: number;
  initial_water_temp?: number;

  // 종료 시 데이터
  final_salinity?: number;
  bend_test?: number;
  output_quantity?: number;
  quality_grade?: 'A' | 'B' | 'C';
  notes?: string;

  // 측정 데이터
  measurements?: Measurement[];
  latest_measurement?: Measurement;
}

// 측정 기록 타입
export interface Measurement {
  id: string;
  batch_id: string;
  timestamp: string;
  elapsed_minutes: number;

  top_salinity?: number;
  bottom_salinity?: number;
  water_temp?: number;
  ph?: number;

  salinity_avg?: number;
  salinity_diff?: number;
  accumulated_temp?: number;

  memo?: string;
}

// 탱크 타입
export interface Tank {
  id: number;
  name: string;
  is_active: boolean;
  current_batch?: Batch;
}

// ML 최적화 요청/응답
export interface OptimizationRequest {
  cultivar: string;              // 품종 (해남, 괴산, 강원 등)
  avg_weight: number;            // 평균 무게 (kg)
  firmness?: number;             // 경도 (0~100)
  leaf_thickness?: number;       // 잎 두께
  season: string;                // 계절 (봄, 여름, 가을, 겨울)
  room_temp?: number;            // 실내 온도
  target_quality?: 'A' | 'B' | 'C';  // 목표 품질
}

export interface QualityProbability {
  A: number;
  B: number;
  C: number;
}

export interface OptimizationResponse {
  recommended_salinity: number;       // 추천 초기 염도 (%)
  recommended_duration: number;       // 추천 절임 시간 (hours)
  predicted_quality: string;          // 예상 품질 등급 (A/B/C)
  quality_probability?: QualityProbability;  // 등급별 확률
  confidence: number;                 // 신뢰도 (0~1)
  reasoning: string;                  // 추천 이유
  expected_final_salinity?: number;   // 예상 최종 염도
  is_optimal: boolean;                // 최적 범위 여부
}

// 시간 예측 응답
export interface TimePredictionResponse {
  remaining_hours: number;
  predicted_end_time: string;
  confidence: number;
  current_progress: number;
}

// 품질 예측 응답
export interface QualityPredictionResponse {
  predicted_grade: 'A' | 'B' | 'C';
  probabilities: {
    A: number;
    B: number;
    C: number;
  };
  confidence: number;
  risk_factors: string[];
}

// Claude 인사이트 응답
export interface InsightResponse {
  insight: string;
  recommendations: string[];
  warnings: string[];
  tokens_used: number;
}

// Claude 채팅 메시지
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// Claude 채팅 요청
export interface ChatRequest {
  message: string;
  context?: Record<string, unknown>;
}

// Claude 채팅 응답
export interface ChatResponse {
  response: string;
  tokens_used: number;
}

// 대시보드 상태
export interface DashboardState {
  tanks: Tank[];
  activeBatches: Batch[];
  insights: InsightResponse | null;
  isLoading: boolean;
  error: string | null;
}

// ============ 완료 시점 결정 ============
export interface CompletionScenario {
  hours_from_now: number;
  predicted_salinity: number;
  predicted_grade: string;
  grade_probabilities: Record<string, number>;
  confidence: number;
  is_recommended: boolean;
}

export interface CompletionDecisionResponse {
  batch_id: number;
  current_status: {
    elapsed_hours: number;
    current_salinity: number;
    initial_salinity: number;
    water_temp: number;
    cultivar: string;
    season: string;
  };
  scenarios: CompletionScenario[];
  recommendation: string;
  optimal_scenario_index: number;
  generated_at: string;
}

// ============ 이상감지 ============
export interface SimilarBatch {
  batch_id: number;
  cultivar: string;
  avg_weight: number;
  initial_salinity: number;
  duration_hours: number;
  quality_grade: string;
  similarity_score: number;
}

export interface AnomalyCheckResponse {
  batch_id: number;
  is_anomaly: boolean;
  anomaly_score: number;
  current_vs_expected: Record<string, number | string>;
  similar_batches: SimilarBatch[];
  alerts: string[];
  generated_at: string;
}
