/**
 * useJarvis.ts
 * -----------
 * Custom React hook that manages communication with the JARVIS FastAPI backend.
 * 
 * Usage:
 *   const { messages, sendMessage, status } = useJarvis();
 */

import { useState, useCallback } from 'react';

export type MessageRole = 'user' | 'jarvis' | 'system';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

export type ConnectionStatus = 'unknown' | 'online' | 'offline';

const API_BASE = '/api';  // Proxied to http://localhost:8000 by Vite

export function useJarvis() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'boot',
      role: 'system',
      content: 'JARVIS SYSTEM INITIALIZED... LOADING MODULES...',
      timestamp: new Date(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus>('unknown');

  /** Adds a message to the conversation log. */
  const addMessage = useCallback((role: MessageRole, content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
  }, []);

  /**
   * Pings the backend to verify connectivity.
   * Called on component mount and on user request.
   */
  const checkConnection = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/ping`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        setStatus('online');
        return true;
      }
      setStatus('offline');
      return false;
    } catch {
      setStatus('offline');
      return false;
    }
  }, []);

  /**
   * Sends a message to the MasterAgent via POST /api/chat
   * and appends the response to the message log.
   */
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    addMessage('user', text);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: AbortSignal.timeout(120_000),  // 2-min timeout for LLM responses
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown server error' }));
        addMessage('system', `[ERROR ${res.status}] ${err.detail}`);
        return;
      }

      const data = await res.json();
      addMessage('jarvis', data.response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error';
      addMessage('system', `[CONNECTION ERROR] ${msg} — Is the JARVIS backend running?`);
      setStatus('offline');
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, addMessage]);

  return { messages, sendMessage, isLoading, status, checkConnection };
}
