'use client';

import { CheckCircle, Circle, BookOpen, HelpCircle, Loader2 } from 'lucide-react';

export interface SectionInfo {
  id: string;
  title: string;
  order: number;
  status: string; // not_started, in_progress, read, tested, mastered
  quiz_score?: number | null;
  concepts?: string[];
}

interface SectionProgressProps {
  sections: SectionInfo[];
  currentSectionId?: string | null;
  onSectionClick: (sectionId: string) => void;
}

function getStatusIcon(status: string, isCurrent: boolean) {
  if (isCurrent) return <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />;
  switch (status) {
    case 'mastered':
      return <CheckCircle className="h-3.5 w-3.5 text-green-500" />;
    case 'tested':
      return <CheckCircle className="h-3.5 w-3.5 text-blue-500" />;
    case 'read':
      return <BookOpen className="h-3.5 w-3.5 text-amber-500" />;
    case 'in_progress':
      return <Loader2 className="h-3.5 w-3.5 text-blue-400" />;
    default:
      return <Circle className="h-3.5 w-3.5 text-gray-300 dark:text-gray-600" />;
  }
}

function getStatusLabel(status: string, quizScore?: number | null) {
  switch (status) {
    case 'mastered': return 'Mastered';
    case 'tested': return quizScore ? `${Math.round(quizScore * 100)}%` : 'Tested';
    case 'read': return 'Read';
    case 'in_progress': return 'Reading...';
    default: return '';
  }
}

export default function SectionProgressList({ sections, currentSectionId, onSectionClick }: SectionProgressProps) {
  const mastered = sections.filter(s => s.status === 'mastered' || s.status === 'tested').length;

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Sections</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500">{mastered}/{sections.length}</span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-3">
        <div
          className="h-full rounded-full bg-green-500 transition-all duration-500"
          style={{ width: `${sections.length > 0 ? (mastered / sections.length) * 100 : 0}%` }}
        />
      </div>

      {/* Section list */}
      <div className="space-y-1">
        {sections.map((section) => {
          const isCurrent = section.id === currentSectionId;
          return (
            <button
              key={section.id}
              onClick={() => onSectionClick(section.id)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition text-sm ${
                isCurrent
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                  : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
              }`}
            >
              {getStatusIcon(section.status, isCurrent)}
              <span className="flex-1 truncate text-xs">{section.title}</span>
              <span className="text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">
                {getStatusLabel(section.status, section.quiz_score)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
