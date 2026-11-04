'use client';

import { BACKEND_API_URL } from '@/app/lib/constants';

export async function getSections(documentId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/sections/${documentId}`);
  if (!res.ok) throw new Error('Failed to get sections');
  return res.json();
}

export async function updateSectionProgress(documentId: string, sectionId: string, status: string, quizScore?: number) {
  const res = await fetch(`${BACKEND_API_URL}/api/sections/${documentId}/${sectionId}/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, quiz_score: quizScore }),
  });
  if (!res.ok) throw new Error('Failed to update progress');
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${BACKEND_API_URL}/api/documents`);
  if (!res.ok) throw new Error('Failed to list documents');
  return res.json();
}

export async function getLatestDocument() {
  const res = await fetch(`${BACKEND_API_URL}/api/documents/latest`);
  if (!res.ok) throw new Error('Failed to get latest document');
  return res.json();
}

export async function getLatestSession() {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions/latest`);
  if (!res.ok) throw new Error('Failed to get latest session');
  return res.json();
}

export async function createDocument(id: string, filename: string, summary: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, filename, summary }),
  });
  if (!res.ok) throw new Error('Failed to create document');
  return res.json();
}

export async function getKnowledgeGraph(docId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/documents/${docId}/graph`);
  if (!res.ok) throw new Error('Failed to get knowledge graph');
  return res.json();
}

export async function createSession(documentId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function recordFocusEvents(
  sessionId: string,
  events: { score: number; contentType: string }[]
) {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions/${sessionId}/focus`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events }),
  });
  if (!res.ok) throw new Error('Failed to record focus events');
  return res.json();
}

export async function recordDistraction(sessionId: string, durationSec: number) {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions/${sessionId}/distraction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ duration_sec: durationSec }),
  });
  if (!res.ok) throw new Error('Failed to record distraction');
  return res.json();
}

export async function endSession(sessionId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions/${sessionId}/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to end session');
  return res.json();
}

export async function getSessionAnalytics(sessionId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/sessions/${sessionId}/analytics`);
  if (!res.ok) throw new Error('Failed to get analytics');
  return res.json();
}
