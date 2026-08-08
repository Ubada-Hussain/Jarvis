import React from 'react';

interface AgentTownGameProps {
  agentStates: Record<string, string>;
}

const AgentTownGame: React.FC<AgentTownGameProps> = ({ agentStates }) => {
  const getAgentStyle = (id: string) => {
    const isBusy = agentStates[id] === 'busy' || agentStates[id] === 'working';
    
    // Default positions (corners)
    let top = '14px';
    let left = '20px';
    
    if (id === 'DEV') { top = '14px'; left = '20px'; }
    if (id === 'SYS') { top = '14px'; left = 'calc(100% - 60px)'; }
    if (id === 'ACAD') { top = 'calc(100% - 40px)'; left = '20px'; }
    if (id === 'OBS') { top = 'calc(100% - 40px)'; left = 'calc(100% - 60px)'; }

    // If busy, move near the TASK CORE center
    if (isBusy) {
       // Add slight random offset based on ID so they don't exactly overlap
       const offset = id === 'DEV' ? -10 : id === 'SYS' ? 10 : id === 'ACAD' ? -20 : 20;
       top = `calc(50% + ${offset}px)`;
       left = `calc(50% + ${offset/2}px)`;
    }

    return { top, left };
  };

  const getAgentColorClass = (id: string) => {
    switch(id) {
      case 'DEV': return 'text-jarvis-cyan';
      case 'SYS': return 'text-jarvis-crimson';
      case 'ACAD': return 'text-[#39d98a]'; // Green
      case 'OBS': return 'text-[#b585ff]'; // Purple
      default: return 'text-white';
    }
  };

  return (
    <div className="w-full h-full p-4 pt-10 flex flex-col relative overflow-hidden">
      
      {/* Grid Background */}
      <div 
        className="absolute inset-0 z-0 opacity-50"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          backgroundPosition: 'center center'
        }}
      />

      <div className="relative w-full flex-grow border border-white/5 bg-black/20 z-10">
        
        {/* TASK CORE */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-11 border border-jarvis-crimson bg-black/50 flex items-center justify-center text-[8px] tracking-[1px] text-jarvis-crimson text-center leading-snug z-10 shadow-[0_0_10px_rgba(255,59,78,0.2)]">
          TASK<br/>CORE
        </div>

        {/* AGENTS */}
        {Object.keys(agentStates).map(id => {
          const isBusy = agentStates[id] === 'busy' || agentStates[id] === 'working';
          return (
            <div 
              key={id} 
              className={`absolute flex flex-col items-center gap-1.5 transition-all duration-1000 ease-[cubic-bezier(.4,0,.2,1)] z-20 ${getAgentColorClass(id)}`}
              style={getAgentStyle(id)}
            >
              <div className="w-[22px] h-[22px] rounded-full bg-current shadow-[0_0_14px_currentColor] opacity-90" />
              <div className={`text-[10px] tracking-[1.5px] font-mono whitespace-nowrap ${isBusy ? 'text-jarvis-amber' : 'text-jarvis-text-dim'}`}>
                {id} {isBusy ? '[AWAY]' : ''}
              </div>
            </div>
          );
        })}

      </div>
    </div>
  );
};

export default AgentTownGame;
