import React from 'react';
import { Terminal, BrainCircuit, BookOpen, Eye } from 'lucide-react';

interface AgentDeskProps {
  name: string;
  role: string;
  icon: React.ReactNode;
  status: 'idle' | 'busy' | 'offline';
}

const AgentDesk: React.FC<AgentDeskProps> = ({ name, role, icon, status }) => {
  const statusColor = 
    status === 'idle' ? 'bg-cyan-500 shadow-[0_0_8px_#06b6d4]' :
    status === 'busy' ? 'bg-red-500 shadow-[0_0_12px_#ef4444] animate-pulse' :
    'bg-gray-600';

  return (
    <div className="relative group p-4 bg-gray-950/80 border border-red-900/30 rounded-lg flex flex-col items-center justify-center gap-2 hover:bg-gray-900 hover:border-red-700/50 transition-all duration-300">
      <div className={`absolute top-2 right-2 w-2 h-2 rounded-full ${statusColor}`} />
      <div className="p-3 bg-gray-900 rounded-full border border-red-900/50 group-hover:border-cyan-700/50 transition-colors text-red-500 group-hover:text-cyan-400">
        {icon}
      </div>
      <div className="text-center">
        <h4 className="text-xs font-bold text-gray-200 tracking-widest">{name}</h4>
        <p className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">{role}</p>
      </div>
    </div>
  );
};

const AgentTown: React.FC = () => {
  return (
    <div className="w-full h-full p-4 bg-[#050505] rounded-b-lg overflow-hidden flex items-center justify-center">
      <div className="grid grid-cols-2 gap-4 w-full h-full">
        <AgentDesk name="DEV" role="System Builder" icon={<Terminal size={20} />} status="idle" />
        <AgentDesk name="SYS" role="Orchestrator" icon={<BrainCircuit size={20} />} status="busy" />
        <AgentDesk name="ACAD" role="Research" icon={<BookOpen size={20} />} status="offline" />
        <AgentDesk name="OBS" role="Oversight" icon={<Eye size={20} />} status="idle" />
      </div>
    </div>
  );
};

export default AgentTown;
