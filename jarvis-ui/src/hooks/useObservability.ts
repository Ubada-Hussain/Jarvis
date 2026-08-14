import { useState, useEffect, useCallback } from 'react';

const WS_OBSERVABILITY = `ws://${window.location.host}/api/ws/observability`;

export interface ObservabilityEvent {
  event_id: string;
  timestamp: string;
  task_id: string | null;
  event_type: string;
  agent: string | null;
  tool: string | null;
  status: string | null;
  duration_ms: number | null;
  model: string | null;
  risk_level: string | null;
  permission_status: string | null;
  verification_status: string | null;
  error: string | null;
  metadata: Record<string, any>;
}

export interface RuntimeState {
  task_id: string | null;
  user_request: string;
  status: string;
  current_step: string;
  active_agent: string | null;
  active_tool: string | null;
  started_at: string | null;
  elapsed_time: number;
  model: string | null;
  risk_level: string | null;
  permission_status: string | null;
  verification_status: string | null;
  last_error: string | null;
}

export function useObservability() {
  const [runtimeState, setRuntimeState] = useState<RuntimeState | null>(null);
  const [events, setEvents] = useState<ObservabilityEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    let ws: WebSocket;
    try {
      ws = new WebSocket(WS_OBSERVABILITY);
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'observability_update') {
          if (payload.state) {
            setRuntimeState(payload.state);
          }
          if (payload.event) {
            setEvents(prev => [payload.event, ...prev].slice(0, 100)); // Keep last 100
          }
        }
      };

      ws.onopen = () => setIsConnected(true);
      
      ws.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 3000); // Reconnect
      };
    } catch (e) {
      console.error("Failed to connect to observability WS", e);
    }
    
    return () => {
      if (ws) ws.close();
    };
  }, []);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  return { runtimeState, events, isConnected };
}
