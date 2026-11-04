'use client';

import { useEffect, useRef } from 'react';
import { Camera, CameraOff } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface CameraFeedProps {
  isCameraActive: boolean;
  isCalibrating: boolean;
  isCalibrated: boolean;
  onStartCamera: (videoElement: HTMLVideoElement) => Promise<void>;
  onStopCamera: () => void;
  onStartCalibration: () => void;
}

export default function CameraFeed({
  isCameraActive,
  isCalibrating,
  isCalibrated,
  onStartCamera,
  onStopCamera,
  onStartCalibration,
}: CameraFeedProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hasAutoStarted = useRef(false);

  // Auto-start camera after studio panel slides in
  useEffect(() => {
    if (hasAutoStarted.current || isCameraActive) return;

    // Wait for the slide-in animation to finish and video element to be ready
    const timer = setTimeout(async () => {
      if (hasAutoStarted.current || !videoRef.current) return;
      hasAutoStarted.current = true;
      try {
        await onStartCamera(videoRef.current);
        // Auto-start calibration once camera is live
        setTimeout(() => onStartCalibration(), 800);
      } catch (err) {
        console.error('Auto-start camera failed:', err);
        hasAutoStarted.current = false;
      }
    }, 600); // Wait for slide animation (500ms) + buffer

    return () => clearTimeout(timer);
  }, [isCameraActive, onStartCamera, onStartCalibration]);

  const handleToggleCamera = async () => {
    if (isCameraActive) {
      onStopCamera();
    } else if (videoRef.current) {
      await onStartCamera(videoRef.current);
    }
  };

  return (
    <div className="relative aspect-video bg-gray-900 flex items-center justify-center rounded-lg overflow-hidden shadow-sm">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className={`w-full h-full object-cover rounded-lg ${
          !isCameraActive ? 'hidden' : ''
        }`}
      />

      {!isCameraActive && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-white rounded-lg">
          <Camera className="w-12 h-12 mb-2 opacity-60" />
          <p className="text-sm opacity-80">Camera is off</p>
        </div>
      )}

      {/* Calibration overlay */}
      {isCameraActive && isCalibrating && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-white rounded-lg">
          <div className="w-16 h-16 border-4 border-white border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-sm font-medium">Look at the screen naturally...</p>
          <p className="text-xs opacity-70 mt-1">Calibrating your baseline</p>
        </div>
      )}

      {/* Status badges */}
      <div className="absolute top-3 left-3 flex flex-wrap gap-2">
        {isCameraActive && (
          <Badge
            variant="outline"
            className={`text-white border-none ${
              isCalibrated
                ? 'bg-green-600/70'
                : isCalibrating
                ? 'bg-yellow-600/70 animate-pulse'
                : 'bg-blue-600/70'
            }`}
          >
            {isCalibrated
              ? 'Tracking'
              : isCalibrating
              ? 'Calibrating...'
              : 'Ready'}
          </Badge>
        )}
      </div>

      {/* Controls */}
      <div className="absolute bottom-3 right-3 flex gap-2">
        <Button
          size="icon"
          variant="secondary"
          className="rounded-full bg-black/50 hover:bg-black/70 backdrop-blur-sm"
          onClick={handleToggleCamera}
        >
          {isCameraActive ? (
            <CameraOff size={18} className="text-white" />
          ) : (
            <Camera size={18} className="text-white" />
          )}
        </Button>

        {isCameraActive && !isCalibrated && !isCalibrating && (
          <Button
            size="sm"
            variant="secondary"
            className="rounded-full bg-black/50 hover:bg-black/70 backdrop-blur-sm text-white"
            onClick={onStartCalibration}
          >
            Calibrate
          </Button>
        )}
      </div>
    </div>
  );
}
