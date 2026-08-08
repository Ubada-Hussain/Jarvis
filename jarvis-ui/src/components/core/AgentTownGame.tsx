import React from 'react';

interface AgentTownGameProps {
  agentStates: Record<string, string>;
}

const AgentTownGame: React.FC<AgentTownGameProps> = ({ agentStates }) => {
  const getAgentStyle = (id: string) => {
    const isBusy = agentStates[id] === 'busy' || agentStates[id] === 'working';
    
    // Default positions based on mockup CSS
    let top = '14px';
    let left = 'auto';
    let right = 'auto';
    let bottom = 'auto';
    
    if (id === 'DEV') { top = '14px'; left = '20px'; }
    if (id === 'SYS') { top = '14px'; right = '20px'; }
    if (id === 'ACAD') { bottom = '14px'; top = 'auto'; left = '20px'; }
    if (id === 'OBS') { bottom = '14px'; top = 'auto'; right = '20px'; }

    // If busy, move near the TASK CORE center
    if (isBusy) {
       top = '45%';
       bottom = 'auto';
       
       if (id === 'DEV') { left = '40%'; right = 'auto'; }
       if (id === 'SYS') { right = '40%'; left = 'auto'; }
       if (id === 'ACAD') { top = '55%'; left = '40%'; right = 'auto'; }
       if (id === 'OBS') { top = '55%'; right = '40%'; left = 'auto'; }
    }

    return { top, left, right, bottom };
  };

  const getAgentClass = (id: string) => {
    switch(id) {
      case 'DEV': return 'agent-dev';
      case 'SYS': return 'agent-sys';
      case 'ACAD': return 'agent-acad';
      case 'OBS': return 'agent-obs';
      default: return '';
    }
  };

  return (
    <>
      <div className="town-grid">
        {Object.keys(agentStates).map(id => {
          const isBusy = agentStates[id] === 'busy' || agentStates[id] === 'working';
          return (
            <div 
              key={id} 
              className={`agent ${getAgentClass(id)}`}
              style={getAgentStyle(id)}
            >
              <div className="node" />
              <div className={`name ${isBusy ? 'away' : ''}`}>
                {id} {isBusy ? '[AWAY]' : ''}
              </div>
            </div>
          );
        })}
        <div className="task-core">
          TASK<br/>CORE
        </div>
      </div>
      <button className="assign-btn" style={{ visibility: 'hidden' }}>
        → Assign task to DEV
      </button>
    </>
  );
};

export default AgentTownGame;
