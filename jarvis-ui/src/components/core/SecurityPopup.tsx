import React from 'react';

interface SecurityPopupProps {
  pendingAction: string | null;
  onRespond: (approved: boolean) => void;
}

const SecurityPopup: React.FC<SecurityPopupProps> = ({ pendingAction, onRespond }) => {
  if (!pendingAction) return null;

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 w-[500px] max-w-[90vw] animate-in fade-in slide-in-from-top-4 duration-300">
      <div className="bg-red-950 border-2 border-red-500 rounded-lg shadow-[0_0_30px_rgba(239,68,68,0.4)] overflow-hidden font-mono">
        {/* Header */}
        <div className="bg-red-600 text-white px-4 py-2 flex items-center gap-2 font-bold tracking-widest text-sm">
          <span className="animate-pulse">⚠️</span>
          SECURITY ALERT: Action Requires Approval
        </div>
        
        {/* Body */}
        <div className="p-4 bg-gray-900 text-red-50">
          <p className="text-sm text-red-300 mb-2">JARVIS wants to execute a critical action:</p>
          <div className="bg-black/50 p-3 rounded border border-red-900 text-red-400 font-bold mb-4 font-sans">
            "{pendingAction}"
          </div>
          
          <p className="text-xs text-red-400/80 mb-4 text-center">
            Do you want to proceed? (Auto-cancels in 30s)<br/>
            <span className="opacity-70">You can also say or type "Yes" / "No"</span>
          </p>
          
          {/* Buttons */}
          <div className="flex gap-4">
            <button
              onClick={() => onRespond(false)}
              className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 text-red-400 border border-red-900 hover:border-red-500 rounded transition-colors font-bold text-sm tracking-wider"
            >
              NO, CANCEL
            </button>
            <button
              onClick={() => onRespond(true)}
              className="flex-1 py-2 bg-red-700 hover:bg-red-600 text-white border border-red-500 hover:border-red-400 rounded transition-colors font-bold text-sm tracking-wider shadow-[0_0_10px_rgba(239,68,68,0.5)]"
            >
              YES, PROCEED
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SecurityPopup;
