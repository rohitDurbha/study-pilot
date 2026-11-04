'use client';

import { BACKEND_API_URL } from '@/app/lib/constants';

export async function generateFlashcards(text: string, documentId?: string | null, sectionId?: string | null) {
  const res = await fetch(`${BACKEND_API_URL}/generate-flashcards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, document_id: documentId, section_id: sectionId }),
  });
  if (!res.ok) throw new Error('Failed to generate flashcards');
  return res.json();
}

export async function generateQuiz(text: string, documentId?: string | null, sectionId?: string | null) {
  const res = await fetch(`${BACKEND_API_URL}/generate-quiz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, document_id: documentId, section_id: sectionId }),
  });
  if (!res.ok) throw new Error('Failed to generate quiz');
  return res.json();
}

export async function generateMindmap(text: string, documentId?: string | null, sectionId?: string | null) {
  const res = await fetch(`${BACKEND_API_URL}/generate-mindmap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, document_id: documentId, section_id: sectionId }),
  });
  if (!res.ok) throw new Error('Failed to generate mindmap');
  return res.json();
}

export async function generateMiniGame(text: string, documentId?: string | null, sectionId?: string | null) {
  const res = await fetch(`${BACKEND_API_URL}/generate-mini-game`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, document_id: documentId, section_id: sectionId }),
  });
  if (!res.ok) throw new Error('Failed to generate mini game');
  return res.json();
}
