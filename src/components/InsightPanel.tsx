import { Lightbulb, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import type { InsightResponse } from '../types';

interface InsightPanelProps {
  insights: InsightResponse | null;
  isLoading?: boolean;
  onRefresh?: () => void;
}

export function InsightPanel({ insights, isLoading, onRefresh }: InsightPanelProps) {
  if (!insights && !isLoading) {
    return (
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb className="w-5 h-5 text-yellow-500" />
          <h3 className="text-lg font-semibold text-gray-900">AI 인사이트</h3>
        </div>
        <p className="text-gray-500 text-center py-8">
          진행 중인 배치가 있을 때 AI 인사이트가 표시됩니다.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 text-yellow-500" />
          <h3 className="text-lg font-semibold text-gray-900">AI 인사이트</h3>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="py-8 text-center">
          <RefreshCw className="w-8 h-8 text-green-500 animate-spin mx-auto mb-3" />
          <p className="text-gray-500">AI 분석 중...</p>
        </div>
      ) : insights ? (
        <>
          {/* 메인 인사이트 */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg p-4 mb-4">
            <p className="text-gray-700 whitespace-pre-line leading-relaxed">
              {insights.insight}
            </p>
          </div>

          {/* 권장사항 */}
          {insights.recommendations.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                권장사항
              </h4>
              <ul className="space-y-2">
                {insights.recommendations.map((rec, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 text-sm text-gray-600 bg-green-50 rounded-lg px-3 py-2"
                  >
                    <span className="text-green-500 mt-0.5">•</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 경고사항 */}
          {insights.warnings.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                주의사항
              </h4>
              <ul className="space-y-2">
                {insights.warnings.map((warning, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 text-sm text-gray-600 bg-amber-50 rounded-lg px-3 py-2"
                  >
                    <span className="text-amber-500 mt-0.5">!</span>
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 토큰 사용량 */}
          <div className="text-xs text-gray-400 text-right">
            토큰 사용량: {insights.tokens_used}
          </div>
        </>
      ) : null}
    </div>
  );
}
