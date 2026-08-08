import React, { useEffect, useRef } from 'react';
import { Panel } from './Panel';
import type { Message } from '../../hooks/useJarvis';

interface TerminalPanelProps {
  messages: Message[];
  isLoading: boolean;
}

export const TerminalPanel: React.FC<TerminalPanelProps> = ({ messages, isLoading }) => {
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <Panel 
      title="" // Custom header via children since it's just tabs
      hasRedDot={false}
      className="h-[350px]"
    >
      {/* Custom Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-red-900/20 bg-[#0c0c0c]">
        <div className="flex gap-4">
          <button className="text-[10px] text-red-900/50 hover:text-red-500 font-bold tracking-widest uppercase">VOICE</button>
          <button className="text-[10px] text-red-500 border-b border-red-500 pb-1 font-bold tracking-widest uppercase">AGENT</button>
          <button className="text-[10px] text-red-900/50 hover:text-red-500 font-bold tracking-widest uppercase">NOTES</button>
        </div>
        <div className="flex gap-3 text-red-900/50">
          <button className="hover:text-red-500 text-sm">+</button>
          <button className="hover:text-red-500 text-sm">⟳</button>
          <button className="hover:text-red-500 text-sm">⛶</button>
        </div>
      </div>

      {/* Terminal Content */}
      <div className="p-4 h-full overflow-y-auto bg-[#0a0a0a] text-xs font-mono">
        <div className="space-y-4 pb-12">
          {messages.map((msg, idx) => (
            <div key={msg.id} className="opacity-80 hover:opacity-100 transition-opacity">
              {msg.role === 'user' && (
                <div className="mb-1">
                  <span className="text-cyan-700 tracking-wider text-[10px]">INPUT</span>
                  <p className="text-cyan-400/80 mt-1">{msg.content}</p>
                </div>
              )}
              {msg.role === 'jarvis' && (
                <div className="mb-1">
                  <span className="text-red-700 tracking-wider text-[10px]">OUTPUT</span>
                  <div className="text-red-400/80 mt-1 whitespace-pre-wrap leading-relaxed">
                    {msg.content}
                  </div>
                </div>
              )}
              {msg.role === 'system' && (
                <div className="mb-1">
                  <span className="text-yellow-700/50 tracking-wider text-[10px]">SYSTEM</span>
                  <p className="text-yellow-600/50 mt-1 italic">{msg.content}</p>
                </div>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="animate-pulse flex gap-2 items-center text-red-700/50 text-[10px]">
              <div className="w-1.5 h-1.5 bg-red-700/50 rounded-full"></div>
              Processing...
            </div>
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </Panel>
  );
};
