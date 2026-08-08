import React, { KeyboardEvent } from 'react';
import { Panel } from './Panel';

interface StonicAIPanelProps {
  input: string;
  setInput: (val: string) => void;
  handleSend: () => void;
  isLoading: boolean;
  isListeningContinuous: boolean;
  toggleRecording: () => void;
}

export const StonicAIPanel: React.FC<StonicAIPanelProps> = ({
  input, setInput, handleSend, isLoading, isListeningContinuous, toggleRecording
}) => {
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <Panel 
      title="STONIC AI" 
      headerRight={<span className="text-[10px] text-red-900/50">0.0s ⋁</span>}
      className="h-[300px]"
    >
      <div className="flex flex-col h-full bg-[#050505]">
        
        {/* Mock Tool Execution Area */}
        <div className="flex-grow p-4 overflow-y-auto text-xs font-mono relative">
          
          <div className="flex items-center gap-2 mb-4">
            <span className="text-red-500 font-bold">#</span>
            <span className="text-red-300 tracking-wider">write_file</span>
          </div>

          <div className="mb-4">
            <span className="text-red-900/60 text-[10px] tracking-widest uppercase">INPUT</span>
            <div className="mt-1 text-gray-500 bg-[#0a0a0a] border border-gray-900/50 rounded p-2 text-[10px] break-all">
              {`{ "content": "==============================================\\n STONIC DATA RESEARCH REPORT... }`}
            </div>
          </div>

          <div className="mb-4">
            <span className="text-red-900/60 text-[10px] tracking-widest uppercase">OUTPUT</span>
            <div className="mt-1 text-gray-500 bg-[#0a0a0a] border border-gray-900/50 rounded p-2 text-[10px] break-all">
              {`{ "bytes_written": 2698, "dirs_created": true, "lint": { "status": "skipped", "message": "No linter for .txt files" } }`}
            </div>
          </div>
          
          {/* Mock New Messages badge */}
          <div className="sticky bottom-0 left-0 right-0 flex justify-center pb-2 pointer-events-none">
             <div className="bg-[#111] border border-gray-800 text-gray-400 text-[10px] px-3 py-1 rounded-full flex items-center gap-1 shadow-lg pointer-events-auto cursor-pointer hover:bg-[#1a1a1a]">
               ↓ New messages
             </div>
          </div>
        </div>

        {/* Chat Input Area */}
        <div className="p-3 border-t border-red-900/20 bg-[#080808]">
          <div className="relative flex items-center bg-[#111] border border-gray-800 rounded-lg p-1 px-2 focus-within:border-red-900/50 transition-colors">
            
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              className="flex-grow bg-transparent outline-none text-gray-300 text-xs placeholder-gray-600 px-2 h-8"
              placeholder={isListeningContinuous ? 'Listening...' : 'Type instruction or / command for Hermes...'}
              autoComplete="off"
              spellCheck={false}
            />

            <div className="flex items-center gap-1 ml-2">
              <button 
                onClick={toggleRecording}
                className={`w-6 h-6 flex items-center justify-center rounded transition-colors ${isListeningContinuous ? 'text-cyan-400 bg-cyan-900/20' : 'text-gray-500 hover:text-gray-300'}`}
              >
                🎤
              </button>
              <button className="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-gray-300">
                📎
              </button>
              <button 
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="w-6 h-6 flex items-center justify-center rounded bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200 disabled:opacity-50"
              >
                ↑
              </button>
            </div>
          </div>
        </div>

      </div>
    </Panel>
  );
};
