import React, { useEffect, useRef, useState, useMemo } from 'react';
import Globe from 'react-globe.gl';
import type { Message } from '../../hooks/useJarvis';

interface WorldMonitorProps {
  messages: Message[];
  isLoading: boolean;
}

const WorldMonitor: React.FC<WorldMonitorProps> = ({ messages, isLoading }) => {
  const globeRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    
    // Auto-rotate safely
    if (globeRef.current && typeof globeRef.current.controls === 'function') {
      const controls = globeRef.current.controls();
      if (controls) {
        controls.autoRotate = true;
        controls.autoRotateSpeed = isLoading ? 2.0 : 0.5;
        controls.enableZoom = false;
      }
    }
    
    return () => window.removeEventListener('resize', updateDimensions);
  }, [isLoading, globeRef.current]);

  // Static server nodes for simulated geolocation
  const serverNodes = [
    { lat: 37.7749, lng: -122.4194, role: 'DEV', color: '#06b6d4' },  // San Francisco
    { lat: 51.5074, lng: -0.1278, role: 'SYS', color: '#ef4444' },    // London
    { lat: 35.6895, lng: 139.6917, role: 'ACAD', color: '#22c55e' },  // Tokyo
    { lat: -33.8688, lng: 151.2093, role: 'OBS', color: '#a855f7' }   // Sydney
  ];

  // If loading, show glowing rings at active nodes (DEV and SYS)
  const ringData = isLoading ? serverNodes.filter(n => n.role === 'DEV' || n.role === 'SYS') : [];

  // Generate random arcs for background ambient traffic
  const arcsData = useMemo(() => {
    return [...Array(10).keys()].map(() => ({
      startLat: (Math.random() - 0.5) * 180,
      startLng: (Math.random() - 0.5) * 360,
      endLat: (Math.random() - 0.5) * 180,
      endLng: (Math.random() - 0.5) * 360,
      color: ['#dc2626', '#7f1d1d'][Math.floor(Math.random() * 2)]
    }));
  }, []);

  // Format messages for feed
  const displayMessages = messages.length > 0 
    ? [...messages].reverse().slice(0, 10) 
    : [{ id: 'sys-1', role: 'system', content: 'SYS: Monitoring global network traffic...', timestamp: new Date().toISOString() }];

  return (
    <div className="w-full h-full relative bg-[#050505] rounded-b-lg overflow-hidden flex flex-col" ref={containerRef}>
      
      {/* Globe Container */}
      <div className="absolute inset-0 flex items-center justify-center opacity-90">
        {dimensions.width > 0 && (
          <Globe
            ref={globeRef}
            width={dimensions.width}
            height={dimensions.height}
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-dark.jpg"
            bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
            backgroundColor="rgba(0,0,0,0)"
            
            // Arcs for ambient traffic
            arcsData={arcsData}
            arcColor="color"
            arcDashLength={() => Math.random()}
            arcDashGap={() => Math.random()}
            arcDashAnimateTime={() => Math.random() * 4000 + 500}

            // Rings for active system agents
            ringsData={ringData}
            ringColor={(d: any) => d.color}
            ringMaxRadius={isLoading ? 8 : 2}
            ringPropagationSpeed={isLoading ? 3 : 1}
            ringRepeatPeriod={800}
          />
        )}
      </div>

      {/* Headlines Feed Overlay */}
      <div className="absolute bottom-0 w-full bg-gray-950/80 backdrop-blur-md border-t border-red-900/50 p-2 z-10 pointer-events-auto">
        <div className="text-[10px] text-cyan-500 font-bold uppercase tracking-widest mb-1 flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${isLoading ? 'bg-cyan-500' : 'bg-red-500'} animate-pulse`} />
          Live Event Feed {isLoading ? '[PROCESSING]' : '[IDLE]'}
        </div>
        <div className="overflow-hidden h-[40px] text-xs text-gray-300 relative">
          <div className="animate-[scroll_15s_linear_infinite] flex flex-col gap-2 hover:[animation-play-state:paused] absolute w-full">
            {displayMessages.map((msg, i) => (
              <div key={`first-${msg.id || i}`} className="truncate">
                <span className={msg.role === 'user' ? 'text-cyan-400' : msg.role === 'jarvis' ? 'text-red-400' : 'text-gray-500'}>
                  [{msg.role.toUpperCase()}]
                </span>{' '}
                {msg.content}
              </div>
            ))}
            {/* Duplicate for seamless scrolling */}
            {displayMessages.map((msg, i) => (
              <div key={`second-${msg.id || i}`} className="truncate">
                <span className={msg.role === 'user' ? 'text-cyan-400' : msg.role === 'jarvis' ? 'text-red-400' : 'text-gray-500'}>
                  [{msg.role.toUpperCase()}]
                </span>{' '}
                {msg.content}
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <style>{`
        @keyframes scroll {
          0% { top: 40px; }
          100% { top: -${displayMessages.length * 24}px; }
        }
      `}</style>
    </div>
  );
};

export default WorldMonitor;
