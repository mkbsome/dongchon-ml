import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Search, Filter, ArrowUpDown, RefreshCw, TrendingUp, AlertCircle,
  BarChart3, GitCompare, X
} from 'lucide-react';
import { batchesApi } from '../services/api';
import type { Batch } from '../types';

const gradeColors = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-yellow-100 text-yellow-700',
  C: 'bg-red-100 text-red-700',
};

const tankNames: Record<number, string> = {
  1: '절임조 1', 2: '절임조 2', 3: '절임조 3', 4: '절임조 4',
  5: '절임조 5', 6: '절임조 6', 7: '절임조 7',
};

interface HistoryBatch extends Batch {
  tank_name: string;
  duration_hours: number;
}

type ViewMode = 'list' | 'compare' | 'analysis';

export function History() {
  const [batches, setBatches] = useState<HistoryBatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [gradeFilter, setGradeFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<'start_time' | 'tank_id' | 'quality_grade'>('start_time');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // 비교 모드
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedBatches, setSelectedBatches] = useState<number[]>([]);
  const [showAnalysis, setShowAnalysis] = useState(false);

  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await batchesApi.getAll({ status: 'completed', limit: 100 });
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
      const matchesGrade =
        gradeFilter === 'all' || batch.quality_grade === gradeFilter;
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

  // 통계 계산
  const stats = useMemo(() => {
    if (batches.length === 0) {
      return { total: 0, gradeA: 0, gradeB: 0, gradeC: 0, avgDuration: 0, avgSalinityDrop: 0 };
    }

    const gradeA = batches.filter((b) => b.quality_grade === 'A').length;
    const gradeB = batches.filter((b) => b.quality_grade === 'B').length;
    const gradeC = batches.filter((b) => b.quality_grade === 'C').length;
    const avgDuration = batches.reduce((acc, b) => acc + b.duration_hours, 0) / batches.length;

    const salinityDrops = batches
      .filter(b => b.initial_salinity && b.final_salinity)
      .map(b => (b.initial_salinity || 0) - (b.final_salinity || 0));
    const avgSalinityDrop = salinityDrops.length > 0
      ? salinityDrops.reduce((a, b) => a + b, 0) / salinityDrops.length
      : 0;

    return { total: batches.length, gradeA, gradeB, gradeC, avgDuration, avgSalinityDrop };
  }, [batches]);

  const gradeAPercent = stats.total > 0 ? Math.round((stats.gradeA / stats.total) * 100) : 0;

  // 배치 선택 토글
  const toggleBatchSelection = (batchId: number) => {
    setSelectedBatches(prev => {
      if (prev.includes(batchId)) {
        return prev.filter(id => id !== batchId);
      }
      if (prev.length >= 3) {
        return [...prev.slice(1), batchId]; // 최대 3개
      }
      return [...prev, batchId];
    });
  };

  // 선택된 배치 데이터
  const selectedBatchData = useMemo(() => {
    return batches.filter(b => selectedBatches.includes(b.id as unknown as number));
  }, [batches, selectedBatches]);

  // 성공 요인 분석
  const successFactorAnalysis = useMemo(() => {
    const aBatches = batches.filter(b => b.quality_grade === 'A');
    const bBatches = batches.filter(b => b.quality_grade === 'B');
    const cBatches = batches.filter(b => b.quality_grade === 'C');

    const avg = (arr: number[]) => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

    return {
      A: {
        count: aBatches.length,
        avgDuration: avg(aBatches.map(b => b.duration_hours)),
        avgInitialSalinity: avg(aBatches.filter(b => b.initial_salinity).map(b => b.initial_salinity || 0)),
        avgWeight: avg(aBatches.filter(b => b.avg_weight).map(b => b.avg_weight)),
        avgSalinityDrop: avg(aBatches.filter(b => b.initial_salinity && b.final_salinity)
          .map(b => (b.initial_salinity || 0) - (b.final_salinity || 0))),
      },
      B: {
        count: bBatches.length,
        avgDuration: avg(bBatches.map(b => b.duration_hours)),
        avgInitialSalinity: avg(bBatches.filter(b => b.initial_salinity).map(b => b.initial_salinity || 0)),
        avgWeight: avg(bBatches.filter(b => b.avg_weight).map(b => b.avg_weight)),
        avgSalinityDrop: avg(bBatches.filter(b => b.initial_salinity && b.final_salinity)
          .map(b => (b.initial_salinity || 0) - (b.final_salinity || 0))),
      },
      C: {
        count: cBatches.length,
        avgDuration: avg(cBatches.map(b => b.duration_hours)),
        avgInitialSalinity: avg(cBatches.filter(b => b.initial_salinity).map(b => b.initial_salinity || 0)),
        avgWeight: avg(cBatches.filter(b => b.avg_weight).map(b => b.avg_weight)),
        avgSalinityDrop: avg(cBatches.filter(b => b.initial_salinity && b.final_salinity)
          .map(b => (b.initial_salinity || 0) - (b.final_salinity || 0))),
      },
    };
  }, [batches]);

  return (
    <div className="space-y-6">
      {/* 에러 알림 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-red-700 font-medium">{error}</p>
            <p className="text-red-600 text-sm">백엔드 서버 연결을 확인해주세요</p>
          </div>
          <button onClick={loadBatches} className="btn-secondary text-sm">다시 시도</button>
        </div>
      )}

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="card">
          <p className="text-sm text-gray-500">전체 배치</p>
          <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">A등급</p>
          <p className="text-2xl font-bold text-green-600">{stats.gradeA}</p>
          <p className="text-xs text-gray-400">{gradeAPercent}%</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">B등급</p>
          <p className="text-2xl font-bold text-yellow-600">{stats.gradeB}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">C등급</p>
          <p className="text-2xl font-bold text-red-600">{stats.gradeC}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">평균 절임시간</p>
          <p className="text-2xl font-bold text-gray-900">{stats.avgDuration.toFixed(1)}h</p>
        </div>
        <div className="card">
          <div className="flex items-center gap-1">
            <TrendingUp className="w-4 h-4 text-blue-500" />
            <p className="text-sm text-gray-500">평균 염도 감소</p>
          </div>
          <p className="text-2xl font-bold text-blue-600">{stats.avgSalinityDrop.toFixed(1)}%</p>
        </div>
      </div>

      {/* 뷰 모드 및 필터 */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          {/* 뷰 모드 토글 */}
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                viewMode === 'list' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              목록
            </button>
            <button
              onClick={() => setViewMode('compare')}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1 ${
                viewMode === 'compare' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <GitCompare className="w-4 h-4" />
              비교
              {selectedBatches.length > 0 && (
                <span className="bg-white/20 px-1.5 rounded">{selectedBatches.length}</span>
              )}
            </button>
            <button
              onClick={() => setShowAnalysis(!showAnalysis)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1 ${
                showAnalysis ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              패턴 분석
            </button>
          </div>

          {/* 검색 */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="품종, 탱크명, 배치코드로 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
          </div>

          {/* 등급 필터 */}
          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={gradeFilter}
              onChange={(e) => setGradeFilter(e.target.value)}
              className="input w-auto"
            >
              <option value="all">전체 등급</option>
              <option value="A">A등급</option>
              <option value="B">B등급</option>
              <option value="C">C등급</option>
            </select>
          </div>

          <button onClick={loadBatches} disabled={isLoading} className="btn-secondary flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        </div>
      </div>

      {/* 패턴 분석 섹션 */}
      {showAnalysis && (
        <div className="card border-2 border-purple-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-600" />
              <h3 className="text-lg font-semibold text-gray-900">등급별 성공 요인 분석</h3>
            </div>
            <button onClick={() => setShowAnalysis(false)} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">지표</th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-green-600">A등급 ({successFactorAnalysis.A.count}건)</th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-yellow-600">B등급 ({successFactorAnalysis.B.count}건)</th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-red-600">C등급 ({successFactorAnalysis.C.count}건)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                <tr>
                  <td className="px-4 py-3 text-sm text-gray-700">평균 절임시간</td>
                  <td className="px-4 py-3 text-center font-medium text-green-700">{successFactorAnalysis.A.avgDuration.toFixed(1)}h</td>
                  <td className="px-4 py-3 text-center font-medium text-yellow-700">{successFactorAnalysis.B.avgDuration.toFixed(1)}h</td>
                  <td className="px-4 py-3 text-center font-medium text-red-700">{successFactorAnalysis.C.avgDuration.toFixed(1)}h</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-sm text-gray-700">평균 초기염도</td>
                  <td className="px-4 py-3 text-center font-medium text-green-700">{successFactorAnalysis.A.avgInitialSalinity.toFixed(1)}%</td>
                  <td className="px-4 py-3 text-center font-medium text-yellow-700">{successFactorAnalysis.B.avgInitialSalinity.toFixed(1)}%</td>
                  <td className="px-4 py-3 text-center font-medium text-red-700">{successFactorAnalysis.C.avgInitialSalinity.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-sm text-gray-700">평균 배추 무게</td>
                  <td className="px-4 py-3 text-center font-medium text-green-700">{successFactorAnalysis.A.avgWeight.toFixed(1)}kg</td>
                  <td className="px-4 py-3 text-center font-medium text-yellow-700">{successFactorAnalysis.B.avgWeight.toFixed(1)}kg</td>
                  <td className="px-4 py-3 text-center font-medium text-red-700">{successFactorAnalysis.C.avgWeight.toFixed(1)}kg</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 text-sm text-gray-700">평균 염도 감소량</td>
                  <td className="px-4 py-3 text-center font-medium text-green-700">{successFactorAnalysis.A.avgSalinityDrop.toFixed(1)}%</td>
                  <td className="px-4 py-3 text-center font-medium text-yellow-700">{successFactorAnalysis.B.avgSalinityDrop.toFixed(1)}%</td>
                  <td className="px-4 py-3 text-center font-medium text-red-700">{successFactorAnalysis.C.avgSalinityDrop.toFixed(1)}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* 인사이트 */}
          <div className="mt-4 p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-purple-800">
              <strong>분석 인사이트:</strong> A등급 배치는 평균 {successFactorAnalysis.A.avgDuration.toFixed(1)}시간 절임,
              초기 염도 {successFactorAnalysis.A.avgInitialSalinity.toFixed(1)}%에서 {successFactorAnalysis.A.avgSalinityDrop.toFixed(1)}% 감소했습니다.
              {successFactorAnalysis.A.avgDuration > successFactorAnalysis.B.avgDuration
                ? ' B등급 대비 충분한 절임 시간이 품질 향상에 기여했습니다.'
                : ' 적정 시간 내 완료가 품질 유지에 중요합니다.'}
            </p>
          </div>
        </div>
      )}

      {/* 비교 모드 패널 */}
      {viewMode === 'compare' && selectedBatchData.length > 0 && (
        <div className="card border-2 border-blue-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">배치 비교</h3>
              <span className="text-sm text-gray-500">(최대 3개 선택 가능)</span>
            </div>
            <button
              onClick={() => setSelectedBatches([])}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              선택 초기화
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {selectedBatchData.map((batch) => (
              <div key={batch.id} className="p-4 bg-gray-50 rounded-lg relative">
                <button
                  onClick={() => toggleBatchSelection(batch.id as unknown as number)}
                  className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="flex items-center gap-2 mb-3">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    gradeColors[batch.quality_grade as keyof typeof gradeColors] || 'bg-gray-100 text-gray-600'
                  }`}>
                    {batch.quality_grade}등급
                  </span>
                  <span className="text-sm text-gray-600">{batch.tank_name}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">품종</span>
                    <span className="font-medium">{batch.cultivar || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">무게</span>
                    <span className="font-medium">{batch.avg_weight}kg</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">절임시간</span>
                    <span className="font-medium">{batch.duration_hours}h</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">초기→최종 염도</span>
                    <span className="font-medium">
                      {batch.initial_salinity?.toFixed(1) || '-'}% → {batch.final_salinity?.toFixed(1) || '-'}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">시작일</span>
                    <span className="font-medium">
                      {new Date(batch.start_time).toLocaleDateString('ko-KR')}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 비교 인사이트 */}
          {selectedBatchData.length >= 2 && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>비교 분석:</strong>{' '}
                {(() => {
                  const durations = selectedBatchData.map(b => b.duration_hours);
                  const maxDiff = Math.max(...durations) - Math.min(...durations);
                  const grades = selectedBatchData.map(b => b.quality_grade);
                  const hasAGrade = grades.includes('A');

                  if (hasAGrade && maxDiff > 5) {
                    return `A등급 배치는 평균 ${selectedBatchData.find(b => b.quality_grade === 'A')?.duration_hours.toFixed(1)}시간 절임. 시간 관리가 핵심 요인으로 보입니다.`;
                  } else if (maxDiff < 2) {
                    return '선택된 배치들의 절임 시간이 비슷합니다. 다른 요인(초기 염도, 배추 상태)이 품질 차이를 만들었을 수 있습니다.';
                  } else {
                    return `절임 시간 차이가 ${maxDiff.toFixed(1)}시간입니다. 품질과 시간의 관계를 확인해보세요.`;
                  }
                })()}
              </p>
            </div>
          )}
        </div>
      )}

      {/* 테이블 */}
      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="py-12 text-center">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-3" />
            <p className="text-gray-500">데이터를 불러오는 중...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {viewMode === 'compare' && (
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      선택
                    </th>
                  )}
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button className="flex items-center gap-1 hover:text-gray-700" onClick={() => toggleSort('tank_id')}>
                      절임조
                      <ArrowUpDown className={`w-3 h-3 ${sortField === 'tank_id' ? 'text-blue-500' : ''}`} />
                    </button>
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">배치 코드</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">품종</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">무게</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button className="flex items-center gap-1 hover:text-gray-700" onClick={() => toggleSort('start_time')}>
                      시작 시간
                      <ArrowUpDown className={`w-3 h-3 ${sortField === 'start_time' ? 'text-blue-500' : ''}`} />
                    </button>
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">절임 시간</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">염도 (시작→종료)</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button className="flex items-center gap-1 hover:text-gray-700" onClick={() => toggleSort('quality_grade')}>
                      품질
                      <ArrowUpDown className={`w-3 h-3 ${sortField === 'quality_grade' ? 'text-blue-500' : ''}`} />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredBatches.map((batch) => {
                  const isSelected = selectedBatches.includes(batch.id as unknown as number);
                  return (
                    <tr
                      key={batch.id}
                      className={`hover:bg-gray-50 cursor-pointer transition-colors ${
                        isSelected ? 'bg-blue-50' : ''
                      }`}
                      onClick={() => viewMode === 'compare' && toggleBatchSelection(batch.id as unknown as number)}
                    >
                      {viewMode === 'compare' && (
                        <td className="px-4 py-4 text-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="w-4 h-4 text-blue-600 rounded"
                          />
                        </td>
                      )}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="font-medium text-gray-900">{batch.tank_name}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-500 text-sm">{batch.batch_code || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600">{batch.cultivar || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600">{batch.avg_weight ? `${batch.avg_weight}kg` : '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                        {new Date(batch.start_time).toLocaleString('ko-KR', {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                        })}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600">{batch.duration_hours}시간</td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                        <span className="text-blue-600">{batch.initial_salinity?.toFixed(1) || '-'}%</span>
                        <span className="mx-1">→</span>
                        <span className="text-green-600">{batch.final_salinity?.toFixed(1) || '-'}%</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {batch.quality_grade ? (
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            gradeColors[batch.quality_grade as keyof typeof gradeColors] || 'bg-gray-100 text-gray-600'
                          }`}>
                            {batch.quality_grade}등급
                          </span>
                        ) : (
                          <span className="text-gray-400 text-sm">미평가</span>
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
          <div className="py-12 text-center text-gray-500">
            {batches.length === 0 ? (
              <>
                <p className="text-lg font-medium mb-1">완료된 배치가 없습니다</p>
                <p className="text-sm">터치패널에서 배치를 완료하면 이력이 표시됩니다</p>
              </>
            ) : (
              '검색 결과가 없습니다'
            )}
          </div>
        )}
      </div>
    </div>
  );
}
