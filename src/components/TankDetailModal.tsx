import { useState, useEffect } from 'react';
import { X, Send, Loader2, TrendingDown, Thermometer, Droplets, Bot, LineChart } from 'lucide-react';
import type { Tank } from '../types';
import { batchesApi } from '../services/api';
import { useStore } from '../stores/useStore';

interface TankDetailModalProps {
  tank: Tank;
  onClose: () => void;
}

interface MeasurementData {
  timestamp: string;
  top_salinity: number;
  bottom_salinity: number;
  water_temp: number;
  salinity_avg: number;
}

export function TankDetailModal({ tank, onClose }: TankDetailModalProps) {
  const batch = tank.current_batch;
  const [measurements, setMeasurements] = useState<MeasurementData[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [hoveredPoint, setHoveredPoint] = useState<{ index: number; x: number; y: number } | null>(null);
  const sendAnalysisRequest = useStore((state) => state.sendAnalysisRequest);

  // 측정 데이터 로드
  useEffect(() => {
    const loadMeasurements = async () => {
      if (!batch?.id) return;

      setIsLoadingData(true);
      try {
        const batchDetail = await batchesApi.getById(batch.id);
        if (batchDetail.measurements) {
          setMeasurements(batchDetail.measurements);
        }
      } catch (error) {
        console.error('Failed to load measurements:', error);
        // 더미 데이터 사용
        setMeasurements(generateDummyMeasurements());
      } finally {
        setIsLoadingData(false);
      }
    };

    loadMeasurements();
  }, [batch?.id]);

  // 더미 측정 데이터 생성
  const generateDummyMeasurements = (): MeasurementData[] => {
    const data: MeasurementData[] = [];
    const startSalinity = batch?.initial_salinity || 12;
    const now = new Date();

    for (let i = 0; i < 10; i++) {
      const progress = i / 9;
      const timestamp = new Date(now.getTime() - (9 - i) * 2 * 60 * 60 * 1000);
      const salinity = startSalinity * Math.exp(-2 * progress) + 2;

      data.push({
        timestamp: timestamp.toISOString(),
        top_salinity: salinity + Math.random() * 0.3,
        bottom_salinity: salinity + 0.5 + Math.random() * 0.3,
        water_temp: 12 + progress * 6 + Math.random() * 2,
        salinity_avg: salinity + 0.25,
      });
    }
    return data;
  };

  // AI 분석 요청 - 프롬프트를 AI 어시스턴트 채팅창으로 전송
  const handleAIAnalysis = () => {
    if (!batch) return;

    const currentSalinity = batch.latest_measurement?.salinity_avg || 0;
    const topSalinity = batch.latest_measurement?.top_salinity || 0;
    const bottomSalinity = batch.latest_measurement?.bottom_salinity || 0;
    const waterTemp = batch.latest_measurement?.water_temp || 0;
    const progress = batch.progress || 0;
    const elapsedHours = batch.latest_measurement?.elapsed_minutes
      ? Math.round(batch.latest_measurement.elapsed_minutes / 60)
      : 0;

    // AI 어시스턴트에 전송할 프롬프트 생성
    const prompt = `[${tank.name}] 절임 상태 분석을 요청합니다.

현재 상태:
- 품종: ${batch.cultivar || '미지정'}
- 평균 무게: ${batch.avg_weight || '-'}kg
- 초기 염도: ${batch.initial_salinity || '-'}%
- 진행률: ${progress}%
- 경과 시간: ${elapsedHours}시간

현재 측정값:
- 상단 염도: ${topSalinity.toFixed(1)}%
- 하단 염도: ${bottomSalinity.toFixed(1)}%
- 평균 염도: ${currentSalinity.toFixed(1)}%
- 수온: ${waterTemp.toFixed(1)}°C

위 정보를 바탕으로 현재 절임 상태를 분석하고, 최적의 완료 시점과 권장 조치사항을 알려주세요.`;

    // 측정 이력 컨텍스트 추가
    let measurementContext = '';
    if (measurements.length > 0) {
      const recentMeasurements = measurements.slice(-5);
      measurementContext = `\n[측정 이력 데이터]
최근 ${recentMeasurements.length}회 측정값:
${recentMeasurements.map((m, i) =>
  `- ${i + 1}회: 상단 ${m.top_salinity.toFixed(1)}%, 하단 ${m.bottom_salinity.toFixed(1)}%, 수온 ${m.water_temp.toFixed(1)}°C`
).join('\n')}`;
    }

    // AI 어시스턴트 채팅창에 프롬프트 전송 (페이지 컨텍스트 + 측정 이력)
    sendAnalysisRequest(prompt, measurementContext);

    // 모달 닫기
    onClose();
  };

  // 시간 포맷팅 함수
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  };

  // 인터랙티브 라인 차트 렌더링
  const renderInteractiveChart = (
    data: number[],
    color: string,
    label: string,
    chartId: string
  ) => {
    if (data.length === 0) return null;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const width = 100;
    const height = 60;
    const padding = 8;

    const pointsArray = data.map((val, i) => {
      const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((val - min) / range) * (height - 2 * padding);
      return { x, y, value: val };
    });

    const polylinePoints = pointsArray.map(p => `${p.x},${p.y}`).join(' ');

    return (
      <div className="flex-1">
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <div className="bg-gray-50 rounded-lg p-2 relative">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-16"
            onMouseLeave={() => setHoveredPoint(null)}
          >
            {/* 그리드 라인 */}
            <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#e5e7eb" strokeWidth="0.5" />
            <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="#e5e7eb" strokeWidth="0.5" />

            {/* 라인 */}
            <polyline
              fill="none"
              stroke={color}
              strokeWidth="2"
              points={polylinePoints}
            />

            {/* 인터랙티브 포인트들 */}
            {pointsArray.map((point, i) => (
              <g key={i}>
                {/* 투명한 큰 원 - 호버 영역 */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r="6"
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
                    if (rect) {
                      setHoveredPoint({ index: i, x: point.x, y: point.y });
                    }
                  }}
                />
                {/* 실제 보이는 원 */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={hoveredPoint?.index === i ? 4 : 2.5}
                  fill={hoveredPoint?.index === i ? color : 'white'}
                  stroke={color}
                  strokeWidth="1.5"
                  className="transition-all duration-150"
                />
              </g>
            ))}
          </svg>

          {/* 툴팁 */}
          {hoveredPoint && (
            <div
              className="absolute bg-gray-800 text-white text-xs px-2 py-1 rounded shadow-lg pointer-events-none z-10 whitespace-nowrap"
              style={{
                left: `${(hoveredPoint.x / width) * 100}%`,
                top: '-8px',
                transform: 'translate(-50%, -100%)',
              }}
            >
              <div className="font-semibold">{data[hoveredPoint.index]?.toFixed(2)}</div>
              <div className="text-gray-300 text-[10px]">
                {measurements[hoveredPoint.index] && formatTime(measurements[hoveredPoint.index].timestamp)}
              </div>
            </div>
          )}

          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{data[0]?.toFixed(1)}</span>
            <span className="text-gray-300">|</span>
            <span>{data[data.length - 1]?.toFixed(1)}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="bg-gradient-to-r from-blue-500 to-emerald-500 text-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">{tank.name}</h2>
              {batch && (
                <p className="text-white/80 text-sm mt-1">
                  {batch.cultivar} 배추 · {batch.avg_weight}kg · 초기염도 {batch.initial_salinity}%
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {batch && (
            <div className="mt-4 flex items-center gap-4">
              <div className="flex-1 bg-white/20 rounded-full h-3">
                <div
                  className="bg-white h-3 rounded-full transition-all"
                  style={{ width: `${batch.progress || 0}%` }}
                />
              </div>
              <span className="text-lg font-bold">{batch.progress || 0}%</span>
            </div>
          )}
        </div>

        {/* 본문 */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {!batch ? (
            <div className="text-center py-12 text-gray-400">
              <Droplets className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>현재 진행 중인 배치가 없습니다</p>
            </div>
          ) : (
            <>
              {/* 현재 상태 */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-blue-50 rounded-xl p-4 text-center">
                  <Droplets className="w-6 h-6 text-blue-500 mx-auto mb-2" />
                  <p className="text-xs text-blue-600 mb-1">상단 염도</p>
                  <p className="text-2xl font-bold text-blue-700">
                    {batch.latest_measurement?.top_salinity?.toFixed(1) || '-'}%
                  </p>
                </div>
                <div className="bg-emerald-50 rounded-xl p-4 text-center">
                  <Droplets className="w-6 h-6 text-emerald-500 mx-auto mb-2" />
                  <p className="text-xs text-emerald-600 mb-1">하단 염도</p>
                  <p className="text-2xl font-bold text-emerald-700">
                    {batch.latest_measurement?.bottom_salinity?.toFixed(1) || '-'}%
                  </p>
                </div>
                <div className="bg-orange-50 rounded-xl p-4 text-center">
                  <Thermometer className="w-6 h-6 text-orange-500 mx-auto mb-2" />
                  <p className="text-xs text-orange-600 mb-1">수온</p>
                  <p className="text-2xl font-bold text-orange-700">
                    {batch.latest_measurement?.water_temp?.toFixed(1) || '-'}°C
                  </p>
                </div>
              </div>

              {/* 그래프 섹션 */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <LineChart className="w-5 h-5 text-gray-500" />
                  <h3 className="font-semibold text-gray-800">변화 추이</h3>
                </div>

                {isLoadingData ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                  </div>
                ) : (
                  <>
                    {/* 인터랙티브 차트 */}
                    <div className="flex gap-4 mb-4">
                      {renderInteractiveChart(
                        measurements.map(m => m.top_salinity),
                        '#3B82F6',
                        '상단 염도 (%)',
                        'top-salinity'
                      )}
                      {renderInteractiveChart(
                        measurements.map(m => m.bottom_salinity),
                        '#10B981',
                        '하단 염도 (%)',
                        'bottom-salinity'
                      )}
                      {renderInteractiveChart(
                        measurements.map(m => m.water_temp),
                        '#F97316',
                        '수온 (°C)',
                        'water-temp'
                      )}
                    </div>

                    {/* 측정 이력 테이블 */}
                    <div className="bg-gray-50 rounded-lg overflow-hidden">
                      <div className="text-xs font-medium text-gray-500 bg-gray-100 px-3 py-2">
                        최근 측정 이력
                      </div>
                      <div className="max-h-32 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr className="text-gray-500">
                              <th className="px-3 py-1.5 text-left font-medium">시간</th>
                              <th className="px-3 py-1.5 text-right font-medium">상단</th>
                              <th className="px-3 py-1.5 text-right font-medium">하단</th>
                              <th className="px-3 py-1.5 text-right font-medium">수온</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[...measurements].reverse().slice(0, 5).map((m, i) => (
                              <tr key={i} className={i === 0 ? 'bg-blue-50' : 'hover:bg-gray-50'}>
                                <td className="px-3 py-1.5 text-gray-600">
                                  {formatTime(m.timestamp)}
                                </td>
                                <td className="px-3 py-1.5 text-right text-blue-600 font-medium">
                                  {m.top_salinity.toFixed(1)}%
                                </td>
                                <td className="px-3 py-1.5 text-right text-emerald-600 font-medium">
                                  {m.bottom_salinity.toFixed(1)}%
                                </td>
                                <td className="px-3 py-1.5 text-right text-orange-600 font-medium">
                                  {m.water_temp.toFixed(1)}°C
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* AI 분석 섹션 */}
              <div className="border-t pt-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="w-5 h-5 text-purple-500" />
                    <h3 className="font-semibold text-gray-800">AI 어시스턴트</h3>
                  </div>
                  <button
                    onClick={handleAIAnalysis}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-indigo-500 text-white rounded-lg hover:from-purple-600 hover:to-indigo-600 transition-all"
                  >
                    <Send className="w-4 h-4" />
                    AI 분석 요청
                  </button>
                </div>
                <p className="text-gray-400 text-sm text-center py-3">
                  버튼을 누르면 오른쪽 AI 어시스턴트 채팅창에서 분석을 받아볼 수 있습니다
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
