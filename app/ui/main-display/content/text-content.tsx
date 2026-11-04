'use client';

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Volume2, VolumeX, Pause, Play, Loader2 } from 'lucide-react';
import { BACKEND_API_URL } from '@/app/lib/constants';

interface TextContentProps {
  data: {
    title?: string;
    content: string;
  };
  onSectionDone?: () => void;
}

function cleanMarkdown(content: string): string {
  if (!content) return '';
  return content
    .replace(/^```(?:markdown)?\s*/, '')
    .replace(/```$/, '')
    .trim();
}

function prepareForTTS(content: string): string {
  // Split by headings first — add a long pause after each heading
  let text = content
    // Convert headings to spoken form with pauses
    .replace(/#{1,6}\s+(.*?)$/gm, '\n\n$1.\n\n')
    // Strip formatting
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`(.*?)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Convert bullet points to spoken sentences
    .replace(/^[-*+]\s+(.*?)$/gm, '$1.')
    // Convert numbered lists
    .replace(/^\d+\.\s+(.*?)$/gm, '$1.')
    // Strip blockquotes
    .replace(/^>\s/gm, '')
    // Strip horizontal rules
    .replace(/---+/g, '')
    // Ensure paragraphs have clear breaks (Edge TTS respects these)
    .replace(/\n{2,}/g, '\n\n');

  // Remove duplicate consecutive sentences
  const lines = text.split('\n');
  const processed: string[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      processed.push(''); // Keep empty lines as pauses
      continue;
    }
    const normalized = trimmed.toLowerCase().replace(/[.!?]+$/, '');
    if (!seen.has(normalized)) {
      seen.add(normalized);
      // Ensure each line ends with punctuation for natural pausing
      const withPunctuation = /[.!?]$/.test(trimmed) ? trimmed : trimmed + '.';
      processed.push(withPunctuation);
    }
  }

  // Join with double newlines for paragraph pauses
  return processed
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')  // Max 2 newlines (one pause)
    .replace(/\.{2,}/g, '.')      // No double periods
    .trim();
}

export default function TextContent({ data, onSectionDone }: TextContentProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handleSpeak = async () => {
    if (isPlaying) return;

    setIsLoading(true);
    try {
      const text = prepareForTTS(data.content);
      const res = await fetch(`${BACKEND_API_URL}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) throw new Error('TTS failed');
      const { url } = await res.json();

      const audio = new Audio(`${BACKEND_API_URL}${url}`);
      audioRef.current = audio;

      audio.onplay = () => { setIsPlaying(true); setIsLoading(false); };
      audio.onpause = () => setIsPaused(true);
      audio.onended = () => { setIsPlaying(false); setIsPaused(false); setProgress(0); };
      audio.ontimeupdate = () => {
        if (audio.duration) {
          setProgress((audio.currentTime / audio.duration) * 100);
        }
      };

      await audio.play();
      setIsPaused(false);
    } catch (err) {
      console.error('TTS error:', err);
      // Fallback to Web Speech API
      const text = prepareForTTS(data.content);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.onend = () => { setIsPlaying(false); setIsLoading(false); };
      window.speechSynthesis.speak(utterance);
      setIsPlaying(true);
      setIsLoading(false);
    }
  };

  const handlePause = () => {
    if (!audioRef.current) return;
    if (isPaused) {
      audioRef.current.play();
      setIsPaused(false);
    } else {
      audioRef.current.pause();
      setIsPaused(true);
    }
  };

  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    window.speechSynthesis.cancel();
    setIsPlaying(false);
    setIsPaused(false);
    setProgress(0);
    setIsLoading(false);
  };

  return (
    <div className="w-full h-full max-w-2xl mx-auto overflow-auto">
      <div className="px-10 py-10">
        {/* Header */}
        {data.title && (
          <h1 className="text-2xl font-semibold tracking-tight dark:text-gray-50 mb-1 leading-snug">
            {data.title}
          </h1>
        )}

        {/* TTS controls */}
        <div className="flex items-center gap-2 mt-4 mb-8 pb-5 border-b border-gray-200 dark:border-gray-700/60">
          {!isPlaying && !isLoading ? (
            <button
              onClick={handleSpeak}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition"
            >
              <Volume2 className="h-4 w-4" />
              Read aloud
            </button>
          ) : isLoading ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-gray-100 dark:bg-gray-700 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating audio...
            </div>
          ) : (
            <>
              <button
                onClick={handlePause}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-200 transition"
              >
                {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                {isPaused ? 'Resume' : 'Pause'}
              </button>
              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition"
              >
                <VolumeX className="h-4 w-4" />
                Stop
              </button>
              <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-1 ml-2">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all duration-200"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </>
          )}
        </div>

        {/* Content — reading-optimized typography */}
        <article className="
          prose prose-gray dark:prose-invert max-w-none

          prose-headings:font-semibold prose-headings:tracking-tight

          prose-h2:text-[1.3rem] prose-h2:mt-10 prose-h2:mb-4
          prose-h2:text-gray-900 dark:prose-h2:text-gray-100
          prose-h2:pb-2 prose-h2:border-b prose-h2:border-gray-200 dark:prose-h2:border-gray-700/50

          prose-h3:text-[1.1rem] prose-h3:mt-8 prose-h3:mb-3
          prose-h3:text-gray-800 dark:prose-h3:text-gray-200

          prose-p:text-[0.95rem] prose-p:leading-[1.85] prose-p:text-gray-700 dark:prose-p:text-gray-300
          prose-p:mb-5

          prose-li:text-[0.95rem] prose-li:leading-[1.85] prose-li:text-gray-700 dark:prose-li:text-gray-300
          prose-li:mb-1.5
          prose-ul:pl-5 prose-ul:my-4
          prose-ol:pl-5 prose-ol:my-4

          prose-strong:text-gray-900 dark:prose-strong:text-white prose-strong:font-semibold

          prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline

          prose-code:text-[0.85rem] prose-code:bg-gray-100 dark:prose-code:bg-gray-800
          prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-normal

          prose-blockquote:border-l-[3px] prose-blockquote:border-blue-400 dark:prose-blockquote:border-blue-500
          prose-blockquote:bg-blue-50/40 dark:prose-blockquote:bg-blue-900/10
          prose-blockquote:rounded-r-lg prose-blockquote:py-2 prose-blockquote:px-5 prose-blockquote:my-6
          prose-blockquote:text-[0.93rem] prose-blockquote:leading-[1.8] prose-blockquote:italic
          prose-blockquote:text-gray-600 dark:prose-blockquote:text-gray-400

          prose-hr:my-8 prose-hr:border-gray-200 dark:prose-hr:border-gray-700/50
        ">
          <ReactMarkdown>{cleanMarkdown(data.content)}</ReactMarkdown>
        </article>

        {/* Section done button */}
        {onSectionDone && (
          <div className="mt-10 pt-6 border-t border-gray-200 dark:border-gray-700/60 flex justify-center">
            <button
              onClick={onSectionDone}
              className="px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg transition font-medium flex items-center gap-2"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Done with this section
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
