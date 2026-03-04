import { useEffect, useState, useCallback, useRef } from 'react';
import { TankCard } from '../components/TankCard';
import { InsightPanel } from '../components/InsightPanel';
import { ChatPanel } from '../components/ChatPanel';
import { useStore, dummyTanks, dummyInsight } from '../stores/useStore';
import { RefreshCw, Plus, BarChart3, Bot, Send, Clock, Wifi, WifiOff, Pause, Play } from 'lucide-react';
import { chatApi, tanksApi, batchesApi } from '../services/api';
import type { Tank } from '../types';

// 자동 새로고침 간격 (30초)
const AUTO_REFRESH_INTERVAL = 30 * 1000;

export function Dashboard() {
  const { tanks, setTanks, insights, setInsights } = useStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [quickQuestion, setQuickQuestion] = useState('');
  const [aiMessage, setAiMessage] = useState('');
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // 자동 새로고침 상태
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isConnected, setIsConnected] = useState(true);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 실제 API에서 데이터 로드
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setApiError(null);

    try {
      // 1. 탱크 목록 조회
      const tanksData = await tanksApi.getAll();

      // 2. 활성 배치 목록 조회
      const activeBatches = await batchesApi.getAll({ status: 'active' });

      // 3. 탱크와 배치 매핑
      const tanksWithBatches: Tank[] = tanksData.map((tank: any) => {
        const batch = activeBatches.find((b: any) => b.tank_id === tank.id);

        if (batch) {
          // 경과 시간 계산
          const startTime = new Date(batch.start_time);
          const now = new Date();
          const elapsedHours = (now.getTime() - startTime.getTime()) / (1000 * 60 * 60);

          // 진행률 계산 (예상 22시간 기준)
          const expectedDuration = 22; // TODO: ML에서 가져오기
          const progress = Math.min(Math.round((elapsedHours / expectedDuration) * 100), 100);

          return {
            id: tank.id,
            name: tank.name,
            is_active: tank.is_active,
            current_batch: {
              id: String(batch.id),
              tank_id: batch.tank_id,
              tank_name: tank.name,
              batch_code: `B${new Date(batch.start_time).toISOString().slice(2, 10).replace(/-/g, '')}-${String(batch.id).padStart(3, '0')}`,
              status: batch.status,
              start_time: batch.start_time,
              progress,
              cultivar: batch.cultivar || '일반',
              avg_weight: Number(batch.avg_weight) || 3.0,
              initial_salinity: Number(batch.initial_salinity) || 12.0,
              room_temp: Number(batch.room_temp) || 18,
              season: batch.season || '겨울',
              latest_measurement: batch.measurements?.[batch.measurements.length - 1] ? {
                id: String(batch.measurements[batch.measurements.length - 1].id),
                batch_id: String(batch.id),
                timestamp: batch.measurements[batch.measurements.length - 1].timestamp,
                elapsed_minutes: Math.round(elapsedHours * 60),
                top_salinity: Number(batch.measurements[batch.measurements.length - 1].top_salinity),
                bottom_salinity: Number(batch.measurements[batch.measurements.length - 1].bottom_salinity),
                water_temp: Number(batch.measurements[batch.measurements.length - 1].water_temp),
                salinity_avg: Number(batch.measurements[batch.measurements.length - 1].salinity_avg),
              } : undefined,
            },
          };
        }

        return {
          id: tank.id,
          name: tank.name,
          is_active: tank.is_active,
          current_batch: undefined,
        };
      });

      setTanks(tanksWithBatches);

      // 4. 인사이트 생성 (활성 배치가 있는 경우)
      if (activeBatches.length > 0) {
        const insightTexts: string[] = [];
        const recommendations: string[] = [];
        const warnings: string[] = [];

        for (const batch of activeBatches.slice(0, 3)) { // 최대 3개 배치
          try {
            const tankInfo = tanksWithBatches.find(t => t.id === batch.tank_id);
            const progress = tankInfo?.current_batch?.progress || 0;

            insightTexts.push(
              `${tankInfo?.name || '절임조'}: ${batch.cultivar || '배추'}(${batch.avg_weight || 3}kg)가 진행 중입니다. 진행률 ${progress}%.`
            );

            if (progress >= 80) {
              recommendations.push(`${tankInfo?.name}: 곧 완료 예정, 세척 준비 권장`);
            }
            if (progress >= 95) {
              warnings.push(`${tankInfo?.name}: 과절임 주의`);
            }
          } catch (err) {
            console.error('Insight generation error for batch:', batch.id, err);
          }
        }

        setInsights({
          insight: insightTexts.join('\n\n') || '현재 진행 중인 배치 정보를 분석 중입니다.',
          recommendations: recommendations.length > 0 ? recommendations : ['정상 운영 중입니다.'],
          warnings,
          tokens_used: 0,
        });
      } else {
        setInsights({
          insight: '현재 진행 중인 배치가 없습니다. 새 배치를 시작해보세요.',
          recommendations: [],
          warnings: [],
          tokens_used: 0,
        });
      }

    } catch (error: any) {
      console.error('API 연결 오류:', error);
      setApiError(error.message || 'API 연결에 실패했습니다.');
      setIsConnected(false);
      // 오류 시 더미 데이터 사용
      setTanks(dummyTanks);
      setInsights(dummyInsight);
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date());
    }
  }, [setTanks, setInsights]);

  // 자동 새로고침 설정
  useEffect(() => {
    if (autoRefresh && isConnected) {
      refreshIntervalRef.current = setInterval(() => {
        loadData();
      }, AUTO_REFRESH_INTERVAL);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, isConnected, loadData]);

  // 자동 새로고침 토글
  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
  };

  // 마지막 업데이트 시간 포맷
  const formatLastUpdated = () => {
    if (!lastUpdated) return '-';
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - lastUpdated.getTime()) / 1000);

    if (diffSeconds < 60) return `${diffSeconds}초 전`;
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}분 전`;
    return lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  };

  // 초기 데이터 로드
  useEffect(() => {
    loadData();
  }, [loadData]);

  // 새로고침
  const handleRefresh = async () => {
    await loadData();
  };

  // 활성 배치 수
  const activeBatchCount = tanks.filter((t) => t.current_batch).length;

  // AI 어시스턴트 메시지 생성
  useEffect(() => {
    const generateAiMessage = () => {
      const activeTanks = tanks.filter((t) => t.current_batch);
      if (activeTanks.length === 0) {
        setAiMessage('현재 진행 중인 절임 배치가 없습니다. 새 배치를 시작해보세요!');
        return;
      }

      // 가장 진행률이 높은 탱크 찾기
      const nearCompleteTank = activeTanks.find((t) => {
        if (!t.current_batch) return false;
        const progress = t.current_batch.progress || 0;
        return progress >= 80;
      });

      if (nearCompleteTank && nearCompleteTank.current_batch) {
        const remaining = 100 - (nearCompleteTank.current_batch.progress || 0);
        setAiMessage(
          `${nearCompleteTank.name}이 목표 염도에 가까워지고 있습니다. ` +
          `약 ${Math.round(remaining * 0.3)}시간 후 세척을 시작하시면 적정 품질을 얻을 수 있습니다.`
        );
      } else {
        setAiMessage(
          `현재 ${activeTanks.length}개의 배치가 진행 중입니다. ` +
          `모든 절임조가 정상 범위 내에서 운영되고 있습니다.`
        );
      }
    };

    generateAiMessage();
  }, [tanks]);

  // 빠른 질문 전송
  const handleQuickAsk = async () => {
    if (!quickQuestion.trim() || isAiLoading) return;

    setIsAiLoading(true);
    try {
      const activeTanks = tanks.filter((t) => t.current_batch);
      const response = await chatApi.send({
        message: quickQuestion,
        context: {
          active_batches: activeTanks.length,
          tanks: activeTanks.map((t) => ({
            name: t.name,
            batch: t.current_batch?.batch_code,
            progress: t.current_batch?.progress,
          })),
        },
      });
      setAiMessage(response.response);
      setQuickQuestion('');
    } catch (error) {
      console.error('AI 질문 오류:', error);
      setAiMessage('죄송합니다. 응답을 생성하는 데 문제가 발생했습니다.');
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* API 연결 오류 알림 */}
      {apiError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center gap-3">
          <div className="bg-amber-100 p-2 rounded-lg">
            <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-amber-800 font-medium">백엔드 연결 오류</p>
            <p className="text-amber-600 text-sm">더미 데이터를 표시 중입니다. 백엔드 서버(localhost:8000)가 실행 중인지 확인하세요.</p>
          </div>
          <button onClick={handleRefresh} className="text-amber-700 hover:text-amber-800">
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* 상단 요약 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card bg-gradient-to-br from-green-500 to-green-600 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">진행 중 배치</p>
              <p className="text-3xl font-bold mt-1">{activeBatchCount}</p>
            </div>
            <div className="bg-white/20 p-3 rounded-lg">
              <BarChart3 className="w-6 h-6" />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">전체 탱크</p>
              <p className="text-3xl font-bold mt-1 text-gray-900">{tanks.length}</p>
            </div>
            <div className="bg-gray-100 p-3 rounded-lg">
              <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">오늘 완료</p>
              <p className="text-3xl font-bold mt-1 text-gray-900">2</p>
            </div>
            <div className="bg-blue-100 p-3 rounded-lg">
              <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">A등급 비율</p>
              <p className="text-3xl font-bold mt-1 text-gray-900">94%</p>
            </div>
            <div className="bg-amber-100 p-3 rounded-lg">
              <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold text-gray-900">절임조 현황</h3>
          {/* 연결 상태 표시 */}
          <div className="flex items-center gap-2 text-sm">
            {isConnected ? (
              <span className="flex items-center gap-1 text-green-600">
                <Wifi className="w-4 h-4" />
                <span className="hidden sm:inline">연결됨</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-red-500">
                <WifiOff className="w-4 h-4" />
                <span className="hidden sm:inline">오프라인</span>
              </span>
            )}
            <span className="text-gray-400">|</span>
            <span className="text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatLastUpdated()}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {/* 자동 새로고침 토글 */}
          <button
            onClick={toggleAutoRefresh}
            className={`btn-secondary flex items-center gap-2 ${autoRefresh ? 'bg-green-50 border-green-200 text-green-700' : ''}`}
            title={autoRefresh ? '자동 새로고침 중지' : '자동 새로고침 시작'}
          >
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            <span className="hidden sm:inline">{autoRefresh ? '자동' : '수동'}</span>
          </button>
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">새로고침</span>
          </button>
          <button className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">새 배치</span>
          </button>
        </div>
      </div>

      {/* 메인 콘텐츠 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 탱크 카드들 */}
        <div className="lg:col-span-2">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {tanks.map((tank) => (
              <TankCard
                key={tank.id}
                tank={tank}
                onClick={() => console.log('Tank clicked:', tank.id)}
              />
            ))}
          </div>
        </div>

        {/* 인사이트 패널 */}
        <div className="lg:col-span-1">
          <InsightPanel
            insights={insights}
            isLoading={isLoading}
            onRefresh={handleRefresh}
          />
        </div>
      </div>

      {/* AI 어시스턴트 패널 */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <div className="bg-blue-100 p-2 rounded-lg">
            <Bot className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="font-semibold text-gray-900">AI 어시스턴트</h3>
        </div>

        {/* AI 메시지 */}
        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <p className="text-gray-700 text-sm leading-relaxed">
            {isAiLoading ? (
              <span className="flex items-center gap-2">
                <span className="animate-pulse">응답 생성 중...</span>
              </span>
            ) : (
              aiMessage || '절임 공정에 대해 무엇이든 물어보세요.'
            )}
          </p>
        </div>

        {/* 빠른 질문 입력 */}
        <div className="flex gap-2">
          <input
            type="text"
            value={quickQuestion}
            onChange={(e) => setQuickQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuickAsk()}
            placeholder="질문을 입력하세요..."
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            disabled={isAiLoading}
          />
          <button
            onClick={handleQuickAsk}
            disabled={!quickQuestion.trim() || isAiLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsChatOpen(true)}
            className="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm text-gray-700"
          >
            전체 채팅
          </button>
        </div>
      </div>

      {/* 채팅 패널 모달 */}
      <ChatPanel
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        context={{
          active_batches: activeBatchCount,
          tanks: tanks
            .filter((t) => t.current_batch)
            .map((t) => ({
              name: t.name,
              batch: t.current_batch?.batch_code,
              progress: t.current_batch?.progress,
            })),
        }}
      />
    </div>
  );
}
