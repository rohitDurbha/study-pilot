'use client';

import { BACKEND_API_URL } from '@/app/lib/constants';

export interface AgentContext {
  documentTitle: string;
  summaryText: string;
  focusScore: number;
  contentType: string;
  distractionCount: number;
  sessionDurationMin: number;
  knowledgeGraph?: any;
  quizPerformance?: any;
}

// Agent decision endpoints (deterministic, no LLM)
export async function agentWelcome(documentId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/decide/welcome`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  });
  if (!res.ok) throw new Error('Agent welcome failed');
  return res.json();
}

export async function agentFocusDrop(documentId: string, sectionId: string, contentType: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/decide/focus-drop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, section_id: sectionId, content_type: contentType }),
  });
  if (!res.ok) throw new Error('Agent focus drop failed');
  return res.json();
}

export async function agentSectionComplete(documentId: string, sectionId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/decide/section-complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, section_id: sectionId }),
  });
  if (!res.ok) throw new Error('Agent section complete failed');
  return res.json();
}

export async function agentDistractionReturn(documentId: string, sectionId: string, sectionTitle: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/decide/distraction-return`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, section_id: sectionId, section_title: sectionTitle }),
  });
  if (!res.ok) throw new Error('Agent distraction return failed');
  return res.json();
}

export interface ChatSource {
  text: string;
  section_id: string;
  section_title: string;
  score: number;
}

export interface ChatResponse {
  response: string;
  sources?: ChatSource[];
  pipeline?: string;
}

export async function chatWithAgent(
  message: string,
  sessionId: string | null,
  context: AgentContext,
  pipeline: 'rag' | 'full_context' = 'full_context'
): Promise<ChatResponse> {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sessionId, context, pipeline }),
  });
  if (!res.ok) throw new Error('Agent chat failed');
  return res.json();
}

export async function getChatHistory(sessionId: string) {
  const res = await fetch(`${BACKEND_API_URL}/api/agent/history/${sessionId}`);
  if (!res.ok) throw new Error('Failed to load chat history');
  return res.json();
}
