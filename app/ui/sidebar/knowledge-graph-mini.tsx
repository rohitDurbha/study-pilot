'use client';

import React from 'react';
import { SectionInfo } from './section-progress';

interface Concept {
  id: string;
  name: string;
  description: string;
  importance: number;
  prerequisites: string[];
}

interface KnowledgeGraphMiniProps {
  concepts: Concept[];
  sections: SectionInfo[];
}

function getConceptMastery(conceptId: string, sections: SectionInfo[]): string {
  // Find sections that cover this concept
  const coveringSections = sections.filter(s =>
    s.concepts && s.concepts.some(c =>
      c === conceptId || c.toLowerCase() === conceptId.toLowerCase()
    )
  );

  if (coveringSections.length === 0) {
    // Concept not linked to any section — check by name similarity
    return 'not_started';
  }

  // If any covering section is mastered/tested, concept is mastered
  if (coveringSections.some(s => s.status === 'mastered' || s.status === 'tested')) {
    return 'mastered';
  }
  // If any is read or in progress
  if (coveringSections.some(s => s.status === 'read' || s.status === 'in_progress')) {
    return 'in_progress';
  }
  return 'not_started';
}

function getMasteryColor(mastery: string): string {
  switch (mastery) {
    case 'mastered': return 'bg-green-500';
    case 'in_progress': return 'bg-amber-500';
    default: return 'bg-gray-400 dark:bg-gray-600';
  }
}

function getMasteryRing(mastery: string): string {
  switch (mastery) {
    case 'mastered': return 'ring-green-300 dark:ring-green-700';
    case 'in_progress': return 'ring-amber-300 dark:ring-amber-700';
    default: return 'ring-gray-200 dark:ring-gray-700';
  }
}

export default function KnowledgeGraphMini({ concepts, sections }: KnowledgeGraphMiniProps) {
  if (!concepts || concepts.length === 0) return null;

  const masteryMap = concepts.map(c => ({
    ...c,
    mastery: getConceptMastery(c.id, sections),
  }));

  const mastered = masteryMap.filter(c => c.mastery === 'mastered').length;

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Concepts</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500">{mastered}/{concepts.length}</span>
      </div>

      {/* Concept grid */}
      <div className="flex flex-wrap gap-1.5">
        {masteryMap
          .sort((a, b) => b.importance - a.importance)
          .map((concept) => (
            <div key={concept.id} className="group relative">
              <div
                className={`w-3 h-3 rounded-full ${getMasteryColor(concept.mastery)} ring-1 ${getMasteryRing(concept.mastery)} cursor-default transition-transform hover:scale-150`}
              />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 pointer-events-none">
                <div className="bg-gray-900 text-white text-xs rounded-md px-2 py-1 whitespace-nowrap shadow-lg">
                  {concept.name}
                  {concept.mastery === 'mastered' && ' ✓'}
                </div>
              </div>
            </div>
          ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-gray-500">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span>Done</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-amber-500" />
          <span>Learning</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-600" />
          <span>New</span>
        </div>
      </div>
    </div>
  );
}
