import React from 'react';
import AgentTownGame from '../core/AgentTownGame';

interface AgentTownPanelProps {
  agentStates: Record<string, 'idle' | 'busy'>;
}

export const AgentTownPanel: React.FC<AgentTownPanelProps> = ({ agentStates }) => {
  return (
    <div className="fui-panel fui-border rounded relative h-[350px] flex flex-col p-4 overflow-hidden">
      <div className="absolute top-0 left-0 border-b border-r border-secondary/20 px-2 py-1 bg-secondary/10 font-label-caps text-label-caps text-secondary z-10">
        SEC-02 // AGENT TOWN
      </div>
      
      {/* Top inner nav - adapting existing tabs to the new style */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 flex items-center gap-1 z-20">
        {['agents', 'visual hub', 'gesture'].map((tab, idx) => (
          <button 
            key={tab} 
            className={`px-3 py-1 text-[10px] uppercase tracking-widest rounded transition-all ${idx === 0 ? 'bg-secondary/20 text-secondary border border-secondary/50' : 'text-on-surface-variant hover:text-secondary'}`}
          >
            {tab}
          </button>
        ))}
      </div>
      
      <div className="absolute top-2 right-2 z-20 flex gap-1">
        <button className="w-6 h-6 rounded bg-surface-container-high/80 border border-secondary/30 text-secondary hover:bg-secondary/10 flex items-center justify-center transition-all">⟳</button>
      </div>

      <div className="mt-8 flex-grow relative w-full h-full border border-secondary/10 bg-surface-container-lowest/50 rounded overflow-hidden">
        <AgentTownGame agentStates={agentStates} />
      </div>

      {/* Bottom overlay elements specific to the image */}
      <div className="absolute bottom-3 left-3 z-20 flex gap-2 pointer-events-none">
        <div className="bg-surface-container-high/80 border border-surface-variant rounded px-2 py-1 flex items-center gap-2">
          <div className="w-4 h-4 bg-surface-variant rounded-full flex items-center justify-center text-[8px] text-on-surface">N</div>
          <span className="text-[10px] text-on-surface-variant">Llama</span>
        </div>
        <div className="bg-surface-container-high/80 border border-surface-variant rounded px-2 py-1 flex items-center gap-2">
          <span className="text-[10px] text-on-surface-variant">No model yet</span>
        </div>
        <div className="bg-surface-container-high/80 border border-surface-variant rounded px-2 py-1 flex items-center gap-2">
          <span className="text-[10px] text-on-surface-variant font-bold">CTX</span>
          <div className="w-16 h-1.5 bg-surface-variant rounded-full overflow-hidden">
            <div className="w-1/4 h-full bg-secondary"></div>
          </div>
        </div>
        <div className="bg-surface-container-high/80 border border-surface-variant rounded px-2 py-1 flex items-center gap-2 text-[10px] text-on-surface-variant">
          👤 4/7 seat
        </div>
        <div className="bg-surface-container-high/80 border border-surface-variant rounded px-2 py-1 flex items-center gap-2 text-[10px] text-on-surface-variant">
          ⚡ 0/4 busy
        </div>
      </div>

      <div className="absolute bottom-3 right-3 z-20">
        <button className="bg-tertiary/20 hover:bg-tertiary/40 border border-tertiary/50 text-tertiary px-3 py-1.5 rounded flex items-center gap-2 text-[10px] font-bold tracking-widest shadow-[0_0_10px_rgba(255,185,85,0.2)] transition-all">
          ✉ CHAT
        </button>
      </div>
    </div>
  );
};
