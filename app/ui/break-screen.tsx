'use client';

import React, { useState, useEffect, useRef } from 'react';

interface BreakScreenProps {
  onBack: () => void;
}

export default function BreakScreen({ onBack }: BreakScreenProps) {
  const [elapsed, setElapsed] = useState(0);
  const startTime = useRef(Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  // Breathing animation — gentle scale pulse
  const breathPhase = (elapsed % 8) / 8; // 8 second breath cycle
  const scale = 1 + Math.sin(breathPhase * Math.PI * 2) * 0.05;

  return (
    <div className="absolute inset-0 bg-gray-950/98 backdrop-blur-md flex items-center justify-center z-50">
      <div className="text-center">
        {/* Breathing circle with timer */}
        <div className="relative w-48 h-48 mx-auto mb-8">
          {/* Outer ring — subtle glow */}
          <div
            className="absolute inset-0 rounded-full border border-blue-500/20"
            style={{ transform: `scale(${scale})`, transition: 'transform 0.5s ease' }}
          />
          {/* Middle ring */}
          <div
            className="absolute inset-3 rounded-full border border-blue-500/30"
            style={{ transform: `scale(${scale * 0.98})`, transition: 'transform 0.5s ease' }}
          />
          {/* Inner circle */}
          <div
            className="absolute inset-6 rounded-full bg-blue-950/50 border border-blue-500/20 flex flex-col items-center justify-center"
            style={{ transform: `scale(${scale * 0.96})`, transition: 'transform 0.5s ease' }}
          >
            <span className="text-3xl font-light text-white tabular-nums">
              {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
            </span>
            <span className="text-xs text-blue-300/60 mt-1">break time</span>
          </div>
        </div>

        {/* Message */}
        <h2 className="text-xl font-light text-white/90 mb-2">Take a breath</h2>
        <p className="text-gray-500 text-sm mb-10 max-w-xs mx-auto">
          Step away, stretch, or just close your eyes for a moment.
          Your progress is saved.
        </p>

        {/* Back button */}
        <button
          onClick={onBack}
          className="px-8 py-3 bg-white/10 hover:bg-white/20 text-white rounded-full transition-all duration-300 font-medium border border-white/10 hover:border-white/20"
        >
          I&apos;m ready to continue
        </button>

        {/* Subtle tip */}
        {elapsed > 60 && (
          <p className="text-gray-600 text-xs mt-6 animate-in fade-in duration-1000">
            Short breaks every 25 minutes help retain what you learn
          </p>
        )}
      </div>
    </div>
  );
}
