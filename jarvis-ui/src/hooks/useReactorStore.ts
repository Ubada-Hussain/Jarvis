import { useState, useEffect } from 'react';

export type ReactorState = 'idle' | 'processing' | 'complete';

interface ReactorStoreData {
  status: ReactorState;
  percent: number;
  taskLabel: string;
  success: boolean;
}

let store: ReactorStoreData = {
  status: 'idle',
  percent: 0,
  taskLabel: 'STANDBY',
  success: true,
};

const listeners = new Set<() => void>();

const emit = () => {
  listeners.forEach((l) => l());
};

// Actions to mutate state
export const setReactorLoad = (percent: number, taskLabel: string) => {
  store = { ...store, status: 'processing', percent, taskLabel };
  emit();
};

export const setReactorComplete = (success: boolean) => {
  store = { ...store, status: 'complete', percent: 100, success };
  emit();
};

export const setReactorIdle = () => {
  store = { ...store, status: 'idle', percent: 0, taskLabel: 'STANDBY', success: true };
  emit();
};

// Hook for components to subscribe
export const useReactorStore = () => {
  const [state, setState] = useState<ReactorStoreData>(store);

  useEffect(() => {
    const handleUpdate = () => setState(store);
    listeners.add(handleUpdate);
    return () => {
      listeners.delete(handleUpdate);
    };
  }, []);

  return state;
};
