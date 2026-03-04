import { useState } from 'react';
import { Server, Database, Bell, Save, RefreshCw } from 'lucide-react';

export function Settings() {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30);
  const [notifications, setNotifications] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    alert('설정이 저장되었습니다.');
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* API 설정 */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <Server className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">API 서버 설정</h3>
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
            <p className="mt-1 text-xs text-gray-500">
              FastAPI 백엔드 서버의 주소를 입력하세요
            </p>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <Database className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900">연결 상태</p>
                <p className="text-xs text-gray-500">{apiUrl}/api/v1</p>
              </div>
            </div>
            <span className="flex items-center gap-2 text-sm">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              <span className="text-green-600">연결됨</span>
            </span>
          </div>
        </div>
      </div>

      {/* 자동 새로고침 설정 */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <RefreshCw className="w-5 h-5 text-green-600" />
          <h3 className="text-lg font-semibold text-gray-900">자동 새로고침</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">자동 새로고침 활성화</p>
              <p className="text-xs text-gray-500">
                대시보드 데이터를 자동으로 업데이트합니다
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-100 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
            </label>
          </div>

          {autoRefresh && (
            <div>
              <label className="label">새로고침 간격 (초)</label>
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                className="input"
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
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <Bell className="w-5 h-5 text-amber-500" />
          <h3 className="text-lg font-semibold text-gray-900">알림 설정</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">알림 활성화</p>
              <p className="text-xs text-gray-500">
                절임 완료 및 경고 알림을 받습니다
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={notifications}
                onChange={(e) => setNotifications(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-100 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
            </label>
          </div>

          {notifications && (
            <div className="space-y-3 pl-4 border-l-2 border-gray-200">
              <label className="flex items-center gap-3">
                <input type="checkbox" defaultChecked className="w-4 h-4 text-green-600 rounded" />
                <span className="text-sm text-gray-700">절임 완료 알림</span>
              </label>
              <label className="flex items-center gap-3">
                <input type="checkbox" defaultChecked className="w-4 h-4 text-green-600 rounded" />
                <span className="text-sm text-gray-700">염도 이상 경고</span>
              </label>
              <label className="flex items-center gap-3">
                <input type="checkbox" defaultChecked className="w-4 h-4 text-green-600 rounded" />
                <span className="text-sm text-gray-700">온도 이상 경고</span>
              </label>
            </div>
          )}
        </div>
      </div>

      {/* 저장 버튼 */}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="btn-primary w-full flex items-center justify-center gap-2 py-3"
      >
        {isSaving ? (
          <>
            <RefreshCw className="w-5 h-5 animate-spin" />
            저장 중...
          </>
        ) : (
          <>
            <Save className="w-5 h-5" />
            설정 저장
          </>
        )}
      </button>
    </div>
  );
}
