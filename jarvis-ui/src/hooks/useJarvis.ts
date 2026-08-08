/**
 * useJarvis.ts
 * -----------
 * Custom React hook that manages communication with the JARVIS FastAPI backend.
 * 
 * Usage:
 *   const { messages, sendMessage, status } = useJarvis();
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { visualizer } from '../utils/audioVisualizer';
import { setReactorLoad, setReactorComplete, setReactorIdle } from './useReactorStore';

export type MessageRole = 'user' | 'jarvis' | 'system';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

export type ConnectionStatus = 'unknown' | 'online' | 'offline';
export type SystemState = 'idle' | 'listening' | 'thinking' | 'speaking';

const API_BASE = '/api';  // Proxied to http://localhost:8000 by Vite
const WS_BASE = `ws://${window.location.host}/api/ws/state`;
const WS_AGENTS = `ws://${window.location.host}/api/ws/agents`;

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
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus>('unknown');
  const [systemState, setSystemState] = useState<SystemState>('idle');
  const [agentStates, setAgentStates] = useState<Record<string, string>>({
    DEV: 'idle', SYS: 'idle', ACAD: 'idle', OBS: 'idle'
  });

  const addMessage = useCallback((role: MessageRole, content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
  }, []);

  const [isListeningContinuous, setIsListeningContinuous] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  // Poll for approval status
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/approval/status`);
        if (res.ok) {
          const data = await res.json();
          setPendingAction(data.pending_action);
        }
      } catch (err) {
        // silently ignore network errors during polling
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket for System State
  useEffect(() => {
    let ws: WebSocket;
    const connectWS = () => {
      ws = new WebSocket(WS_BASE);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'state_sync') {
            setSystemState(data.state as SystemState);
          } else if (data.type === 'wake_word') {
            // Wake word detected by backend! Turn on mic!
            setIsListeningContinuous(true);
          }
        } catch {
          // Fallback for old plain-text state
          const newState = event.data as SystemState;
          if (['idle', 'listening', 'thinking', 'speaking'].includes(newState)) {
            setSystemState(newState);
          }
        }
      };
      ws.onclose = () => {
        setTimeout(connectWS, 2000); // Reconnect loop
      };
    };
    connectWS();
    return () => {
      if (ws) ws.close();
    };
  }, []);

  // WebSocket for Agent Status (REAL parallel agent tracking)
  useEffect(() => {
    let ws: WebSocket;
    const connectAgentWS = () => {
      ws = new WebSocket(WS_AGENTS);
      ws.onmessage = (event) => {
        try {
          const states = JSON.parse(event.data);
          setAgentStates(states);
        } catch { /* ignore parse errors */ }
      };
      ws.onclose = () => {
        setTimeout(connectAgentWS, 2000);
      };
    };
    connectAgentWS();
    return () => {
      if (ws) ws.close();
    };
  }, []);

  const respondToApproval = useCallback(async (approved: boolean) => {
    try {
      await fetch(`${API_BASE}/approval/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved })
      });
      setPendingAction(null);
    } catch (err) {
      console.error("Failed to respond to approval:", err);
    }
  }, []);

  // Initialize SpeechRecognition
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech recognition not supported in this browser.");
      return;
    }
    
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    
    recognition.onresult = (event: any) => {
      const current = event.resultIndex;
      const transcript = event.results[current][0].transcript;
      if (transcript.trim()) {
        const text = transcript.trim();
        
        // INTERCEPT FOR APPROVAL
        // Since we can't reliably read pendingAction from closure inside this event 
        // without complex ref wrapping, we handle it inside sendMessage.
        sendMessage(text);
      }
    };
    
    recognition.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);
    };
    
    recognitionRef.current = recognition;
  }, []);

  // Handle continuous listening auto-restart
  useEffect(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;

    const handleEnd = () => {
      if (isListeningContinuous) {
        try {
          recognition.start();
        } catch (e) {
          // Ignore restart errors
        }
      }
    };

    recognition.onend = handleEnd;

    if (isListeningContinuous) {
      try {
        visualizer.startMic();
        recognition.start();
      } catch (e) {
        console.error("Error starting recognition:", e);
      }
    } else {
      try {
        visualizer.stopMic();
        recognition.stop();
      } catch (e) {
        // ignore
      }
    }

    return () => {
      recognition.onend = null;
    };
  }, [isListeningContinuous]);

  const toggleContinuousListening = useCallback(() => {
    if (!recognitionRef.current) {
      addMessage('system', '[VOICE ERROR] Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }
    setIsListeningContinuous(prev => !prev);
  }, [addMessage]);

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

  // Use a ref to access the latest pendingAction inside sendMessage without adding it to dependencies
  const pendingActionRef = useRef(pendingAction);
  useEffect(() => {
    pendingActionRef.current = pendingAction;
  }, [pendingAction]);

  /**
   * Sends a message to the MasterAgent via POST /api/chat
   * and appends the response to the message log.
   */
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    // INTERCEPT: If an action is pending, treat input as approval response
    const currentPending = pendingActionRef.current;
    if (currentPending) {
       const lower = text.toLowerCase();
       if (lower.includes('yes') || lower.includes('proceed') || lower.includes('y')) {
          addMessage('user', `(Confirmed) ${text}`);
          respondToApproval(true);
       } else if (lower.includes('no') || lower.includes('cancel') || lower.includes('n')) {
          addMessage('user', `(Cancelled) ${text}`);
          respondToApproval(false);
       } else {
          addMessage('system', 'Please answer Yes or No to the pending security request.');
       }
       return;
    }

    addMessage('user', text);
    setIsLoading(true);

    let pct = 0;
    setReactorLoad(pct, 'RUNNING: process_command');
    const loadInterval = setInterval(() => {
      pct += Math.random() * 10;
      if (pct > 90) pct = 90 + Math.random() * 5;
      setReactorLoad(pct, 'RUNNING: process_command');
    }, 400);

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
        clearInterval(loadInterval);
        setReactorComplete(false);
        setTimeout(() => setReactorIdle(), 2000);
        return;
      }

      const data = await res.json();
      addMessage('jarvis', data.response);
      
      // If the backend generated an audio URL, play it!
      if (data.audio_url) {
        setIsSpeaking(true);
        const audio = new Audio(`${API_BASE.replace('/api', '')}${data.audio_url}`);
        audio.crossOrigin = "anonymous";
        audio.play().then(() => {
          visualizer.connectTTS(audio);
        }).catch(e => {
          console.error("Audio play failed:", e);
          setIsSpeaking(false);
        });
        audio.onended = () => {
          setIsSpeaking(false);
          setSystemState('idle'); // Backend sets to speaking, we revert to idle when audio finishes
        };
      } else {
        setSystemState('idle'); // Revert to idle if no audio
      }
      
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error';
      addMessage('system', `[CONNECTION ERROR] ${msg} — Is the JARVIS backend running?`);
      setStatus('offline');
      clearInterval(loadInterval);
      setReactorComplete(false);
      setTimeout(() => setReactorIdle(), 2000);
    } finally {
      setIsLoading(false);
      clearInterval(loadInterval);
      setReactorComplete(true);
      setTimeout(() => setReactorIdle(), 2000);
    }
  }, [isLoading, addMessage, respondToApproval]);

  /**
   * Sends an audio blob to the STT endpoint for transcription,
   * then sends the transcribed text to the chat.
   */
  const sendAudio = useCallback(async (audioBlob: Blob) => {
    if (isLoading) return;
    setIsLoading(true);
    addMessage('system', '> Processing voice input...');
    
    try {
      const formData = new FormData();
      formData.append('file', audioBlob, 'voice_input.webm');

      const res = await fetch(`${API_BASE}/transcribe`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Transcription failed' }));
        addMessage('system', `[VOICE ERROR] ${err.detail}`);
        setIsLoading(false);
        return;
      }

      const data = await res.json();
      const transcribedText = data.text.trim();
      
      setIsLoading(false); // reset so sendMessage can run
      if (transcribedText) {
        // Send the transcribed text as a normal chat message!
        sendMessage(transcribedText);
      } else {
        addMessage('system', '[VOICE ERROR] Could not understand audio.');
      }
    } catch (err: unknown) {
      addMessage('system', '[VOICE ERROR] Network error while transcribing.');
      setIsLoading(false);
    }
  }, [isLoading, addMessage, sendMessage]);

  const jarvisState = 
    isSpeaking ? 'speaking' :
    isLoading ? 'thinking' :
    isListeningContinuous ? 'listening' :
    'idle';

  return { 
    messages, 
    sendMessage, 
    sendAudio, 
    isLoading, 
    status, 
    checkConnection, 
    isListeningContinuous, 
    toggleContinuousListening, 
    pendingAction, 
    respondToApproval,
    systemState,
    jarvisState,
    agentStates
  };
}
