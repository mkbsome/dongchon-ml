import { useState, useEffect } from 'react';
import { Clock, Thermometer, Droplets, Activity, Star, AlertTriangle, TrendingUp, AlertCircle } from 'lucide-react';
import type { Tank, AnomalyCheckResponse } from '../types';
import { mlApi } from '../services/api';

interface TankCardProps {
  tank: Tank;
  onClick?: () => void;
}

interface MLPrediction {
  remainingHours: number;
  predictedGrade: string;
  confidence: number;
  progress: number;
}

export function TankCard({ tank, onClick }: TankCardProps) {
  const batch = tank.current_batch;
  const isActive = tank.is_active && batch;
  const [mlPrediction, setMlPrediction] = useState<MLPrediction | null>(null);
  const [anomalyData, setAnomalyData] = useState<AnomalyCheckResponse | null>(null);

  // ML 예측 및 이상감지
  useEffect(() => {
    if (!isActive || !batch?.id) return;

    const fetchPrediction = async () => {
      try {
        // 병렬로 시간 예측과 이상감지 요청
        const batchIdNum = typeof batch.id === 'string' ? parseInt(batch.id) : batch.id;

        const [timePred, anomalyCheck] = await Promise.allSettled([
          mlApi.predictTime(batch.id.toString()),
          mlApi.checkAnomaly(batchIdNum)
        ]);

        // 경과 시간 계산
        const startTime = new Date(batch.start_time);
        const now = new Date();
        const elapsedHours = (now.getTime() - startTime.getTime()) / (1000 * 60 * 60);

        // 시간 예측 처리
        let remainingHours = 22 - elapsedHours;
        let progress = batch.progress || 0;

        if (timePred.status === 'fulfilled') {
          remainingHours = timePred.value.remaining_hours || remainingHours;
          progress = timePred.value.current_progress || progress;
        }

        // 이상감지 처리
        if (anomalyCheck.status === 'fulfilled') {
          setAnomalyData(anomalyCheck.value);
        }

        // 품질 예측 (현재 상태 기준)
        let predictedGrade = 'A';
        let confidence = 0.85;

        if (batch.latest_measurement?.salinity_avg) {
          const currentSalinity = batch.latest_measurement.salinity_avg;
          if (currentSalinity > 4) {
            predictedGrade = 'A';
            confidence = 0.9;
          } else if (currentSalinity > 2.5) {
            predictedGrade = 'A';
            confidence = 0.85;
          } else if (currentSalinity > 1.5) {
            predictedGrade = 'B';
            confidence = 0.7;
          } else {
            predictedGrade = 'C';
            confidence = 0.6;
          }
        }

        setMlPrediction({
          remainingHours,
          predictedGrade,
          confidence,
          progress,
        });
      } catch (error) {
        console.error('ML prediction error:', error);
        // 폴백: 간단한 계산
        const startTime = new Date(batch.start_time);
        const now = new Date();
        const elapsedHours = (now.getTime() - startTime.getTime()) / (1000 * 60 * 60);
        const expectedDuration = batch.season === '겨울' ? 38 : 22;

        setMlPrediction({
          remainingHours: Math.max(0, expectedDuration - elapsedHours),
          predictedGrade: 'A',
          confidence: 0.7,
          progress: Math.min(100, (elapsedHours / expectedDuration) * 100),
        });
      }
    };

    fetchPrediction();

    // 5분마다 갱신
    const interval = setInterval(fetchPrediction, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [isActive, batch?.id, batch?.start_time, batch?.season, batch?.progress, batch?.latest_measurement]);

  // 경과 시간 계산
  const getElapsedTime = () => {
    if (!batch?.start_time) return null;
    const elapsed = Date.now() - new Date(batch.start_time).getTime();
    const hours = Math.floor(elapsed / (1000 * 60 * 60));
    const minutes = Math.floor((elapsed % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}시간 ${minutes}분`;
  };

  // 남은 시간 포맷
  const formatRemainingTime = (hours: number) => {
    if (hours <= 0) return '완료 임박';
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (h === 0) return `약 ${m}분`;
    if (m === 0) return `약 ${h}시간`;
    return `약 ${h}시간 ${m}분`;
  };

  // 품질 등급 색상
  const gradeColors: Record<string, { bg: string; text: string; border: string }> = {
    A: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200' },
    B: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200' },
    C: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' },
  };

  // 진행률 기반 색상
  const getProgressColor = (progress: number) => {
    if (progress >= 90) return 'bg-amber-500';
    if (progress >= 70) return 'bg-green-500';
    return 'bg-blue-500';
  };

  // 이상 여부 확인
  const hasAnomaly = anomalyData?.is_anomaly || false;
  const anomalyAlerts = anomalyData?.alerts || [];

  return (
    <div
      onClick={onClick}
      className={`rounded-2xl p-5 cursor-pointer transition-all duration-300 ${
        hasAnomaly
          ? 'bg-gradient-to-br from-red-500 to-orange-600 text-white shadow-lg shadow-red-200'
          : isActive
          ? 'bg-gradient-to-br from-blue-500 to-emerald-500 text-white shadow-lg shadow-blue-200'
          : 'bg-white border border-gray-200 shadow-sm hover:shadow-md'
      }`}
    >
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-3 gap-2">
        <h3 className={`text-lg font-semibold shrink-0 ${isActive || hasAnomaly ? 'text-white' : 'text-gray-900'}`}>{tank.name}</h3>
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {/* 이상감지 경고 */}
          {hasAnomaly && (
            <span className="px-2 py-1 rounded-full text-[11px] font-bold flex items-center gap-1 bg-white/20 text-white whitespace-nowrap">
              <AlertCircle className="w-3 h-3" />
              이상감지
            </span>
          )}
          {/* ML 예상 품질 등급 */}
          {isActive && mlPrediction && !hasAnomaly && (
            <span className="px-2 py-1 rounded-full text-[11px] font-bold flex items-center gap-1 bg-white/20 text-white whitespace-nowrap">
              <Star className="w-3 h-3" />
              {mlPrediction.predictedGrade}등급
            </span>
          )}
          <span
            className={`px-2 py-1 rounded-full text-[11px] font-medium whitespace-nowrap ${
              isActive || hasAnomaly
                ? 'bg-white/20 text-white'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {isActive ? '작업중' : '대기'}
          </span>
        </div>
      </div>

      {isActive && batch ? (
        <>
          {/* 이상감지 알림 (있는 경우) */}
          {hasAnomaly && anomalyAlerts.length > 0 && (
            <div className="mb-3 p-3 rounded-lg bg-white/10 backdrop-blur">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="w-4 h-4 text-white" />
                <span className="text-sm font-medium text-white">주의 필요</span>
              </div>
              <ul className="text-xs text-white/90 space-y-1">
                {anomalyAlerts.slice(0, 2).map((alert, idx) => (
                  <li key={idx} className="flex items-start gap-1">
                    <span className="mt-0.5">•</span>
                    <span>{alert}</span>
                  </li>
                ))}
              </ul>
              {anomalyData?.similar_batches && anomalyData.similar_batches.length > 0 && (
                <p className="text-xs text-white/80 mt-2">
                  유사 배치 {anomalyData.similar_batches.length}건 기준 비교
                </p>
              )}
            </div>
          )}

          {/* 배추 정보 */}
          <div className={`mb-3 pb-3 border-b ${hasAnomaly ? 'border-white/20' : 'border-white/30'}`}>
            <p className="text-sm text-white/90">
              <span className="font-medium text-white">{batch.cultivar}</span> 배추
              <span className="mx-2">·</span>
              <span>{batch.avg_weight}kg</span>
              <span className="mx-2">·</span>
              <span className="text-white">{batch.initial_salinity}%</span>
            </p>
            <p className="text-xs text-white/60 mt-1">
              배치: {batch.batch_code}
            </p>
          </div>

          {/* ML 예측 하이라이트 */}
          {mlPrediction && !hasAnomaly && (
            <div className={`mb-3 p-3 rounded-lg ${
              mlPrediction.remainingHours <= 2
                ? 'bg-amber-400/30'
                : 'bg-white/10'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {mlPrediction.remainingHours <= 2 ? (
                    <AlertTriangle className="w-4 h-4 text-amber-200" />
                  ) : (
                    <TrendingUp className="w-4 h-4 text-white/80" />
                  )}
                  <span className="text-sm font-medium text-white">
                    {mlPrediction.remainingHours <= 2 ? '완료 임박' : 'ML 예측'}
                  </span>
                </div>
                <span className="text-xs text-white/70">
                  신뢰도 {Math.round(mlPrediction.confidence * 100)}%
                </span>
              </div>
              <p className="text-lg font-bold mt-1 text-white">
                {formatRemainingTime(mlPrediction.remainingHours)} 남음
              </p>
            </div>
          )}

          {/* 상태 정보 그리드 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-white/70" />
              <div>
                <p className="text-xs text-white/60">경과 시간</p>
                <p className="text-sm font-medium text-white">{getElapsedTime()}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-white/70" />
              <div>
                <p className="text-xs text-white/60">수온</p>
                <p className="text-sm font-medium text-white">
                  {batch.latest_measurement?.water_temp?.toFixed(1) || '-'}°C
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Droplets className="w-4 h-4 text-white/70" />
              <div>
                <p className="text-xs text-white/60">상단 염도</p>
                <p className="text-sm font-medium text-white">
                  {batch.latest_measurement?.top_salinity?.toFixed(1) || '-'}%
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Droplets className="w-4 h-4 text-white/70" />
              <div>
                <p className="text-xs text-white/60">하단 염도</p>
                <p className="text-sm font-medium text-white">
                  {batch.latest_measurement?.bottom_salinity?.toFixed(1) || '-'}%
                </p>
              </div>
            </div>
          </div>

          {/* 진행률 바 */}
          <div className="mt-4 pt-3 border-t border-white/20">
            <div className="flex justify-between text-xs text-white/70 mb-1">
              <span>진행률</span>
              <span className="font-medium text-white">
                {Math.round(mlPrediction?.progress || batch.progress || 0)}%
              </span>
            </div>
            <div className="w-full bg-white/20 rounded-full h-2.5">
              <div
                className="h-2.5 rounded-full transition-all duration-500 bg-white"
                style={{
                  width: `${Math.min(100, mlPrediction?.progress || batch.progress || 0)}%`,
                }}
              />
            </div>
            {(mlPrediction?.progress || batch.progress || 0) >= 90 && !hasAnomaly && (
              <p className="text-xs text-amber-200 mt-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                세척 준비를 시작하세요
              </p>
            )}
          </div>
        </>
      ) : (
        <div className="py-8 text-center">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 flex items-center justify-center">
            <Droplets className="w-6 h-6 text-gray-300" />
          </div>
          <p className="text-gray-400 text-sm">배치 대기 중</p>
          <p className="text-xs text-gray-300 mt-1">터치패널에서 새 배치를 시작하세요</p>
        </div>
      )}
    </div>
  );
}
