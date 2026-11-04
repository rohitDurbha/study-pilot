import type { FocusSignals, CalibrationData, FocusDetectionConfig } from './types';
import { DEFAULT_FOCUS_CONFIG } from './types';

// Landmark type matching what MediaPipe FaceLandmarker actually returns
interface Landmark {
  x: number;
  y: number;
  z?: number;
}

// MediaPipe Face Mesh landmark indices
// Reference: https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png

// Right eye landmarks
const RIGHT_EYE_TOP = 159;
const RIGHT_EYE_BOTTOM = 145;
const RIGHT_EYE_LEFT = 33;
const RIGHT_EYE_RIGHT = 133;
const RIGHT_EYE_UPPER_1 = 158;
const RIGHT_EYE_LOWER_1 = 153;

// Left eye landmarks
const LEFT_EYE_TOP = 386;
const LEFT_EYE_BOTTOM = 374;
const LEFT_EYE_LEFT = 362;
const LEFT_EYE_RIGHT = 263;
const LEFT_EYE_UPPER_1 = 385;
const LEFT_EYE_LOWER_1 = 380;

// Iris landmarks (indices 468-477 in refined landmarks)
const RIGHT_IRIS_CENTER = 468;
const LEFT_IRIS_CENTER = 473;

// Head pose reference points
const NOSE_TIP = 1;
const FOREHEAD = 10;
const CHIN = 152;
const LEFT_CHEEK = 234;
const RIGHT_CHEEK = 454;

function distance(a: Landmark, b: Landmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function distance3d(a: Landmark, b: Landmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y, (a.z ?? 0) - (b.z ?? 0));
}

/**
 * Compute Eye Aspect Ratio for one eye.
 * EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
 * Based on Soukupova & Cech (2016)
 */
function computeEar(
  landmarks: Landmark[],
  topIdx: number,
  bottomIdx: number,
  leftIdx: number,
  rightIdx: number,
  upper1Idx: number,
  lower1Idx: number
): number {
  const vertical1 = distance(landmarks[upper1Idx], landmarks[lower1Idx]);
  const vertical2 = distance(landmarks[topIdx], landmarks[bottomIdx]);
  const horizontal = distance(landmarks[leftIdx], landmarks[rightIdx]);

  if (horizontal === 0) return 0;
  return (vertical1 + vertical2) / (2.0 * horizontal);
}

/**
 * Compute average EAR for both eyes
 */
export function computeAverageEar(landmarks: Landmark[]): number {
  const rightEar = computeEar(
    landmarks,
    RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM,
    RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT,
    RIGHT_EYE_UPPER_1, RIGHT_EYE_LOWER_1
  );
  const leftEar = computeEar(
    landmarks,
    LEFT_EYE_TOP, LEFT_EYE_BOTTOM,
    LEFT_EYE_LEFT, LEFT_EYE_RIGHT,
    LEFT_EYE_UPPER_1, LEFT_EYE_LOWER_1
  );
  return (rightEar + leftEar) / 2.0;
}

/**
 * Compute gaze deviation from center.
 * Uses iris center position relative to eye corners.
 * Returns 0 (looking at screen) to 1 (looking far away).
 */
export function computeGazeDeviation(
  landmarks: Landmark[],
  calibration: CalibrationData | null
): number {
  if (landmarks.length < 478) {
    // No iris landmarks available (need refinement enabled)
    return 0;
  }

  const rightIris = landmarks[RIGHT_IRIS_CENTER];
  const leftIris = landmarks[LEFT_IRIS_CENTER];

  // Compute iris position relative to eye corners (0-1, 0.5 = center)
  const rightEyeLeft = landmarks[RIGHT_EYE_LEFT];
  const rightEyeRight = landmarks[RIGHT_EYE_RIGHT];
  const leftEyeLeft = landmarks[LEFT_EYE_LEFT];
  const leftEyeRight = landmarks[LEFT_EYE_RIGHT];

  const rightHorizontalSpan = distance(rightEyeLeft, rightEyeRight);
  const leftHorizontalSpan = distance(leftEyeLeft, leftEyeRight);

  if (rightHorizontalSpan === 0 || leftHorizontalSpan === 0) return 0;

  // Horizontal ratio: how far iris is from the inner corner
  const rightIrisRatioX = distance(rightEyeLeft, rightIris) / rightHorizontalSpan;
  const leftIrisRatioX = distance(leftEyeLeft, leftIris) / leftHorizontalSpan;

  const avgIrisX = (rightIrisRatioX + leftIrisRatioX) / 2;

  // Vertical component using eye top/bottom
  const rightVerticalSpan = distance(landmarks[RIGHT_EYE_TOP], landmarks[RIGHT_EYE_BOTTOM]);
  const leftVerticalSpan = distance(landmarks[LEFT_EYE_TOP], landmarks[LEFT_EYE_BOTTOM]);

  let avgIrisY = 0.5;
  if (rightVerticalSpan > 0 && leftVerticalSpan > 0) {
    const rightIrisRatioY = distance(landmarks[RIGHT_EYE_TOP], rightIris) / rightVerticalSpan;
    const leftIrisRatioY = distance(landmarks[LEFT_EYE_TOP], leftIris) / leftVerticalSpan;
    avgIrisY = (rightIrisRatioY + leftIrisRatioY) / 2;
  }

  // Center is approximately (0.5, 0.5)
  const centerX = calibration?.baselineGazeCenter.x ?? 0.5;
  const centerY = calibration?.baselineGazeCenter.y ?? 0.5;

  // Distance from center, normalized to 0-1
  const deviation = Math.hypot(avgIrisX - centerX, avgIrisY - centerY) * 2;
  return Math.min(deviation, 1.0);
}

/**
 * Compute head pose deviation from facing the camera.
 * Uses the relative positions of nose, forehead, chin, and cheeks.
 * Returns 0 (facing camera) to 1 (turned away).
 */
export function computeHeadPoseDeviation(landmarks: Landmark[]): number {
  const nose = landmarks[NOSE_TIP];
  const leftCheek = landmarks[LEFT_CHEEK];
  const rightCheek = landmarks[RIGHT_CHEEK];

  // Yaw estimation: if nose is closer to one cheek than the other, head is turned
  const noseToLeft = distance(nose, leftCheek);
  const noseToRight = distance(nose, rightCheek);
  const cheekSpan = distance(leftCheek, rightCheek);

  if (cheekSpan === 0) return 0;

  // Ratio of nose distances to cheeks (0.5 = centered)
  const yawRatio = noseToLeft / (noseToLeft + noseToRight);
  const yawDeviation = Math.abs(yawRatio - 0.5) * 2; // 0 to 1

  // Pitch estimation: using z-coordinates if available
  const forehead = landmarks[FOREHEAD];
  const chin = landmarks[CHIN];
  const faceHeight = distance(forehead, chin);

  let pitchDeviation = 0;
  if (faceHeight > 0 && nose.z !== undefined && forehead.z !== undefined) {
    // If nose z is very different from forehead z, head is tilted
    const zDiff = Math.abs((nose.z ?? 0) - (forehead.z ?? 0));
    pitchDeviation = Math.min(zDiff * 5, 1.0); // Scale and clamp
  }

  // Combined deviation
  return Math.min(Math.max(yawDeviation, pitchDeviation), 1.0);
}

/**
 * Blink detector - tracks EAR over time to detect and count blinks
 */
export class BlinkDetector {
  private earHistory: { ear: number; timestamp: number }[] = [];
  private blinkCount = 0;
  private lastBlinkTime = 0;
  private inBlink = false;
  private blinkStartTime = 0;
  private windowMs = 60000; // 1 minute window for blink rate

  constructor(private config: FocusDetectionConfig = DEFAULT_FOCUS_CONFIG) {}

  update(ear: number, timestamp: number): void {
    // Clean old entries
    this.earHistory = this.earHistory.filter(
      (e) => timestamp - e.timestamp < this.windowMs
    );
    this.earHistory.push({ ear, timestamp });

    // Detect blink: EAR drops below threshold then recovers
    if (!this.inBlink && ear < this.config.earClosedThreshold) {
      this.inBlink = true;
      this.blinkStartTime = timestamp;
    } else if (this.inBlink && ear >= this.config.earClosedThreshold) {
      const blinkDuration = timestamp - this.blinkStartTime;
      // Only count as blink if duration is short enough (not eyes closed)
      if (blinkDuration < this.config.blinkDurationMs) {
        this.blinkCount++;
        this.lastBlinkTime = timestamp;
      }
      this.inBlink = false;
    }

    // Clean old blink counts (keep only last minute)
    // We approximate by tracking total count and decay
  }

  getBlinkRate(): number {
    if (this.earHistory.length < 2) return 15; // Default normal rate

    const timeSpanMs =
      this.earHistory[this.earHistory.length - 1].timestamp -
      this.earHistory[0].timestamp;

    if (timeSpanMs < 5000) return 15; // Not enough data yet

    // Blinks per minute
    return (this.blinkCount / timeSpanMs) * 60000;
  }

  reset(): void {
    this.earHistory = [];
    this.blinkCount = 0;
    this.lastBlinkTime = 0;
    this.inBlink = false;
  }
}

/**
 * Convert raw signals into a composite focus score (0-100)
 */
export function computeCompositeScore(
  signals: FocusSignals,
  calibration: CalibrationData | null,
  config: FocusDetectionConfig = DEFAULT_FOCUS_CONFIG
): number {
  if (!signals.facePresent) return 0;

  // EAR score: higher EAR = more open eyes = more focused
  const baselineEar = calibration?.baselineEar ?? 0.28;
  const earRatio = signals.ear / baselineEar;
  const earScore = Math.max(0, Math.min(earRatio * 90, 100));

  // Gaze score: lower deviation = more focused
  const gazeScore = Math.max(0, (1 - signals.gazeDeviation / config.gazeDeviationThreshold) * 100);

  // Blink score: normal blink rate (15-20/min) = focused
  // Too high (>25) = fatigued, too low (<8) = zoned out
  const baselineBlinkRate = calibration?.baselineBlinkRate ?? 17;
  const blinkDeviation = Math.abs(signals.blinkRate - baselineBlinkRate) / baselineBlinkRate;
  const blinkScore = Math.max(0, (1 - blinkDeviation) * 100);

  // Presence score: binary, but smooth transitions handled elsewhere
  const presenceScore = signals.facePresent ? 100 : 0;

  // Weighted composite
  const composite =
    config.earWeight * earScore +
    config.gazeWeight * gazeScore +
    config.blinkWeight * blinkScore +
    config.presenceWeight * presenceScore;

  return Math.max(0, Math.min(Math.round(composite), 100));
}

/**
 * Exponential Moving Average smoother.
 * Uses faster decay when score drops (responds quickly to disengagement)
 * and slower rise (doesn't spike on brief glances).
 */
export class EmaSmoother {
  private value: number | null = null;

  constructor(
    private alphaUp: number = 0.25,   // Slow rise
    private alphaDown: number = 0.5,  // Fast drop
  ) {}

  update(raw: number): number {
    if (this.value === null) {
      this.value = raw;
    } else {
      // Use faster alpha when score is dropping
      const alpha = raw < this.value ? this.alphaDown : this.alphaUp;
      this.value = alpha * raw + (1 - alpha) * this.value;
    }
    return Math.round(this.value);
  }

  getValue(): number {
    return this.value !== null ? Math.round(this.value) : 0;
  }

  reset(): void {
    this.value = null;
  }
}

/**
 * Process a full frame of landmarks into FocusSignals
 */
export function extractSignals(
  landmarks: Landmark[],
  blinkDetector: BlinkDetector,
  calibration: CalibrationData | null,
  timestamp: number
): FocusSignals {
  const ear = computeAverageEar(landmarks);
  const gazeDeviation = computeGazeDeviation(landmarks, calibration);
  const headPoseDeviation = computeHeadPoseDeviation(landmarks);

  blinkDetector.update(ear, timestamp);

  return {
    ear,
    gazeDeviation: Math.max(gazeDeviation, headPoseDeviation),
    blinkRate: blinkDetector.getBlinkRate(),
    facePresent: true,
    headPoseDeviation,
  };
}
