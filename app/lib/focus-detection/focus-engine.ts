'use client';

import type {
  FocusScore,
  FocusEvent,
  FocusDetectionConfig,
  CalibrationData,
} from './types';

// MediaPipe types — loaded dynamically to avoid SSR/bundler issues with WASM
type FaceLandmarkerType = any;
import { DEFAULT_FOCUS_CONFIG } from './types';
import {
  extractSignals,
  computeCompositeScore,
  EmaSmoother,
  BlinkDetector,
  computeAverageEar,
  computeGazeDeviation,
} from './signal-processor';

type FocusEventCallback = (event: FocusEvent) => void;

export class FocusEngine {
  private faceLandmarker: FaceLandmarkerType | null = null;
  private videoElement: HTMLVideoElement | null = null;
  private stream: MediaStream | null = null;
  private animationFrameId: number | null = null;
  private lastProcessTime = 0;
  private isRunning = false;

  private config: FocusDetectionConfig;
  private smoother: EmaSmoother;
  private blinkDetector: BlinkDetector;
  private calibration: CalibrationData | null = null;
  private listeners: FocusEventCallback[] = [];

  // Absence tracking
  private lastFaceSeenTime = 0;
  private isAbsent = false;
  private absenceStartTime = 0;

  // Calibration
  private calibrationSamples: {
    ear: number;
    gazeX: number;
    gazeY: number;
  }[] = [];
  private isCalibrating = false;
  private calibrationStartTime = 0;
  private calibrationDurationMs = 5000;

  // Latest score for external access
  private latestScore: FocusScore | null = null;

  constructor(config: Partial<FocusDetectionConfig> = {}) {
    this.config = { ...DEFAULT_FOCUS_CONFIG, ...config };
    this.smoother = new EmaSmoother(this.config.smoothingAlpha, 0.5);
    this.blinkDetector = new BlinkDetector(this.config);
  }

  /**
   * Initialize MediaPipe FaceLandmarker
   */
  async initialize(): Promise<void> {
    // Dynamic import to avoid SSR/bundler issues with WASM
    const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');

    const vision = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
    );

    this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numFaces: 1,
      outputFaceBlendshapes: false,
      outputFacialTransformationMatrixes: false,
    });
  }

  /**
   * Start the camera and begin processing
   */
  async startCamera(videoElement: HTMLVideoElement): Promise<void> {
    if (!this.faceLandmarker) {
      await this.initialize();
    }

    this.videoElement = videoElement;

    this.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: 'user',
      },
    });

    videoElement.srcObject = this.stream;
    await new Promise<void>((resolve) => {
      videoElement.onloadeddata = () => resolve();
    });
    // Ensure video is actually playing before processing
    await videoElement.play();

    // Wait until video has real dimensions
    await new Promise<void>((resolve) => {
      const check = () => {
        if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
          resolve();
        } else {
          requestAnimationFrame(check);
        }
      };
      setTimeout(check, 800);
    });

    // Warm up MediaPipe — wait extra time for WASM to fully initialize
    // instead of calling detectForVideo which throws in Next.js dev overlay
    await new Promise(r => setTimeout(r, 1500));

    this.isRunning = true;
    this.lastFaceSeenTime = Date.now();
    this.processFrame();
  }

  /**
   * Stop camera and processing
   */
  stop(): void {
    this.isRunning = false;

    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }

    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
  }

  /**
   * Pause processing without stopping camera
   */
  pause(): void {
    this.isRunning = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  /**
   * Resume processing
   */
  resume(): void {
    if (!this.isRunning && this.videoElement && this.stream) {
      this.isRunning = true;
      this.processFrame();
    }
  }

  /**
   * Start calibration phase
   */
  startCalibration(): void {
    this.isCalibrating = true;
    this.calibrationStartTime = Date.now();
    this.calibrationSamples = [];
  }

  /**
   * Main processing loop — wrapped in try/catch to prevent
   * errors from bubbling to React error overlay during initialization
   */
  private mediapipeReady = false;

  private processFrame = (): void => {
    if (!this.isRunning || !this.faceLandmarker || !this.videoElement) return;

    const now = Date.now();
    const frameInterval = 1000 / this.config.targetFps;

    // Throttle to target FPS
    if (now - this.lastProcessTime >= frameInterval) {
      this.lastProcessTime = now;

      // Skip if video isn't ready or dimensions are 0
      if (
        !this.videoElement ||
        !this.faceLandmarker ||
        this.videoElement.readyState < 2 ||
        this.videoElement.videoWidth === 0 ||
        this.videoElement.videoHeight === 0 ||
        this.videoElement.paused
      ) {
        this.animationFrameId = requestAnimationFrame(this.processFrame);
        return;
      }

      // Skip first 3 seconds of frames to let MediaPipe fully initialize
      if (!this.mediapipeReady) {
        if (now - this.lastFaceSeenTime > 3000) {
          this.mediapipeReady = true;
        } else {
          this.animationFrameId = requestAnimationFrame(this.processFrame);
          return;
        }
      }

      // Call detectForVideo — wrapped to prevent Next.js dev overlay from catching init errors
      let result: any;
      try { result = this.faceLandmarker!.detectForVideo(this.videoElement!, now); } catch { /* skip */ }

      if (result?.faceLandmarks && result.faceLandmarks.length > 0) {
        const landmarks = result.faceLandmarks[0];
        this.handleFaceDetected(landmarks, now);
      } else {
        this.handleNoFace(now);
      }
    }

    this.animationFrameId = requestAnimationFrame(this.processFrame);
  }

  /**
   * Handle frame where face is detected
   */
  private handleFaceDetected(
    landmarks: { x: number; y: number; z: number }[],
    timestamp: number
  ): void {
    // If was absent, emit absence_end
    if (this.isAbsent) {
      this.isAbsent = false;
      const duration = timestamp - this.absenceStartTime;
      this.emit({
        type: 'absence_end',
        data: { duration },
        timestamp,
      });
    }

    this.lastFaceSeenTime = timestamp;

    // Handle calibration
    if (this.isCalibrating) {
      this.handleCalibrationFrame(landmarks, timestamp);
      return;
    }

    // Extract signals (landmarks are compatible with our Landmark type)
    const signals = extractSignals(
      landmarks as { x: number; y: number; z?: number }[],
      this.blinkDetector,
      this.calibration,
      timestamp
    );

    // Compute composite score
    const rawScore = computeCompositeScore(
      signals,
      this.calibration,
      this.config
    );
    const smoothedScore = this.smoother.update(rawScore);

    const focusScore: FocusScore = {
      raw: rawScore,
      smoothed: smoothedScore,
      signals,
      timestamp,
    };

    this.latestScore = focusScore;

    this.emit({
      type: 'focus_update',
      data: focusScore,
      timestamp,
    });
  }

  /**
   * Handle frame where no face is detected
   */
  private handleNoFace(timestamp: number): void {
    const timeSinceLastFace = timestamp - this.lastFaceSeenTime;

    // Immediately reset smoother to 0 when no face — no slow decay
    this.smoother.update(0);
    this.smoother.update(0);

    if (!this.isAbsent && timeSinceLastFace > this.config.absenceThresholdMs) {
      this.isAbsent = true;
      this.absenceStartTime = timestamp;
      this.emit({
        type: 'absence_start',
        data: {
          raw: 0,
          smoothed: 0,
          signals: {
            ear: 0,
            gazeDeviation: 0,
            blinkRate: 0,
            facePresent: false,
            headPoseDeviation: 0,
          },
          timestamp,
        },
        timestamp,
      });
    }

    // Force score to 0 — no face means no focus
    const noFaceScore: FocusScore = {
      raw: 0,
      smoothed: 0,
      signals: {
        ear: 0,
        gazeDeviation: 0,
        blinkRate: 0,
        facePresent: false,
        headPoseDeviation: 0,
      },
      timestamp,
    };
    this.latestScore = noFaceScore;

    this.emit({
      type: 'focus_update',
      data: noFaceScore,
      timestamp,
    });
  }

  /**
   * Collect calibration samples
   */
  private handleCalibrationFrame(
    landmarks: { x: number; y: number; z: number }[],
    timestamp: number
  ): void {
    const lm = landmarks as { x: number; y: number; z?: number }[];
    const ear = computeAverageEar(lm);
    const gazeDeviation = computeGazeDeviation(lm, null);

    // Approximate gaze center position from iris landmarks
    let gazeX = 0.5;
    let gazeY = 0.5;
    if (landmarks.length >= 478) {
      // Use iris centers relative to eye boundaries
      const rightIris = landmarks[468];
      const leftIris = landmarks[473];
      const rightEyeLeft = landmarks[33];
      const rightEyeRight = landmarks[133];
      const leftEyeLeft = landmarks[362];
      const leftEyeRight = landmarks[263];

      const rightSpan = Math.hypot(
        rightEyeRight.x - rightEyeLeft.x,
        rightEyeRight.y - rightEyeLeft.y
      );
      const leftSpan = Math.hypot(
        leftEyeRight.x - leftEyeLeft.x,
        leftEyeRight.y - leftEyeLeft.y
      );

      if (rightSpan > 0 && leftSpan > 0) {
        const rightRatio =
          Math.hypot(rightIris.x - rightEyeLeft.x, rightIris.y - rightEyeLeft.y) /
          rightSpan;
        const leftRatio =
          Math.hypot(leftIris.x - leftEyeLeft.x, leftIris.y - leftEyeLeft.y) /
          leftSpan;
        gazeX = (rightRatio + leftRatio) / 2;
      }
    }

    this.calibrationSamples.push({ ear, gazeX, gazeY });

    // Check if calibration is complete
    if (timestamp - this.calibrationStartTime >= this.calibrationDurationMs) {
      this.finishCalibration(timestamp);
    }
  }

  /**
   * Finalize calibration from collected samples
   */
  private finishCalibration(timestamp: number): void {
    this.isCalibrating = false;

    if (this.calibrationSamples.length === 0) return;

    const avgEar =
      this.calibrationSamples.reduce((sum, s) => sum + s.ear, 0) /
      this.calibrationSamples.length;
    const avgGazeX =
      this.calibrationSamples.reduce((sum, s) => sum + s.gazeX, 0) /
      this.calibrationSamples.length;
    const avgGazeY =
      this.calibrationSamples.reduce((sum, s) => sum + s.gazeY, 0) /
      this.calibrationSamples.length;

    this.calibration = {
      baselineEar: avgEar,
      baselineGazeCenter: { x: avgGazeX, y: avgGazeY },
      baselineBlinkRate: 17, // Will be refined over session
      isCalibrated: true,
    };

    this.emit({
      type: 'calibration_complete',
      data: this.calibration,
      timestamp,
    });
  }

  /**
   * Subscribe to focus events
   */
  on(callback: FocusEventCallback): () => void {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== callback);
    };
  }

  /**
   * Emit event to all listeners
   */
  private emit(event: FocusEvent): void {
    this.listeners.forEach((listener) => listener(event));
  }

  /**
   * Get the latest focus score
   */
  getLatestScore(): FocusScore | null {
    return this.latestScore;
  }

  /**
   * Get calibration data
   */
  getCalibration(): CalibrationData | null {
    return this.calibration;
  }

  /**
   * Check if engine is currently running
   */
  getIsRunning(): boolean {
    return this.isRunning;
  }

  /**
   * Check if currently in calibration phase
   */
  getIsCalibrating(): boolean {
    return this.isCalibrating;
  }

  /**
   * Check if student is currently absent
   */
  getIsAbsent(): boolean {
    return this.isAbsent;
  }
}
