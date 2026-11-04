'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { FocusEngine } from './focus-engine';
import type {
  FocusScore,
  FocusEvent,
  CalibrationData,
  FocusDetectionConfig,
} from './types';

export interface UseFocusDetectionReturn {
  // State
  focusScore: number; // Smoothed 0-100
  rawScore: number; // Unsmoothed 0-100
  isCalibrating: boolean;
  isCalibrated: boolean;
  isCameraActive: boolean;
  isAbsent: boolean; // Student left
  absenceDuration: number | null; // How long they've been gone (ms)
  signals: FocusScore['signals'] | null;

  // Actions
  startCamera: (videoElement: HTMLVideoElement) => Promise<void>;
  stopCamera: () => void;
  startCalibration: () => void;
  pauseDetection: () => void;
  resumeDetection: () => void;

  // Event history
  focusHistory: { score: number; timestamp: number }[];
}

export function useFocusDetection(
  config?: Partial<FocusDetectionConfig>,
  onFocusEvent?: (event: FocusEvent) => void
): UseFocusDetectionReturn {
  const engineRef = useRef<FocusEngine | null>(null);
  const [focusScore, setFocusScore] = useState(0);
  const [rawScore, setRawScore] = useState(0);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [isCalibrated, setIsCalibrated] = useState(false);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isAbsent, setIsAbsent] = useState(false);
  const [absenceDuration, setAbsenceDuration] = useState<number | null>(null);
  const [signals, setSignals] = useState<FocusScore['signals'] | null>(null);
  const [focusHistory, setFocusHistory] = useState<
    { score: number; timestamp: number }[]
  >([]);

  const absenceStartRef = useRef<number | null>(null);
  const absenceIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const onFocusEventRef = useRef(onFocusEvent);
  onFocusEventRef.current = onFocusEvent;

  // Initialize engine once
  useEffect(() => {
    engineRef.current = new FocusEngine(config);

    const unsubscribe = engineRef.current.on((event: FocusEvent) => {
      switch (event.type) {
        case 'focus_update': {
          const score = event.data as FocusScore;
          setFocusScore(score.smoothed);
          setRawScore(score.raw);
          setSignals(score.signals);

          // Add to history (keep last 5 minutes at ~1 sample per 2 seconds)
          setFocusHistory((prev) => {
            const entry = { score: score.smoothed, timestamp: score.timestamp };
            const cutoff = Date.now() - 5 * 60 * 1000;
            const filtered = prev.filter((h) => h.timestamp > cutoff);
            return [...filtered, entry];
          });
          break;
        }

        case 'absence_start': {
          setIsAbsent(true);
          absenceStartRef.current = event.timestamp;
          // Start counting absence duration
          absenceIntervalRef.current = setInterval(() => {
            if (absenceStartRef.current) {
              setAbsenceDuration(Date.now() - absenceStartRef.current);
            }
          }, 1000);
          break;
        }

        case 'absence_end': {
          setIsAbsent(false);
          setAbsenceDuration(null);
          absenceStartRef.current = null;
          if (absenceIntervalRef.current) {
            clearInterval(absenceIntervalRef.current);
            absenceIntervalRef.current = null;
          }
          break;
        }

        case 'calibration_complete': {
          setIsCalibrating(false);
          setIsCalibrated(true);
          break;
        }
      }

      // Forward to external listener
      onFocusEventRef.current?.(event);
    });

    return () => {
      unsubscribe();
      engineRef.current?.stop();
      if (absenceIntervalRef.current) {
        clearInterval(absenceIntervalRef.current);
      }
    };
  }, []); // Engine created once, config changes require remount

  const startCamera = useCallback(async (videoElement: HTMLVideoElement) => {
    if (!engineRef.current) return;
    try {
      await engineRef.current.startCamera(videoElement);
      setIsCameraActive(true);
    } catch (err) {
      console.error('Failed to start camera:', err);
      setIsCameraActive(false);
    }
  }, []);

  const stopCamera = useCallback(() => {
    engineRef.current?.stop();
    setIsCameraActive(false);
    setFocusScore(0);
    setRawScore(0);
    setSignals(null);
    setIsAbsent(false);
    setAbsenceDuration(null);
  }, []);

  const startCalibration = useCallback(() => {
    engineRef.current?.startCalibration();
    setIsCalibrating(true);
  }, []);

  const pauseDetection = useCallback(() => {
    engineRef.current?.pause();
  }, []);

  const resumeDetection = useCallback(() => {
    engineRef.current?.resume();
  }, []);

  return {
    focusScore,
    rawScore,
    isCalibrating,
    isCalibrated,
    isCameraActive,
    isAbsent,
    absenceDuration,
    signals,
    startCamera,
    stopCamera,
    startCalibration,
    pauseDetection,
    resumeDetection,
    focusHistory,
  };
}
