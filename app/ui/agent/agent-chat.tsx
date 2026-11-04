'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, BookOpen, Zap, FileText, GripVertical } from 'lucide-react';
import { chatWithAgent, getChatHistory, AgentContext, ChatSource } from '@/app/services/agentService';
import ReactMarkdown from 'react-markdown';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  pipeline?: 'rag' | 'full_context';
}

interface AgentChatProps {
  context: AgentContext;
  sessionId: string | null;
  isVisible: boolean;
  onCommand?: (command: string) => void;
  onScrollToSection?: (sectionId: string) => void;
}

/** Renders response text with interactive [1], [2] citation badges that show tooltips on hover */
function CitationText({
  content,
  sources,
  msgIdx,
  onHover,
  onNavigate,
}: {
  content: string;
  sources: ChatSource[];
  msgIdx: number;
  onHover: (info: { msgIdx: number; srcIdx: number; rect: DOMRect } | null) => void;
  onNavigate?: (sectionId: string) => void;
}) {
  // Split content around [1], [2], etc. patterns
  const parts = content.split(/(\[\d+\])/g);
  const [tooltip, setTooltip] = useState<{ idx: number; x: number; y: number } | null>(null);

  return (
    <div className="relative">
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown
          components={{
            p: ({ children }) => {
              // Process children to find citation patterns
              const processNode = (node: React.ReactNode): React.ReactNode => {
                if (typeof node !== 'string') return node;
                const nodeParts = node.split(/(\[\d+\])/g);
                if (nodeParts.length === 1) return node;
                return nodeParts.map((part, pi) => {
                  const match = part.match(/^\[(\d+)\]$/);
                  if (match) {
                    const srcIdx = parseInt(match[1]) - 1;
                    const source = sources[srcIdx];
                    if (!source) return part;
                    return (
                      <span
                        key={pi}
                        className="relative inline-flex"
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setTooltip({ idx: srcIdx, x: rect.left, y: rect.top });
                        }}
                        onMouseLeave={() => setTooltip(null)}
                        onClick={(e) => { e.stopPropagation(); onNavigate?.(source.section_id); }}
                      >
                        <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 mx-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-[10px] font-bold text-emerald-700 dark:text-emerald-300 cursor-pointer hover:bg-emerald-200 dark:hover:bg-emerald-800 hover:scale-110 transition-all align-middle">
                          {match[1]}
                        </span>
                      </span>
                    );
                  }
                  return part;
                });
              };
              const processed = Array.isArray(children)
                ? children.map(processNode)
                : processNode(children);
              return <p>{processed}</p>;
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>

      {/* Hover tooltip */}
      {tooltip && sources[tooltip.idx] && (
        <div
          className="fixed z-[100] w-72 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-xl p-3 pointer-events-none animate-in fade-in duration-150"
          style={{
            left: Math.min(tooltip.x, window.innerWidth - 300),
            top: tooltip.y - 8,
            transform: 'translateY(-100%)',
          }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
              {tooltip.idx + 1}
            </span>
            <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate">
              {sources[tooltip.idx].section_title}
            </span>
          </div>
          <p className="text-[11px] text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-4">
            {sources[tooltip.idx].text}
          </p>
          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-1">
              <div className="w-10 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${Math.round(sources[tooltip.idx].score * 100)}%` }} />
              </div>
              <span className="text-[9px] text-gray-400">{Math.round(sources[tooltip.idx].score * 100)}% match</span>
            </div>
            <span className="text-[9px] text-emerald-500">Click to view →</span>
          </div>
          {/* Tooltip arrow */}
          <div className="absolute bottom-0 left-6 translate-y-full">
            <div className="w-2 h-2 bg-white dark:bg-gray-800 border-r border-b border-gray-200 dark:border-gray-600 rotate-45 -translate-y-1" />
          </div>
        </div>
      )}
    </div>
  );
}

export default function AgentChat({ context, sessionId, isVisible, onCommand, onScrollToSection }: AgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(true);
  const [pipeline, setPipeline] = useState<'rag' | 'full_context'>('rag');
  const [expandedSources, setExpandedSources] = useState<number | null>(null);
  const [hoveredCitation, setHoveredCitation] = useState<{ msgIdx: number; srcIdx: number; rect: DOMRect } | null>(null);
  const [size, setSize] = useState({ w: 540, h: 680 });
  const [isExpanded, setIsExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasLoadedHistory = useRef(false);
  const isResizing = useRef(false);
  const startPos = useRef({ x: 0, y: 0, w: 0, h: 0 });

  // Drag-to-resize from top-left corner
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    startPos.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h };

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const dw = startPos.current.x - ev.clientX;
      const dh = startPos.current.y - ev.clientY;
      setSize({
        w: Math.max(400, Math.min(800, startPos.current.w + dw)),
        h: Math.max(400, Math.min(900, startPos.current.h + dh)),
      });
    };

    const onMouseUp = () => {
      isResizing.current = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [size]);

  const toggleExpand = () => {
    if (isExpanded) {
      setSize({ w: 540, h: 680 });
    } else {
      setSize({ w: 700, h: 850 });
    }
    setIsExpanded(!isExpanded);
  };

  // Load chat history from DB when session starts
  useEffect(() => {
    if (!sessionId || hasLoadedHistory.current) return;
    hasLoadedHistory.current = true;

    getChatHistory(sessionId).then(res => {
      if (res.messages && res.messages.length > 0) {
        setMessages(res.messages);
      }
    }).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!isVisible) return null;

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Check for quick commands
    const lower = userMessage.toLowerCase();
    if (lower.match(/^(quiz|test)\s*me/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Generating a quiz for you...' }]);
      onCommand?.('quiz');
      return;
    }
    if (lower.match(/^(flash\s*cards?|show\s*cards)/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Generating flashcards...' }]);
      onCommand?.('flipcard');
      return;
    }
    if (lower.match(/^(next\s*section|move\s*on|continue)/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Moving to the next section.' }]);
      onCommand?.('next_section');
      return;
    }
    if (lower.match(/^(mind\s*map|visual)/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Generating a mind map...' }]);
      onCommand?.('mindmap');
      return;
    }
    if (lower.match(/^(game|play)/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Starting a matching game...' }]);
      onCommand?.('mini-game');
      return;
    }
    if (lower.match(/^(read\s*aloud|speak|audio)/i)) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Starting read aloud. Check the reading view.' }]);
      onCommand?.('read_aloud');
      return;
    }

    // Regular chat — send to LLM
    setIsLoading(true);
    try {
      const result = await chatWithAgent(userMessage, sessionId, context, pipeline);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.response,
        sources: result.sources,
        pipeline: pipeline,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I had trouble responding. Try again.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-[240px] z-40">
        <button
          onClick={() => setIsMinimized(false)}
          className="flex items-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg transition"
        >
          <Bot className="h-5 w-5" />
          <span className="text-sm font-medium">Study Assistant</span>
          {messages.length > 0 && (
            <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">
              {messages.length}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div
      className="fixed bottom-4 right-[240px] bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-xl shadow-2xl flex flex-col z-[60]"
      style={{ width: size.w, height: size.h }}
    >
      {/* Resize handle — top-left corner */}
      <div
        onMouseDown={onResizeStart}
        className="absolute -top-1 -left-1 w-5 h-5 cursor-nw-resize flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity z-10"
        title="Drag to resize"
      >
        <GripVertical className="h-3 w-3 text-gray-400 -rotate-45" />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-blue-600" />
          <span className="font-medium text-sm dark:text-gray-100">Study Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          {/* Pipeline toggle */}
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
            <button
              onClick={() => setPipeline('full_context')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition ${
                pipeline === 'full_context'
                  ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
              title="Quick Search — sends question directly to Claude for a general-purpose answer"
            >
              <Zap className="h-3 w-3" />
              <span>Quick Search</span>
            </button>
            <button
              onClick={() => setPipeline('rag')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition ${
                pipeline === 'rag'
                  ? 'bg-white dark:bg-gray-700 text-emerald-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
              title="Deep Search — uses RAG pipeline to find exact passages from your document and cite sources"
            >
              <BookOpen className="h-3 w-3" />
              <span>Deep Search</span>
            </button>
          </div>
          {/* Window controls — macOS style */}
          <div className="flex items-center gap-1.5 ml-2">
            <button
              onClick={() => setIsMinimized(true)}
              className="w-3 h-3 rounded-full bg-yellow-400 hover:bg-yellow-500 transition border border-yellow-500/30"
              title="Minimize"
            />
            <button
              onClick={toggleExpand}
              className="w-3 h-3 rounded-full bg-green-400 hover:bg-green-500 transition border border-green-500/30"
              title={isExpanded ? 'Restore' : 'Expand'}
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 dark:text-gray-500 text-sm mt-8">
            <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>Ask me anything about your study material</p>
            <p className="text-xs mt-1">I can explain concepts, quiz you, or help you focus</p>
            <div className="mt-3 flex items-center justify-center gap-1 text-xs">
              <span className={pipeline === 'rag' ? 'text-emerald-500' : 'text-blue-500'}>
                {pipeline === 'rag' ? 'Deep Search — RAG retrieves exact passages & cites sources' : 'Quick Search — general-purpose answer from Claude'}
              </span>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0 mt-1">
                  <Bot className="h-3.5 w-3.5 text-blue-600" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 dark:text-gray-100'
                }`}
              >
                {msg.role === 'assistant' ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    {msg.sources && msg.sources.length > 0 ? (
                      <CitationText content={msg.content} sources={msg.sources} msgIdx={i} onHover={setHoveredCitation} onNavigate={onScrollToSection} />
                    ) : (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    )}
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>

            {/* Source references for RAG responses */}
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
              <div className="ml-8 mt-2">
                <button
                  onClick={() => setExpandedSources(expandedSources === i ? null : i)}
                  className="group flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 transition"
                >
                  <div className="flex -space-x-1">
                    {msg.sources.slice(0, 3).map((_, si) => (
                      <div key={si} className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-900/40 border-2 border-white dark:border-gray-900 flex items-center justify-center">
                        <span className="text-[8px] font-bold text-emerald-600 dark:text-emerald-400">{si + 1}</span>
                      </div>
                    ))}
                  </div>
                  <span className="group-hover:underline">
                    {msg.sources.length} source{msg.sources.length > 1 ? 's' : ''} from your document
                  </span>
                  <span className="text-[10px] transition-transform" style={{ transform: expandedSources === i ? 'rotate(180deg)' : 'rotate(0)' }}>▼</span>
                </button>

                {expandedSources === i && (
                  <div className="mt-2 space-y-2">
                    {msg.sources.map((source, si) => (
                      <div
                        key={si}
                        className="group/card relative bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden cursor-pointer hover:border-emerald-400 dark:hover:border-emerald-500 hover:shadow-md transition-all"
                        onClick={() => onScrollToSection?.(source.section_id)}
                      >
                        {/* Left accent bar */}
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-400 dark:bg-emerald-500 rounded-l-lg" />

                        <div className="pl-3.5 pr-3 py-2.5">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                              {si + 1}
                            </span>
                            <span className="text-xs font-medium text-gray-800 dark:text-gray-200 flex-1 truncate">
                              {source.section_title}
                            </span>
                            {/* Match confidence bar */}
                            <div className="flex items-center gap-1">
                              <div className="w-12 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-emerald-400 dark:bg-emerald-500 rounded-full"
                                  style={{ width: `${Math.round(source.score * 100)}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-gray-400 dark:text-gray-500 w-7 text-right">
                                {Math.round(source.score * 100)}%
                              </span>
                            </div>
                          </div>
                          <p className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed pl-7">
                            {source.text}
                          </p>
                          <div className="flex items-center gap-1 mt-1 pl-7 opacity-0 group-hover/card:opacity-100 transition-opacity">
                            <span className="text-[10px] text-emerald-500 dark:text-emerald-400">Click to view in document →</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2">
            <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
              <Bot className="h-3.5 w-3.5 text-blue-600" />
            </div>
            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions + Input */}
      <div className="p-3 border-t dark:border-gray-700">
        {/* Quick action chips */}
        <div className="flex flex-wrap gap-1.5 mb-2">
          {[
            { label: 'Quiz me', cmd: 'quiz' },
            { label: 'Flashcards', cmd: 'flipcard' },
            { label: 'Mind map', cmd: 'mindmap' },
            { label: 'Next section', cmd: 'next_section' },
          ].map(chip => (
            <button
              key={chip.cmd}
              onClick={() => { onCommand?.(chip.cmd); setMessages(prev => [...prev, { role: 'user', content: chip.label }, { role: 'assistant', content: `Loading ${chip.label.toLowerCase()}...` }]); }}
              className="px-2.5 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:text-blue-600 transition"
            >
              {chip.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={pipeline === 'rag' ? 'Deep Search — find exact passages in your document...' : 'Quick Search — ask Claude anything...'}
            className="flex-1 px-3 py-2 text-sm border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
