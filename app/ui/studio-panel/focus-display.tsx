'use client';

import { Brain } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { FocusSignals } from '@/app/lib/focus-detection';

interface FocusDisplayProps {
  focusScore: number;
  isCameraActive: boolean;
  isCalibrated: boolean;
  signals: FocusSignals | null;
}

function FocusProgressBar({ value }: { value: number }) {
  const getColor = (level: number) => {
    if (level < 30) return '#ef4444';
    if (level < 70) return '#eab308';
    return '#22c55e';
  };

  return (
    <div className="w-full bg-gray-200 rounded-full overflow-hidden h-3">
      <div
        className="h-full rounded-full transition-all duration-1000 ease-out"
        style={{
          width: `${value}%`,
          backgroundColor: getColor(value),
        }}
      />
    </div>
  );
}

function getLabel(level: number): string {
  if (level < 30) return 'Take a break!';
  if (level < 70) return 'We can do better';
  if (level < 90) return 'Locked in';
  return 'Deep focus';
}

function getLabelColor(level: number): string {
  if (level < 30) return '#ef4444';
  if (level < 70) return '#eab308';
  return '#22c55e';
}

export default function FocusDisplay({
  focusScore,
  isCameraActive,
  isCalibrated,
  signals,
}: FocusDisplayProps) {
  const statusColor = !isCameraActive
    ? '#ef4444'
    : !isCalibrated
    ? '#eab308'
    : '#22c55e';

  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4" /> Focus Level
          </div>
          <div
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: statusColor }}
          />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold">{focusScore}%</div>
            <div
              className="text-sm font-medium"
              style={{ color: getLabelColor(focusScore) }}
            >
              {isCameraActive && isCalibrated
                ? getLabel(focusScore)
                : !isCameraActive
                ? 'Camera off'
                : 'Calibrate to start'}
            </div>
          </div>

          <FocusProgressBar value={focusScore} />

          <div className="flex justify-between mt-1 text-xs text-gray-500">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>

          {/* Signal breakdown — small detail for power users */}
          {signals && isCameraActive && isCalibrated && (
            <div className="grid grid-cols-2 gap-2 mt-2 text-xs text-gray-500">
              <div>
                Eyes: {signals.facePresent ? (signals.ear * 100).toFixed(0) : '--'}
              </div>
              <div>
                Gaze: {signals.facePresent ? ((1 - signals.gazeDeviation) * 100).toFixed(0) : '--'}%
              </div>
              <div>
                Blinks: {signals.facePresent ? signals.blinkRate.toFixed(0) : '--'}/min
              </div>
              <div>
                Head: {signals.facePresent ? ((1 - signals.headPoseDeviation) * 100).toFixed(0) : '--'}%
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
