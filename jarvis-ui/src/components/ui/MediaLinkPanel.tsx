import React from 'react';
import { Panel } from './Panel';

export const MediaLinkPanel: React.FC = () => {
  return (
    <Panel 
      title="MEDIA LINK" 
      headerRight={<span className="text-red-900 tracking-widest text-[10px]">...</span>}
      className="h-[250px]"
      contentClassName="p-3"
    >
      <div className="w-full h-full rounded-lg border border-red-900/20 bg-[#050505] flex flex-col items-center justify-center relative shadow-[inset_0_0_20px_rgba(220,38,38,0.02)]">
        <div className="px-4 py-1.5 border border-red-900/30 rounded-full text-red-900/50 text-[10px] tracking-[0.2em] uppercase bg-red-900/5 backdrop-blur-sm">
          SYSTEM OFFLINE
        </div>
        
        <div className="absolute bottom-3 right-3 flex gap-2">
          <div className="w-6 h-6 rounded border border-red-900/30 flex items-center justify-center text-red-900/40 text-xs">
            📷
          </div>
          <div className="w-6 h-6 rounded border border-red-900/30 flex items-center justify-center text-red-900/40 text-xs">
            🎤
          </div>
        </div>
      </div>
    </Panel>
  );
};
