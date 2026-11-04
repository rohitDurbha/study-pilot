'use client';

import { FileText, Sun, Moon, CheckCircle, Pencil, Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useEffect, useState } from 'react';
import SectionProgressList, { SectionInfo } from './section-progress';
import KnowledgeGraphMini from './knowledge-graph-mini';
import { BACKEND_API_URL } from '@/app/lib/constants';

export interface SavedSource {
  id: string;
  filename: string;
  isActive: boolean;
}

interface SidebarProps {
  onAddClick?: () => void;
  sources?: SavedSource[];
  onSourceClick?: (id: string) => void;
  onSourceRenamed?: (id: string, newName: string) => void;
  sections?: SectionInfo[];
  currentSectionId?: string | null;
  onSectionClick?: (sectionId: string) => void;
  knowledgeGraph?: any;
}

export default function Sidebar({
  onAddClick,
  sources = [],
  onSourceClick,
  onSourceRenamed,
  sections = [],
  currentSectionId,
  onSectionClick,
  knowledgeGraph,
}: SidebarProps) {
  const [isDark, setIsDark] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'));
  }, []);

  const toggleTheme = () => {
    const html = document.documentElement;
    if (html.classList.contains('dark')) {
      html.classList.remove('dark');
      setIsDark(false);
    } else {
      html.classList.add('dark');
      setIsDark(true);
    }
  };

  const startRename = (source: SavedSource) => {
    setEditingId(source.id);
    setEditName(source.filename.replace(/\.[^.]+$/, ''));
  };

  const confirmRename = async (id: string) => {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await fetch(`${BACKEND_API_URL}/api/documents/${id}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName.trim() }),
      });
      onSourceRenamed?.(id, editName.trim());
    } catch { /* ignore */ }
    setEditingId(null);
  };

  return (
    <div className="w-1/5 min-w-[220px] p-4 border-r bg-white dark:bg-gray-900 dark:border-gray-800 flex flex-col h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold dark:text-gray-100">StudyBuddy</h1>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={toggleTheme}>
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </Button>
      </div>

      <Button
        variant="outline"
        className="w-full mb-4 border-blue-500 bg-blue-100 dark:bg-blue-900/30 text-blue-500 hover:bg-blue-200 dark:hover:bg-blue-900/50"
        onClick={onAddClick}
      >
        + Add Source
      </Button>

      {/* Sources */}
      {sources.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Materials</h3>
          <div className="space-y-1">
            {sources.map((source) => (
              <div key={source.id} className="group">
                {editingId === source.id ? (
                  <div className="flex items-center gap-1 px-2 py-1">
                    <input
                      autoFocus
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') confirmRename(source.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      className="flex-1 text-xs px-1.5 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <button onClick={() => confirmRename(source.id)} className="p-0.5 text-green-500 hover:text-green-400">
                      <Check className="h-3 w-3" />
                    </button>
                    <button onClick={() => setEditingId(null)} className="p-0.5 text-gray-400 hover:text-gray-300">
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <div
                    onClick={() => onSourceClick?.(source.id)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition text-sm cursor-pointer ${
                      source.isActive
                        ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    <FileText className={`h-3.5 w-3.5 flex-shrink-0 ${source.isActive ? 'text-blue-500' : 'text-gray-400'}`} />
                    <span className="truncate text-xs flex-1">{source.filename.replace(/\.[^.]+$/, '')}</span>
                    {source.isActive && <CheckCircle className="h-3 w-3 text-blue-500 flex-shrink-0" />}
                    <span
                      onClick={(e) => { e.stopPropagation(); startRename(source); }}
                      className="hidden group-hover:inline-block p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex-shrink-0 cursor-pointer"
                    >
                      <Pencil className="h-3 w-3" />
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Section progress */}
      {sections.length > 0 && onSectionClick && (
        <SectionProgressList
          sections={sections}
          currentSectionId={currentSectionId}
          onSectionClick={onSectionClick}
        />
      )}

      {/* Knowledge graph */}
      {knowledgeGraph?.concepts && sections.length > 0 && (
        <KnowledgeGraphMini
          concepts={knowledgeGraph.concepts}
          sections={sections}
        />
      )}

      {sources.length === 0 && sections.length === 0 && (
        <div className="mt-6 text-center text-gray-400 dark:text-gray-500 text-sm flex-1">
          <p>No sources yet</p>
          <p className="mt-2 text-xs">Upload a PDF to get started</p>
        </div>
      )}
    </div>
  );
}
