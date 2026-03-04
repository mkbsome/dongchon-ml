import { create } from 'zustand';
import type { Tank, Batch, InsightResponse } from '../types';

interface AppState {
  // 데이터
  tanks: Tank[];
  activeBatches: Batch[];
  selectedBatch: Batch | null;
  insights: InsightResponse | null;

  // UI 상태
  isLoading: boolean;
  error: string | null;
  currentPage: 'dashboard' | 'optimize' | 'history' | 'settings';

  // 액션
  setTanks: (tanks: Tank[]) => void;
  setActiveBatches: (batches: Batch[]) => void;
  setSelectedBatch: (batch: Batch | null) => void;
  setInsights: (insights: InsightResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentPage: (page: AppState['currentPage']) => void;
}

export const useStore = create<AppState>((set) => ({
  // 초기 데이터
  tanks: [],
  activeBatches: [],
  selectedBatch: null,
  insights: null,

  // 초기 UI 상태
  isLoading: false,
  error: null,
  currentPage: 'dashboard',

  // 액션
  setTanks: (tanks) => set({ tanks }),
  setActiveBatches: (activeBatches) => set({ activeBatches }),
  setSelectedBatch: (selectedBatch) => set({ selectedBatch }),
  setInsights: (insights) => set({ insights }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setCurrentPage: (currentPage) => set({ currentPage }),
}));

// 더미 데이터 (API 연결 전 테스트용) - 절임조 7개
export const dummyTanks: Tank[] = [
  {
    id: 1,
    name: '절임조 1호',
    is_active: true,
    current_batch: {
      id: 'batch-001',
      tank_id: 1,
      tank_name: '절임조 1호',
      batch_code: 'B2026-0302-001',
      status: 'active',
      start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      progress: 65,
      cultivar: '해남',
      avg_weight: 3.2,
      initial_salinity: 12.5,
      room_temp: 18,
      season: '겨울',
      latest_measurement: {
        id: 'm-001',
        batch_id: 'batch-001',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 120,
        top_salinity: 8.5,
        bottom_salinity: 9.2,
        water_temp: 17.5,
        salinity_avg: 8.85,
      },
    },
  },
  {
    id: 2,
    name: '절임조 2호',
    is_active: false,
    current_batch: undefined,
  },
  {
    id: 3,
    name: '절임조 3호',
    is_active: true,
    current_batch: {
      id: 'batch-002',
      tank_id: 3,
      tank_name: '절임조 3호',
      batch_code: 'B2026-0302-002',
      status: 'active',
      start_time: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
      progress: 90,
      cultivar: '고랭지',
      avg_weight: 2.8,
      initial_salinity: 11.0,
      room_temp: 16,
      season: '겨울',
      latest_measurement: {
        id: 'm-002',
        batch_id: 'batch-002',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 300,
        top_salinity: 5.2,
        bottom_salinity: 5.8,
        water_temp: 16.2,
        salinity_avg: 5.5,
      },
    },
  },
  {
    id: 4,
    name: '절임조 4호',
    is_active: true,
    current_batch: {
      id: 'batch-003',
      tank_id: 4,
      tank_name: '절임조 4호',
      batch_code: 'B2026-0302-003',
      status: 'active',
      start_time: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
      progress: 25,
      cultivar: '괴산',
      avg_weight: 2.5,
      initial_salinity: 13.0,
      room_temp: 17,
      season: '겨울',
      latest_measurement: {
        id: 'm-003',
        batch_id: 'batch-003',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 60,
        top_salinity: 10.5,
        bottom_salinity: 11.0,
        water_temp: 16.8,
        salinity_avg: 10.75,
      },
    },
  },
  {
    id: 5,
    name: '절임조 5호',
    is_active: false,
    current_batch: undefined,
  },
  {
    id: 6,
    name: '절임조 6호',
    is_active: true,
    current_batch: {
      id: 'batch-004',
      tank_id: 6,
      tank_name: '절임조 6호',
      batch_code: 'B2026-0302-004',
      status: 'active',
      start_time: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
      progress: 78,
      cultivar: '월동',
      avg_weight: 3.5,
      initial_salinity: 10.5,
      room_temp: 15,
      season: '겨울',
      latest_measurement: {
        id: 'm-004',
        batch_id: 'batch-004',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 240,
        top_salinity: 4.8,
        bottom_salinity: 5.3,
        water_temp: 15.2,
        salinity_avg: 5.05,
      },
    },
  },
  {
    id: 7,
    name: '절임조 7호',
    is_active: false,
    current_batch: undefined,
  },
];

export const dummyInsight: InsightResponse = {
  insight: `절임조 1: 해남 배추(3.2kg)가 정상 진행 중입니다. 현재 염도 침투율이 양호하며, 약 3시간 후 A등급 품질을 기대할 수 있습니다.

절임조 3: 고랭지 배추(2.8kg)의 염도 침투가 예상보다 빠릅니다. 현재 5.5% 수준으로 약 1시간 후 완료될 것으로 예상됩니다. 30분 후 중간 점검을 권장합니다.`,
  recommendations: [
    '절임조 1: 3시간 후 최종 점검 예정',
    '절임조 3: 30분 후 중간 점검 권장',
  ],
  warnings: [
    '절임조 3: 염도 침투 속도가 예상보다 10% 빠름',
  ],
  tokens_used: 312,
};
