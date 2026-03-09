import { useState } from 'react';
import { Server, Database, Bell, Save, RefreshCw, CheckCircle } from 'lucide-react';

export function Settings() {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30);
  const [notifications, setNotifications] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 800));
    setIsSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* API 설정 */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <Server className="w-4 h-4 text-slate-600" />
          </div>
          <h3 className="font-semibold text-slate-800">API 서버 설정</h3>
        </div>

        <div className="space-y-4">
          <div>
            <label className="label">API 서버 주소</label>
            <input
              type="url"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="input"
              placeholder="http://localhost:8000"
            />
            <p className="mt-1.5 text-xs text-slate-400">
              FastAPI 백엔드 서버의 주소를 입력하세요
            </p>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-3">
              <Database className="w-4 h-4 text-slate-400" />
              <div>
                <p className="text-sm font-medium text-slate-700">연결 상태</p>
                <p className="text-xs text-slate-400">{apiUrl}/api/v1</p>
              </div>
            </div>
            <span className="flex items-center gap-1.5 text-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="text-emerald-600 font-medium">연결됨</span>
            </span>
          </div>
        </div>
      </div>

      {/* 자동 새로고침 설정 */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <RefreshCw className="w-4 h-4 text-slate-600" />
          </div>
          <h3 className="font-semibold text-slate-800">자동 새로고침</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">자동 새로고침 활성화</p>
              <p className="text-xs text-slate-400">대시보드 데이터를 자동으로 업데이트합니다</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-emerald-500 peer-focus:ring-2 peer-focus:ring-emerald-200 after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-5 after:shadow-sm"></div>
            </label>
          </div>

          {autoRefresh && (
            <div>
              <label className="label">새로고침 간격</label>
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                className="select"
              >
                <option value={10}>10초</option>
                <option value={30}>30초</option>
                <option value={60}>1분</option>
                <option value={120}>2분</option>
                <option value={300}>5분</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {/* 알림 설정 */}
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <Bell className="w-4 h-4 text-slate-600" />
          </div>
          <h3 className="font-semibold text-slate-800">알림 설정</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">알림 활성화</p>
              <p className="text-xs text-slate-400">절임 완료 및 경고 알림을 받습니다</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={notifications}
                onChange={(e) => setNotifications(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-emerald-500 peer-focus:ring-2 peer-focus:ring-emerald-200 after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-5 after:shadow-sm"></div>
            </label>
          </div>

          {notifications && (
            <div className="space-y-2.5 pl-4 border-l-2 border-slate-100">
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-4 h-4 text-emerald-600 bg-white border-slate-300 rounded focus:ring-emerald-500 focus:ring-2"
                />
                <span className="text-sm text-slate-600 group-hover:text-slate-800">
                  절임 완료 알림
                </span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-4 h-4 text-emerald-600 bg-white border-slate-300 rounded focus:ring-emerald-500 focus:ring-2"
                />
                <span className="text-sm text-slate-600 group-hover:text-slate-800">
                  염도 이상 경고
                </span>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-4 h-4 text-emerald-600 bg-white border-slate-300 rounded focus:ring-emerald-500 focus:ring-2"
                />
                <span className="text-sm text-slate-600 group-hover:text-slate-800">
                  온도 이상 경고
                </span>
              </label>
            </div>
          )}
        </div>
      </div>

      {/* 저장 버튼 */}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className={`w-full py-2.5 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
          saved
            ? 'bg-emerald-500 text-white'
            : 'bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50'
        }`}
      >
        {isSaving ? (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            저장 중...
          </>
        ) : saved ? (
          <>
            <CheckCircle className="w-4 h-4" />
            저장 완료
          </>
        ) : (
          <>
            <Save className="w-4 h-4" />
            설정 저장
          </>
        )}
      </button>
    </div>
  );
}
