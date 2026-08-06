import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

interface SidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children?: React.ReactNode;
}

const SidePanel: React.FC<SidePanelProps> = ({ isOpen, onClose, title, children }) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="absolute top-0 right-0 w-80 h-full bg-gray-950/90 backdrop-blur-xl border-l border-red-900/50 shadow-[-10px_0_30px_rgba(220,38,38,0.1)] z-40 flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-red-900/30 bg-gray-900/50">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
              <h2 className="text-cyan-400 font-bold tracking-widest uppercase text-sm">
                {title}
              </h2>
            </div>
            <button 
              onClick={onClose}
              className="p-1 text-gray-500 hover:text-red-400 transition-colors rounded-full hover:bg-red-900/20"
            >
              <X size={18} />
            </button>
          </div>
          
          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 text-gray-300 text-sm">
            {children ? children : (
              <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-4">
                <div className="w-12 h-12 rounded-full border border-gray-700 border-t-cyan-700 animate-spin" />
                <p className="tracking-widest text-xs uppercase">Initializing {title}...</p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SidePanel;
