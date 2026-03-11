import { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, CheckCircle, Loader2, Clock, Target, TrendingUp, Play, ChevronRight, Info
} from 'lucide-react';
import type {
  OptimizationRequest, OptimizationResponse,
  CompletionDecisionResponse, CompletionScenario, Batch
} from '../types';
import { mlApi, batchesApi } from '../services/api';

const cultivars = ['해남', '괴산', '강원', '월동', '봄배추', '가을배추', '고랭지', '기타'];
const seasons = ['봄', '여름', '가을', '겨울'];

// 확장된 폼 타입
interface ExtendedForm extends OptimizationRequest {
  leaf_thickness?: number;
  storage_days?: number;
  storage_type?: 'cold' | 'room';
  cut_type?: 'whole' | 'half';
  quantity?: number;
  salt_type?: 'sea' | 'refined';
  water_temp?: number;
}

type TabType = 'start' | 'completion';

export function Optimize() {
  const [activeTab, setActiveTab] = useState<TabType>('start');

  // 배치 시작 최적화
  const [formData, setFormData] = useState<ExtendedForm>({
    cultivar: '해남',
    avg_weight: 3.0,
    firmness: 70,           // UI: 0-100 스케일
    leaf_thickness: 3,      // mm 단위 (학습 데이터: 1-5)
    room_temp: 18,
    season: '겨울',
    target_quality: 'A',
    storage_days: 0,
    storage_type: 'cold',
    cut_type: 'half',
    quantity: 1000,
    salt_type: 'sea',
    water_temp: 12,
  });
  const [result, setResult] = useState<OptimizationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 염도 조정 상태
  const [adjustedSalinity, setAdjustedSalinity] = useState<number | null>(null);
  const [adjustedDuration, setAdjustedDuration] = useState<number | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);

  // 완료 시점 결정
  const [activeBatches, setActiveBatches] = useState<Batch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [completionResult, setCompletionResult] = useState<CompletionDecisionResponse | null>(null);
  const [isCompletionLoading, setIsCompletionLoading] = useState(false);

  // 활성 배치 로드
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

  // 배치 시작 최적화 핸들러
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResult(null);
    setAdjustedSalinity(null);
    setAdjustedDuration(null);

    try {
      const optimizationResult = await mlApi.optimize(formData);
      setResult(optimizationResult);
    } catch (err) {
      console.error('Optimization failed:', err);
      // 폴백 결과
      const dummyResult: OptimizationResponse = {
        recommended_salinity: formData.season === '겨울' ? 10.5 : 12.5,
        recommended_duration: formData.season === '겨울' ? 38.0 : 22.0,
        predicted_quality: formData.target_quality || 'A',
        quality_probability: { A: 0.72, B: 0.25, C: 0.03 },
        confidence: 0.89,
        reasoning: `${formData.cultivar} ${formData.avg_weight}kg, ${formData.season}철 조건`,
        expected_final_salinity: 1.85,
        is_optimal: true,
      };
      setResult(dummyResult);
      setError('백엔드 연결 오류 - 기본값으로 계산됨');
    } finally {
      setIsLoading(false);
    }
  };

  // 염도 조정 시 시간 재계산
  const handleSalinityAdjust = async (newSalinity: number) => {
    setAdjustedSalinity(newSalinity);
    setIsRecalculating(true);

    try {
      const response = await fetch(
        `http://localhost:8000/api/ml/recalculate-duration?salinity=${newSalinity}&season=${encodeURIComponent(formData.season)}&water_temp=${formData.water_temp || 15}&avg_weight=${formData.avg_weight}&base_duration=${result?.recommended_duration || 28}`,
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        setAdjustedDuration(data.recalculated_duration);
      }
    } catch (err) {
      console.error('Recalculation failed:', err);
      // 폴백: 간단한 선형 계산
      const baseSalinity = result?.recommended_salinity || 12;
      const baseDuration = result?.recommended_duration || 28;
      const salinityDiff = newSalinity - baseSalinity;
      const durationChange = salinityDiff * -6;
      setAdjustedDuration(Math.max(18, Math.min(48, baseDuration + durationChange)));
    } finally {
      setIsRecalculating(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]:
        name === 'avg_weight' ||
        name === 'firmness' ||
        name === 'room_temp' ||
        name === 'leaf_thickness' ||
        name === 'storage_days' ||
        name === 'quantity' ||
        name === 'water_temp'
          ? parseFloat(value)
          : value,
    }));
  };

  // 완료 시점 분석
  const handleCompletionAnalysis = async () => {
    if (!selectedBatchId) return;

    setIsCompletionLoading(true);
    setCompletionResult(null);

    try {
      const result = await mlApi.getCompletionDecision(selectedBatchId);
      setCompletionResult(result);
    } catch (err) {
      console.error('Completion decision failed:', err);
      // 목업 데이터
      const selectedBatch = activeBatches.find(b => (b.id as unknown as number) === selectedBatchId);
      if (selectedBatch) {
        const startTime = new Date(selectedBatch.start_time);
        const elapsed = (Date.now() - startTime.getTime()) / (1000 * 60 * 60);

        setCompletionResult({
          batch_id: selectedBatchId,
          current_status: {
            elapsed_hours: Math.round(elapsed * 10) / 10,
            current_salinity: 5.5,
            initial_salinity: Number(selectedBatch.initial_salinity) || 12,
            water_temp: 15,
            cultivar: selectedBatch.cultivar || '해남',
            season: selectedBatch.season || '겨울',
          },
          scenarios: [
            { hours_from_now: 0, predicted_grade: 'B', grade_probabilities: { A: 0.3, B: 0.5, C: 0.2 }, predicted_salinity: 5.5, confidence: 0.7, is_recommended: false },
            { hours_from_now: 2, predicted_grade: 'A', grade_probabilities: { A: 0.6, B: 0.3, C: 0.1 }, predicted_salinity: 3.8, confidence: 0.8, is_recommended: false },
            { hours_from_now: 4, predicted_grade: 'A', grade_probabilities: { A: 0.85, B: 0.12, C: 0.03 }, predicted_salinity: 2.2, confidence: 0.9, is_recommended: true },
            { hours_from_now: 6, predicted_grade: 'A', grade_probabilities: { A: 0.75, B: 0.2, C: 0.05 }, predicted_salinity: 1.5, confidence: 0.85, is_recommended: false },
          ],
          recommendation: '4시간 후 완료 시 A등급 확률 85%',
          optimal_scenario_index: 2,
          generated_at: new Date().toISOString(),
        });
      }
    } finally {
      setIsCompletionLoading(false);
    }
  };

  const getGradeColor = (grade: string) => {
    if (grade === 'A') return 'bg-emerald-100 text-emerald-700';
    if (grade === 'B') return 'bg-amber-100 text-amber-700';
    return 'bg-red-100 text-red-700';
  };

  const getRecommendationBadge = (scenario: CompletionScenario) => {
    if (scenario.is_recommended) {
      return { color: 'bg-emerald-500', text: '권장' };
    }
    const aProb = scenario.grade_probabilities['A'] || 0;
    if (aProb >= 0.7) return { color: 'bg-emerald-500', text: '적정' };
    if (aProb >= 0.4) return { color: 'bg-amber-500', text: '보통' };
    return { color: 'bg-red-500', text: '위험' };
  };

  // 최적 시나리오 찾기
  const getBestScenario = (result: CompletionDecisionResponse) => {
    return result.scenarios[result.optimal_scenario_index] || result.scenarios[0];
  };

  return (
    <div className="space-y-6">
      {/* 탭 */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('start')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'start'
              ? 'bg-slate-800 text-white'
              : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
        >
          <Play className="w-4 h-4" />
          배치 시작 최적화
        </button>
        <button
          onClick={() => setActiveTab('completion')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'completion'
              ? 'bg-slate-800 text-white'
              : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
        >
          <Target className="w-4 h-4" />
          완료 시점 결정
          {activeBatches.length > 0 && (
            <span className={`px-1.5 py-0.5 rounded text-xs ${activeTab === 'completion' ? 'bg-white/20' : 'bg-slate-100'}`}>
              {activeBatches.length}
            </span>
          )}
        </button>
      </div>

      {/* 배치 시작 최적화 */}
      {activeTab === 'start' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 입력 폼 */}
          <div className="bg-white rounded-lg border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-5">
              <FlaskConical className="w-5 h-5 text-slate-600" />
              <h3 className="font-semibold text-slate-800">원물 정보</h3>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 기본 정보 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">품종</label>
                  <select name="cultivar" value={formData.cultivar} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                    {cultivars.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">평균 무게 (kg)</label>
                  <input type="number" name="avg_weight" value={formData.avg_weight} onChange={handleInputChange} step="0.1" min="1" max="10" className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400" />
                </div>
              </div>

              {/* 배추 상태 */}
              <div className="pt-3 border-t border-slate-100">
                <p className="text-xs font-medium text-slate-500 mb-3">배추 상태</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">경도 (단단함)</label>
                    <input type="range" name="firmness" value={formData.firmness || 50} onChange={handleInputChange} min="0" max="100" className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer" />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>무름</span>
                      <span className="font-medium text-slate-600">{formData.firmness}</span>
                      <span>단단함</span>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">잎 두께 (mm)</label>
                    <input type="range" name="leaf_thickness" value={formData.leaf_thickness || 3} onChange={(e) => setFormData(prev => ({ ...prev, leaf_thickness: parseInt(e.target.value) }))} min="1" max="5" step="1" className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer" />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>얇음</span>
                      <span className="font-medium text-slate-600">{formData.leaf_thickness || 3}mm</span>
                      <span>두꺼움</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 mt-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">입고 시점</label>
                    <select name="storage_days" value={formData.storage_days} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      <option value={0}>당일 입고</option>
                      <option value={1}>1일 전</option>
                      <option value={2}>2일 전</option>
                      <option value={3}>3일 이상</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">보관 상태</label>
                    <select name="storage_type" value={formData.storage_type} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      <option value="cold">냉장</option>
                      <option value="room">상온</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">절단</label>
                    <select name="cut_type" value={formData.cut_type} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      <option value="half">반절</option>
                      <option value="whole">통배추</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 작업 환경 */}
              <div className="pt-3 border-t border-slate-100">
                <p className="text-xs font-medium text-slate-500 mb-3">작업 환경</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">계절</label>
                    <select name="season" value={formData.season} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      {seasons.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">실내 온도 (°C)</label>
                    <input type="number" name="room_temp" value={formData.room_temp} onChange={handleInputChange} step="0.5" className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">소금 종류</label>
                    <select name="salt_type" value={formData.salt_type} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      <option value="sea">천일염</option>
                      <option value="refined">정제염</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">염수 온도 (°C)</label>
                    <input type="number" name="water_temp" value={formData.water_temp} onChange={handleInputChange} step="0.5" className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400" />
                  </div>
                </div>
              </div>

              {/* 물량 및 목표 */}
              <div className="pt-3 border-t border-slate-100">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">예상 물량 (kg)</label>
                    <input type="number" name="quantity" value={formData.quantity} onChange={handleInputChange} step="100" className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">목표 품질</label>
                    <select name="target_quality" value={formData.target_quality} onChange={handleInputChange} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400">
                      <option value="A">A등급 (최고)</option>
                      <option value="B">B등급 (양호)</option>
                      <option value="C">C등급 (보통)</option>
                    </select>
                  </div>
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
                  <Info className="w-4 h-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> 분석 중...</>
                ) : (
                  <><FlaskConical className="w-4 h-4" /> 최적화 분석</>
                )}
              </button>
            </form>
          </div>

          {/* 결과 */}
          <div className="space-y-4">
            <div className={`bg-white rounded-lg border p-5 ${result ? 'border-emerald-200' : 'border-slate-200'}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle className={`w-5 h-5 ${result ? 'text-emerald-500' : 'text-slate-300'}`} />
                  <h3 className="font-semibold text-slate-800">AI 추천 결과</h3>
                </div>
                {result && (
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${result.is_optimal ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {result.is_optimal ? '최적 범위' : '조정 필요'}
                  </span>
                )}
              </div>

              {result ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-50 rounded-lg p-4">
                      <p className="text-xs text-slate-500 mb-1">권장 초기염도</p>
                      <p className="text-2xl font-bold text-slate-800">
                        {adjustedSalinity !== null ? adjustedSalinity : result.recommended_salinity}%
                        {adjustedSalinity !== null && adjustedSalinity !== result.recommended_salinity && (
                          <span className="text-xs font-normal text-amber-600 ml-2">
                            (기본: {result.recommended_salinity}%)
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-4">
                      <p className="text-xs text-slate-500 mb-1">권장 절임시간</p>
                      <div className="flex items-center gap-2">
                        <p className="text-2xl font-bold text-slate-800">
                          {(() => {
                            const duration = adjustedDuration !== null ? adjustedDuration : result.recommended_duration;
                            return `${Math.floor(duration)}시간${Math.round((duration % 1) * 60) > 0 ? ` ${Math.round((duration % 1) * 60)}분` : ''}`;
                          })()}
                        </p>
                        {isRecalculating && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                      </div>
                      {adjustedDuration !== null && adjustedDuration !== result.recommended_duration && (
                        <span className="text-xs text-amber-600">
                          (기본: {Math.floor(result.recommended_duration)}시간)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 염도 조정 슬라이더 */}
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-blue-800">염도 조정</p>
                      <span className="text-xs text-blue-600">
                        염도 ↑ → 시간 ↓ | 염도 ↓ → 시간 ↑
                      </span>
                    </div>
                    <input
                      type="range"
                      min="8"
                      max="15"
                      step="0.5"
                      value={adjustedSalinity !== null ? adjustedSalinity : result.recommended_salinity}
                      onChange={(e) => handleSalinityAdjust(parseFloat(e.target.value))}
                      className="w-full h-2 bg-blue-200 rounded-lg appearance-none cursor-pointer"
                    />
                    <div className="flex justify-between text-xs text-blue-500 mt-1">
                      <span>8%</span>
                      <span className="font-medium text-blue-700">
                        {adjustedSalinity !== null ? adjustedSalinity : result.recommended_salinity}%
                      </span>
                      <span>15%</span>
                    </div>
                    {adjustedSalinity !== null && adjustedSalinity !== result.recommended_salinity && (
                      <button
                        onClick={() => {
                          setAdjustedSalinity(null);
                          setAdjustedDuration(null);
                        }}
                        className="mt-2 text-xs text-blue-600 hover:text-blue-800 underline"
                      >
                        기본값으로 초기화
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-3 pt-4 border-t border-slate-100">
                    <div className="text-center">
                      <p className="text-xs text-slate-500">예상 최종 염도</p>
                      <p className="text-lg font-semibold text-slate-700">{result.expected_final_salinity?.toFixed(2)}%</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-slate-500">예상 품질</p>
                      <span className={`inline-block px-2 py-0.5 text-sm font-bold rounded ${getGradeColor(result.predicted_quality)}`}>
                        {result.predicted_quality}등급
                      </span>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-slate-500">신뢰도</p>
                      <p className="text-lg font-semibold text-emerald-600">{Math.round(result.confidence * 100)}%</p>
                    </div>
                  </div>

                  {result.quality_probability && (
                    <div className="pt-4 border-t border-slate-100">
                      <p className="text-xs text-slate-500 mb-2">품질 확률 분포</p>
                      <div className="flex gap-2">
                        {Object.entries(result.quality_probability).map(([grade, prob]) => (
                          <div key={grade} className="flex-1">
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${grade === 'A' ? 'bg-emerald-500' : grade === 'B' ? 'bg-amber-500' : 'bg-red-500'}`}
                                style={{ width: `${prob * 100}%` }}
                              />
                            </div>
                            <p className="text-xs text-center mt-1 text-slate-500">{grade}: {Math.round(prob * 100)}%</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-12 text-center text-slate-400">
                  <FlaskConical className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>원물 정보를 입력하고 분석하세요</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 완료 시점 결정 */}
      {activeTab === 'completion' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 배치 선택 */}
          <div className="bg-white rounded-lg border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-slate-600" />
              <h3 className="font-semibold text-slate-800">진행 중인 배치</h3>
            </div>

            {activeBatches.length === 0 ? (
              <div className="py-12 text-center text-slate-400">
                <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>진행 중인 배치 없음</p>
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
                          ? 'border-slate-400 bg-slate-50'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-slate-700">절임조 {batch.tank_id}</span>
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      </div>
                      <p className="text-sm text-slate-500 mt-1">
                        {batch.cultivar || '일반'} · {batch.avg_weight || 3}kg · {elapsed.toFixed(1)}h 경과
                      </p>
                    </button>
                  );
                })}
              </div>
            )}

            {selectedBatchId && (
              <button
                onClick={handleCompletionAnalysis}
                disabled={isCompletionLoading}
                className="w-full mt-4 py-2.5 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
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
            {completionResult ? (
              <>
                {/* 현재 상태 */}
                <div className="bg-white rounded-lg border border-slate-200 p-5">
                  <h4 className="font-semibold text-slate-700 mb-3">현재 상태</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div>
                      <p className="text-xs text-slate-500">경과 시간</p>
                      <p className="text-xl font-bold text-slate-800">{completionResult.current_status.elapsed_hours}h</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">현재 염도</p>
                      <p className="text-xl font-bold text-slate-800">{completionResult.current_status.current_salinity}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">품종</p>
                      <p className="text-xl font-bold text-slate-800">{completionResult.current_status.cultivar}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">수온</p>
                      <p className="text-xl font-bold text-slate-800">{completionResult.current_status.water_temp}°C</p>
                    </div>
                  </div>
                </div>

                {/* 최적 시나리오 */}
                {(() => {
                  const bestScenario = getBestScenario(completionResult);
                  return (
                    <div className="bg-emerald-50 rounded-lg border border-emerald-200 p-5">
                      <div className="flex items-center gap-2 mb-2">
                        <CheckCircle className="w-5 h-5 text-emerald-600" />
                        <h4 className="font-semibold text-emerald-800">최적 완료 시점</h4>
                      </div>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-3xl font-bold text-emerald-700">
                            {bestScenario.hours_from_now === 0
                              ? '지금'
                              : `${bestScenario.hours_from_now}시간 후`}
                          </p>
                          <p className="text-sm text-emerald-600 mt-1">{completionResult.recommendation}</p>
                        </div>
                        <div className="text-right">
                          <span className={`inline-block px-3 py-1 text-xl font-bold rounded ${getGradeColor(bestScenario.predicted_grade)}`}>
                            {bestScenario.predicted_grade}등급
                          </span>
                          <p className="text-sm text-emerald-600 mt-1">
                            확률 {Math.round((bestScenario.grade_probabilities['A'] || 0) * 100)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* 시나리오 타임라인 */}
                <div className="bg-white rounded-lg border border-slate-200 p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-5 h-5 text-slate-600" />
                    <h4 className="font-semibold text-slate-700">시간별 품질 예측</h4>
                  </div>

                  <div className="space-y-2">
                    {completionResult.scenarios.map((scenario: CompletionScenario, idx: number) => {
                      const badge = getRecommendationBadge(scenario);
                      return (
                        <div
                          key={idx}
                          className={`flex items-center gap-4 p-3 rounded-lg border ${
                            scenario.is_recommended
                              ? 'border-emerald-300 bg-emerald-50'
                              : 'border-slate-100'
                          }`}
                        >
                          <div className="w-16 text-center">
                            <p className="font-semibold text-slate-800">
                              {scenario.hours_from_now === 0 ? '지금' : `+${scenario.hours_from_now}h`}
                            </p>
                          </div>

                          <span className={`px-2 py-1 text-sm font-bold rounded ${getGradeColor(scenario.predicted_grade)}`}>
                            {scenario.predicted_grade}
                          </span>

                          <div className="flex-1 flex gap-0.5 h-5">
                            {Object.entries(scenario.grade_probabilities).map(([grade, prob]) => (
                              <div
                                key={grade}
                                className={`rounded ${grade === 'A' ? 'bg-emerald-400' : grade === 'B' ? 'bg-amber-400' : 'bg-red-400'} flex items-center justify-center text-xs text-white font-medium`}
                                style={{ width: `${prob * 100}%` }}
                              >
                                {prob >= 0.2 && `${Math.round(prob * 100)}%`}
                              </div>
                            ))}
                          </div>

                          <span className={`px-2 py-1 text-xs text-white font-medium rounded ${badge.color}`}>
                            {badge.text}
                          </span>

                          <span className="w-14 text-right text-sm text-slate-500">
                            {scenario.predicted_salinity}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-white rounded-lg border border-slate-200 p-16 text-center text-slate-400">
                <Target className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-lg">배치를 선택하고 분석하세요</p>
                <p className="text-sm mt-2">시간별 품질 변화를 예측합니다</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
