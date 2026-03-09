import { create } from 'zustand';
import type { Tank, Batch, InsightResponse, ChatMessage } from '../types';

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

  // 채팅 상태 (전역)
  chatMessages: ChatMessage[];
  chatContext: Record<string, unknown>;
  isChatOpen: boolean;
  isChatLoading: boolean;

  // 액션
  setTanks: (tanks: Tank[]) => void;
  setActiveBatches: (batches: Batch[]) => void;
  setSelectedBatch: (batch: Batch | null) => void;
  setInsights: (insights: InsightResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentPage: (page: AppState['currentPage']) => void;

  // 채팅 액션
  addChatMessage: (message: ChatMessage) => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  setChatContext: (context: Record<string, unknown>) => void;
  setChatOpen: (open: boolean) => void;
  setChatLoading: (loading: boolean) => void;
  clearChat: () => void;
  sendAnalysisRequest: (prompt: string, pageContext?: string) => void;
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

  // 초기 채팅 상태
  chatMessages: [
    {
      id: 'init',
      role: 'assistant',
      content: '안녕하세요. 절임 공정에 대해 궁금한 점을 물어보세요.',
      timestamp: new Date().toISOString(),
    },
  ],
  chatContext: {},
  isChatOpen: true,
  isChatLoading: false,

  // 액션
  setTanks: (tanks) => set({ tanks }),
  setActiveBatches: (activeBatches) => set({ activeBatches }),
  setSelectedBatch: (selectedBatch) => set({ selectedBatch }),
  setInsights: (insights) => set({ insights }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setCurrentPage: (currentPage) => set({ currentPage }),

  // 채팅 액션
  addChatMessage: (message) =>
    set((state) => ({ chatMessages: [...state.chatMessages, message] })),
  setChatMessages: (chatMessages) => set({ chatMessages }),
  setChatContext: (chatContext) => set({ chatContext }),
  setChatOpen: (isChatOpen) => set({ isChatOpen }),
  setChatLoading: (isChatLoading) => set({ isChatLoading }),
  clearChat: () =>
    set({
      chatMessages: [
        {
          id: 'init',
          role: 'assistant',
          content: '안녕하세요. 절임 공정에 대해 궁금한 점을 물어보세요.',
          timestamp: new Date().toISOString(),
        },
      ],
    }),
  sendAnalysisRequest: (prompt: string, pageContext?: string) =>
    set((state) => {
      // 페이지 컨텍스트 정보 생성
      const pageNames: Record<string, string> = {
        dashboard: '대시보드 (실시간 모니터링)',
        optimize: '최적화 (배치 시작/완료 예측)',
        history: '이력 조회 (과거 데이터 분석)',
        settings: '설정',
      };

      // 현재 페이지에 따른 추가 컨텍스트
      let contextInfo = '';
      if (state.currentPage === 'dashboard') {
        const activeBatchCount = state.tanks.filter(t => t.current_batch).length;
        const totalTanks = state.tanks.length;
        contextInfo = `\n\n[페이지 컨텍스트: ${pageNames[state.currentPage]}]
- 현재 가동 중인 절임조: ${activeBatchCount}개 / 총 ${totalTanks}개
- 이 페이지에서는 실시간 절임조 상태를 모니터링하고 있습니다.`;
      } else if (state.currentPage === 'optimize') {
        contextInfo = `\n\n[페이지 컨텍스트: ${pageNames[state.currentPage]}]
- 이 페이지에서는 새 배치 시작 시 최적 조건과 완료 시점을 예측합니다.
- 과거 데이터 기반 AI 예측 기능을 제공합니다.`;
      } else if (state.currentPage === 'history') {
        contextInfo = `\n\n[페이지 컨텍스트: ${pageNames[state.currentPage]}]
- 이 페이지에서는 과거 절임 이력과 성과를 분석합니다.
- 품질 등급별 분포, 성공 조건 분석, 절임조별 성과 비교가 가능합니다.`;
      }

      // 사용자 지정 컨텍스트가 있으면 추가
      if (pageContext) {
        contextInfo += `\n${pageContext}`;
      }

      const fullPrompt = prompt + contextInfo;

      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: fullPrompt,
        timestamp: new Date().toISOString(),
      };
      return {
        isChatOpen: true,
        chatMessages: [...state.chatMessages, userMessage],
      };
    }),
}));

// 더미 데이터 (API 연결 전 테스트용) - 절임조 7개
export const dummyTanks: Tank[] = [
  {
    id: 1,
    name: '1호기',
    is_active: true,
    current_batch: {
      id: 'batch-001',
      tank_id: 1,
      tank_name: '1호기',
      batch_code: 'B260302-001',
      status: 'active',
      start_time: new Date(Date.now() - 14 * 60 * 60 * 1000).toISOString(),
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
        elapsed_minutes: 840,
        top_salinity: 8.5,
        bottom_salinity: 9.2,
        water_temp: 12.5,
        salinity_avg: 8.85,
      },
    },
  },
  {
    id: 2,
    name: '2호기',
    is_active: false,
    current_batch: undefined,
  },
  {
    id: 3,
    name: '3호기',
    is_active: true,
    current_batch: {
      id: 'batch-002',
      tank_id: 3,
      tank_name: '3호기',
      batch_code: 'B260302-002',
      status: 'active',
      start_time: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
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
        elapsed_minutes: 1200,
        top_salinity: 3.2,
        bottom_salinity: 3.8,
        water_temp: 11.2,
        salinity_avg: 3.5,
      },
    },
  },
  {
    id: 4,
    name: '4호기',
    is_active: true,
    current_batch: {
      id: 'batch-003',
      tank_id: 4,
      tank_name: '4호기',
      batch_code: 'B260302-003',
      status: 'active',
      start_time: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      progress: 28,
      cultivar: '괴산',
      avg_weight: 2.5,
      initial_salinity: 13.0,
      room_temp: 17,
      season: '겨울',
      latest_measurement: {
        id: 'm-003',
        batch_id: 'batch-003',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 360,
        top_salinity: 10.5,
        bottom_salinity: 11.0,
        water_temp: 12.8,
        salinity_avg: 10.75,
      },
    },
  },
  {
    id: 5,
    name: '5호기',
    is_active: false,
    current_batch: undefined,
  },
  {
    id: 6,
    name: '6호기',
    is_active: true,
    current_batch: {
      id: 'batch-004',
      tank_id: 6,
      tank_name: '6호기',
      batch_code: 'B260302-004',
      status: 'active',
      start_time: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString(),
      progress: 82,
      cultivar: '월동',
      avg_weight: 3.5,
      initial_salinity: 10.5,
      room_temp: 15,
      season: '겨울',
      latest_measurement: {
        id: 'm-004',
        batch_id: 'batch-004',
        timestamp: new Date().toISOString(),
        elapsed_minutes: 1080,
        top_salinity: 4.1,
        bottom_salinity: 4.6,
        water_temp: 10.2,
        salinity_avg: 4.35,
      },
    },
  },
  {
    id: 7,
    name: '7호기',
    is_active: false,
    current_batch: undefined,
  },
];

export const dummyInsight: InsightResponse = {
  insight: '현재 4개의 배치가 진행 중입니다. 전체적으로 정상 범위 내에서 운영되고 있습니다.',
  recommendations: [
    '3호기: 완료 임박, 세척 준비 권장',
    '6호기: 약 4시간 후 완료 예상',
  ],
  warnings: [
    '3호기: 목표 염도 도달, 점검 필요',
  ],
  tokens_used: 0,
};
