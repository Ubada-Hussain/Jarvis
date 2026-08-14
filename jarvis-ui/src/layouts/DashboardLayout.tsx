import React, { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import CoreAssistant from '../components/core/CoreAssistant';
import { AgentTownPanel } from '../components/ui/AgentTownPanel';
import { DeveloperModePanel } from '../components/ui/DeveloperModePanel';
import { useJarvis } from '../hooks/useJarvis';
import SecurityPopup from '../components/core/SecurityPopup';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, isLoading, status, checkConnection, isListeningContinuous, toggleContinuousListening, pendingAction, respondToApproval, systemState, agentStates } = useJarvis();
  const [input, setInput] = useState('');
  const [devMode, setDevMode] = useState(false);
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

  // Map backend agent states (working/idle) to UI states (busy/idle)
  const uiAgentStates: Record<string, 'busy'|'idle'> = {};
  for (const [key, val] of Object.entries(agentStates)) {
    uiAgentStates[key] = val === 'working' ? 'busy' : (val as 'idle');
  }

  const getSystemTime = () => {
    const d = new Date();
    return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}:${String(d.getUTCSeconds()).padStart(2, '0')} UTC`;
  };

  return (
    <>
      <SecurityPopup pendingAction={pendingAction} onRespond={respondToApproval} />
      
      {/* TopAppBar */}
      <header className="bg-background/80 backdrop-blur-md text-secondary font-headline-md text-headline-md w-full top-0 sticky border-b border-secondary/20 shadow-[0_0_15px_#44e2f833] flex justify-between items-center px-margin-desktop py-4 z-50">
        <div className="font-display-lg text-display-lg tracking-widest bg-gradient-to-r from-primary to-[#ff3b4e] bg-clip-text text-transparent drop-shadow-[0_0_15px_#ffb3b233]">
          JARVIS
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 border border-tertiary/30 px-3 py-1 rounded bg-tertiary/10">
            {status === 'online' && <div className="w-2 h-2 rounded-full bg-tertiary amber-dot"></div>}
            <span className="font-label-caps text-label-caps text-tertiary">
              {status === 'online' ? 'BACKEND ONLINE' : status === 'offline' ? 'BACKEND OFFLINE' : 'CONNECTING...'}
            </span>
          </div>
          <div className="flex gap-4">
            <span 
              onClick={() => setDevMode(!devMode)}
              className={`material-symbols-outlined hover:bg-secondary/10 hover:text-secondary transition-all scale-95 duration-150 p-2 rounded cursor-pointer ${devMode ? 'text-primary bg-primary/10' : 'text-secondary'}`}
              title="Toggle Developer Mode"
            >
              bug_report
            </span>
            <span className="material-symbols-outlined text-secondary hover:bg-secondary/10 hover:text-secondary transition-all scale-95 duration-150 p-2 rounded cursor-pointer">sensors</span>
            <span className="material-symbols-outlined text-secondary hover:bg-secondary/10 hover:text-secondary transition-all scale-95 duration-150 p-2 rounded cursor-pointer">settings_input_component</span>
          </div>
        </div>
      </header>

      <div className="flex-grow flex flex-col md:flex-row gap-gutter">
        {/* Left Column */}
        <div className="w-full md:w-1/2 flex flex-col gap-gutter">
          <CoreAssistant systemState={systemState} />
          {devMode ? (
            <DeveloperModePanel />
          ) : (
            <AgentTownPanel agentStates={uiAgentStates} />
          )}
        </div>

        {/* Right Column: TERMINAL Section */}
        <div className="w-full md:w-1/2 flex flex-col fui-panel fui-border rounded relative overflow-hidden min-h-[600px]">
          <div className="absolute top-0 left-0 border-b border-r border-secondary/20 px-2 py-1 bg-secondary/10 font-label-caps text-label-caps text-secondary z-10 w-full flex justify-between">
            <span>SEC-03 // TERMINAL_LOG</span>
            <span className="text-on-surface-variant/60">SYS_TIME: {getSystemTime()}</span>
          </div>

          {/* Chat Log Area */}
          <div className="flex-grow mt-10 p-4 overflow-y-auto flex flex-col gap-4 font-body-md text-body-md font-mono">
            <div className="text-secondary/60 text-terminal-sm font-terminal-sm border-l-2 border-secondary/30 pl-2">
              [{getSystemTime()}] SYSTEM: Connection established. Initializing core protocols... DONE.
            </div>

            {messages.map((msg) => (
              <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} w-full`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`font-terminal-sm text-terminal-sm ${msg.role === 'user' ? 'text-on-surface-variant/70' : 'text-primary'}`}>
                    {msg.role === 'user' ? 'USER' : msg.role === 'system' ? '[SYS.CORE] SYSTEM' : '[SYS.CORE] JARVIS'}
                  </span>
                </div>
                <div className={`${msg.role === 'user' ? 'bg-surface-container-high border-surface-variant' : 'bg-primary/5 border-primary/20 shadow-[0_0_10px_#ffb3b211]'} border px-4 py-2 rounded text-on-surface max-w-[80%]`}>
                  {msg.content}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex flex-col items-start w-full">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-terminal-sm text-terminal-sm text-primary">[SYS.CORE] SYSTEM</span>
                </div>
                <div className="bg-primary/5 border border-primary/20 px-4 py-2 rounded text-on-surface max-w-[80%] shadow-[0_0_10px_#ffb3b211]">
                  Processing command...
                </div>
              </div>
            )}
            
            <div className="text-secondary/60 text-terminal-sm font-terminal-sm border-l-2 border-secondary/30 pl-2 flex items-center gap-2 mt-2">
              SYSTEM: Awaiting input <span className="animate-pulse font-bold">_</span>
            </div>
            <div ref={terminalEndRef} />
          </div>

          {/* Bottom Dock: Input Area */}
          <div className="border-t border-secondary/20 p-4 bg-background/50 backdrop-blur-md flex-shrink-0">
            <div className="flex items-center gap-3">
              <button
                onClick={toggleRecording}
                disabled={isLoading}
                className={`w-10 h-10 rounded-full border border-secondary/50 flex items-center justify-center bg-secondary/10 text-secondary hover:bg-secondary/20 hover:shadow-[0_0_10px_#44e2f833] transition-all flex-shrink-0 ${isListeningContinuous ? 'bg-secondary/30 shadow-[0_0_10px_#44e2f833]' : ''}`}
                title="Toggle Voice Input"
              >
                <span className="material-symbols-outlined text-[20px]">mic</span>
              </button>
              
              <div className="w-24 h-10 border border-secondary/20 rounded bg-surface-container-lowest/50 flex items-center justify-center overflow-hidden flex-shrink-0 relative waveform">
                 {Array.from({ length: 20 }).map((_, i) => (
                   <span key={i} className={`w-[2px] mx-[1px] bg-secondary opacity-70 ${systemState === 'listening' || systemState === 'speaking' ? 'active' : ''}`} style={{ animationDelay: `${Math.random() * 1.1}s`, height: systemState === 'idle' ? '6px' : undefined }} />
                 ))}
              </div>
              
              <div className="flex-grow relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  placeholder={isListeningContinuous ? 'Listening... (Speak or type)' : isLoading ? 'Awaiting response...' : 'Enter command or speak to JARVIS...'}
                  autoComplete="off"
                  spellCheck={false}
                  className="w-full bg-transparent border-0 border-b border-secondary/30 focus:border-secondary focus:ring-0 text-on-surface font-body-md text-body-md font-mono placeholder:text-on-surface-variant/40 px-2 py-2 pb-1 transition-colors"
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 text-secondary/50 font-terminal-sm text-terminal-sm pointer-events-none">
                  [ENTER]
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default DashboardLayout;
