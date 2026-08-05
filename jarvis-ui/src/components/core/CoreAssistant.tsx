import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere } from '@react-three/drei';
import * as THREE from 'three';

// A rotating, wireframe "brain" sphere
const ThinkingSphere = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  
  useFrame((state, delta) => {
    meshRef.current.rotation.x += delta * 0.2;
    meshRef.current.rotation.y += delta * 0.3;
  });

  return (
    <Sphere ref={meshRef} args={[2, 32, 32]}>
      <meshStandardMaterial 
        color="#ef4444" 
        wireframe={true} 
        emissive="#7f1d1d"
        emissiveIntensity={0.5}
        transparent={true}
        opacity={0.8}
      />
    </Sphere>
  );
};

const NodeLabel: React.FC<{ label: string; position: string }> = ({ label, position }) => {
  return (
    <div className={`absolute ${position} flex items-center gap-2 text-cyan-500 bg-gray-950/80 px-3 py-1 border border-cyan-900 rounded-full text-xs uppercase tracking-widest shadow-[0_0_10px_rgba(6,182,212,0.3)] backdrop-blur-sm z-20 transition-all hover:bg-cyan-950 hover:text-cyan-300 cursor-pointer`}>
      <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></div>
      {label}
    </div>
  );
};

const CoreAssistant: React.FC = () => {
  return (
    <div className="w-full h-full relative bg-gray-950 rounded-lg">
      
      {/* 3D Canvas */}
      <Canvas camera={{ position: [0, 0, 6], fov: 50 }} className="w-full h-full">
        <ambientLight intensity={0.2} />
        <directionalLight position={[10, 10, 5]} intensity={1.5} color="#dc2626" />
        <pointLight position={[-10, -10, -5]} intensity={1} color="#06b6d4" />
        <ThinkingSphere />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={1.5} />
      </Canvas>

      {/* Connection Nodes Overlay */}
      <NodeLabel label="Memory" position="top-1/4 left-8" />
      <NodeLabel label="Skills" position="top-1/4 right-8" />
      <NodeLabel label="Soul" position="bottom-1/4 left-8" />
      <NodeLabel label="Settings" position="bottom-1/4 right-8" />
      
      {/* Central HUD elements */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        <div className="w-64 h-64 border border-red-900/30 rounded-full animate-[spin_10s_linear_infinite]"></div>
      </div>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        <div className="w-72 h-72 border-t border-b border-cyan-900/20 rounded-full animate-[spin_15s_linear_infinite_reverse]"></div>
      </div>
      
    </div>
  );
};

export default CoreAssistant;
