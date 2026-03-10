import type { ReactNode } from 'react';
import { LayoutDashboard, FlaskConical, History } from 'lucide-react';
import { useStore } from '../stores/useStore';
import { ChatSidebar } from './ChatSidebar';

interface LayoutProps {
  children: ReactNode;
}

type PageType = 'dashboard' | 'optimize' | 'history';

const navItems: { id: PageType; label: string; icon: ReactNode }[] = [
  { id: 'dashboard', label: '대시보드', icon: <LayoutDashboard size={18} /> },
  { id: 'optimize', label: '최적화', icon: <FlaskConical size={18} /> },
  { id: 'history', label: '이력조회', icon: <History size={18} /> },
];

export function Layout({ children }: LayoutProps) {
  const { currentPage, setCurrentPage, isChatOpen } = useStore();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 상단 헤더 + 네비게이션 */}
      <header className="h-12 bg-slate-800 flex items-center justify-between px-6 sticky top-0 z-30">
        {/* 네비게이션 탭 */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentPage(item.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                currentPage === item.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* 우측: 날짜 */}
        <span className="text-slate-400 text-sm">
          {new Date().toLocaleDateString('ko-KR', {
            month: 'long',
            day: 'numeric',
            weekday: 'short',
          })}
        </span>
      </header>

      {/* 메인 영역 */}
      <div className={`flex-1 flex flex-col min-w-0 ${isChatOpen ? 'mr-96' : ''} transition-all duration-300`}>
        {/* 페이지 콘텐츠 */}
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>

      {/* 우측 AI 채팅 사이드바 */}
      <ChatSidebar />
    </div>
  );
}
