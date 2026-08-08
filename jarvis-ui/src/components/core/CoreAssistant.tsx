import React, { useEffect, useRef } from 'react';
import type { SystemState } from '../../hooks/useJarvis';

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
      idle:      { c1: '255,59,78', c2: '122,22,34', speed: 0.15, spread: 1, glow: 0.35 },
      listening: { c1: '45,212,234', c2: '20,90,100', speed: 0.35, spread: 1.25, glow: 0.55 },
      thinking:  { c1: '255,80,60', c2: '150,20,10', speed: 1.4, spread: 0.85, glow: 0.75 },
      speaking:  { c1: '245,220,180', c2: '150,90,20', speed: 0.6, spread: 1.35, glow: 0.65 },
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

      const audioPulse = (systemState === 'listening' || systemState === 'speaking') ? (Math.sin(t * 6) * 0.15 + 1) : 1;
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
    <>
      <canvas ref={canvasRef} id="coreCanvas" width={360} height={360}></canvas>
      <div className="core-caption" id="stateLabel">{systemState.toUpperCase()}</div>
      
      {/* Visual buttons for pure aesthetics, although backend controls state */}
      <div className="state-row">
        <button className={`state-btn ${systemState === 'idle' ? 'active' : ''}`} disabled>Idle</button>
        <button className={`state-btn ${systemState === 'listening' ? 'active' : ''}`} disabled>Listening</button>
        <button className={`state-btn ${systemState === 'thinking' ? 'active' : ''}`} disabled>Thinking</button>
        <button className={`state-btn ${systemState === 'speaking' ? 'active' : ''}`} disabled>Speaking</button>
      </div>
    </>
  );
};

export default CoreAssistant;
