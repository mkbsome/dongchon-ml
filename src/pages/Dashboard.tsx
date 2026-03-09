import { useEffect, useState, useCallback, useRef } from 'react';
import { TankCard } from '../components/TankCard';
import { TankDetailModal } from '../components/TankDetailModal';
import { useStore, dummyTanks } from '../stores/useStore';
import { RefreshCw, Clock, Wifi, WifiOff, Pause, Play, AlertTriangle, Activity, CheckCircle, Zap } from 'lucide-react';
import { tanksApi, batchesApi } from '../services/api';
import type { Tank } from '../types';

const AUTO_REFRESH_INTERVAL = 30 * 1000;

export function Dashboard() {
  const { tanks, setTanks } = useStore();
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isConnected, setIsConnected] = useState(true);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [selectedTank, setSelectedTank] = useState<Tank | null>(null);

  // 데이터 로드
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setApiError(null);

    try {
      const tanksData = await tanksApi.getAll();
      const activeBatches = await batchesApi.getAll({ status: 'active' });

      const tanksWithBatches: Tank[] = tanksData.map((tank: Tank) => {
        const batch = activeBatches.find((b: any) => b.tank_id === tank.id);

        if (batch) {
          const startTime = new Date(batch.start_time);
          const now = new Date();
          const elapsedHours = (now.getTime() - startTime.getTime()) / (1000 * 60 * 60);
          const expectedDuration = batch.season === '겨울' ? 38 : 22;
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
              latest_measurement: batch.measurements?.[batch.measurements.length - 1]
                ? {
                    id: String(batch.measurements[batch.measurements.length - 1].id),
                    batch_id: String(batch.id),
                    timestamp: batch.measurements[batch.measurements.length - 1].timestamp,
                    elapsed_minutes: Math.round(elapsedHours * 60),
                    top_salinity: Number(batch.measurements[batch.measurements.length - 1].top_salinity),
                    bottom_salinity: Number(batch.measurements[batch.measurements.length - 1].bottom_salinity),
                    water_temp: Number(batch.measurements[batch.measurements.length - 1].water_temp),
                    salinity_avg: Number(batch.measurements[batch.measurements.length - 1].salinity_avg),
                  }
                : undefined,
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
      setIsConnected(true);
    } catch (error: any) {
      console.error('API error:', error);
      setApiError(error.message || 'API 연결 실패');
      setIsConnected(false);
      setTanks(dummyTanks);
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date());
    }
  }, [setTanks]);

  // 자동 새로고침
  useEffect(() => {
    if (autoRefresh && isConnected) {
      refreshIntervalRef.current = setInterval(loadData, AUTO_REFRESH_INTERVAL);
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, isConnected, loadData]);

  // 초기 로드
  useEffect(() => {
    loadData();
  }, [loadData]);

  const formatLastUpdated = () => {
    if (!lastUpdated) return '-';
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - lastUpdated.getTime()) / 1000);
    if (diffSeconds < 60) return `${diffSeconds}초 전`;
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}분 전`;
    return lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  };

  // 통계
  const activeBatchCount = tanks.filter((t) => t.current_batch).length;
  const nearCompleteTanks = tanks.filter(
    (t) => t.current_batch && (t.current_batch.progress || 0) >= 85
  );

  return (
    <div className="space-y-6">
      {/* API 연결 오류 */}
      {apiError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
          <div className="flex-1 text-sm">
            <span className="font-medium text-amber-700">백엔드 연결 오류</span>
            <span className="text-amber-600 ml-2">더미 데이터 표시 중</span>
          </div>
          <button onClick={loadData} className="text-amber-600 hover:text-amber-700">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 상단 요약 - 그라데이션 카드 */}
      <div className="grid grid-cols-4 gap-4">
        {/* 진행 중 배치 - 프라이머리 그라데이션 */}
        <div className="stat-card-primary">
          <div className="flex items-center justify-between mb-2">
            <Activity className="w-5 h-5 text-white/80" />
            <span className="text-xs text-white/60 uppercase tracking-wide">진행 중</span>
          </div>
          <p className="text-3xl font-bold text-white">{activeBatchCount}</p>
          <p className="text-sm text-white/70 mt-1">/ {tanks.length} 절임조</p>
        </div>

        {/* 대기 중 - 일반 카드 */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <Clock className="w-5 h-5 text-gray-400" />
            <span className="text-xs text-gray-500 uppercase tracking-wide">대기 중</span>
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {tanks.length - activeBatchCount}
          </p>
          <p className="text-sm text-gray-500 mt-1">사용 가능</p>
        </div>

        {/* 완료 임박 - 성공 그라데이션 */}
        <div className="stat-card-success">
          <div className="flex items-center justify-between mb-2">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            <span className="text-xs text-emerald-600 uppercase tracking-wide">완료 임박</span>
          </div>
          <p className="text-3xl font-bold text-emerald-700">
            {nearCompleteTanks.length}
          </p>
          <p className="text-sm text-emerald-600 mt-1">85% 이상 진행</p>
        </div>

        {/* 연결 상태 */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <Zap className="w-5 h-5 text-gray-400" />
            <span className="text-xs text-gray-500 uppercase tracking-wide">연결 상태</span>
          </div>
          <div className="flex items-center gap-2 mt-2">
            {isConnected ? (
              <>
                <Wifi className="w-6 h-6 text-emerald-500" />
                <span className="text-lg font-semibold text-emerald-600">연결됨</span>
              </>
            ) : (
              <>
                <WifiOff className="w-6 h-6 text-gray-400" />
                <span className="text-lg font-semibold text-gray-500">오프라인</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 컨트롤 바 */}
      <div className="flex items-center justify-between bg-white rounded-lg border border-gray-100 p-4 shadow-sm">
        <div className="flex items-center gap-4">
          <h3 className="font-semibold text-gray-800">절임조 현황</h3>
          <span className="text-sm text-gray-400 flex items-center gap-1.5 bg-gray-50 px-2 py-1 rounded">
            <Clock className="w-3.5 h-3.5" />
            {formatLastUpdated()}
          </span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-all flex items-center gap-2 ${
              autoRefresh
                ? 'bg-gradient-to-r from-emerald-500 to-green-500 text-white shadow-sm'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? '자동 갱신' : '수동 모드'}
          </button>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="btn-outline flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        </div>
      </div>

      {/* 탱크 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {tanks.map((tank) => (
          <TankCard key={tank.id} tank={tank} onClick={() => setSelectedTank(tank)} />
        ))}
      </div>

      {/* 탱크 상세 모달 */}
      {selectedTank && (
        <TankDetailModal
          tank={selectedTank}
          onClose={() => setSelectedTank(null)}
        />
      )}
    </div>
  );
}
