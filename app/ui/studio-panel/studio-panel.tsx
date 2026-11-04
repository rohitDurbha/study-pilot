'use client';

import React, { useRef, useEffect } from 'react';
import FocusDisplay from './focus-display';
import FocusChart from './focus-chart';
import { useFocusDetection } from '@/app/lib/focus-detection';
import type { FocusEvent, FocusScore } from '@/app/lib/focus-detection';
import { Camera, CameraOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface StudioPanelProps {
  onFocusUpdate?: (focusScore: number) => void;
  onAbsenceStart?: () => void;
  onAbsenceEnd?: (duration: number) => void;
  isContentLoaded?: boolean;
  currentSummaryText?: string;
}

export default function StudioPanel({
  onFocusUpdate,
  onAbsenceStart,
  onAbsenceEnd,
}: StudioPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hasAutoStarted = useRef(false);

  const handleFocusEvent = React.useCallback(
    (event: FocusEvent) => {
      switch (event.type) {
        case 'focus_update': {
          const score = event.data as FocusScore;
          onFocusUpdate?.(score.smoothed);
          break;
        }
        case 'absence_start':
          onAbsenceStart?.();
          break;
        case 'absence_end': {
          const data = event.data as { duration: number };
          onAbsenceEnd?.(data.duration);
          break;
        }
      }
    },
    [onFocusUpdate, onAbsenceStart, onAbsenceEnd]
  );

  const {
    focusScore,
    isCalibrating,
    isCalibrated,
    isCameraActive,
    signals,
    startCamera,
    stopCamera,
    startCalibration,
    focusHistory,
  } = useFocusDetection({}, handleFocusEvent);

  // Auto-start camera after panel mounts
  useEffect(() => {
    if (hasAutoStarted.current || isCameraActive) return;

    const timer = setTimeout(async () => {
      if (hasAutoStarted.current || !videoRef.current) return;
      hasAutoStarted.current = true;
      try {
        await startCamera(videoRef.current);
        setTimeout(() => startCalibration(), 800);
      } catch (err) {
        console.error('Auto-start camera failed:', err);
        hasAutoStarted.current = false;
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [isCameraActive, startCamera, startCalibration]);

  const handleToggleCamera = async () => {
    if (isCameraActive) {
      stopCamera();
    } else if (videoRef.current) {
      await startCamera(videoRef.current);
    }
  };

  return (
    <div className="w-[320px] bg-white dark:bg-gray-900 border-l dark:border-gray-800 flex-shrink-0 h-full overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Camera live feed — always visible */}
        <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className={`studio-video w-full h-full object-cover ${!isCameraActive ? 'hidden' : ''}`}
          />

          {isCameraActive && isCalibrating && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-white">
              <div className="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-sm">Look at the screen naturally...</p>
              <p className="text-xs opacity-70 mt-1">Calibrating</p>
            </div>
          )}

          {!isCameraActive && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-white">
              <Camera className="w-10 h-10 mb-2 opacity-60" />
              <p className="text-sm opacity-80">Camera off</p>
            </div>
          )}

          <div className="absolute top-2 left-2">
            {isCameraActive && (
              <Badge
                variant="outline"
                className={`text-white border-none text-xs ${
                  isCalibrated ? 'bg-green-600/70' : 'bg-yellow-600/70 animate-pulse'
                }`}
              >
                {isCalibrated ? 'Tracking' : 'Calibrating...'}
              </Badge>
            )}
          </div>

          <div className="absolute bottom-2 right-2">
            <Button
              size="icon"
              variant="secondary"
              className="rounded-full bg-black/50 hover:bg-black/70 h-8 w-8"
              onClick={handleToggleCamera}
            >
              {isCameraActive ? (
                <CameraOff size={14} className="text-white" />
              ) : (
                <Camera size={14} className="text-white" />
              )}
            </Button>
          </div>
        </div>

        {/* Focus score */}
        <FocusDisplay
          focusScore={focusScore}
          isCameraActive={isCameraActive}
          isCalibrated={isCalibrated}
          signals={signals}
        />

        {/* Focus chart — real data */}
        <FocusChart focusHistory={focusHistory} />
      </div>
    </div>
  );
}
