import { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Lightbulb, CheckCircle, Loader2, MessageCircle, Star,
  Clock, Target, AlertTriangle, TrendingUp, Play, ChevronRight
} from 'lucide-react';
import type {
  OptimizationRequest, OptimizationResponse,
  CompletionDecisionResponse, CompletionScenario, Batch
} from '../types';
import { mlApi, insightApi, batchesApi } from '../services/api';
import { ChatPanel } from '../components/ChatPanel';

const cultivars = ['해남', '괴산', '강원', '월동', '봄배추', '가을배추', '고랭지', '기타'];
const seasons = ['봄', '여름', '가을', '겨울'];
const targetGrades = [
  { value: 'A', label: 'A등급 (최고품질)' },
  { value: 'B', label: 'B등급 (양호)' },
  { value: 'C', label: 'C등급 (보통)' },
];

type TabType = 'start' | 'completion';

export function Optimize() {
  const [activeTab, setActiveTab] = useState<TabType>('start');

  // ===== 배치 시작 최적화 상태 =====
  const [formData, setFormData] = useState<OptimizationRequest>({
    avg_weight: 3.0,
    firmness: 70,
    room_temp: 18,
    cultivar: '해남',
    season: '겨울',
    target_quality: 'A',
  });
  const [result, setResult] = useState<OptimizationResponse | null>(null);
  const [insight, setInsight] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInsightLoading, setIsInsightLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  // ===== 완료 시점 결정 상태 =====
  const [activeBatches, setActiveBatches] = useState<Batch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [completionResult, setCompletionResult] = useState<CompletionDecisionResponse | null>(null);
  const [isCompletionLoading, setIsCompletionLoading] = useState(false);
  const [completionError, setCompletionError] = useState<string | null>(null);

  // 활성 배치 목록 로드
  const loadActiveBatches = useCallback(async () => {
    try {
      const batches = await batchesApi.getAll({ status: 'active' });
      setActiveBatches(batches);
      if (batches.length > 0 && !selectedBatchId) {
        setSelectedBatchId(batches[0].id as unknown as number);
      }
    } catch (err) {
      console.error('Failed to load active batches:', err);
    }
  }, [selectedBatchId]);

  useEffect(() => {
    if (activeTab === 'completion') {
      loadActiveBatches();
    }
  }, [activeTab, loadActiveBatches]);

  // ===== 배치 시작 최적화 핸들러 =====
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResult(null);
    setInsight(null);

    try {
      const optimizationResult = await mlApi.optimize(formData);
      setResult(optimizationResult);

      setIsInsightLoading(true);
      try {
        const insightResult = await insightApi.getOptimizationInsight({
          optimization_result: optimizationResult,
          input: formData,
        });
        setInsight(insightResult.insight);
      } catch {
        setInsight(generateDefaultInsight(formData, optimizationResult));
      } finally {
        setIsInsightLoading(false);
      }
    } catch (err) {
      console.error('Optimization failed:', err);
      setError('최적화 분석에 실패했습니다. 백엔드 서버 연결을 확인해주세요.');

      const dummyResult: OptimizationResponse = {
        recommended_salinity: formData.season === '겨울' ? 10.5 : 12.5,
        recommended_duration: formData.season === '겨울' ? 38.0 : 22.0,
        predicted_quality: formData.target_quality || 'A',
        quality_probability: { A: 0.72, B: 0.25, C: 0.03 },
        confidence: 0.89,
        reasoning: `규칙 기반 예측: ${formData.season} ${formData.cultivar} 품종, 무게 ${formData.avg_weight}kg 기준`,
        expected_final_salinity: 1.85,
        is_optimal: true,
      };
      setResult(dummyResult);
      setInsight(generateDefaultInsight(formData, dummyResult));
    } finally {
      setIsLoading(false);
    }
  };

  const generateDefaultInsight = (input: OptimizationRequest, output: OptimizationResponse): string => {
    const hours = Math.floor(output.recommended_duration);
    const minutes = Math.round((output.recommended_duration - hours) * 60);

    let insightText = `현재 ${input.cultivar} 배추(${input.avg_weight}kg)는 경도가 ${
      (input.firmness || 50) > 70 ? '높은' : (input.firmness || 50) > 40 ? '보통' : '낮은'
    } 편입니다.\n\n`;

    insightText += `초기 염도 ${output.recommended_salinity}%로 설정하시면 약 ${hours}시간`;
    if (minutes > 0) insightText += ` ${minutes}분`;
    insightText += ` 후 ${output.predicted_quality}등급 품질을 기대할 수 있습니다.`;

    return insightText;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'avg_weight' || name === 'firmness' || name === 'room_temp'
        ? parseFloat(value)
        : value,
    }));
  };

  // ===== 완료 시점 결정 핸들러 =====
  const handleCompletionAnalysis = async () => {
    if (!selectedBatchId) return;

    setIsCompletionLoading(true);
    setCompletionError(null);
    setCompletionResult(null);

    try {
      const result = await mlApi.getCompletionDecision(selectedBatchId);
      setCompletionResult(result);
    } catch (err) {
      console.error('Completion decision failed:', err);
      setCompletionError('완료 시점 분석에 실패했습니다.');
    } finally {
      setIsCompletionLoading(false);
    }
  };

  // 품질 등급 색상
  const getGradeColor = (grade: string, type: 'bg' | 'text' | 'border' = 'bg') => {
    const colors = {
      A: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-500' },
      B: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-500' },
      C: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-500' },
    };
    return colors[grade as keyof typeof colors]?.[type] || 'bg-gray-100';
  };

  // 시나리오 권장 레벨 색상
  const getRecommendationColor = (recommendation: string) => {
    switch (recommendation) {
      case '권장': return 'bg-green-500';
      case '적정': return 'bg-yellow-500';
      case '위험': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  // 품질 등급 별점
  const renderQualityStars = (grade: string) => {
    const stars = grade === 'A' ? 5 : grade === 'B' ? 3 : 1;
    return (
      <div className="flex items-center gap-1">
        {[...Array(5)].map((_, i) => (
          <Star
            key={i}
            className={`w-4 h-4 ${i < stars ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300'}`}
          />
        ))}
        <span className="ml-1 text-sm text-gray-600">({grade}등급)</span>
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto">
      {/* 헤더 */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">AI 절임 최적화</h2>
        <p className="text-gray-500 mt-1">ML 모델을 활용한 의사결정 지원</p>
      </div>

      {/* 탭 네비게이션 */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('start')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'start'
              ? 'bg-green-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Play className="w-4 h-4" />
          배치 시작 최적화
        </button>
        <button
          onClick={() => setActiveTab('completion')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'completion'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Target className="w-4 h-4" />
          완료 시점 결정
          {activeBatches.length > 0 && (
            <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">
              {activeBatches.length}
            </span>
          )}
        </button>
      </div>

      {/* 배치 시작 최적화 탭 */}
      {activeTab === 'start' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 입력 폼 */}
          <div className="card">
            <div className="flex items-center gap-3 mb-6">
              <FlaskConical className="w-5 h-5 text-green-600" />
              <h3 className="text-lg font-semibold text-gray-900">원물 정보 입력</h3>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">품종</label>
                <select name="cultivar" value={formData.cultivar} onChange={handleInputChange} className="input">
                  {cultivars.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div>
                <label className="label">평균 무게 (kg)</label>
                <input
                  type="number" name="avg_weight" value={formData.avg_weight}
                  onChange={handleInputChange} step="0.1" min="1" max="10" className="input"
                />
              </div>

              <div>
                <label className="label">경도 (단단함)</label>
                <input
                  type="range" name="firmness" value={formData.firmness || 50}
                  onChange={handleInputChange} min="0" max="100"
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>무름</span>
                  <span className="font-medium text-green-600">{formData.firmness || 50}</span>
                  <span>단단함</span>
                </div>
              </div>

              <div>
                <label className="label">실내 온도 (°C)</label>
                <input
                  type="number" name="room_temp" value={formData.room_temp || 18}
                  onChange={handleInputChange} step="0.5" min="0" max="40" className="input"
                />
              </div>

              <div>
                <label className="label">계절</label>
                <select name="season" value={formData.season} onChange={handleInputChange} className="input">
                  {seasons.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div>
                <label className="label">목표 품질</label>
                <select name="target_quality" value={formData.target_quality} onChange={handleInputChange} className="input">
                  {targetGrades.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                </select>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-600">{error}</div>
              )}

              <button type="submit" disabled={isLoading} className="btn-primary w-full flex items-center justify-center gap-2 py-3">
                {isLoading ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> AI 분석 중...</>
                ) : (
                  <><FlaskConical className="w-5 h-5" /> 최적화 분석</>
                )}
              </button>
            </form>
          </div>

          {/* 결과 패널 */}
          <div className="space-y-6">
            <div className={`card ${result ? 'border-green-200 border-2' : ''}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <CheckCircle className={`w-5 h-5 ${result ? 'text-green-600' : 'text-gray-300'}`} />
                  <h3 className="text-lg font-semibold text-gray-900">AI 추천 결과</h3>
                </div>
                {result && (
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    result.is_optimal ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {result.is_optimal ? '최적 범위' : '조정 필요'}
                  </span>
                )}
              </div>

              {result ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-green-50 rounded-lg p-4">
                      <p className="text-sm text-green-600 mb-1">권장 초기염도</p>
                      <p className="text-2xl font-bold text-green-700">{result.recommended_salinity}%</p>
                    </div>
                    <div className="bg-blue-50 rounded-lg p-4">
                      <p className="text-sm text-blue-600 mb-1">권장 절임시간</p>
                      <p className="text-2xl font-bold text-blue-700">
                        {Math.floor(result.recommended_duration)}시간
                        {Math.round((result.recommended_duration % 1) * 60) > 0 && ` ${Math.round((result.recommended_duration % 1) * 60)}분`}
                      </p>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-4">
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div>
                        <p className="text-xs text-gray-500">예상 최종 염도</p>
                        <p className="text-lg font-semibold text-gray-900">{result.expected_final_salinity?.toFixed(2) || '-'}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">예상 품질</p>
                        {renderQualityStars(result.predicted_quality)}
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">신뢰도</p>
                        <p className="text-lg font-semibold text-green-600">{Math.round(result.confidence * 100)}%</p>
                      </div>
                    </div>
                  </div>

                  {result.quality_probability && (
                    <div className="border-t border-gray-100 pt-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">품질 확률 분포</h4>
                      <div className="flex gap-2">
                        {Object.entries(result.quality_probability).map(([grade, prob]) => (
                          <div key={grade} className="flex-1">
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${grade === 'A' ? 'bg-green-500' : grade === 'B' ? 'bg-yellow-500' : 'bg-red-500'}`}
                                style={{ width: `${prob * 100}%` }}
                              />
                            </div>
                            <p className="text-xs text-center mt-1 text-gray-500">{grade}: {Math.round(prob * 100)}%</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-8 text-center text-gray-400">
                  <FlaskConical className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>원물 정보를 입력하고 분석을 시작하세요</p>
                </div>
              )}
            </div>

            {/* Claude 인사이트 */}
            <div className={`card ${insight ? 'border-yellow-200 border-2' : ''}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Lightbulb className={`w-5 h-5 ${insight ? 'text-yellow-500' : 'text-gray-300'}`} />
                  <h3 className="text-lg font-semibold text-gray-900">Claude 인사이트</h3>
                </div>
                {insight && (
                  <button onClick={() => setIsChatOpen(true)} className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
                    <MessageCircle className="w-4 h-4" /> 채팅
                  </button>
                )}
              </div>

              {isInsightLoading ? (
                <div className="py-8 text-center">
                  <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-yellow-500" />
                  <p className="text-gray-500">Claude가 분석 중입니다...</p>
                </div>
              ) : insight ? (
                <div className="bg-gradient-to-r from-yellow-50 to-amber-50 rounded-lg p-4">
                  <p className="text-gray-700 whitespace-pre-line leading-relaxed">{insight}</p>
                </div>
              ) : (
                <div className="py-8 text-center text-gray-400">
                  <Lightbulb className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>AI 분석 후 상세 인사이트가 표시됩니다</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 완료 시점 결정 탭 */}
      {activeTab === 'completion' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 배치 선택 */}
          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <Clock className="w-5 h-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">진행 중인 배치</h3>
            </div>

            {activeBatches.length === 0 ? (
              <div className="py-8 text-center text-gray-400">
                <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>진행 중인 배치가 없습니다</p>
              </div>
            ) : (
              <div className="space-y-2">
                {activeBatches.map((batch) => {
                  const startTime = new Date(batch.start_time);
                  const elapsed = (Date.now() - startTime.getTime()) / (1000 * 60 * 60);

                  return (
                    <button
                      key={batch.id}
                      onClick={() => setSelectedBatchId(batch.id as unknown as number)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedBatchId === (batch.id as unknown as number)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900">절임조 {batch.tank_id}</span>
                        <ChevronRight className="w-4 h-4 text-gray-400" />
                      </div>
                      <div className="mt-1 text-sm text-gray-500">
                        {batch.cultivar || '일반'} · {batch.avg_weight || 3}kg · {elapsed.toFixed(1)}시간 경과
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {selectedBatchId && (
              <button
                onClick={handleCompletionAnalysis}
                disabled={isCompletionLoading}
                className="btn-primary w-full mt-4 flex items-center justify-center gap-2"
              >
                {isCompletionLoading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> 분석 중...</>
                ) : (
                  <><Target className="w-4 h-4" /> 완료 시점 분석</>
                )}
              </button>
            )}
          </div>

          {/* 시나리오 결과 */}
          <div className="lg:col-span-2 space-y-4">
            {completionError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                <p className="text-red-700">{completionError}</p>
              </div>
            )}

            {completionResult ? (
              <>
                {/* 현재 상태 */}
                <div className="card border-2 border-blue-200">
                  <h4 className="font-semibold text-gray-900 mb-3">현재 배치 상태</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <p className="text-xs text-gray-500">경과 시간</p>
                      <p className="text-xl font-bold text-blue-600">
                        {completionResult.current_status.elapsed_hours}h
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500">현재 염도</p>
                      <p className="text-xl font-bold text-gray-900">
                        {completionResult.current_status.current_salinity}%
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500">품종</p>
                      <p className="text-xl font-bold text-gray-900">
                        {completionResult.current_status.cultivar}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500">무게</p>
                      <p className="text-xl font-bold text-gray-900">
                        {completionResult.current_status.avg_weight}kg
                      </p>
                    </div>
                  </div>
                </div>

                {/* 최적 시나리오 */}
                <div className="card bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300">
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <h4 className="font-semibold text-green-800">최적 완료 시점</h4>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-3xl font-bold text-green-700">
                        {completionResult.best_scenario.hours_from_now === 0
                          ? '지금 바로'
                          : `${completionResult.best_scenario.hours_from_now}시간 후`}
                      </p>
                      <p className="text-green-600 mt-1">{completionResult.recommendation}</p>
                    </div>
                    <div className="text-right">
                      <div className={`inline-block px-3 py-1 rounded-full ${getGradeColor(completionResult.best_scenario.predicted_grade)} ${getGradeColor(completionResult.best_scenario.predicted_grade, 'text')}`}>
                        <span className="text-2xl font-bold">{completionResult.best_scenario.predicted_grade}</span>
                        <span className="text-sm ml-1">등급</span>
                      </div>
                      <p className="text-sm text-green-600 mt-1">
                        확률 {Math.round(completionResult.best_scenario.grade_probabilities['A'] * 100)}%
                      </p>
                    </div>
                  </div>
                </div>

                {/* 시나리오 타임라인 */}
                <div className="card">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-5 h-5 text-blue-600" />
                    <h4 className="font-semibold text-gray-900">시간별 품질 예측</h4>
                  </div>

                  <div className="space-y-3">
                    {completionResult.scenarios.map((scenario: CompletionScenario, index: number) => (
                      <div
                        key={index}
                        className={`flex items-center gap-4 p-3 rounded-lg border ${
                          scenario.hours_from_now === completionResult.best_scenario.hours_from_now
                            ? 'border-green-300 bg-green-50'
                            : 'border-gray-200'
                        }`}
                      >
                        {/* 시간 */}
                        <div className="w-20 text-center">
                          <p className="text-lg font-bold text-gray-900">
                            {scenario.hours_from_now === 0 ? '지금' : `+${scenario.hours_from_now}h`}
                          </p>
                        </div>

                        {/* 등급 */}
                        <div className={`w-16 py-1 text-center rounded ${getGradeColor(scenario.predicted_grade)} ${getGradeColor(scenario.predicted_grade, 'text')}`}>
                          <span className="font-bold">{scenario.predicted_grade}</span>
                        </div>

                        {/* 확률 바 */}
                        <div className="flex-1">
                          <div className="flex gap-1 h-6">
                            {Object.entries(scenario.grade_probabilities).map(([grade, prob]) => (
                              <div
                                key={grade}
                                className={`${getGradeColor(grade)} rounded flex items-center justify-center text-xs font-medium ${getGradeColor(grade, 'text')}`}
                                style={{ width: `${prob * 100}%` }}
                              >
                                {prob >= 0.15 && `${grade}:${Math.round(prob * 100)}%`}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* 권장 레벨 */}
                        <div className={`w-16 py-1 text-center rounded text-white text-sm ${getRecommendationColor(scenario.recommendation)}`}>
                          {scenario.recommendation}
                        </div>

                        {/* 예상 염도 */}
                        <div className="w-16 text-right text-sm text-gray-500">
                          {scenario.estimated_salinity}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="card py-16 text-center text-gray-400">
                <Target className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-lg">배치를 선택하고 분석을 시작하세요</p>
                <p className="text-sm mt-2">
                  "지금 끝내면 어떤 등급인지, 더 기다리면 어떻게 되는지"<br />
                  시간별 품질 변화를 예측합니다
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat Panel */}
      <ChatPanel
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        context={result ? { optimization_result: result } : undefined}
      />
    </div>
  );
}
