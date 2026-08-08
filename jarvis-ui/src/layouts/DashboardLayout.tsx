import React, { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import ReactorCore from '../components/core/ReactorCore';
import AgentTownGame from '../components/core/AgentTownGame';
import { useJarvis } from '../hooks/useJarvis';

import SecurityPopup from '../components/core/SecurityPopup';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, isLoading, status, checkConnection, isListeningContinuous, toggleContinuousListening, pendingAction, respondToApproval } = useJarvis();
  const [input, setInput] = useState('');
  const terminalEndRef = useRef<HTMLDivElement>(null);

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

  const toggleRecording = () => {
    toggleContinuousListening();
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
    <div className="h-screen w-screen bg-[#050505] text-red-500 font-mono p-4 box-border overflow-hidden relative">
      <SecurityPopup pendingAction={pendingAction} onRespond={respondToApproval} />
      <div className="flex h-full w-full gap-4">

        {/* Left Half: JARVIS Reactor Core */}
        <div className="w-1/2 h-full relative">
          <ReactorCore />
        </div>

        {/* Right Half: Stacked Panels */}
        <div className="w-1/2 h-full flex flex-col gap-4 min-h-0">
          
          {/* Top: Terminal & Output Module (Takes remaining space) */}
          <div className="flex-grow bg-[#0a0a0a] border border-red-900/50 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.1)] relative flex flex-col min-h-0">
            {/* Panel header */}
            <div className="flex items-center justify-between bg-[#0a0a0a] px-3 py-1 rounded-t-lg border-b border-red-900/50 shrink-0">
              <div className="flex items-center gap-2">
                 <div className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
                 <span className="text-[10px] font-bold tracking-widest uppercase text-red-500">TERMINAL.OUT</span>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <div className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`} />
                <span className={status === 'online' ? 'text-green-400' : status === 'offline' ? 'text-red-400' : 'text-yellow-400'}>
                  {statusLabel}
                </span>
              </div>
            </div>

            {/* Message log */}
            <div className="flex-grow p-4 overflow-y-auto text-sm space-y-2 bg-[#050505] rounded-b-lg font-mono">
              {messages.map((msg) => (
                <div key={msg.id} className="mb-2">
                  {msg.role === 'user' && (
                    <div>
                      <span className="text-cyan-700 tracking-wider text-[10px] block">INPUT</span>
                      <p className="text-cyan-400/90 text-xs">{msg.content}</p>
                    </div>
                  )}
                  {msg.role === 'jarvis' && (
                    <div className="mt-2">
                      <span className="text-red-700 tracking-wider text-[10px] block">OUTPUT</span>
                      <p className="text-red-400/90 whitespace-pre-wrap text-xs">{msg.content}</p>
                    </div>
                  )}
                  {msg.role === 'system' && (
                    <div className="mt-1">
                      <span className="text-yellow-700/50 tracking-wider text-[10px] block">SYSTEM</span>
                      <p className="text-yellow-600/50 italic text-xs">{msg.content}</p>
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <p className="text-red-700 animate-pulse text-xs">&gt; Processing command...</p>
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>

          {/* Middle: Agent Town Module */}
          <div className="h-[220px] shrink-0 bg-[#0a0a0a] border border-red-900/50 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.1)] relative flex flex-col">
            <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10 z-20 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
              AGENT.TOWN
            </div>
            <AgentTownGame agentStates={agentStates} />
          </div>

          {/* Bottom: Voice/Chat Interface */}
          <div className="h-[120px] shrink-0 bg-[#0a0a0a] border border-red-900/50 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.1)] relative flex flex-col items-center justify-center p-4">
            <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
              COM.LINK
            </div>
            
            <div className="w-full flex w-full gap-2 items-end justify-center h-full pt-4">
              <button
                id="jarvis-mic-btn-main"
                onClick={toggleRecording}
                disabled={isLoading}
                className={`transition-all rounded-full w-14 h-14 flex items-center justify-center flex-shrink-0 text-xl border border-red-900/50 bg-[#050505]
                  ${isListeningContinuous 
                    ? 'border-cyan-500 text-cyan-400 animate-pulse shadow-[0_0_15px_rgba(34,211,238,0.3)]' 
                    : 'text-red-500 hover:text-red-300 hover:bg-red-950 transition-colors'}`}
                title="Continuous Voice Input"
              >
                🎤
              </button>
              
              <div className="flex-grow flex flex-col h-14">
                <input
                  id="jarvis-command-input-main"
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  className="w-full h-full bg-[#050505] border border-red-900/50 rounded outline-none text-red-400 placeholder-red-900/70 disabled:opacity-50 px-3 text-sm focus:border-red-700 transition-colors"
                  placeholder={isListeningContinuous ? 'Listening... (Speak or type)' : isLoading ? 'Awaiting response...' : 'Type instruction...'}
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>

              <button
                id="jarvis-send-btn-main"
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="h-14 px-4 bg-[#050505] border border-red-900/50 rounded text-red-500 hover:text-red-400 hover:bg-red-950 disabled:opacity-30 transition-colors text-[10px] font-bold tracking-widest uppercase shadow-[0_0_10px_rgba(220,38,38,0.05)]"
              >
                SEND
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default DashboardLayout;
