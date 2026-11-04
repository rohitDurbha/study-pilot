/**
 * Activity Tracker — detects tab switches and inactivity.
 *
 * Complements the camera-based focus detection:
 * - Tab hidden (document.visibilityState) = definitely distracted
 * - No scroll/click/key for 60+ seconds while "focused" = probably on phone
 */

export interface ActivityState {
  isTabVisible: boolean;
  lastInteractionAt: number;
  inactiveDurationMs: number;
  isProbablyOnPhone: boolean; // No interaction for 60s+ while face is present
}

type ActivityCallback = (state: ActivityState) => void;

export class ActivityTracker {
  private lastInteractionAt: number = Date.now();
  private isTabVisible: boolean = true;
  private listeners: ActivityCallback[] = [];
  private checkInterval: NodeJS.Timeout | null = null;
  private boundHandlers: {
    visibility: () => void;
    interaction: () => void;
  };

  constructor(private inactivityThresholdMs: number = 60_000) {
    this.boundHandlers = {
      visibility: this.handleVisibilityChange.bind(this),
      interaction: this.handleInteraction.bind(this),
    };
  }

  start(): void {
    document.addEventListener('visibilitychange', this.boundHandlers.visibility);
    document.addEventListener('scroll', this.boundHandlers.interaction, { passive: true });
    document.addEventListener('click', this.boundHandlers.interaction);
    document.addEventListener('keydown', this.boundHandlers.interaction);
    document.addEventListener('mousemove', this.boundHandlers.interaction, { passive: true });
    document.addEventListener('touchstart', this.boundHandlers.interaction, { passive: true });

    // Check inactivity every 5 seconds
    this.checkInterval = setInterval(() => this.checkInactivity(), 5000);
  }

  stop(): void {
    document.removeEventListener('visibilitychange', this.boundHandlers.visibility);
    document.removeEventListener('scroll', this.boundHandlers.interaction);
    document.removeEventListener('click', this.boundHandlers.interaction);
    document.removeEventListener('keydown', this.boundHandlers.interaction);
    document.removeEventListener('mousemove', this.boundHandlers.interaction);
    document.removeEventListener('touchstart', this.boundHandlers.interaction);

    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  private handleVisibilityChange(): void {
    this.isTabVisible = document.visibilityState === 'visible';
    this.emit();
  }

  private handleInteraction(): void {
    this.lastInteractionAt = Date.now();
  }

  private checkInactivity(): void {
    this.emit();
  }

  private emit(): void {
    const now = Date.now();
    const inactiveDuration = now - this.lastInteractionAt;
    const state: ActivityState = {
      isTabVisible: this.isTabVisible,
      lastInteractionAt: this.lastInteractionAt,
      inactiveDurationMs: inactiveDuration,
      isProbablyOnPhone: this.isTabVisible && inactiveDuration > this.inactivityThresholdMs,
    };
    this.listeners.forEach(l => l(state));
  }

  on(callback: ActivityCallback): () => void {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }

  getState(): ActivityState {
    const now = Date.now();
    const inactiveDuration = now - this.lastInteractionAt;
    return {
      isTabVisible: this.isTabVisible,
      lastInteractionAt: this.lastInteractionAt,
      inactiveDurationMs: inactiveDuration,
      isProbablyOnPhone: this.isTabVisible && inactiveDuration > this.inactivityThresholdMs,
    };
  }
}
