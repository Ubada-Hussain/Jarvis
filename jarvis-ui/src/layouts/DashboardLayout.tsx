import React, { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import CoreAssistant from '../components/core/CoreAssistant';
import AgentTownGame from '../components/core/AgentTownGame';
import { useJarvis } from '../hooks/useJarvis';

import SecurityPopup from '../components/core/SecurityPopup';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, isLoading, status, checkConnection, isListeningContinuous, toggleContinuousListening, pendingAction, respondToApproval, systemState } = useJarvis();
  const [input, setInput] = useState('');
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

  const statusColor = status === 'online' ? 'bg-jarvis-cyan shadow-[0_0_8px_#2dd4ea]' : status === 'offline' ? 'bg-jarvis-crimson' : 'bg-jarvis-amber';
  const statusLabel = status === 'online' ? 'BACKEND ONLINE' : status === 'offline' ? 'BACKEND OFFLINE' : 'CONNECTING...';

  const agentStates = {
    'DEV': isLoading ? 'busy' : 'idle',
    'SYS': isLoading ? 'busy' : 'idle',
    'ACAD': 'idle',
    'OBS': status === 'online' ? 'busy' : 'idle'
  };

  return (
    <div className="h-screen w-screen bg-jarvis-bg text-jarvis-text font-mono p-4 box-border overflow-hidden relative" style={{
      backgroundImage: `radial-gradient(ellipse 900px 500px at 30% 20%, rgba(122,22,34,0.35), transparent 60%), radial-gradient(ellipse 700px 500px at 80% 80%, rgba(45,212,234,0.06), transparent 60%)`
    }}>
      <SecurityPopup pendingAction={pendingAction} onRespond={respondToApproval} />
      
      {/* Topbar */}
      <div className="flex justify-between items-center px-4 py-2 mb-4 border-b border-jarvis-panel-border">
        <div className="font-display font-bold text-xl tracking-[6px] text-jarvis-text">J<span className="text-jarvis-crimson">A</span>RVIS</div>
        <div className="flex items-center gap-2 text-[11px] tracking-[2px] text-jarvis-cyan border border-jarvis-cyan/30 px-3 py-1 rounded-full">
          <div className={`w-2 h-2 rounded-full ${statusColor} ${status === 'online' ? 'animate-pulse' : ''}`}></div>
          {statusLabel}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 h-[calc(100%-60px)] max-w-[1400px] mx-auto w-full">

        {/* Left Column */}
        <div className="flex flex-col gap-4 h-full min-h-0">
          {/* SYS.CORE */}
          <div className="flex-grow relative bg-jarvis-panel bg-gradient-to-b from-white/[0.015] to-transparent border border-jarvis-panel-border rounded overflow-hidden">
            <div className="absolute top-0 left-0 bg-jarvis-crimson/90 text-[#0a0a0a] font-semibold text-[11px] tracking-[2px] px-3 py-1 z-10">SYS.CORE</div>
            <CoreAssistant systemState={systemState} />
          </div>

          {/* AGENT.TOWN */}
          <div className="h-[260px] shrink-0 relative bg-jarvis-panel bg-gradient-to-b from-white/[0.015] to-transparent border border-jarvis-panel-border rounded overflow-hidden">
            <div className="absolute top-0 left-0 bg-jarvis-crimson/90 text-[#0a0a0a] font-semibold text-[11px] tracking-[2px] px-3 py-1 z-10">AGENT.TOWN</div>
            <AgentTownGame agentStates={agentStates} />
          </div>
        </div>

        {/* Right Column: Chat/Voice */}
        <div className="flex flex-col h-full bg-jarvis-panel bg-gradient-to-b from-white/[0.015] to-transparent border border-jarvis-panel-border rounded relative min-h-0">
          <div className="absolute top-0 left-0 bg-jarvis-crimson/90 text-[#0a0a0a] font-semibold text-[11px] tracking-[2px] px-3 py-1 z-10">TERMINAL.OUT</div>
          
          <div className="flex-grow overflow-y-auto p-4 pt-10 flex flex-col gap-3">
            {messages.map((msg) => (
              <div key={msg.id} className={`max-w-[88%] text-[12.5px] leading-[1.5] ${msg.role === 'user' ? 'self-end text-jarvis-cyan text-right' : 'self-start text-jarvis-text'}`}>
                <span className="text-[9px] tracking-[2px] opacity-55 block mb-1">
                  {msg.role === 'user' ? 'YOU' : msg.role === 'jarvis' ? 'JARVIS' : 'SYSTEM'}
                </span>
                {msg.content}
              </div>
            ))}
            {isLoading && (
              <div className="self-start text-jarvis-crimson max-w-[88%] text-[12.5px] leading-[1.5]">
                <span className="text-[9px] tracking-[2px] opacity-55 block mb-1">SYSTEM</span>
                &gt; Processing command...
              </div>
            )}
            <div ref={terminalEndRef} />
          </div>

          <div className="border-t border-jarvis-panel-border p-4">
            {/* Waveform placeholder */}
            <div className="flex items-end gap-[3px] h-[34px] mb-3">
               {Array.from({ length: 28 }).map((_, i) => (
                 <span key={i} className={`w-[3px] bg-jarvis-crimson rounded-sm opacity-75 ${systemState === 'listening' || systemState === 'speaking' ? 'animate-[wave_1.1s_ease-in-out_infinite]' : 'h-[6px]'}`} style={{ animationDelay: `${Math.random() * 1.1}s` }} />
               ))}
            </div>
            
            <div className="flex gap-2 items-center">
              <button
                onClick={toggleRecording}
                disabled={isLoading}
                className={`w-[38px] h-[38px] rounded-full border border-jarvis-crimson flex items-center justify-center shrink-0 transition-all text-sm
                  ${isListeningContinuous 
                    ? 'bg-jarvis-crimson text-[#0a0a0a]' 
                    : 'bg-jarvis-crimson/10 text-jarvis-crimson hover:bg-jarvis-crimson hover:text-[#0a0a0a]'}`}
              >
                ●
              </button>
              
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                className="flex-grow bg-white/5 border border-white/10 text-jarvis-text font-mono text-xs px-3 py-2 rounded-sm focus:outline-none focus:border-jarvis-crimson"
                placeholder={isListeningContinuous ? 'Listening... (Speak or type)' : isLoading ? 'Awaiting response...' : 'Enter command or speak to JARVIS...'}
                autoComplete="off"
                spellCheck={false}
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="hidden" // Hiding the button, relying on Enter key for minimalist look like the mockup, but could keep it.
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
