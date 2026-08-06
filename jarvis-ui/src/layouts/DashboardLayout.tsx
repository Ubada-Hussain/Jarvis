import React, { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import CoreAssistant from '../components/core/CoreAssistant';
import AgentTownGame from '../components/core/AgentTownGame';
import WorldMonitor from '../components/core/WorldMonitor';
import { useJarvis } from '../hooks/useJarvis';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, sendAudio, isLoading, status, checkConnection } = useJarvis();
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Auto-scroll terminal to latest message
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Ping backend on mount to show connection status
  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSend();
  };

  const toggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      // Start recording
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          sendAudio(audioBlob);
          // Stop all tracks to release microphone
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        setIsRecording(true);
      } catch (err) {
        console.error("Microphone access denied:", err);
      }
    }
  };

  const statusColor =
    status === 'online' ? 'bg-green-400' :
    status === 'offline' ? 'bg-red-500' :
    'bg-yellow-400';

  const statusLabel =
    status === 'online' ? 'BACKEND ONLINE' :
    status === 'offline' ? 'BACKEND OFFLINE' :
    'CONNECTING...';

  // Basic derived state for AgentTown Phase 2 integration
  // When isLoading is true, make DEV and SYS busy so they move to the center.
  const agentStates = {
    'DEV': isLoading ? 'busy' : 'idle',
    'SYS': isLoading ? 'busy' : 'idle',
    'ACAD': 'idle',
    'OBS': status === 'online' ? 'busy' : 'idle' // OBS constantly monitoring if online
  };

  return (
    <div className="h-screen w-screen bg-gray-950 text-red-500 font-mono p-4 box-border overflow-hidden">
      <div className="grid grid-cols-12 grid-rows-12 gap-4 h-full w-full">

        {/* Top Left: Core Assistant Module (Three.js) */}
        <div className="col-span-8 row-span-7 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative flex flex-col">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            SYS.CORE
          </div>
          <CoreAssistant isLoading={isLoading} />
        </div>

        {/* Right Column: Terminal & Output Module */}
        <div className="col-span-4 row-span-12 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative flex flex-col">
          {/* Panel header */}
          <div className="flex items-center justify-between bg-red-950 px-3 py-1 rounded-t-lg border-b border-red-900">
            <span className="text-xs tracking-widest">TERMINAL.OUT</span>
            <div className="flex items-center gap-2 text-xs">
              <div className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`} />
              <span className={status === 'online' ? 'text-green-400' : status === 'offline' ? 'text-red-400' : 'text-yellow-400'}>
                {statusLabel}
              </span>
            </div>
          </div>

          {/* Message log */}
          <div className="flex-grow p-4 overflow-y-auto text-sm space-y-2">
            {messages.map((msg) => (
              <div key={msg.id}>
                {msg.role === 'user' && (
                  <p className="text-cyan-400">
                    <span className="text-cyan-600 mr-1">YOU &gt;</span>
                    {msg.content}
                  </p>
                )}
                {msg.role === 'jarvis' && (
                  <p className="text-red-400 whitespace-pre-wrap">
                    <span className="text-red-600 mr-1">JARVIS &gt;</span>
                    {msg.content}
                  </p>
                )}
                {msg.role === 'system' && (
                  <p className="text-yellow-600 text-xs">
                    &gt; {msg.content}
                  </p>
                )}
              </div>
            ))}
            {isLoading && (
              <p className="text-red-700 animate-pulse text-xs">&gt; Processing command...</p>
            )}
            <div ref={terminalEndRef} />
          </div>

          {/* Input bar */}
          <div className="border-t border-red-900 p-2 flex items-center bg-gray-950 rounded-b-lg gap-2">
            <span className="text-red-500">&gt;</span>
            <input
              id="jarvis-command-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || isRecording}
              className="w-full bg-transparent outline-none text-red-400 placeholder-red-800 disabled:opacity-50"
              placeholder={isRecording ? 'Listening (click mic to stop)...' : isLoading ? 'Awaiting response...' : 'Enter command...'}
              autoComplete="off"
              spellCheck={false}
            />
            <button
              id="jarvis-mic-btn"
              onClick={toggleRecording}
              disabled={isLoading}
              className={`transition-colors text-xs border border-red-900 px-2 py-1 rounded flex items-center justify-center
                ${isRecording ? 'bg-red-900 text-white animate-pulse' : 'text-red-700 hover:text-red-400 bg-transparent disabled:opacity-30'}`}
              title="Voice Input"
            >
              🎤
            </button>
            <button
              id="jarvis-send-btn"
              onClick={handleSend}
              disabled={isLoading || !input.trim() || isRecording}
              className="text-red-700 hover:text-red-400 disabled:opacity-30 transition-colors text-xs border border-red-900 px-2 py-1 rounded"
            >
              SEND
            </button>
          </div>
        </div>

        {/* Bottom Left: Agent Town Module */}
        <div className="col-span-4 row-span-5 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative flex flex-col">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10 z-20">
            AGENT.TOWN
          </div>
          <AgentTownGame agentStates={agentStates} />
        </div>

        {/* Bottom Middle: World Monitor Module */}
        <div className="col-span-4 row-span-5 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative flex flex-col">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            WORLD.MONITOR
          </div>
          <WorldMonitor messages={messages} isLoading={isLoading} />
        </div>

      </div>
    </div>
  );
};

export default DashboardLayout;
