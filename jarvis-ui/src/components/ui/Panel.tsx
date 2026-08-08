import React from 'react';

interface PanelProps {
  title?: string;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  hasRedDot?: boolean;
}

export const Panel: React.FC<PanelProps> = ({ 
  title, 
  headerRight, 
  children, 
  className = '', 
  contentClassName = '',
  hasRedDot = true
}) => {
  return (
    <div className={`flex flex-col bg-[#0a0a0a] border border-red-900/30 rounded-xl overflow-hidden shadow-[0_4px_20px_rgba(220,38,38,0.05)] ${className}`}>
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-red-900/20 bg-[#0c0c0c]">
          <div className="flex items-center gap-2">
            {hasRedDot && (
              <div className="w-1.5 h-1.5 rounded-full bg-red-600 shadow-[0_0_8px_rgba(220,38,38,0.8)] animate-pulse" />
            )}
            <span className="text-[10px] font-bold tracking-[0.2em] text-red-500 uppercase">{title}</span>
          </div>
          {headerRight && (
            <div className="flex items-center gap-2 text-red-700">
              {headerRight}
            </div>
          )}
        </div>
      )}
      <div className={`flex-grow relative ${contentClassName}`}>
        {children}
      </div>
    </div>
  );
};
