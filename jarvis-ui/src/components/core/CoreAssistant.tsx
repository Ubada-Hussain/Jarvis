import React, { useEffect, useRef } from 'react';
import type { SystemState } from '../../hooks/useJarvis';
import { visualizer } from '../../utils/audioVisualizer';

interface CoreAssistantProps {
  systemState: SystemState;
}

const CoreAssistant: React.FC<CoreAssistantProps> = ({ systemState }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const CX = W / 2;
    const CY = H / 2;
    let t = 0;
    let animationFrameId: number;

    const particles: { theta: number, phi: number, r: number, speedOffset: number }[] = [];
    const N = 260;
    for (let i = 0; i < N; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      particles.push({ theta, phi, r: 95 + Math.random() * 10, speedOffset: Math.random() * Math.PI * 2 });
    }

    const stateColors: Record<SystemState, { c1: string, c2: string, speed: number, spread: number, glow: number }> = {
      idle:      { c1: '45,212,234', c2: '20,90,100', speed: 0.15, spread: 1, glow: 0.2 }, // Cyan for idle
      listening: { c1: '255,59,78', c2: '122,22,34', speed: 0.35, spread: 1.25, glow: 0.55 }, // Red for listening
      thinking:  { c1: '255,185,85', c2: '150,90,20', speed: 1.4, spread: 0.85, glow: 0.6 }, // Amber for thinking
      speaking:  { c1: '255,179,178', c2: '150,90,20', speed: 0.6, spread: 1.35, glow: 0.65 }, // Light red for speaking
    };

    const draw = () => {
      t += 0.016;
      ctx.clearRect(0, 0, W, H);
      const cfg = stateColors[systemState] || stateColors.idle;

      // core glow
      const grad = ctx.createRadialGradient(CX, CY, 10, CX, CY, 120);
      grad.addColorStop(0, `rgba(${cfg.c1},${cfg.glow})`);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      // Get real-time audio data
      let micAmp = 0;
      let ttsAmp = 0;
      if (systemState === 'listening') micAmp = visualizer.getMicAmplitude();
      if (systemState === 'speaking') ttsAmp = visualizer.getTTSAmplitude();
      
      const realTimePulse = 1 + (micAmp * 2) + (ttsAmp * 1.5);
      const fallbackPulse = (systemState === 'listening' || systemState === 'speaking') ? (Math.sin(t * 6) * 0.15 + 1) : 1;
      const audioPulse = (micAmp > 0.01 || ttsAmp > 0.01) ? realTimePulse : fallbackPulse;
      
      const rot = t * cfg.speed;

      particles.forEach((p) => {
        const theta = p.theta + rot;
        const r = p.r * cfg.spread * audioPulse * (1 + 0.05 * Math.sin(t * 2 + p.speedOffset));
        const x = CX + r * Math.sin(p.phi) * Math.cos(theta);
        const y = CY + r * Math.sin(p.phi) * Math.sin(theta) * 0.9;
        const z = Math.cos(p.phi);
        const size = 1.2 + (z + 1) * 1.1;
        const alpha = 0.25 + (z + 1) * 0.35;
        
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${cfg.c1},${alpha})`;
        ctx.fill();
      });

      // inner ring
      ctx.beginPath();
      ctx.arc(CX, CY, 58 + Math.sin(t * 3) * (systemState === 'thinking' ? 4 : 1.5), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${cfg.c1},0.5)`;
      ctx.lineWidth = 1;
      ctx.stroke();

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [systemState]);

  return (
    <div className="fui-panel fui-border rounded relative flex-grow min-h-[400px] flex flex-col p-4">
      <div className="absolute top-0 left-0 border-b border-r border-secondary/20 px-2 py-1 bg-secondary/10 font-label-caps text-label-caps text-secondary z-10">
        SEC-01 // SYS.CORE
      </div>
      
      <div className="relative flex-grow flex items-center justify-center mt-8">
        {/* 3D Neural Core Animation (Sphere) */}
        <div className="absolute inset-0 w-full h-full z-0 opacity-80 flex items-center justify-center">
          <canvas ref={canvasRef} id="coreCanvas" width={300} height={300}></canvas>
        </div>
        
        {/* Nodes Container */}
        <div className="relative w-full h-full max-w-[400px] max-h-[400px] z-10 pointer-events-none">
          {/* Connecting Lines */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-[80%] h-px dashed-connector absolute"></div>
            <div className="h-[80%] w-px dashed-connector-v absolute"></div>
          </div>
          
          {/* Node: Memory (Top) */}
          <div className="absolute top-8 left-1/2 -translate-x-1/2 pointer-events-auto">
            <div className="border border-secondary/40 bg-background/90 px-3 py-1 rounded font-terminal-sm text-terminal-sm text-secondary flex items-center gap-2 shadow-[0_0_10px_#44e2f833]">
              <div className="w-1.5 h-1.5 bg-secondary animate-pulse"></div> MEMORY
            </div>
          </div>
          
          {/* Node: Skills (Right) */}
          <div className="absolute top-1/2 right-8 -translate-y-1/2 pointer-events-auto">
            <div className="border border-secondary/40 bg-background/90 px-3 py-1 rounded font-terminal-sm text-terminal-sm text-secondary flex items-center gap-2 shadow-[0_0_10px_#44e2f833]">
              <div className="w-1.5 h-1.5 bg-secondary animate-pulse"></div> SKILLS
            </div>
          </div>
          
          {/* Node: Settings (Bottom) */}
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-auto">
            <div className="border border-secondary/40 bg-background/90 px-3 py-1 rounded font-terminal-sm text-terminal-sm text-secondary flex items-center gap-2 shadow-[0_0_10px_#44e2f833]">
              <span className="material-symbols-outlined text-[14px]">settings</span> SETTINGS
            </div>
          </div>
          
          {/* Node: Soul (Left) */}
          <div className="absolute top-1/2 left-8 -translate-y-1/2 pointer-events-auto">
            <div className="border border-primary/40 bg-background/90 px-3 py-1 rounded font-terminal-sm text-terminal-sm text-primary flex items-center gap-2 shadow-[0_0_10px_#ffb3b233]">
              <div className="w-1.5 h-1.5 bg-primary animate-pulse"></div> SOUL
            </div>
          </div>
        </div>
      </div>
      
      {/* State Toggles */}
      <div className="mt-auto pt-4 flex justify-center gap-4 z-10">
        <button className={`px-4 py-1.5 rounded-full border ${systemState === 'idle' ? 'border-secondary bg-secondary/20 text-secondary shadow-[0_0_15px_rgba(68,226,248,0.4)]' : 'border-secondary/30 text-on-surface-variant hover:bg-secondary/10 hover:text-secondary'} font-label-caps text-label-caps transition-all`}>
          IDLE
        </button>
        <button className={`px-4 py-1.5 rounded-full border ${systemState === 'listening' ? 'border-[#ff3b4e] bg-[#ff3b4e]/20 text-[#ff3b4e] shadow-[0_0_15px_rgba(255,59,78,0.4)]' : 'border-secondary/30 text-on-surface-variant hover:bg-secondary/10 hover:text-secondary'} font-label-caps text-label-caps transition-all flex items-center gap-2`}>
          {systemState === 'listening' && <div className="w-2 h-2 rounded-full bg-[#ff3b4e] animate-pulse"></div>}
          LISTENING
        </button>
        <button className={`px-4 py-1.5 rounded-full border ${systemState === 'thinking' ? 'border-tertiary bg-tertiary/20 text-tertiary shadow-[0_0_15px_rgba(255,185,85,0.4)]' : 'border-secondary/30 text-on-surface-variant hover:bg-secondary/10 hover:text-secondary'} font-label-caps text-label-caps transition-all`}>
          THINKING
        </button>
        <button className={`px-4 py-1.5 rounded-full border ${systemState === 'speaking' ? 'border-primary bg-primary/20 text-primary shadow-[0_0_15px_rgba(255,179,178,0.4)]' : 'border-secondary/30 text-on-surface-variant hover:bg-secondary/10 hover:text-secondary'} font-label-caps text-label-caps transition-all`}>
          SPEAKING
        </button>
      </div>
    </div>
  );
};

export default CoreAssistant;
