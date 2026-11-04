export type LearningState =
  | 'READING'     // Text-based content
  | 'VISUAL'      // Mind maps, diagrams
  | 'RECALL'      // Flashcards
  | 'TESTING'     // Quizzes
  | 'GAME'        // Mini-games
  | 'BREAK'       // Suggested break
  | 'RECOVERY';   // Post-distraction recap

// Maps learning states to content types used by the frontend
export const STATE_TO_CONTENT_TYPE: Record<LearningState, string> = {
  READING: 'text',
  VISUAL: 'mindmap',
  RECALL: 'flipcard',
  TESTING: 'quiz',
  GAME: 'mini-game',
  BREAK: 'break',
  RECOVERY: 'recovery',
};

export const CONTENT_TYPE_TO_STATE: Record<string, LearningState> = {
  text: 'READING',
  mindmap: 'VISUAL',
  flipcard: 'RECALL',
  quiz: 'TESTING',
  'mini-game': 'GAME',
  react: 'GAME',
};

export interface TransitionRecord {
  fromState: LearningState;
  toState: LearningState;
  focusBefore: number; // avg focus 30s before transition
  focusAfter: number;  // avg focus 30s after transition
  delta: number;       // focusAfter - focusBefore
  timestamp: number;
}

export interface StateMachineConfig {
  // Minimum time (ms) in any state before auto-transition
  minDwellTimeMs: number;

  // Cooldown (ms) after a transition before another can happen
  transitionCooldownMs: number;

  // Max auto-transitions per 30-minute window
  maxTransitionsPerWindow: number;

  // Focus thresholds
  lowFocusThreshold: number;      // Below this for sustainedDuration = trigger
  sustainedLowDurationMs: number; // How long focus must be low to trigger

  // Break suggestion
  breakSuggestAfterMs: number;    // Suggest break after this much continuous study
  veryLowFocusThreshold: number;  // Below this = suggest break immediately
}

export const DEFAULT_STATE_MACHINE_CONFIG: StateMachineConfig = {
  minDwellTimeMs: 30_000,           // 30 seconds minimum in any state
  transitionCooldownMs: 20_000,     // 20 seconds between transitions
  maxTransitionsPerWindow: 8,       // Max 8 switches per 30 min
  lowFocusThreshold: 40,            // Focus below 40 = low
  sustainedLowDurationMs: 10_000,   // Low for 10 seconds = trigger
  breakSuggestAfterMs: 25 * 60_000, // Suggest break after 25 min
  veryLowFocusThreshold: 10,        // Below 10 = immediate break suggestion
};
