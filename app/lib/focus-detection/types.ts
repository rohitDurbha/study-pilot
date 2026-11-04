export interface FocusSignals {
  ear: number; // Eye Aspect Ratio (0-1, typically 0.15-0.35)
  gazeDeviation: number; // How far gaze is from center (0 = center, 1 = far)
  blinkRate: number; // Blinks per minute
  facePresent: boolean; // Is a face detected?
  headPoseDeviation: number; // How far head is turned from facing camera (0-1)
}

export interface FocusScore {
  raw: number; // Unsmoothed composite score (0-100)
  smoothed: number; // EMA-smoothed score (0-100)
  signals: FocusSignals;
  timestamp: number;
}

export interface CalibrationData {
  baselineEar: number;
  baselineGazeCenter: { x: number; y: number };
  baselineBlinkRate: number;
  isCalibrated: boolean;
}

export interface FocusDetectionConfig {
  // Signal weights for composite score
  earWeight: number;
  gazeWeight: number;
  blinkWeight: number;
  presenceWeight: number;

  // EMA smoothing factor (0-1, higher = more responsive)
  smoothingAlpha: number;

  // Thresholds
  earClosedThreshold: number; // Below this = eyes closed
  blinkDurationMs: number; // Max duration of a blink in ms
  gazeDeviationThreshold: number; // Beyond this = looking away
  absenceThresholdMs: number; // No face for this long = absent

  // Frame processing
  targetFps: number; // How many frames per second to process
}

export const DEFAULT_FOCUS_CONFIG: FocusDetectionConfig = {
  earWeight: 0.40,   // Eyes open/closed is the strongest signal
  gazeWeight: 0.35,  // Where you're looking matters a lot
  blinkWeight: 0.10, // Blink rate is a secondary signal
  presenceWeight: 0.15, // Just being there is minimal — you need to actually look

  smoothingAlpha: 0.3,

  earClosedThreshold: 0.19,
  blinkDurationMs: 400,
  gazeDeviationThreshold: 0.35,
  absenceThresholdMs: 3000, // 3 seconds to detect absence (was 5)

  targetFps: 15,
};

export type FocusEventType =
  | 'focus_update' // Regular focus score update
  | 'absence_start' // Face disappeared
  | 'absence_end' // Face reappeared
  | 'calibration_complete'; // Baseline established

export interface FocusEvent {
  type: FocusEventType;
  data: FocusScore | CalibrationData | { duration: number };
  timestamp: number;
}
