'use client';

import React from 'react';
import { Bot, X } from 'lucide-react';

interface AgentButton {
  label: string;
  action: string;
  section_id?: string;
  content_type?: string;
}

interface AgentCardProps {
  message: string;
  buttons: AgentButton[];
  onAction: (action: string, data?: Record<string, string>) => void;
  onDismiss: () => void;
}

export default function AgentCard({ message, buttons, onAction, onDismiss }: AgentCardProps) {
  return (
    <div className="mx-6 mt-4 mb-2 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg p-4 flex gap-3 animate-in slide-in-from-top duration-300">
      <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Bot className="h-4 w-4 text-blue-600 dark:text-blue-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">{message}</p>
        {buttons.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {buttons.map((btn, i) => (
              <button
                key={i}
                onClick={() => onAction(btn.action, {
                  section_id: btn.section_id || '',
                  content_type: btn.content_type || '',
                })}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                  i === 0
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <button onClick={onDismiss} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex-shrink-0">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
