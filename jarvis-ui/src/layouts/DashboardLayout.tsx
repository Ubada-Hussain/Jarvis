import React, { useEffect, useRef, useState, KeyboardEvent } from 'react';
import CoreAssistant from '../components/core/CoreAssistant';
import { useJarvis } from '../hooks/useJarvis';

const DashboardLayout: React.FC = () => {
  const { messages, sendMessage, isLoading, status, checkConnection } = useJarvis();
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

  const statusColor =
    status === 'online' ? 'bg-green-400' :
    status === 'offline' ? 'bg-red-500' :
    'bg-yellow-400';

  const statusLabel =
    status === 'online' ? 'BACKEND ONLINE' :
    status === 'offline' ? 'BACKEND OFFLINE' :
    'CONNECTING...';

  return (
    <div className="h-screen w-screen bg-gray-950 text-red-500 font-mono p-4 box-border overflow-hidden">
      <div className="grid grid-cols-12 grid-rows-12 gap-4 h-full w-full">

        {/* Top Left: Core Assistant Module (Three.js) */}
        <div className="col-span-8 row-span-7 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative overflow-hidden flex flex-col">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            SYS.CORE
          </div>
          <CoreAssistant />
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
              disabled={isLoading}
              className="w-full bg-transparent outline-none text-red-400 placeholder-red-800 disabled:opacity-50"
              placeholder={isLoading ? 'Awaiting response...' : 'Enter command...'}
              autoComplete="off"
              spellCheck={false}
            />
            <button
              id="jarvis-send-btn"
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="text-red-700 hover:text-red-400 disabled:opacity-30 transition-colors text-xs border border-red-900 px-2 py-1 rounded"
            >
              SEND
            </button>
          </div>
        </div>

        {/* Bottom Left: Agent Town Module */}
        <div className="col-span-4 row-span-5 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            AGENT.TOWN
          </div>
          <div className="w-full h-full flex items-center justify-center text-red-800">
            [ 2D VISUALIZER OFFLINE ]
          </div>
        </div>

        {/* Bottom Middle: World Monitor Module */}
        <div className="col-span-4 row-span-5 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative">
          <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            WORLD.MONITOR
          </div>
          <div className="w-full h-full flex items-center justify-center text-red-800">
            [ 3D GLOBE OFFLINE ]
          </div>
        </div>

      </div>
    </div>
  );
};

export default DashboardLayout;
