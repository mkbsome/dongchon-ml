import axios from 'axios';
import type {
  Batch,
  Tank,
  OptimizationRequest,
  OptimizationResponse,
  TimePredictionResponse,
  QualityPredictionResponse,
  InsightResponse,
  ChatRequest,
  ChatResponse,
  CompletionDecisionResponse,
  AnomalyCheckResponse,
} from '../types';

// API 기본 설정
// 백엔드는 /api prefix 사용 (v1 없음)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 탱크 관련 API
export const tanksApi = {
  getAll: async (): Promise<Tank[]> => {
    const { data } = await api.get('/tanks');
    return data;
  },

  getActive: async (tankId: number): Promise<Batch | null> => {
    const { data } = await api.get(`/tanks/${tankId}/active`);
    return data;
  },
};

// 배치 관련 API
export const batchesApi = {
  getAll: async (params?: { status?: string; limit?: number }): Promise<Batch[]> => {
    const { data } = await api.get('/batches', { params });
    return data;
  },

  getById: async (id: string): Promise<Batch> => {
    const { data } = await api.get(`/batches/${id}`);
    return data;
  },

  create: async (batch: Partial<Batch>): Promise<Batch> => {
    const { data } = await api.post('/batches', batch);
    return data;
  },

  update: async (id: string, batch: Partial<Batch>): Promise<Batch> => {
    const { data } = await api.put(`/batches/${id}`, batch);
    return data;
  },

  finish: async (id: string, finishData: Partial<Batch>): Promise<Batch> => {
    const { data } = await api.post(`/batches/${id}/finish`, finishData);
    return data;
  },
};

// ML 관련 API
export const mlApi = {
  optimize: async (request: OptimizationRequest): Promise<OptimizationResponse> => {
    const { data } = await api.post('/ml/optimize', request);
    return data;
  },

  predictTime: async (batchId: string): Promise<TimePredictionResponse> => {
    const { data } = await api.post('/ml/predict/time', { batch_id: batchId });
    return data;
  },

  predictQuality: async (params: {
    final_salinity: number;
    bend_test: number;
    elapsed_hours?: number;
    cultivar?: string;
    season?: string;
    batch_id?: number;
  }): Promise<QualityPredictionResponse> => {
    const { data } = await api.post('/ml/predict/quality', params);
    return data;
  },

  // ML 상태 조회
  getStatus: async (): Promise<{
    models: Record<string, { type: string; status: string; version: string; is_trained: boolean }>;
    message: string;
  }> => {
    const { data } = await api.get('/ml/status');
    return data;
  },

  // 완료 시점 결정 지원
  getCompletionDecision: async (batchId: number, scenarios?: number[]): Promise<CompletionDecisionResponse> => {
    const { data } = await api.post('/ml/completion-decision', {
      batch_id: batchId,
      scenarios,
    });
    return data;
  },

  // 이상감지
  checkAnomaly: async (batchId: number): Promise<AnomalyCheckResponse> => {
    const { data } = await api.post('/ml/anomaly-check', { batch_id: batchId });
    return data;
  },
};

// 인사이트 API
export const insightApi = {
  generate: async (params: {
    batch_id?: string;
    ml_results?: {
      optimization?: OptimizationResponse;
      time_prediction?: TimePredictionResponse;
      quality_prediction?: QualityPredictionResponse;
    };
    context?: Record<string, unknown>;
  }): Promise<InsightResponse> => {
    const { data } = await api.post('/insight', params);
    return data;
  },

  // Claude 인사이트 (최적화 결과 기반)
  getOptimizationInsight: async (params: {
    optimization_result: OptimizationResponse;
    input: OptimizationRequest;
  }): Promise<{ insight: string }> => {
    const { data } = await api.post('/insight/optimization', params);
    return data;
  },
};

// Claude 채팅 API
export const chatApi = {
  send: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await api.post('/insight/chat', request);
    return data;
  },
};

// 에러 핸들링 인터셉터
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
