'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Clock, Brain, AlertTriangle, ArrowRightLeft, X } from 'lucide-react';

interface SessionReportProps {
  report: {
    total_duration_min: number;
    focused_time_min: number;
    focus_percentage: number;
    avg_focus_score: number;
    distraction_count: number;
    avg_distraction_sec: number;
    content_switches: number;
    content_effectiveness: Record<string, { avg_focus: number; time_pct: number }>;
  };
  onClose: () => void;
}

export default function SessionReport({ report, onClose }: SessionReportProps) {
  const contentTypeLabels: Record<string, string> = {
    text: 'Reading',
    mindmap: 'Mind Map',
    flipcard: 'Flashcards',
    quiz: 'Quiz',
    'mini-game': 'Mini Game',
  };

  // Find best content type
  const bestType = Object.entries(report.content_effectiveness)
    .sort(([, a], [, b]) => b.avg_focus - a.avg_focus)[0];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-900 rounded-xl w-full max-w-lg max-h-[85vh] overflow-y-auto shadow-2xl">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold dark:text-gray-100">Session Report</h2>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
              <X className="h-5 w-5 text-gray-500" />
            </button>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <Card className="dark:bg-gray-800 dark:border-gray-700">
              <CardContent className="p-4 flex items-center gap-3">
                <Clock className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-2xl font-bold dark:text-gray-100">{report.total_duration_min}m</p>
                  <p className="text-xs text-gray-500">Total time</p>
                </div>
              </CardContent>
            </Card>

            <Card className="dark:bg-gray-800 dark:border-gray-700">
              <CardContent className="p-4 flex items-center gap-3">
                <Brain className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-2xl font-bold dark:text-gray-100">{report.focus_percentage}%</p>
                  <p className="text-xs text-gray-500">Focused</p>
                </div>
              </CardContent>
            </Card>

            <Card className="dark:bg-gray-800 dark:border-gray-700">
              <CardContent className="p-4 flex items-center gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                <div>
                  <p className="text-2xl font-bold dark:text-gray-100">{report.distraction_count}</p>
                  <p className="text-xs text-gray-500">Distractions</p>
                </div>
              </CardContent>
            </Card>

            <Card className="dark:bg-gray-800 dark:border-gray-700">
              <CardContent className="p-4 flex items-center gap-3">
                <ArrowRightLeft className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-2xl font-bold dark:text-gray-100">{report.content_switches}</p>
                  <p className="text-xs text-gray-500">Mode switches</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Content effectiveness */}
          {Object.keys(report.content_effectiveness).length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Focus by content type</h3>
              <div className="space-y-2">
                {Object.entries(report.content_effectiveness)
                  .sort(([, a], [, b]) => b.avg_focus - a.avg_focus)
                  .map(([type, data]) => (
                    <div key={type} className="flex items-center gap-3">
                      <span className="text-sm w-24 text-gray-600 dark:text-gray-300">
                        {contentTypeLabels[type] || type}
                      </span>
                      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${data.avg_focus}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right dark:text-gray-100">
                        {data.avg_focus}%
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Insight */}
          {bestType && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-800 dark:text-blue-300">
                <span className="font-medium">Insight:</span> Your focus was highest during{' '}
                <span className="font-medium">{contentTypeLabels[bestType[0]] || bestType[0]}</span>{' '}
                ({bestType[1].avg_focus}% avg focus). Consider starting with this format next time.
              </p>
            </div>
          )}

          <Button
            onClick={onClose}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          >
            Done
          </Button>
        </div>
      </div>
    </div>
  );
}
