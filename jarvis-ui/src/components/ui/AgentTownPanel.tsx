import React from 'react';
import { Panel } from './Panel';
import AgentTownGame from '../core/AgentTownGame';

interface AgentTownPanelProps {
  agentStates: Record<string, 'idle' | 'busy'>;
}

export const AgentTownPanel: React.FC<AgentTownPanelProps> = ({ agentStates }) => {
  return (
    <Panel 
      title="AGENT TOWN" 
      headerRight={<span className="text-[9px] bg-red-900/30 px-2 py-0.5 rounded text-red-500">READY</span>}
      className="h-[350px]"
      contentClassName="relative"
    >
      {/* Top inner nav */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 flex items-center gap-1 z-20">
        {['agents', 'visual hub', 'gesture'].map((tab, idx) => (
          <button 
            key={tab} 
            className={`px-3 py-1 text-[10px] uppercase tracking-widest rounded ${idx === 0 ? 'bg-red-900/40 text-red-400 border border-red-900/50' : 'text-red-900/50 hover:text-red-500'}`}
          >
            {tab}
          </button>
        ))}
      </div>
      
      <div className="absolute top-2 right-2 z-20 flex gap-1">
        <button className="w-6 h-6 rounded bg-gray-900/80 border border-red-900/30 text-red-700 hover:text-red-500 flex items-center justify-center">⟳</button>
      </div>

      <div className="w-full h-full relative z-10 pt-8">
        <AgentTownGame agentStates={agentStates} />
      </div>

      {/* Bottom overlay elements specific to the image */}
      <div className="absolute bottom-3 left-3 z-20 flex gap-2">
        <div className="bg-gray-900/80 border border-gray-800 rounded px-2 py-1 flex items-center gap-2">
          <div className="w-4 h-4 bg-gray-700 rounded-full flex items-center justify-center text-[8px] text-white">N</div>
          <span className="text-[10px] text-gray-400">Llama</span>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded px-2 py-1 flex items-center gap-2">
          <span className="text-[10px] text-gray-500">No model yet</span>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded px-2 py-1 flex items-center gap-2">
          <span className="text-[10px] text-gray-500 font-bold">CTX</span>
          <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div className="w-1/4 h-full bg-cyan-600"></div>
          </div>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded px-2 py-1 flex items-center gap-2 text-[10px] text-gray-400">
          👤 4/7 seat
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded px-2 py-1 flex items-center gap-2 text-[10px] text-gray-400">
          ⚡ 0/4 busy
        </div>
      </div>

      <div className="absolute bottom-3 right-3 z-20">
        <button className="bg-orange-900/30 hover:bg-orange-800/40 border border-orange-800/50 text-orange-400 px-3 py-1.5 rounded flex items-center gap-2 text-[10px] font-bold tracking-widest shadow-[0_0_10px_rgba(249,115,22,0.1)]">
          ✉ CHAT
        </button>
      </div>
    </Panel>
  );
};
