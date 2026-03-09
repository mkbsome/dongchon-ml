import { useState, useRef, useEffect } from 'react';
import { Send, X, MessageSquare, Loader2, Trash2 } from 'lucide-react';
import { useStore } from '../stores/useStore';
import { chatApi } from '../services/api';
import type { ChatMessage } from '../types';

export function ChatSidebar() {
  const {
    chatMessages,
    addChatMessage,
    chatContext,
    isChatOpen,
    setChatOpen,
    isChatLoading,
    setChatLoading,
    clearChat,
    currentPage,
    tanks,
  } = useStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 스크롤 맨 아래로
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // 메시지 전송
  const handleSend = async () => {
    if (!input.trim() || isChatLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    addChatMessage(userMessage);
    setInput('');
    setChatLoading(true);

    try {
      // 현재 페이지와 탱크 정보를 컨텍스트에 포함
      const activeTanks = tanks.filter((t) => t.current_batch);
      const contextData = {
        ...chatContext,
        current_page: currentPage,
        active_tanks: activeTanks.map((t) => ({
          name: t.name,
          cultivar: t.current_batch?.cultivar,
          progress: t.current_batch?.progress,
          salinity: t.current_batch?.latest_measurement?.salinity_avg,
        })),
      };

      const response = await chatApi.send({
        message: userMessage.content,
        context: contextData,
      });

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
      };

      addChatMessage(assistantMessage);
    } catch (error) {
      console.error('Chat error:', error);
      // 에러 시 목업 응답
      const mockResponse = getMockResponse(userMessage.content);
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: mockResponse,
        timestamp: new Date().toISOString(),
      };
      addChatMessage(assistantMessage);
    } finally {
      setChatLoading(false);
    }
  };

  // 목업 응답 (API 연결 전)
  const getMockResponse = (question: string): string => {
    const q = question.toLowerCase();
    if (q.includes('염도') && q.includes('높')) {
      return '염도가 높은 경우, 물을 추가하여 희석하거나 절임 시간을 단축하는 것을 권장합니다. 현재 목표 최종 염도는 1.5-2.5% 범위입니다.';
    }
    if (q.includes('시간') || q.includes('언제') || q.includes('완료')) {
      return '현재 진행 중인 배치의 예상 완료 시간은 대시보드에서 확인하실 수 있습니다. 일반적으로 겨울철 절임은 36-40시간, 기타 계절은 20-24시간이 소요됩니다.';
    }
    if (q.includes('품질') || q.includes('등급')) {
      return 'A등급 품질을 위해서는 최종 염도 1.5-2.0%, 굽힘 테스트 85점 이상이 필요합니다. 초기 염도와 절임 시간 관리가 핵심입니다.';
    }
    if (q.includes('온도')) {
      return '염수 온도는 10-15°C가 적정합니다. 온도가 너무 높으면 절임이 빨라지지만 품질이 떨어질 수 있고, 너무 낮으면 시간이 오래 걸립니다.';
    }
    return '죄송합니다. 현재 AI 서버에 연결되지 않아 상세한 답변을 드리기 어렵습니다. 백엔드 서버 연결 상태를 확인해주세요.';
  };

  // 빠른 질문
  const quickQuestions = [
    '현재 진행 상황은?',
    '완료 예상 시간은?',
    'A등급 조건은?',
  ];

  if (!isChatOpen) {
    return (
      <button
        onClick={() => setChatOpen(true)}
        className="fixed right-4 bottom-4 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-blue-700 transition-colors z-50"
      >
        <MessageSquare className="w-6 h-6" />
      </button>
    );
  }

  return (
    <aside className="w-96 bg-white border-l border-gray-200 flex flex-col fixed top-0 right-0 h-screen z-40 shadow-xl">
      {/* 헤더 */}
      <div className="h-16 px-5 flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse" />
          <span className="font-semibold text-gray-800 text-base">AI 어시스턴트</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearChat}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title="대화 초기화"
          >
            <Trash2 className="w-5 h-5" />
          </button>
          <button
            onClick={() => setChatOpen(false)}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500 text-base">안녕하세요. 절임 공정에 대해 궁금한 점을 물어보세요.</p>
          </div>
        )}

        {chatMessages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] px-4 py-3 rounded-2xl text-base ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}

        {isChatLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-3 rounded-2xl">
              <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 빠른 질문 */}
      {chatMessages.length <= 2 && (
        <div className="px-4 pb-3">
          <div className="flex flex-wrap gap-2">
            {quickQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => setInput(q)}
                className="text-sm px-3 py-1.5 bg-blue-50 hover:bg-blue-100 rounded-full text-blue-700 font-medium transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 입력 영역 */}
      <div className="p-4 border-t border-gray-100 bg-gray-50">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="질문을 입력하세요..."
            className="flex-1 px-4 py-3 text-base border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
            disabled={isChatLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isChatLoading}
            className="px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
