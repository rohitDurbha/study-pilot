'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AdaptiveStateMachine, TransitionEvent } from './state-machine';
import type { LearningState, StateMachineConfig } from './types';

export interface UseAdaptiveEngineReturn {
  currentState: LearningState;
  currentContentType: string;
  timeInState: number;
  transitionHistory: TransitionEvent[];

  // Feed focus data
  updateFocus: (score: number) => void;

  // Manual controls
  forceState: (state: LearningState) => void;
  handleDistractionReturn: () => void;
  endBreak: () => void;
}

export function useAdaptiveEngine(
  config?: Partial<StateMachineConfig>,
  onTransition?: (event: TransitionEvent) => void
): UseAdaptiveEngineReturn {
  const machineRef = useRef<AdaptiveStateMachine | null>(null);
  const [currentState, setCurrentState] = useState<LearningState>('READING');
  const [currentContentType, setCurrentContentType] = useState('text');
  const [timeInState, setTimeInState] = useState(0);
  const [transitionHistory, setTransitionHistory] = useState<TransitionEvent[]>([]);
  const onTransitionRef = useRef(onTransition);
  onTransitionRef.current = onTransition;

  // Initialize machine once
  useEffect(() => {
    const machine = new AdaptiveStateMachine(config);
    machineRef.current = machine;

    const unsubscribe = machine.onTransition((event) => {
      setCurrentState(event.toState);
      setCurrentContentType(event.contentType);
      setTransitionHistory(prev => [...prev, event]);
      onTransitionRef.current?.(event);
    });

    // Update time in state every second
    const timer = setInterval(() => {
      if (machineRef.current) {
        setTimeInState(machineRef.current.getTimeInCurrentState());
      }
    }, 1000);

    return () => {
      unsubscribe();
      clearInterval(timer);
    };
  }, []);

  const updateFocus = useCallback((score: number) => {
    machineRef.current?.update(score);
  }, []);

  const forceState = useCallback((state: LearningState) => {
    machineRef.current?.forceTransition(state, 'user_request');
  }, []);

  const handleDistractionReturn = useCallback(() => {
    machineRef.current?.handleDistractionReturn();
  }, []);

  const endBreak = useCallback(() => {
    machineRef.current?.endBreak();
  }, []);

  return {
    currentState,
    currentContentType,
    timeInState,
    transitionHistory,
    updateFocus,
    forceState,
    handleDistractionReturn,
    endBreak,
  };
}
