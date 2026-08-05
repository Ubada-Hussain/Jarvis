import React from 'react';
import CoreAssistant from '../components/core/CoreAssistant';

const DashboardLayout: React.FC = () => {
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

        {/* Top Right: Terminal & Output Module */}
        <div className="col-span-4 row-span-12 bg-gray-900 border border-red-900 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.2)] relative flex flex-col">
           <div className="absolute top-0 left-0 bg-red-950 px-3 py-1 text-xs tracking-widest border-b border-r border-red-900 rounded-br-lg z-10">
            TERMINAL.OUT
          </div>
          <div className="flex-grow p-4 mt-8 overflow-y-auto text-red-400 text-sm">
            <p className="mb-2">&gt;&nbsp;JARVIS SYSTEM INITIALIZED...</p>
            <p className="mb-2">&gt;&nbsp;LOADING MODULES...</p>
            <p className="mb-2 text-cyan-400">&gt;&nbsp;CREW_AI AGENTS ONLINE.</p>
          </div>
          <div className="border-t border-red-900 p-2 flex items-center bg-gray-950 rounded-b-lg">
            <span className="text-red-500 mr-2">{">"}</span>
            <input 
              type="text" 
              className="w-full bg-transparent outline-none text-red-400 placeholder-red-800"
              placeholder="Awaiting command..."
            />
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
