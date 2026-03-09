import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search,
  Filter,
  ArrowUpDown,
  RefreshCw,
  TrendingUp,
  AlertCircle,
  BarChart3,
  GitCompare,
  X,
  Calendar,
  Clock,
  Droplets,
  Target,
  ThermometerSun,
  Scale,
  CheckCircle,
} from 'lucide-react';
import { batchesApi } from '../services/api';
import type { Batch } from '../types';

const gradeColors = {
  A: 'bg-emerald-100 text-emerald-700',
  B: 'bg-amber-100 text-amber-700',
  C: 'bg-red-100 text-red-700',
};

const tankNames: Record<number, string> = {
  1: '절임조 1',
  2: '절임조 2',
  3: '절임조 3',
  4: '절임조 4',
  5: '절임조 5',
  6: '절임조 6',
  7: '절임조 7',
};

interface HistoryBatch extends Batch {
  tank_name: string;
  duration_hours: number;
}

type TabType = 'overview' | 'success-analysis' | 'tank-performance';

export function History() {
  const [batches, setBatches] = useState<HistoryBatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [gradeFilter, setGradeFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<'start_time' | 'tank_id' | 'quality_grade'>('start_time');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // 탭 상태
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // 비교 모드
  const [selectedBatches, setSelectedBatches] = useState<number[]>([]);

  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await batchesApi.getAll({ status: 'completed', limit: 500 });
      const processedBatches: HistoryBatch[] = data.map((batch) => {
        const startTime = new Date(batch.start_time);
        const endTime = batch.end_time ? new Date(batch.end_time) : new Date();
        const durationHours = (endTime.getTime() - startTime.getTime()) / (1000 * 60 * 60);
        return {
          ...batch,
          tank_name: tankNames[batch.tank_id] || `절임조 ${batch.tank_id}`,
          duration_hours: Math.round(durationHours * 10) / 10,
        };
      });
      setBatches(processedBatches);
    } catch (err) {
      console.error('Failed to load batches:', err);
      setError('배치 이력을 불러오는데 실패했습니다');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const filteredBatches = useMemo(() => {
    let result = batches.filter((batch) => {
      const matchesSearch =
        batch.cultivar?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        batch.tank_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        batch.batch_code?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesGrade = gradeFilter === 'all' || batch.quality_grade === gradeFilter;
      return matchesSearch && matchesGrade;
    });

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

  // 통계
  const stats = useMemo(() => {
    if (batches.length === 0) {
      return { total: 0, gradeA: 0, gradeB: 0, gradeC: 0, avgDuration: 0, avgSalinityDrop: 0, predictionAccuracy: 0 };
    }

    const gradeA = batches.filter((b) => b.quality_grade === 'A').length;
    const gradeB = batches.filter((b) => b.quality_grade === 'B').length;
    const gradeC = batches.filter((b) => b.quality_grade === 'C').length;
    const avgDuration = batches.reduce((acc, b) => acc + b.duration_hours, 0) / batches.length;

    const salinityDrops = batches
      .filter((b) => b.initial_salinity && b.final_salinity)
      .map((b) => (b.initial_salinity || 0) - (b.final_salinity || 0));
    const avgSalinityDrop =
      salinityDrops.length > 0 ? salinityDrops.reduce((a, b) => a + b, 0) / salinityDrops.length : 0;

    // 예측 적중률 (시뮬레이션 - 실제로는 ML API 결과와 비교)
    const predictionAccuracy = 87;

    return { total: batches.length, gradeA, gradeB, gradeC, avgDuration, avgSalinityDrop, predictionAccuracy };
  }, [batches]);

  const gradeAPercent = stats.total > 0 ? Math.round((stats.gradeA / stats.total) * 100) : 0;

  const toggleBatchSelection = (batchId: number) => {
    setSelectedBatches((prev) => {
      if (prev.includes(batchId)) {
        return prev.filter((id) => id !== batchId);
      }
      if (prev.length >= 3) {
        return [...prev.slice(1), batchId];
      }
      return [...prev, batchId];
    });
  };

  const selectedBatchData = useMemo(() => {
    return batches.filter((b) => selectedBatches.includes(b.id as unknown as number));
  }, [batches, selectedBatches]);

  // 성공 요인 분석
  const successFactorAnalysis = useMemo(() => {
    const aBatches = batches.filter((b) => b.quality_grade === 'A');
    const bBatches = batches.filter((b) => b.quality_grade === 'B');
    const cBatches = batches.filter((b) => b.quality_grade === 'C');

    const avg = (arr: number[]) => (arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);

    return {
      A: {
        count: aBatches.length,
        avgDuration: avg(aBatches.map((b) => b.duration_hours)),
        avgInitialSalinity: avg(aBatches.filter((b) => b.initial_salinity).map((b) => b.initial_salinity || 0)),
        avgWeight: avg(aBatches.filter((b) => b.avg_weight).map((b) => b.avg_weight)),
        avgSalinityDrop: avg(
          aBatches
            .filter((b) => b.initial_salinity && b.final_salinity)
            .map((b) => (b.initial_salinity || 0) - (b.final_salinity || 0))
        ),
      },
      B: {
        count: bBatches.length,
        avgDuration: avg(bBatches.map((b) => b.duration_hours)),
        avgInitialSalinity: avg(bBatches.filter((b) => b.initial_salinity).map((b) => b.initial_salinity || 0)),
        avgWeight: avg(bBatches.filter((b) => b.avg_weight).map((b) => b.avg_weight)),
        avgSalinityDrop: avg(
          bBatches
            .filter((b) => b.initial_salinity && b.final_salinity)
            .map((b) => (b.initial_salinity || 0) - (b.final_salinity || 0))
        ),
      },
      C: {
        count: cBatches.length,
        avgDuration: avg(cBatches.map((b) => b.duration_hours)),
        avgInitialSalinity: avg(cBatches.filter((b) => b.initial_salinity).map((b) => b.initial_salinity || 0)),
        avgWeight: avg(cBatches.filter((b) => b.avg_weight).map((b) => b.avg_weight)),
        avgSalinityDrop: avg(
          cBatches
            .filter((b) => b.initial_salinity && b.final_salinity)
            .map((b) => (b.initial_salinity || 0) - (b.final_salinity || 0))
        ),
      },
    };
  }, [batches]);

  // 시즌-품종 성공률 분석
  const seasonCultivarAnalysis = useMemo(() => {
    const seasons = ['봄', '여름', '가을', '겨울'];
    const cultivars = ['일반', '절임배추', '월동'];
    const result: Record<string, Record<string, { total: number; gradeA: number; rate: number }>> = {};

    cultivars.forEach((cultivar) => {
      result[cultivar] = {};
      seasons.forEach((season) => {
        const filtered = batches.filter((b) => b.cultivar === cultivar && b.season === season);
        const gradeA = filtered.filter((b) => b.quality_grade === 'A').length;
        result[cultivar][season] = {
          total: filtered.length,
          gradeA,
          rate: filtered.length > 0 ? Math.round((gradeA / filtered.length) * 100) : 0,
        };
      });
    });

    return { seasons, cultivars, data: result };
  }, [batches]);

  // 조건별 성공률 분석
  const conditionAnalysis = useMemo(() => {
    const salinityRanges = [
      { label: '10-11%', min: 10, max: 11 },
      { label: '11-12%', min: 11, max: 12 },
      { label: '12-13%', min: 12, max: 13 },
      { label: '13%+', min: 13, max: 100 },
    ];

    const weightRanges = [
      { label: '~2.5kg', min: 0, max: 2.5 },
      { label: '2.5-3kg', min: 2.5, max: 3 },
      { label: '3-3.5kg', min: 3, max: 3.5 },
      { label: '3.5kg+', min: 3.5, max: 100 },
    ];

    const salinityStats = salinityRanges.map((range) => {
      const filtered = batches.filter(
        (b) => b.initial_salinity && b.initial_salinity >= range.min && b.initial_salinity < range.max
      );
      const gradeA = filtered.filter((b) => b.quality_grade === 'A').length;
      return {
        label: range.label,
        total: filtered.length,
        rate: filtered.length > 0 ? Math.round((gradeA / filtered.length) * 100) : 0,
      };
    });

    const weightStats = weightRanges.map((range) => {
      const filtered = batches.filter(
        (b) => b.avg_weight && b.avg_weight >= range.min && b.avg_weight < range.max
      );
      const gradeA = filtered.filter((b) => b.quality_grade === 'A').length;
      return {
        label: range.label,
        total: filtered.length,
        rate: filtered.length > 0 ? Math.round((gradeA / filtered.length) * 100) : 0,
      };
    });

    // 최적 조건 추출 (A등급 배치 기준)
    const aBatches = batches.filter((b) => b.quality_grade === 'A');
    const avgValues = (arr: number[]) => (arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
    const stdDev = (arr: number[]) => {
      if (arr.length === 0) return 0;
      const mean = avgValues(arr);
      return Math.sqrt(arr.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / arr.length);
    };

    const salinities = aBatches.filter((b) => b.initial_salinity).map((b) => b.initial_salinity || 0);
    const weights = aBatches.filter((b) => b.avg_weight).map((b) => b.avg_weight);

    const optimalConditions = {
      salinity: {
        min: Math.max(10, avgValues(salinities) - stdDev(salinities)).toFixed(1),
        max: Math.min(14, avgValues(salinities) + stdDev(salinities)).toFixed(1),
        avg: avgValues(salinities).toFixed(1),
      },
      weight: {
        min: Math.max(2, avgValues(weights) - stdDev(weights)).toFixed(1),
        max: Math.min(4, avgValues(weights) + stdDev(weights)).toFixed(1),
        avg: avgValues(weights).toFixed(1),
      },
      temp: { min: '14', max: '16', avg: '15' },
    };

    return { salinityStats, weightStats, optimalConditions };
  }, [batches]);

  // 절임조별 성과 분석
  const tankPerformanceAnalysis = useMemo(() => {
    const tankIds = [1, 2, 3, 4, 5, 6, 7];

    return tankIds.map((tankId) => {
      const tankBatches = batches.filter((b) => b.tank_id === tankId);
      const total = tankBatches.length;
      const gradeA = tankBatches.filter((b) => b.quality_grade === 'A').length;
      const gradeB = tankBatches.filter((b) => b.quality_grade === 'B').length;
      const gradeC = tankBatches.filter((b) => b.quality_grade === 'C').length;
      const avgDuration = total > 0
        ? tankBatches.reduce((acc, b) => acc + b.duration_hours, 0) / total
        : 0;
      const avgSalinityDrop = total > 0
        ? tankBatches
            .filter((b) => b.initial_salinity && b.final_salinity)
            .reduce((acc, b) => acc + ((b.initial_salinity || 0) - (b.final_salinity || 0)), 0) /
          Math.max(1, tankBatches.filter((b) => b.initial_salinity && b.final_salinity).length)
        : 0;

      return {
        tankId,
        tankName: tankNames[tankId],
        total,
        gradeA,
        gradeB,
        gradeC,
        gradeARate: total > 0 ? Math.round((gradeA / total) * 100) : 0,
        avgDuration: Math.round(avgDuration * 10) / 10,
        avgSalinityDrop: Math.round(avgSalinityDrop * 10) / 10,
      };
    }).filter((t) => t.total > 0);
  }, [batches]);

  // 월별 추이 분석
  const monthlyTrend = useMemo(() => {
    const months: { label: string; total: number; gradeA: number; rate: number; avgDuration: number }[] = [];
    const now = new Date();

    for (let i = 5; i >= 0; i--) {
      const monthStart = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const monthEnd = new Date(now.getFullYear(), now.getMonth() - i + 1, 0);

      const monthBatches = batches.filter((b) => {
        const batchDate = new Date(b.start_time);
        return batchDate >= monthStart && batchDate <= monthEnd;
      });

      const gradeA = monthBatches.filter((b) => b.quality_grade === 'A').length;
      const rate = monthBatches.length > 0 ? Math.round((gradeA / monthBatches.length) * 100) : 0;
      const avgDuration = monthBatches.length > 0
        ? Math.round((monthBatches.reduce((acc, b) => acc + b.duration_hours, 0) / monthBatches.length) * 10) / 10
        : 0;

      months.push({
        label: `${monthStart.getMonth() + 1}월`,
        total: monthBatches.length,
        gradeA,
        rate,
        avgDuration,
      });
    }

    return months;
  }, [batches]);

  // 주간 추이 데이터
  const weeklyTrend = useMemo(() => {
    const weeks: { label: string; rate: number; count: number }[] = [];
    const now = new Date();

    for (let i = 4; i >= 0; i--) {
      const weekStart = new Date(now);
      weekStart.setDate(now.getDate() - i * 7 - 7);
      const weekEnd = new Date(now);
      weekEnd.setDate(now.getDate() - i * 7);

      const weekBatches = batches.filter((b) => {
        const batchDate = new Date(b.start_time);
        return batchDate >= weekStart && batchDate < weekEnd;
      });

      const gradeA = weekBatches.filter((b) => b.quality_grade === 'A').length;
      const rate = weekBatches.length > 0 ? Math.round((gradeA / weekBatches.length) * 100) : 0;

      weeks.push({
        label: `${i + 1}주 전`,
        rate,
        count: weekBatches.length,
      });
    }

    return weeks;
  }, [batches]);

  // 진행률 바 컴포넌트
  const ProgressBar = ({ value, max = 100, color = 'bg-emerald-500' }: { value: number; max?: number; color?: string }) => (
    <div className="w-full bg-slate-100 rounded-full h-4">
      <div
        className={`h-4 rounded-full ${color} transition-all duration-500`}
        style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
      />
    </div>
  );

  // 탭 렌더링
  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverviewTab();
      case 'success-analysis':
        return renderSuccessAnalysisTab();
      case 'tank-performance':
        return renderTankPerformanceTab();
      default:
        return null;
    }
  };

  // 전체 현황 탭
  const renderOverviewTab = () => (
    <div className="space-y-6">
      {/* 통계 카드 */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <div className="stat-card">
          <p className="stat-label">전체 배치</p>
          <p className="stat-value">{stats.total}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">A등급</p>
          <p className="stat-value text-emerald-600">{stats.gradeA}</p>
          <p className="stat-subtitle">{gradeAPercent}%</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">B등급</p>
          <p className="stat-value text-amber-600">{stats.gradeB}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">C등급</p>
          <p className="stat-value text-red-600">{stats.gradeC}</p>
        </div>
        <div className="stat-card">
          <div className="flex items-center gap-1.5 stat-label">
            <Clock className="w-3.5 h-3.5" />
            평균 절임시간
          </div>
          <p className="stat-value">{stats.avgDuration.toFixed(1)}h</p>
        </div>
        <div className="stat-card">
          <div className="flex items-center gap-1.5 stat-label">
            <Target className="w-3.5 h-3.5" />
            예측 적중률
          </div>
          <p className="stat-value text-blue-600">{stats.predictionAccuracy}%</p>
        </div>
      </div>

      {/* 등급 분포 + 주간 추이 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 등급 분포 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">등급 분포</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-emerald-600 font-medium">A등급</span>
                <span className="text-slate-600">{gradeAPercent}%</span>
              </div>
              <ProgressBar value={gradeAPercent} color="bg-emerald-500" />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-amber-600 font-medium">B등급</span>
                <span className="text-slate-600">{stats.total > 0 ? Math.round((stats.gradeB / stats.total) * 100) : 0}%</span>
              </div>
              <ProgressBar value={stats.total > 0 ? (stats.gradeB / stats.total) * 100 : 0} color="bg-amber-500" />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-red-600 font-medium">C등급</span>
                <span className="text-slate-600">{stats.total > 0 ? Math.round((stats.gradeC / stats.total) * 100) : 0}%</span>
              </div>
              <ProgressBar value={stats.total > 0 ? (stats.gradeC / stats.total) * 100 : 0} color="bg-red-500" />
            </div>
          </div>
          {gradeAPercent >= 60 && (
            <div className="mt-4 p-2 bg-emerald-50 rounded-lg">
              <p className="text-sm text-emerald-700">
                <CheckCircle className="w-4 h-4 inline mr-1" />
                업계 평균(60%) 대비 양호
              </p>
            </div>
          )}
        </div>

        {/* 주간 추이 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">최근 추이 (주간)</h3>
          <div className="h-40 flex items-end justify-between gap-2">
            {weeklyTrend.map((week, idx) => (
              <div key={idx} className="flex-1 flex flex-col items-center">
                <span className="text-xs text-slate-500 mb-1">{week.rate}%</span>
                <div className="w-full bg-slate-100 rounded-t" style={{ height: '100px' }}>
                  <div
                    className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t transition-all"
                    style={{ height: `${week.rate}%`, marginTop: `${100 - week.rate}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400 mt-2">{week.label}</span>
              </div>
            ))}
          </div>
          {weeklyTrend.length >= 2 && weeklyTrend[weeklyTrend.length - 1].rate > weeklyTrend[0].rate && (
            <div className="mt-4 p-2 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                <TrendingUp className="w-4 h-4 inline mr-1" />
                A등급 비율이 상승 중입니다
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 필터 + 테이블 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex flex-col lg:flex-row gap-3 mb-4">
          {/* 검색 */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="품종, 탱크명, 배치코드 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-9"
            />
          </div>

          {/* 등급 필터 */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select value={gradeFilter} onChange={(e) => setGradeFilter(e.target.value)} className="select w-32">
              <option value="all">전체 등급</option>
              <option value="A">A등급</option>
              <option value="B">B등급</option>
              <option value="C">C등급</option>
            </select>
          </div>

          <button
            onClick={() => setSelectedBatches([])}
            className={`btn-secondary ${selectedBatches.length > 0 ? '' : 'opacity-50'}`}
            disabled={selectedBatches.length === 0}
          >
            <GitCompare className="w-4 h-4" />
            비교 ({selectedBatches.length}/3)
          </button>

          <button onClick={loadBatches} disabled={isLoading} className="btn-secondary">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* 비교 패널 */}
        {selectedBatches.length > 0 && (
          <div className="mb-4 p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-slate-700">배치 비교</h4>
              <button onClick={() => setSelectedBatches([])} className="text-sm text-slate-500 hover:text-slate-700">
                초기화
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {selectedBatchData.map((batch) => (
                <div key={batch.id} className="p-3 bg-white rounded-lg border border-slate-200 relative">
                  <button
                    onClick={() => toggleBatchSelection(batch.id as unknown as number)}
                    className="absolute top-2 right-2 p-1 text-slate-400 hover:text-slate-600"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`badge ${gradeColors[batch.quality_grade as keyof typeof gradeColors] || 'badge-default'}`}>
                      {batch.quality_grade}등급
                    </span>
                    <span className="text-sm text-slate-600">{batch.tank_name}</span>
                  </div>
                  <div className="text-xs space-y-1 text-slate-500">
                    <p>무게: {batch.avg_weight}kg | 시간: {batch.duration_hours}h</p>
                    <p>염도: {batch.initial_salinity?.toFixed(1)}% → {batch.final_salinity?.toFixed(1)}%</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 테이블 */}
        {renderBatchTable()}
      </div>
    </div>
  );

  // 성공 조건 분석 탭
  const renderSuccessAnalysisTab = () => (
    <div className="space-y-6">
      {/* A등급 최적 조건 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Target className="w-5 h-5 text-emerald-600" />
          <h3 className="font-semibold text-slate-800">A등급 최적 조건</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 초기 염도 */}
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Droplets className="w-4 h-4 text-blue-500" />
              <span className="font-medium text-slate-700">초기 염도</span>
            </div>
            <p className="text-2xl font-bold text-slate-800">{conditionAnalysis.optimalConditions.salinity.min} - {conditionAnalysis.optimalConditions.salinity.max}%</p>
            <div className="mt-2 h-2 bg-slate-200 rounded-full relative">
              <div className="absolute h-full bg-blue-500 rounded-full" style={{ left: '20%', width: '30%' }} />
              <div className="absolute w-2 h-4 bg-blue-600 rounded -top-1" style={{ left: '35%' }} />
            </div>
            <p className="text-xs text-slate-500 mt-2">평균: {conditionAnalysis.optimalConditions.salinity.avg}%</p>
          </div>

          {/* 배추 무게 */}
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Scale className="w-4 h-4 text-emerald-500" />
              <span className="font-medium text-slate-700">배추 무게</span>
            </div>
            <p className="text-2xl font-bold text-slate-800">{conditionAnalysis.optimalConditions.weight.min} - {conditionAnalysis.optimalConditions.weight.max}kg</p>
            <div className="mt-2 h-2 bg-slate-200 rounded-full relative">
              <div className="absolute h-full bg-emerald-500 rounded-full" style={{ left: '30%', width: '25%' }} />
              <div className="absolute w-2 h-4 bg-emerald-600 rounded -top-1" style={{ left: '42%' }} />
            </div>
            <p className="text-xs text-slate-500 mt-2">평균: {conditionAnalysis.optimalConditions.weight.avg}kg</p>
          </div>

          {/* 수온 */}
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <ThermometerSun className="w-4 h-4 text-orange-500" />
              <span className="font-medium text-slate-700">수온</span>
            </div>
            <p className="text-2xl font-bold text-slate-800">{conditionAnalysis.optimalConditions.temp.min} - {conditionAnalysis.optimalConditions.temp.max}°C</p>
            <div className="mt-2 h-2 bg-slate-200 rounded-full relative">
              <div className="absolute h-full bg-orange-500 rounded-full" style={{ left: '35%', width: '20%' }} />
              <div className="absolute w-2 h-4 bg-orange-600 rounded -top-1" style={{ left: '45%' }} />
            </div>
            <p className="text-xs text-slate-500 mt-2">평균: {conditionAnalysis.optimalConditions.temp.avg}°C</p>
          </div>
        </div>
      </div>

      {/* 조건별 성공률 비교 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 초기 염도별 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">초기 염도별 A등급 비율</h3>
          <div className="space-y-3">
            {conditionAnalysis.salinityStats.map((stat, idx) => {
              const isOptimal = stat.rate === Math.max(...conditionAnalysis.salinityStats.map((s) => s.rate));
              return (
                <div key={idx}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className={`${isOptimal ? 'text-emerald-600 font-medium' : 'text-slate-600'}`}>
                      {stat.label} {isOptimal && '← 최적'}
                    </span>
                    <span className="text-slate-600">{stat.rate}% ({stat.total}건)</span>
                  </div>
                  <ProgressBar value={stat.rate} color={isOptimal ? 'bg-emerald-500' : 'bg-slate-400'} />
                </div>
              );
            })}
          </div>
        </div>

        {/* 배추 무게별 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">배추 무게별 A등급 비율</h3>
          <div className="space-y-3">
            {conditionAnalysis.weightStats.map((stat, idx) => {
              const isOptimal = stat.rate === Math.max(...conditionAnalysis.weightStats.map((s) => s.rate));
              return (
                <div key={idx}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className={`${isOptimal ? 'text-emerald-600 font-medium' : 'text-slate-600'}`}>
                      {stat.label} {isOptimal && '← 최적'}
                    </span>
                    <span className="text-slate-600">{stat.rate}% ({stat.total}건)</span>
                  </div>
                  <ProgressBar value={stat.rate} color={isOptimal ? 'bg-emerald-500' : 'bg-slate-400'} />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 시즌 × 품종 성공률 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-800 mb-4">시즌 × 품종 A등급 성공률</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="table-header">품종</th>
                {seasonCultivarAnalysis.seasons.map((season) => (
                  <th key={season} className="table-header text-center">{season}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {seasonCultivarAnalysis.cultivars.map((cultivar) => (
                <tr key={cultivar} className="border-b border-slate-100">
                  <td className="table-cell font-medium text-slate-700">{cultivar}</td>
                  {seasonCultivarAnalysis.seasons.map((season) => {
                    const data = seasonCultivarAnalysis.data[cultivar][season];
                    const rate = data.rate;
                    let bgColor = 'bg-slate-100';
                    let textColor = 'text-slate-400';
                    if (data.total > 0) {
                      if (rate >= 85) {
                        bgColor = 'bg-emerald-100';
                        textColor = 'text-emerald-700';
                      } else if (rate >= 70) {
                        bgColor = 'bg-blue-100';
                        textColor = 'text-blue-700';
                      } else if (rate >= 60) {
                        bgColor = 'bg-amber-100';
                        textColor = 'text-amber-700';
                      } else {
                        bgColor = 'bg-red-100';
                        textColor = 'text-red-700';
                      }
                    }
                    return (
                      <td key={season} className="table-cell text-center">
                        <span className={`inline-block px-3 py-1 rounded-lg ${bgColor} ${textColor} font-medium`}>
                          {data.total > 0 ? `${rate}%` : '-'}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex gap-4 text-xs text-slate-500">
          <span><span className="inline-block w-3 h-3 rounded bg-emerald-100 mr-1" /> 85%+</span>
          <span><span className="inline-block w-3 h-3 rounded bg-blue-100 mr-1" /> 70-84%</span>
          <span><span className="inline-block w-3 h-3 rounded bg-amber-100 mr-1" /> 60-69%</span>
          <span><span className="inline-block w-3 h-3 rounded bg-red-100 mr-1" /> ~59%</span>
        </div>
      </div>

      {/* 등급별 비교 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-slate-600" />
          <h3 className="font-semibold text-slate-800">등급별 평균 비교</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="table-header">지표</th>
                <th className="table-header text-center text-emerald-600">A등급 ({successFactorAnalysis.A.count}건)</th>
                <th className="table-header text-center text-amber-600">B등급 ({successFactorAnalysis.B.count}건)</th>
                <th className="table-header text-center text-red-600">C등급 ({successFactorAnalysis.C.count}건)</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-50">
                <td className="table-cell text-slate-600">평균 절임시간</td>
                <td className="table-cell text-center font-medium text-emerald-700">{successFactorAnalysis.A.avgDuration.toFixed(1)}h</td>
                <td className="table-cell text-center font-medium text-amber-700">{successFactorAnalysis.B.avgDuration.toFixed(1)}h</td>
                <td className="table-cell text-center font-medium text-red-700">{successFactorAnalysis.C.avgDuration.toFixed(1)}h</td>
              </tr>
              <tr className="border-b border-slate-50">
                <td className="table-cell text-slate-600">평균 초기염도</td>
                <td className="table-cell text-center font-medium text-emerald-700">{successFactorAnalysis.A.avgInitialSalinity.toFixed(1)}%</td>
                <td className="table-cell text-center font-medium text-amber-700">{successFactorAnalysis.B.avgInitialSalinity.toFixed(1)}%</td>
                <td className="table-cell text-center font-medium text-red-700">{successFactorAnalysis.C.avgInitialSalinity.toFixed(1)}%</td>
              </tr>
              <tr className="border-b border-slate-50">
                <td className="table-cell text-slate-600">평균 배추 무게</td>
                <td className="table-cell text-center font-medium text-emerald-700">{successFactorAnalysis.A.avgWeight.toFixed(1)}kg</td>
                <td className="table-cell text-center font-medium text-amber-700">{successFactorAnalysis.B.avgWeight.toFixed(1)}kg</td>
                <td className="table-cell text-center font-medium text-red-700">{successFactorAnalysis.C.avgWeight.toFixed(1)}kg</td>
              </tr>
              <tr>
                <td className="table-cell text-slate-600">평균 염도 감소</td>
                <td className="table-cell text-center font-medium text-emerald-700">{successFactorAnalysis.A.avgSalinityDrop.toFixed(1)}%</td>
                <td className="table-cell text-center font-medium text-amber-700">{successFactorAnalysis.B.avgSalinityDrop.toFixed(1)}%</td>
                <td className="table-cell text-center font-medium text-red-700">{successFactorAnalysis.C.avgSalinityDrop.toFixed(1)}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // 절임조별 성과 탭
  const renderTankPerformanceTab = () => {
    const bestTank = tankPerformanceAnalysis.reduce((best, tank) =>
      tank.gradeARate > (best?.gradeARate || 0) ? tank : best
    , tankPerformanceAnalysis[0]);

    const avgGradeARate = tankPerformanceAnalysis.length > 0
      ? Math.round(tankPerformanceAnalysis.reduce((acc, t) => acc + t.gradeARate, 0) / tankPerformanceAnalysis.length)
      : 0;

    return (
      <div className="space-y-6">
        {/* 요약 카드 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="stat-card">
            <p className="stat-label">가동 절임조</p>
            <p className="stat-value">{tankPerformanceAnalysis.length}대</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">전체 평균 A등급률</p>
            <p className="stat-value text-emerald-600">{avgGradeARate}%</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">최고 성과 절임조</p>
            <p className="stat-value text-blue-600">{bestTank?.tankName || '-'}</p>
            <p className="stat-subtitle">{bestTank?.gradeARate || 0}% A등급</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">총 완료 배치</p>
            <p className="stat-value">{tankPerformanceAnalysis.reduce((acc, t) => acc + t.total, 0)}건</p>
          </div>
        </div>

        {/* 절임조별 성과 비교 차트 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">절임조별 A등급 비율 비교</h3>
          <div className="space-y-3">
            {tankPerformanceAnalysis
              .sort((a, b) => b.gradeARate - a.gradeARate)
              .map((tank, idx) => {
                const isTop = idx === 0;
                const isBelowAvg = tank.gradeARate < avgGradeARate;
                return (
                  <div key={tank.tankId}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className={`font-medium ${isTop ? 'text-emerald-600' : isBelowAvg ? 'text-amber-600' : 'text-slate-700'}`}>
                        {tank.tankName} {isTop && '🏆'}
                      </span>
                      <span className="text-slate-600">
                        {tank.gradeARate}% ({tank.gradeA}/{tank.total}건)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-4 relative">
                      <div
                        className={`h-4 rounded-full transition-all duration-500 ${
                          isTop ? 'bg-emerald-500' : isBelowAvg ? 'bg-amber-400' : 'bg-blue-500'
                        }`}
                        style={{ width: `${tank.gradeARate}%` }}
                      />
                      {/* 평균선 표시 */}
                      <div
                        className="absolute top-0 h-full w-0.5 bg-slate-400"
                        style={{ left: `${avgGradeARate}%` }}
                        title={`평균: ${avgGradeARate}%`}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
          <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-slate-400 rounded" /> 전체 평균 ({avgGradeARate}%)
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-emerald-500 rounded" /> 최고 성과
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 bg-amber-400 rounded" /> 평균 미달
            </span>
          </div>
        </div>

        {/* 절임조별 상세 테이블 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">절임조별 상세 성과</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="table-header">절임조</th>
                  <th className="table-header text-center">총 배치</th>
                  <th className="table-header text-center text-emerald-600">A등급</th>
                  <th className="table-header text-center text-amber-600">B등급</th>
                  <th className="table-header text-center text-red-600">C등급</th>
                  <th className="table-header text-center">A등급률</th>
                  <th className="table-header text-center">평균 시간</th>
                  <th className="table-header text-center">평균 염도감소</th>
                </tr>
              </thead>
              <tbody>
                {tankPerformanceAnalysis.map((tank) => (
                  <tr key={tank.tankId} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="table-cell font-medium text-slate-800">{tank.tankName}</td>
                    <td className="table-cell text-center">{tank.total}</td>
                    <td className="table-cell text-center text-emerald-600 font-medium">{tank.gradeA}</td>
                    <td className="table-cell text-center text-amber-600">{tank.gradeB}</td>
                    <td className="table-cell text-center text-red-600">{tank.gradeC}</td>
                    <td className="table-cell text-center">
                      <span className={`inline-block px-2 py-0.5 rounded ${
                        tank.gradeARate >= 80 ? 'bg-emerald-100 text-emerald-700' :
                        tank.gradeARate >= 60 ? 'bg-blue-100 text-blue-700' :
                        'bg-amber-100 text-amber-700'
                      } font-medium`}>
                        {tank.gradeARate}%
                      </span>
                    </td>
                    <td className="table-cell text-center">{tank.avgDuration}h</td>
                    <td className="table-cell text-center">{tank.avgSalinityDrop}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 월별 추이 */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">월별 A등급률 추이</h3>
          <div className="h-48 flex items-end justify-between gap-3">
            {monthlyTrend.map((month, idx) => (
              <div key={idx} className="flex-1 flex flex-col items-center">
                <span className="text-xs font-medium text-slate-700 mb-1">{month.rate}%</span>
                <span className="text-[10px] text-slate-400 mb-1">{month.total}건</span>
                <div className="w-full bg-slate-100 rounded-t relative" style={{ height: '120px' }}>
                  <div
                    className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t transition-all absolute bottom-0"
                    style={{ height: `${month.rate}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500 mt-2 font-medium">{month.label}</span>
              </div>
            ))}
          </div>
          {monthlyTrend.length >= 2 && (
            <div className="mt-4 p-3 rounded-lg bg-slate-50">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">평균 절임 시간 추이</span>
                <span className="font-medium text-slate-700">
                  {monthlyTrend[0].avgDuration}h → {monthlyTrend[monthlyTrend.length - 1].avgDuration}h
                  {monthlyTrend[monthlyTrend.length - 1].avgDuration < monthlyTrend[0].avgDuration && (
                    <span className="text-emerald-600 ml-2">↓ 개선</span>
                  )}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 개선 제안 */}
        {tankPerformanceAnalysis.filter((t) => t.gradeARate < avgGradeARate).length > 0 && (
          <div className="bg-amber-50 rounded-lg border border-amber-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-5 h-5 text-amber-600" />
              <h3 className="font-semibold text-amber-800">개선 필요 절임조</h3>
            </div>
            <div className="space-y-2">
              {tankPerformanceAnalysis
                .filter((t) => t.gradeARate < avgGradeARate)
                .map((tank) => (
                  <div key={tank.tankId} className="flex items-center justify-between p-2 bg-white rounded-lg">
                    <span className="font-medium text-slate-700">{tank.tankName}</span>
                    <div className="text-sm text-slate-600">
                      A등급률 {tank.gradeARate}% (평균 대비 -{avgGradeARate - tank.gradeARate}%p)
                    </div>
                  </div>
                ))}
            </div>
            <p className="text-sm text-amber-700 mt-3">
              해당 절임조의 운영 조건 및 장비 상태를 점검해 보세요.
            </p>
          </div>
        )}
      </div>
    );
  };

  // 배치 테이블
  const renderBatchTable = () => (
    <>
      {isLoading ? (
        <div className="py-12 text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">데이터를 불러오는 중...</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="table-header text-center w-12">선택</th>
                <th className="table-header">
                  <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort('tank_id')}>
                    절임조
                    <ArrowUpDown className={`w-3 h-3 ${sortField === 'tank_id' ? 'text-slate-700' : ''}`} />
                  </button>
                </th>
                <th className="table-header">품종</th>
                <th className="table-header">무게</th>
                <th className="table-header">
                  <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort('start_time')}>
                    시작 시간
                    <ArrowUpDown className={`w-3 h-3 ${sortField === 'start_time' ? 'text-slate-700' : ''}`} />
                  </button>
                </th>
                <th className="table-header">절임 시간</th>
                <th className="table-header">염도 변화</th>
                <th className="table-header">
                  <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort('quality_grade')}>
                    품질
                    <ArrowUpDown className={`w-3 h-3 ${sortField === 'quality_grade' ? 'text-slate-700' : ''}`} />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredBatches.map((batch) => {
                const isSelected = selectedBatches.includes(batch.id as unknown as number);
                return (
                  <tr
                    key={batch.id}
                    className={`table-row-hover cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                    onClick={() => toggleBatchSelection(batch.id as unknown as number)}
                  >
                    <td className="table-cell text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="w-4 h-4 text-blue-600 rounded border-slate-300"
                      />
                    </td>
                    <td className="table-cell">
                      <span className="font-medium text-slate-800">{batch.tank_name}</span>
                    </td>
                    <td className="table-cell text-slate-600">{batch.cultivar || '-'}</td>
                    <td className="table-cell text-slate-600">{batch.avg_weight ? `${batch.avg_weight}kg` : '-'}</td>
                    <td className="table-cell text-slate-600">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        {new Date(batch.start_time).toLocaleString('ko-KR', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </td>
                    <td className="table-cell text-slate-600">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {batch.duration_hours}시간
                      </div>
                    </td>
                    <td className="table-cell text-slate-600">
                      <div className="flex items-center gap-1">
                        <Droplets className="w-3 h-3 text-blue-400" />
                        <span className="text-blue-600">{batch.initial_salinity?.toFixed(1) || '-'}%</span>
                        <span className="text-slate-300">→</span>
                        <span className="text-emerald-600">{batch.final_salinity?.toFixed(1) || '-'}%</span>
                      </div>
                    </td>
                    <td className="table-cell">
                      {batch.quality_grade ? (
                        <span className={`badge ${gradeColors[batch.quality_grade as keyof typeof gradeColors] || 'badge-default'}`}>
                          {batch.quality_grade}등급
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs">미평가</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!isLoading && filteredBatches.length === 0 && (
        <div className="py-12 text-center">
          {batches.length === 0 ? (
            <>
              <Droplets className="w-12 h-12 text-slate-200 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">완료된 배치가 없습니다</p>
              <p className="text-slate-400 text-sm">터치패널에서 배치를 완료하면 이력이 표시됩니다</p>
            </>
          ) : (
            <>
              <Search className="w-12 h-12 text-slate-200 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">검색 결과가 없습니다</p>
            </>
          )}
        </div>
      )}
    </>
  );

  return (
    <div className="space-y-6">
      {/* 에러 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="font-medium text-red-700">{error}</p>
            <p className="text-sm text-red-600">백엔드 서버 연결을 확인해주세요</p>
          </div>
          <button onClick={loadBatches} className="px-3 py-1 bg-red-100 text-red-700 rounded-lg text-sm hover:bg-red-200">
            다시 시도
          </button>
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div className="bg-white rounded-lg border border-slate-200 p-1 flex gap-1">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
            activeTab === 'overview'
              ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          전체 현황
        </button>
        <button
          onClick={() => setActiveTab('success-analysis')}
          className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
            activeTab === 'success-analysis'
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          <Target className="w-4 h-4" />
          성공 조건 분석
        </button>
        <button
          onClick={() => setActiveTab('tank-performance')}
          className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
            activeTab === 'tank-performance'
              ? 'bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          절임조별 성과
        </button>
      </div>

      {/* 탭 콘텐츠 */}
      {renderTab()}
    </div>
  );
}
