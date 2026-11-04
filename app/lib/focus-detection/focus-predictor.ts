/**
 * Focus Predictor — uses linear regression on recent focus history
 * to predict where focus will be in 30 seconds.
 *
 * If predicted focus drops below threshold, triggers proactive intervention
 * BEFORE the student actually loses focus.
 */

export interface FocusPrediction {
  currentScore: number;
  predictedScore: number;    // Where focus will be in 30 seconds
  slope: number;             // Rate of change per second (negative = declining)
  confidence: number;        // 0-1 how confident the prediction is
  isDecliningSteadily: boolean;
  willDropBelow: number | null; // Seconds until it drops below threshold, or null
}

/**
 * Linear regression on focus scores to compute slope.
 */
function linearRegression(points: { x: number; y: number }[]): { slope: number; intercept: number; r2: number } {
  const n = points.length;
  if (n < 2) return { slope: 0, intercept: points[0]?.y ?? 0, r2: 0 };

  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (const p of points) {
    sumX += p.x;
    sumY += p.y;
    sumXY += p.x * p.y;
    sumX2 += p.x * p.x;
    sumY2 += p.y * p.y;
  }

  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n, r2: 0 };

  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;

  // R-squared (coefficient of determination)
  const yMean = sumY / n;
  let ssRes = 0, ssTot = 0;
  for (const p of points) {
    const predicted = slope * p.x + intercept;
    ssRes += (p.y - predicted) ** 2;
    ssTot += (p.y - yMean) ** 2;
  }
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;

  return { slope, intercept, r2 };
}

/**
 * Predict focus score based on recent history.
 *
 * @param history Array of { score, timestamp } from the last ~60 seconds
 * @param predictionWindowSec How far ahead to predict (default 30s)
 * @param lowThreshold What counts as "low focus" (default 35)
 */
export function predictFocus(
  history: { score: number; timestamp: number }[],
  predictionWindowSec: number = 30,
  lowThreshold: number = 35,
): FocusPrediction {
  if (history.length < 5) {
    const current = history[history.length - 1]?.score ?? 50;
    return {
      currentScore: current,
      predictedScore: current,
      slope: 0,
      confidence: 0,
      isDecliningSteadily: false,
      willDropBelow: null,
    };
  }

  // Use last 30 seconds of data
  const now = Date.now();
  const windowMs = 30_000;
  const recent = history.filter(h => now - h.timestamp < windowMs);

  if (recent.length < 5) {
    const current = history[history.length - 1]?.score ?? 50;
    return {
      currentScore: current,
      predictedScore: current,
      slope: 0,
      confidence: 0,
      isDecliningSteadily: false,
      willDropBelow: null,
    };
  }

  // Normalize timestamps to seconds from start
  const startTime = recent[0].timestamp;
  const points = recent.map(h => ({
    x: (h.timestamp - startTime) / 1000,
    y: h.score,
  }));

  const { slope, intercept, r2 } = linearRegression(points);

  const currentScore = recent[recent.length - 1].score;
  const currentX = (recent[recent.length - 1].timestamp - startTime) / 1000;
  const futureX = currentX + predictionWindowSec;
  const predictedScore = Math.max(0, Math.min(100, slope * futureX + intercept));

  // Confidence based on R² and sample size
  const confidence = Math.min(r2 * (recent.length / 15), 1);

  // Is it declining steadily? (slope negative and R² decent)
  const isDecliningSteadily = slope < -0.5 && r2 > 0.3;

  // When will it drop below threshold?
  let willDropBelow: number | null = null;
  if (slope < 0 && currentScore > lowThreshold) {
    const secondsUntilThreshold = (lowThreshold - (slope * currentX + intercept)) / slope - currentX;
    if (secondsUntilThreshold > 0 && secondsUntilThreshold < 120) {
      willDropBelow = Math.round(secondsUntilThreshold);
    }
  }

  return {
    currentScore,
    predictedScore: Math.round(predictedScore),
    slope: Math.round(slope * 100) / 100,
    confidence: Math.round(confidence * 100) / 100,
    isDecliningSteadily,
    willDropBelow,
  };
}
