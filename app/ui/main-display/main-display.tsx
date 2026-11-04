'use client';

import React, { useState, useEffect } from 'react';
import TextContent from './content/text-content';
import DefaultDisplay from './default-display';
import FlipCardContent from './content/flip-card-content';
import QuizContent from './content/quiz-content';
import MiniGameContent from './content/mini-game-content';
import MindmapContent from './content/mindmap-content';
import { Spinner } from '../dashboard/redirect';
import { BookOpen, Brain, CreditCard, HelpCircle, Gamepad2 } from 'lucide-react';

interface MainDisplayProps {
  isLoading?: boolean;
  contentData?: {
    type: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data: any;
  } | null;
  onUpload?: () => void;
  onContentTypeRequest?: (type: string) => void;
  onQuizComplete?: (score: number, total: number) => void;
  onSectionDone?: () => void;
}

const CONTENT_TABS = [
  { type: 'text', label: 'Reading', icon: BookOpen },
  { type: 'flipcard', label: 'Flashcards', icon: CreditCard },
  { type: 'quiz', label: 'Quiz', icon: HelpCircle },
  { type: 'mindmap', label: 'Mind Map', icon: Brain },
  { type: 'mini-game', label: 'Game', icon: Gamepad2 },
];

export default function MainDisplay({
  isLoading = false,
  contentData = null,
  onUpload,
  onContentTypeRequest,
  onQuizComplete,
  onSectionDone,
}: MainDisplayProps) {
  const [activeTab, setActiveTab] = useState<string>('text');

  useEffect(() => {
    if (contentData?.type) {
      setActiveTab(contentData.type === 'react' ? 'mini-game' : contentData.type);
    }
  }, [contentData]);

  const handleTabClick = (type: string) => {
    setActiveTab(type);
    onContentTypeRequest?.(type);
  };

  const renderContent = () => {
    if (!contentData) {
      return <DefaultDisplay onUpload={onUpload} />;
    }

    switch (contentData.type) {
      case 'text':
        return <TextContent data={contentData.data} onSectionDone={onSectionDone} />;
      case 'flipcard':
        return <FlipCardContent data={contentData.data} />;
      case 'mindmap':
        return <MindmapContent data={contentData.data} />;
      case 'quiz':
        return <QuizContent data={contentData.data} onQuizComplete={onQuizComplete} />;
      case 'react':
      case 'mini-game':
        return <MiniGameContent data={contentData.data} />;
      default:
        return <TextContent data={contentData.data} />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 p-6 overflow-hidden">
        <div className="flex-1 overflow-y-auto rounded-lg p-8 bg-gray-50 dark:bg-gray-800 flex flex-col items-center justify-center">
          <Spinner />
          <p className="text-gray-500 dark:text-gray-400 mt-4 text-sm">
            Generating content...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden">
      {/* Content type tabs — only show when content is loaded */}
      {contentData && (
        <div className="px-6 pt-4 pb-0">
          <div className="flex items-center gap-1 border-b dark:border-gray-700">
            {CONTENT_TABS.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.type;
              return (
                <button
                  key={tab.type}
                  onClick={() => handleTabClick(tab.type)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                      : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="h-full rounded-lg bg-white dark:bg-gray-900 flex items-center justify-center">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
