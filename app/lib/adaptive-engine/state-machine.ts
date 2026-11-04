import type {
  LearningState,
  TransitionRecord,
  StateMachineConfig,
} from './types';
import {
  STATE_TO_CONTENT_TYPE,
  DEFAULT_STATE_MACHINE_CONFIG,
} from './types';

export type TransitionReason =
  | 'focus_low'       // Sustained low focus
  | 'focus_very_low'  // Very low focus → break
  | 'user_request'    // User manually switched
  | 'distraction'     // Student left and came back
  | 'session_start';  // Initial state

export interface TransitionEvent {
  fromState: LearningState;
  toState: LearningState;
  reason: TransitionReason;
  contentType: string; // Frontend content type
  timestamp: number;
}

export class AdaptiveStateMachine {
  private currentState: LearningState = 'READING';
  private stateEnteredAt: number = Date.now();
  private lastTransitionAt: number = 0;
  private transitionsInWindow: number = 0;
  private windowStartAt: number = Date.now();
  private sessionStartAt: number = Date.now();

  // Focus tracking for transition decisions
  private focusHistory: { score: number; timestamp: number }[] = [];
  private lowFocusSince: number | null = null;

  // Effectiveness memory: which transitions improved focus
  private effectivenessMemory: TransitionRecord[] = [];

  private config: StateMachineConfig;
  private listeners: ((event: TransitionEvent) => void)[] = [];

  constructor(config: Partial<StateMachineConfig> = {}) {
    this.config = { ...DEFAULT_STATE_MACHINE_CONFIG, ...config };
  }

  /**
   * Feed a focus score into the state machine. Called every ~2 seconds.
   * Returns a transition event if a state change should happen.
   */
  update(focusScore: number): TransitionEvent | null {
    const now = Date.now();

    // Record focus
    this.focusHistory.push({ score: focusScore, timestamp: now });
    // Keep last 2 minutes of history
    const cutoff = now - 120_000;
    this.focusHistory = this.focusHistory.filter(h => h.timestamp > cutoff);

    // Reset 30-minute transition window
    if (now - this.windowStartAt > 30 * 60_000) {
      this.transitionsInWindow = 0;
      this.windowStartAt = now;
    }

    // Don't auto-transition during BREAK or RECOVERY
    if (this.currentState === 'BREAK' || this.currentState === 'RECOVERY') {
      return null;
    }

    // Check if focus has been very low → suggest break
    if (focusScore < this.config.veryLowFocusThreshold) {
      const timeSinceStart = now - this.sessionStartAt;
      if (timeSinceStart > 5 * 60_000) { // At least 5 min into session
        return this.tryTransition('BREAK', 'focus_very_low', now);
      }
    }

    // Check sustained session time → suggest break
    const lastBreakOrStart = this.sessionStartAt; // TODO: track last break time
    if (now - lastBreakOrStart > this.config.breakSuggestAfterMs) {
      return this.tryTransition('BREAK', 'focus_low', now);
    }

    // Track how long focus has been low
    if (focusScore < this.config.lowFocusThreshold) {
      if (this.lowFocusSince === null) {
        this.lowFocusSince = now;
      }
    } else {
      this.lowFocusSince = null;
    }

    // Check if focus has been sustained low
    if (
      this.lowFocusSince !== null &&
      now - this.lowFocusSince >= this.config.sustainedLowDurationMs
    ) {
      const nextState = this.pickBestTransition();
      if (nextState && nextState !== this.currentState) {
        this.lowFocusSince = null; // Reset
        return this.tryTransition(nextState, 'focus_low', now);
      }
    }

    return null;
  }

  /**
   * Attempt a transition. Returns event if successful, null if blocked.
   */
  private tryTransition(
    toState: LearningState,
    reason: TransitionReason,
    now: number
  ): TransitionEvent | null {
    // Check minimum dwell time
    if (
      reason !== 'user_request' &&
      reason !== 'distraction' &&
      now - this.stateEnteredAt < this.config.minDwellTimeMs
    ) {
      return null;
    }

    // Check cooldown
    if (
      reason !== 'user_request' &&
      now - this.lastTransitionAt < this.config.transitionCooldownMs
    ) {
      return null;
    }

    // Check max transitions
    if (
      reason !== 'user_request' &&
      this.transitionsInWindow >= this.config.maxTransitionsPerWindow
    ) {
      return null;
    }

    // Record focus before transition (avg of last 30s)
    const focusBefore = this.getAverageFocus(30_000);

    const event: TransitionEvent = {
      fromState: this.currentState,
      toState,
      reason,
      contentType: STATE_TO_CONTENT_TYPE[toState],
      timestamp: now,
    };

    // Execute transition
    this.currentState = toState;
    this.stateEnteredAt = now;
    this.lastTransitionAt = now;
    this.transitionsInWindow++;

    // Schedule effectiveness recording (check focus 30s after transition)
    setTimeout(() => {
      const focusAfter = this.getAverageFocus(30_000);
      this.effectivenessMemory.push({
        fromState: event.fromState,
        toState: event.toState,
        focusBefore,
        focusAfter,
        delta: focusAfter - focusBefore,
        timestamp: now,
      });
    }, 30_000);

    // Notify listeners
    this.listeners.forEach(l => l(event));

    return event;
  }

  /**
   * Pick the best next state based on effectiveness memory.
   * Falls back to the escalation path if no memory exists.
   */
  private pickBestTransition(): LearningState | null {
    const current = this.currentState;

    // Escalation path: READING → VISUAL → RECALL → TESTING → GAME
    const escalationPath: LearningState[] = [
      'READING', 'VISUAL', 'RECALL', 'TESTING', 'GAME',
    ];

    // Get candidates (everything except current and BREAK/RECOVERY)
    const candidates = escalationPath.filter(
      s => s !== current && s !== 'BREAK' && s !== 'RECOVERY'
    );

    if (candidates.length === 0) return null;

    // Check effectiveness memory for transitions from current state
    const relevantMemory = this.effectivenessMemory.filter(
      r => r.fromState === current
    );

    if (relevantMemory.length >= 2) {
      // Group by toState and compute average delta
      const avgDeltas = new Map<LearningState, { total: number; count: number }>();
      for (const record of relevantMemory) {
        const existing = avgDeltas.get(record.toState) || { total: 0, count: 0 };
        existing.total += record.delta;
        existing.count += 1;
        avgDeltas.set(record.toState, existing);
      }

      // Pick the transition with best average delta
      let bestState: LearningState | null = null;
      let bestAvg = -Infinity;
      for (const [state, { total, count }] of avgDeltas) {
        if (!candidates.includes(state)) continue;
        const avg = total / count;
        if (avg > bestAvg) {
          bestAvg = avg;
          bestState = state;
        }
      }

      if (bestState) return bestState;
    }

    // Fallback: move one step down the escalation path
    const currentIdx = escalationPath.indexOf(current);
    if (currentIdx >= 0 && currentIdx < escalationPath.length - 1) {
      return escalationPath[currentIdx + 1];
    }

    // Already at the bottom → suggest GAME
    return 'GAME';
  }

  /**
   * Get average focus score over the last N milliseconds.
   */
  private getAverageFocus(windowMs: number): number {
    const cutoff = Date.now() - windowMs;
    const recent = this.focusHistory.filter(h => h.timestamp > cutoff);
    if (recent.length === 0) return 50;
    return Math.round(
      recent.reduce((sum, h) => sum + h.score, 0) / recent.length
    );
  }

  /**
   * Force a state change (user-initiated or distraction recovery).
   */
  forceTransition(toState: LearningState, reason: TransitionReason = 'user_request'): TransitionEvent {
    const event: TransitionEvent = {
      fromState: this.currentState,
      toState,
      reason,
      contentType: STATE_TO_CONTENT_TYPE[toState],
      timestamp: Date.now(),
    };

    this.currentState = toState;
    this.stateEnteredAt = Date.now();

    this.listeners.forEach(l => l(event));
    return event;
  }

  /**
   * Notify the state machine that the student returned from distraction.
   */
  handleDistractionReturn(): TransitionEvent {
    return this.forceTransition('RECOVERY', 'distraction');
  }

  /**
   * End a break — return to READING.
   */
  endBreak(): TransitionEvent {
    this.sessionStartAt = Date.now(); // Reset session timer
    return this.forceTransition('READING', 'user_request');
  }

  /**
   * Get current state.
   */
  getCurrentState(): LearningState {
    return this.currentState;
  }

  /**
   * Get current content type for the frontend.
   */
  getCurrentContentType(): string {
    return STATE_TO_CONTENT_TYPE[this.currentState];
  }

  /**
   * Get effectiveness memory (for analytics).
   */
  getEffectivenessMemory(): TransitionRecord[] {
    return [...this.effectivenessMemory];
  }

  /**
   * Get time spent in current state.
   */
  getTimeInCurrentState(): number {
    return Date.now() - this.stateEnteredAt;
  }

  /**
   * Subscribe to transition events.
   */
  onTransition(callback: (event: TransitionEvent) => void): () => void {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }
}
