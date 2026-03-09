import type { ReactNode } from 'react';
import { LayoutDashboard, FlaskConical, History, Settings } from 'lucide-react';
import { useStore } from '../stores/useStore';
import { ChatSidebar } from './ChatSidebar';

interface LayoutProps {
  children: ReactNode;
}

type PageType = 'dashboard' | 'optimize' | 'history' | 'settings';

const navItems: { id: PageType; label: string; icon: ReactNode }[] = [
  { id: 'dashboard', label: '대시보드', icon: <LayoutDashboard size={18} /> },
  { id: 'optimize', label: '최적화', icon: <FlaskConical size={18} /> },
  { id: 'history', label: '이력조회', icon: <History size={18} /> },
  { id: 'settings', label: '설정', icon: <Settings size={18} /> },
];

export function Layout({ children }: LayoutProps) {
  const { currentPage, setCurrentPage, isChatOpen } = useStore();

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* 좌측 네비게이션 사이드바 */}
      <aside className="w-56 bg-slate-800 flex flex-col fixed top-0 left-0 h-screen z-30">
        {/* 로고 */}
        <div className="h-14 flex items-center px-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-emerald-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">DC</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white">동촌F&S</h1>
              <p className="text-xs text-slate-400">절임 관리 시스템</p>
            </div>
          </div>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 py-4 px-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentPage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-1 ${
                currentPage === item.id
                  ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-md'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <span className={currentPage === item.id ? 'text-white' : ''}>
                {item.icon}
              </span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* 하단 정보 */}
        <div className="p-4 border-t border-slate-700">
          <div className="text-xs text-slate-500">
            <p>v1.0.0</p>
            <p className="mt-0.5 text-slate-600">localhost:8000</p>
          </div>
        </div>
      </aside>

      {/* 메인 영역 - 좌측 사이드바 만큼 마진, 우측 채팅 열려있으면 마진 추가 */}
      <div className={`flex-1 flex flex-col min-w-0 ml-56 ${isChatOpen ? 'mr-96' : ''} transition-all duration-300`}>
        {/* 헤더 */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-20">
          <h2 className="text-lg font-semibold text-gray-800">
            {navItems.find((item) => item.id === currentPage)?.label}
          </h2>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>
              {new Date().toLocaleDateString('ko-KR', {
                month: 'long',
                day: 'numeric',
                weekday: 'short',
              })}
            </span>
          </div>
        </header>

        {/* 페이지 콘텐츠 */}
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>

      {/* 우측 AI 채팅 사이드바 - 항상 렌더링 (내부에서 닫힘 버튼 처리) */}
      <ChatSidebar />
    </div>
  );
}
