import React from 'react';
import { Panel } from './Panel';

export const SatLinkFeedPanel: React.FC = () => {
  return (
    <Panel title="SAT-LINK FEED" className="h-[400px]">
      <div className="relative w-full h-full bg-[#050505] overflow-hidden group">
        {/* Mock Map Background */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/10 via-[#050505] to-[#050505] opacity-50" />
        
        {/* Mock Grid/Lines */}
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(220, 38, 38, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(220, 38, 38, 0.05) 1px, transparent 1px)', backgroundSize: '20px 20px' }} />

        {/* Mock Orange Nodes */}
        <div className="absolute top-[30%] left-[20%] w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_10px_#f97316]" />
        <div className="absolute top-[50%] left-[70%] w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_10px_#f97316]" />
        <div className="absolute top-[70%] left-[40%] w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_10px_#f97316]" />
        
        {/* Red Highlighted Area Mock */}
        <svg className="absolute top-[40%] left-[30%] w-32 h-32 opacity-50 pointer-events-none" viewBox="0 0 100 100">
          <polygon points="50,10 80,40 60,90 20,70" fill="rgba(220,38,38,0.3)" stroke="rgba(220,38,38,0.8)" strokeWidth="1" />
        </svg>

        {/* BETA tag */}
        <div className="absolute top-2 right-2 bg-cyan-900/40 text-cyan-400 border border-cyan-800 text-[9px] px-2 py-0.5 rounded tracking-widest">
          BETA
        </div>

        {/* Update Available Popup */}
        <div className="absolute top-8 left-3 right-3 bg-[#0a1a15] border border-emerald-900/50 rounded-lg p-3 flex items-start gap-3 shadow-[0_4px_15px_rgba(16,185,129,0.1)]">
          <div className="mt-0.5 text-emerald-500 animate-spin-slow">⟳</div>
          <div className="flex-grow">
            <h4 className="text-emerald-400 text-[11px] font-bold tracking-wider mb-1">Update Available</h4>
            <p className="text-emerald-600/70 text-[9px]">A new version is<br/>ready.</p>
          </div>
          <button className="bg-emerald-900/30 hover:bg-emerald-800/40 text-emerald-400 border border-emerald-800/50 rounded px-3 py-1 text-[10px] tracking-widest transition-colors">
            Reload
          </button>
        </div>

        {/* Bottom Nav */}
        <div className="absolute bottom-0 left-0 right-0 h-14 bg-gradient-to-t from-[#020202] to-transparent flex items-end justify-between px-4 pb-2">
          {['Today', 'Map', 'Search', 'Alerts', 'More'].map((tab, i) => (
            <div key={tab} className={`flex flex-col items-center gap-1 cursor-pointer transition-colors ${i === 0 ? 'text-red-500' : 'text-red-900 hover:text-red-700'}`}>
              <div className="text-xs">
                {i === 0 ? '○' : i === 1 ? '◧' : i === 2 ? '⌕' : i === 3 ? '⚠' : '⋯'}
              </div>
              <span className="text-[9px] font-bold tracking-wider">{tab}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
};
