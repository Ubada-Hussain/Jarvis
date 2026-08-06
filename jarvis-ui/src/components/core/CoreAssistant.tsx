import React, { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import SidePanel from './SidePanel';

const ParticleSphere: React.FC<{ isThinking: boolean }> = ({ isThinking }) => {
  const points = useRef<THREE.Points>(null!);
  const materialRef = useRef<THREE.PointsMaterial>(null!);

  const particlesPosition = useMemo(() => {
    const count = 2000;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * 2 * Math.PI;
      const phi = Math.acos(Math.random() * 2 - 1);
      const r = 2.2; // radius
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
    }
    return positions;
  }, []);

  // Target values
  const targetColor = useMemo(() => new THREE.Color(), []);
  
  useFrame((_, delta) => {
    if (!points.current || !materialRef.current) return;
    
    // Smoothly interpolate rotation speed (requires storing current speed on the ref or just applying delta directly)
    // For simplicity, we just add rotation dynamically. To make it smooth, we can lerp a speed variable, but doing it directly with a multiplier is okay.
    points.current.rotation.x += delta * (isThinking ? 0.5 : 0.1);
    points.current.rotation.y += delta * (isThinking ? 0.8 : 0.15);
    if (isThinking) {
      points.current.rotation.z += delta * 0.2; // Add turbulence
    }

    // Color transition
    targetColor.set(isThinking ? '#22d3ee' : '#dc2626'); // Cyan when thinking, Red when idle
    materialRef.current.color.lerp(targetColor, 0.05);
    
    // Size transition
    const targetSize = isThinking ? 0.06 : 0.04;
    materialRef.current.size += (targetSize - materialRef.current.size) * 0.1;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[particlesPosition, 3]}
          count={particlesPosition.length / 3}
          array={particlesPosition}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        ref={materialRef}
        size={0.04}
        color="#dc2626"
        transparent
        opacity={0.8}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

const NodeLabel: React.FC<{ label: string; position: string; onClick?: () => void }> = ({ label, position, onClick }) => {
  return (
    <div 
      onClick={onClick}
      className={`absolute ${position} transform -translate-x-1/2 -translate-y-1/2 flex items-center gap-2 text-cyan-500 bg-gray-950/80 px-4 py-2 border border-cyan-900 rounded-full text-xs uppercase tracking-widest shadow-[0_0_15px_rgba(6,182,212,0.2)] backdrop-blur-md z-20 transition-all hover:bg-cyan-950 hover:text-cyan-300 hover:scale-105 cursor-pointer hover:shadow-[0_0_20px_rgba(6,182,212,0.5)]`}
    >
      <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_5px_#22d3ee]"></div>
      {label}
    </div>
  );
};

const CircuitLines: React.FC<{ isActive: boolean }> = ({ isActive }) => {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none z-10 opacity-60" style={{ filter: `drop-shadow(0 0 8px rgba(${isActive ? '34, 211, 238' : '220, 38, 38'}, 0.6))` }}>
      <line x1="20%" y1="20%" x2="50%" y2="50%" stroke={isActive ? '#0891b2' : '#991b1b'} strokeWidth="2" strokeDasharray="4 4" className={isActive ? "animate-[dash_0.5s_linear_infinite]" : "animate-[dash_2s_linear_infinite]"} />
      <line x1="80%" y1="20%" x2="50%" y2="50%" stroke={isActive ? '#0891b2' : '#991b1b'} strokeWidth="2" strokeDasharray="4 4" className={isActive ? "animate-[dash_0.5s_linear_infinite]" : "animate-[dash_2s_linear_infinite]"} />
      <line x1="20%" y1="80%" x2="50%" y2="50%" stroke={isActive ? '#0891b2' : '#991b1b'} strokeWidth="2" strokeDasharray="4 4" className={isActive ? "animate-[dash_0.5s_linear_infinite]" : "animate-[dash_2s_linear_infinite]"} />
      <line x1="80%" y1="80%" x2="50%" y2="50%" stroke={isActive ? '#0891b2' : '#991b1b'} strokeWidth="2" strokeDasharray="4 4" className={isActive ? "animate-[dash_0.5s_linear_infinite]" : "animate-[dash_2s_linear_infinite]"} />
      <style>
        {`
          @keyframes dash {
            to {
              stroke-dashoffset: -20;
            }
          }
        `}
      </style>
    </svg>
  );
};

const StartButton: React.FC<{ isThinking: boolean }> = ({ isThinking }) => {
  return (
    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-30">
      <button className="relative group focus:outline-none">
        <div className={`absolute -inset-2 bg-gradient-to-r ${isThinking ? 'from-cyan-600 to-blue-600' : 'from-red-600 to-cyan-600'} rounded-full blur-md opacity-70 group-hover:opacity-100 transition duration-500 group-hover:duration-200 ${isThinking ? 'animate-[pulse_0.5s_ease-in-out_infinite]' : 'animate-pulse'}`}></div>
        <div className={`relative w-32 h-32 bg-gray-950 rounded-full border-2 ${isThinking ? 'border-cyan-900 shadow-[inset_0_0_30px_rgba(34,211,238,0.4)]' : 'border-red-900 shadow-[inset_0_0_20px_rgba(220,38,38,0.3)]'} flex flex-col items-center justify-center transition-transform duration-300 group-hover:scale-105`}>
          <span className={`${isThinking ? 'text-cyan-400 drop-shadow-[0_0_10px_rgba(34,211,238,0.8)] text-sm' : 'text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.8)] text-xl'} font-bold tracking-[0.3em] transition-colors`}>
            {isThinking ? 'PROCESSING' : 'START'}
          </span>
          {!isThinking && (
            <span className="text-cyan-500 font-bold tracking-[0.3em] text-sm mt-1 group-hover:text-cyan-400 drop-shadow-[0_0_5px_rgba(6,182,212,0.8)]">AI</span>
          )}
        </div>
      </button>
    </div>
  );
};

const CoreAssistant: React.FC<{ isLoading?: boolean }> = ({ isLoading = false }) => {
  const [activePanel, setActivePanel] = useState<string | null>(null);

  return (
    <div className="w-full h-full relative bg-[#050505] rounded-b-lg overflow-hidden">
      <div className={`absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] ${isLoading ? 'from-cyan-900/20' : 'from-red-900/20'} via-[#050505] to-[#050505] z-0 transition-colors duration-1000`}></div>
      
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }} className="w-full h-full z-0">
        <ambientLight intensity={0.1} />
        <ParticleSphere isThinking={isLoading} />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={isLoading ? 4.0 : 0.8} />
      </Canvas>

      <CircuitLines isActive={isLoading} />
      <StartButton isThinking={isLoading} />

      {/* Node Labels */}
      <NodeLabel label="Memory" position="top-[20%] left-[20%]" onClick={() => setActivePanel('Memory')} />
      <NodeLabel label="Skills" position="top-[20%] left-[80%]" onClick={() => setActivePanel('Skills')} />
      <NodeLabel label="Soul" position="top-[80%] left-[20%]" onClick={() => setActivePanel('Soul')} />
      <NodeLabel label="Settings" position="top-[80%] left-[80%]" onClick={() => setActivePanel('Settings')} />

      {/* Side Panel Overlay */}
      <SidePanel 
        isOpen={activePanel !== null} 
        onClose={() => setActivePanel(null)} 
        title={activePanel || ''} 
      />
    </div>
  );
};

export default CoreAssistant;
