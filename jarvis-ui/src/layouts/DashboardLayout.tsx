import React, { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import CoreAssistant from '../components/core/CoreAssistant';
import AgentTownGame from '../components/core/AgentTownGame';
import { useJarvis } from '../hooks/useJarvis';
import SecurityPopup from '../components/core/SecurityPopup';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, isLoading, status, checkConnection, isListeningContinuous, toggleContinuousListening, pendingAction, respondToApproval, systemState, agentStates } = useJarvis();
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

  const statusLabel = status === 'online' ? 'BACKEND ONLINE' : status === 'offline' ? 'BACKEND OFFLINE' : 'CONNECTING...';

  // Map backend agent states (working/idle) to UI states (busy/idle)
  const uiAgentStates: Record<string, string> = {};
  for (const [key, val] of Object.entries(agentStates)) {
    uiAgentStates[key] = val === 'working' ? 'busy' : val;
  }

  return (
    <>
      <SecurityPopup pendingAction={pendingAction} onRespond={respondToApproval} />
      
      <div className="topbar">
        <div className="wordmark">J<span>A</span>RVIS</div>
        <div className="status-pill">
          {status === 'online' && <div className="dot"></div>}
          {statusLabel}
        </div>
      </div>

      <div className="dashboard-grid">
        
        <div className="panel core-panel">
          <div className="panel-label">SYS.CORE</div>
          <CoreAssistant systemState={systemState} />
        </div>

        <div className="panel town-panel">
          <div className="panel-label">AGENT.TOWN</div>
          <AgentTownGame agentStates={uiAgentStates} />
        </div>

        <div className="panel chat-panel">
          <div className="panel-label">TERMINAL.OUT</div>
          <div className="chat-log">
            {messages.map((msg) => (
              <div key={msg.id} className={`msg ${msg.role === 'user' ? 'user' : msg.role === 'jarvis' ? 'jarvis' : 'system'}`}>
                <span className="tag">{msg.role === 'user' ? 'YOU' : msg.role === 'jarvis' ? 'JARVIS' : 'SYSTEM'}</span>
                {msg.content}
              </div>
            ))}
            {isLoading && (
              <div className="msg system">
                <span className="tag">SYSTEM</span>
                &gt; Processing command...
              </div>
            )}
            <div ref={terminalEndRef} />
          </div>

          <div className="voice-dock">
            <div className="waveform">
               {Array.from({ length: 28 }).map((_, i) => (
                 <span key={i} className={systemState === 'listening' || systemState === 'speaking' ? 'active' : ''} style={{ animationDelay: `${Math.random() * 1.1}s` }} />
               ))}
            </div>
            
            <div className="input-row">
              <button
                onClick={toggleRecording}
                disabled={isLoading}
                className={`mic-btn ${isListeningContinuous ? 'active' : ''}`}
                title="Toggle Voice Input"
              >
                ●
              </button>
              
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                placeholder={isListeningContinuous ? 'Listening... (Speak or type)' : isLoading ? 'Awaiting response...' : 'Enter command or speak to JARVIS...'}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          </div>
        </div>

      </div>
    </>
  );
};

export default DashboardLayout;
