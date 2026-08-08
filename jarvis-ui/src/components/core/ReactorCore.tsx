import React from 'react';
import { useReactorStore } from '../../hooks/useReactorStore';

const ReactorCore: React.FC = () => {
  const { status, percent, taskLabel, success } = useReactorStore();

  const isProcessing = status === 'processing';
  const isComplete = status === 'complete';

  // Determine core color based on state
  let coreColor = 'rgba(34, 211, 238, 0.2)'; // Cyan dim (idle)
  let glowColor = 'rgba(34, 211, 238, 0.1)';
  let textColor = 'text-cyan-500';
  
  if (isProcessing) {
    coreColor = 'rgba(34, 211, 238, 0.8)'; // Bright cyan
    glowColor = 'rgba(34, 211, 238, 0.5)';
  } else if (isComplete) {
    if (success) {
      coreColor = 'rgba(34, 197, 94, 0.9)'; // Bright green
      glowColor = 'rgba(34, 197, 94, 0.6)';
      textColor = 'text-green-500';
    } else {
      coreColor = 'rgba(239, 68, 68, 0.9)'; // Bright red
      glowColor = 'rgba(239, 68, 68, 0.6)';
      textColor = 'text-red-500';
    }
  }

  const radius = 120;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percent / 100) * circumference;

  return (
    <div className="w-full h-full bg-[#050505] flex items-center justify-center relative overflow-hidden rounded-lg border border-red-900/50 shadow-[0_0_15px_rgba(220,38,38,0.1)]">
      
      {/* Background grid/overlay for that tech feel */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/10 via-[#050505] to-[#050505] opacity-50"></div>
      
      <div className="relative w-[400px] h-[400px] flex items-center justify-center">
        
        {/* OUTER RING (Slow rotation, dotted) */}
        <svg className={`absolute w-[360px] h-[360px] ${isProcessing ? 'animate-[spin_4s_linear_infinite]' : 'animate-[spin_20s_linear_infinite]'}`}>
          <circle 
            cx="180" cy="180" r="170" 
            fill="none" 
            stroke="rgba(34, 211, 238, 0.3)" 
            strokeWidth="2" 
            strokeDasharray="4 8" 
          />
        </svg>

        {/* MIDDLE RING (Segments, reverse rotation) */}
        <svg className={`absolute w-[320px] h-[320px] ${isProcessing ? 'animate-[spin_3s_linear_infinite_reverse]' : 'animate-[spin_15s_linear_infinite_reverse]'}`}>
          <circle 
            cx="160" cy="160" r="150" 
            fill="none" 
            stroke="rgba(34, 211, 238, 0.4)" 
            strokeWidth="12" 
            strokeDasharray="40 20" 
          />
        </svg>

        {/* LOAD GAUGE RING (Fills based on percent) */}
        <svg className="absolute w-[260px] h-[260px] -rotate-90">
          {/* Track */}
          <circle 
            cx="130" cy="130" r={radius} 
            fill="none" 
            stroke="rgba(34, 211, 238, 0.1)" 
            strokeWidth="8" 
          />
          {/* Progress */}
          <circle 
            cx="130" cy="130" r={radius} 
            fill="none" 
            stroke={isComplete ? (success ? '#22c55e' : '#ef4444') : '#22d3ee'}
            strokeWidth="8" 
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-300 ease-linear"
          />
        </svg>

        {/* INNER CORE GLOW */}
        <div 
          className={`absolute w-32 h-32 rounded-full flex items-center justify-center transition-all duration-500`}
          style={{
            backgroundColor: coreColor,
            boxShadow: `0 0 40px 10px ${glowColor}, inset 0 0 20px rgba(255,255,255,0.5)`,
            transform: isProcessing ? 'scale(1.05)' : 'scale(1)'
          }}
        >
          {/* CORE PULSE INNER */}
          <div className="w-16 h-16 rounded-full bg-white opacity-40 blur-sm"></div>
        </div>

        {/* TEXT OVERLAY */}
        <div className="absolute z-10 flex flex-col items-center pointer-events-none mt-40">
          <div className={`text-2xl font-bold tracking-[0.2em] mb-1 drop-shadow-[0_0_8px_rgba(0,0,0,1)] ${textColor}`}>
            {percent.toFixed(0)}%
          </div>
          <div className="text-[10px] uppercase tracking-widest text-cyan-300 bg-black/60 px-3 py-1 rounded border border-cyan-900/50 backdrop-blur-sm">
            {taskLabel}
          </div>
        </div>

      </div>

      {/* Satellite Readouts (Static for now, can be wired to active agents) */}
      <div className="absolute left-8 top-1/2 -translate-y-1/2 flex flex-col gap-8">
         <SatelliteNode label="WEB.SEARCH" active={taskLabel.includes('search')} />
         <SatelliteNode label="MEM.BANK" active={taskLabel.includes('memory')} />
         <SatelliteNode label="SYS.OPS" active={taskLabel.includes('system') || taskLabel.includes('file')} />
      </div>

    </div>
  );
};

const SatelliteNode: React.FC<{ label: string, active: boolean }> = ({ label, active }) => (
  <div className="flex items-center gap-3">
    <div className={`w-3 h-3 rounded-full border border-cyan-500 flex items-center justify-center ${active ? 'bg-cyan-500 shadow-[0_0_10px_#22d3ee]' : 'bg-transparent'}`}>
       {active && <div className="w-1 h-1 bg-white rounded-full animate-pulse" />}
    </div>
    <div className={`text-[9px] uppercase tracking-[0.2em] ${active ? 'text-cyan-300 font-bold' : 'text-cyan-800'}`}>
      {label}
    </div>
    {active && (
       <div className="w-12 h-[1px] bg-cyan-500/50 ml-2 relative">
          <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-1 bg-cyan-400 rotate-45" />
       </div>
    )}
  </div>
);

export default ReactorCore;
