import type { ReactNode } from 'react';
import { LayoutDashboard, FlaskConical, History, Settings, Leaf } from 'lucide-react';
import { useStore } from '../stores/useStore';

interface LayoutProps {
  children: ReactNode;
}

type PageType = 'dashboard' | 'optimize' | 'history' | 'settings';

const navItems: { id: PageType; label: string; icon: ReactNode }[] = [
  { id: 'dashboard', label: '대시보드', icon: <LayoutDashboard size={20} /> },
  { id: 'optimize', label: '최적화', icon: <FlaskConical size={20} /> },
  { id: 'history', label: '이력조회', icon: <History size={20} /> },
  { id: 'settings', label: '설정', icon: <Settings size={20} /> },
];

export function Layout({ children }: LayoutProps) {
  const { currentPage, setCurrentPage } = useStore();

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* 사이드바 */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* 로고 */}
        <div className="h-16 flex items-center px-6 border-b border-gray-100">
          <Leaf className="w-8 h-8 text-green-600" />
          <div className="ml-3">
            <h1 className="text-lg font-bold text-gray-900">동촌에프에스</h1>
            <p className="text-xs text-gray-500">AI 절임 최적화</p>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 py-4">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentPage(item.id)}
              className={`w-full flex items-center px-6 py-3 text-sm font-medium transition-colors ${
                currentPage === item.id
                  ? 'text-green-700 bg-green-50 border-r-2 border-green-600'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <span className={currentPage === item.id ? 'text-green-600' : 'text-gray-400'}>
                {item.icon}
              </span>
              <span className="ml-3">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* 하단 정보 */}
        <div className="p-4 border-t border-gray-100">
          <div className="text-xs text-gray-400">
            <p>버전 1.0.0</p>
            <p className="mt-1">API: localhost:8000</p>
          </div>
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 flex flex-col">
        {/* 헤더 */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h2 className="text-xl font-semibold text-gray-900">
            {navItems.find((item) => item.id === currentPage)?.label}
          </h2>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {new Date().toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                weekday: 'short',
              })}
            </span>
          </div>
        </header>

        {/* 페이지 콘텐츠 */}
        <div className="flex-1 p-6 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
