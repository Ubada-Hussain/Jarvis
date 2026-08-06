import React, { useEffect, useRef } from 'react';
import Phaser from 'phaser';

interface AgentTownGameProps {
  agentStates: Record<string, string>;
}

const AgentTownGame: React.FC<AgentTownGameProps> = ({ agentStates }) => {
  const gameRef = useRef<HTMLDivElement>(null);
  const phaserGame = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (!gameRef.current || phaserGame.current) return;

    class MainScene extends Phaser.Scene {
      agents: Record<string, Phaser.GameObjects.Arc & { roleId?: string }> = {};
      deskLabels: Record<string, Phaser.GameObjects.Text> = {};
      desks: Record<string, {x: number, y: number}> = {
        'DEV': { x: 60, y: 60 },
        'SYS': { x: 340, y: 60 },
        'ACAD': { x: 60, y: 240 },
        'OBS': { x: 340, y: 240 },
      };
      center = { x: 200, y: 150 };

      constructor() {
        super('MainScene');
      }

      create() {
        // Floor
        this.add.rectangle(200, 150, 400, 300, 0x111111);
        
        // Grid lines for office feel
        const graphics = this.add.graphics();
        graphics.lineStyle(1, 0x333333, 0.5);
        for(let i=0; i<400; i+=20) { graphics.moveTo(i,0); graphics.lineTo(i,300); }
        for(let i=0; i<300; i+=20) { graphics.moveTo(0,i); graphics.lineTo(400,i); }
        graphics.strokePath();

        // Central Server (Task Core)
        const core = this.add.rectangle(this.center.x, this.center.y, 60, 40, 0x000000).setStrokeStyle(2, 0xef4444);
        const coreText = this.add.text(this.center.x, this.center.y - 35, 'TASK\nCORE', { fontSize: '10px', color: '#ef4444', align: 'center' }).setOrigin(0.5);
        coreText.setDepth(20); // ensure it is always above agents
        
        // Pulsing core effect
        this.tweens.add({
          targets: core,
          alpha: 0.5,
          duration: 1000,
          yoyo: true,
          repeat: -1
        });

        // Desks and Agents
        const colors: Record<string, number> = {
          'DEV': 0x06b6d4, // Cyan
          'SYS': 0xef4444, // Red
          'ACAD': 0x22c55e, // Green
          'OBS': 0xa855f7  // Purple
        };

        for (const [id, pos] of Object.entries(this.desks)) {
          // Desk
          this.add.rectangle(pos.x, pos.y, 40, 30, 0x222222).setStrokeStyle(1, 0x444444);
          const label = this.add.text(pos.x, pos.y - 25, id, { fontSize: '10px', color: '#ffffff' }).setOrigin(0.5);
          this.deskLabels[id] = label;

          // Agent (Colored Circle)
          const agent = this.add.circle(pos.x, pos.y, 8, colors[id]);
          agent.setDepth(10);
          this.agents[id] = agent;
        }

        // Expose update function to React
        this.events.on('updateAgentState', this.handleStateChange, this);
      }

      handleStateChange(states: Record<string, string>) {
        for (const [id, state] of Object.entries(states)) {
          const agent = this.agents[id];
          const label = this.deskLabels[id];
          if (!agent || !label) continue;
          
          const isBusy = state === 'busy' || state === 'working';
          const target = isBusy ? this.center : this.desks[id];
          
          // Update desk label indicator
          if (isBusy) {
            label.setText(`${id} [AWAY]`);
            label.setColor('#888888');
          } else {
            label.setText(id);
            label.setColor('#ffffff');
          }
          
          // Move if not already at target
          // Using distance check because tweens add slight random offsets
          const dist = Phaser.Math.Distance.Between(agent.x, agent.y, target.x, target.y);
          
          if (dist > 15) {
            // Check if tween already exists to avoid restarting
            const tweens = this.tweens.getTweensOf(agent);
            if (tweens.length === 0) {
              const offsetX = isBusy ? (Math.random() * 40 - 20) : 0;
              const offsetY = isBusy ? (Math.random() * 40 - 20) : 0;
              
              this.tweens.add({
                targets: agent,
                x: target.x + offsetX,
                y: target.y + offsetY,
                duration: 800,
                ease: 'Power2'
              });
            }
          }
        }
      }
    }

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: 400,
      height: 300,
      parent: gameRef.current,
      backgroundColor: '#050505',
      scene: [MainScene]
    };

    phaserGame.current = new Phaser.Game(config);

    return () => {
      phaserGame.current?.destroy(true);
      phaserGame.current = null;
    };
  }, []);

  // Sync state changes from React into Phaser
  useEffect(() => {
    if (phaserGame.current) {
      const scene = phaserGame.current.scene.getScene('MainScene');
      if (scene) {
        scene.events.emit('updateAgentState', agentStates);
      }
    }
  }, [agentStates]);

  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-[#050505] rounded-b-lg">
      <div 
        ref={gameRef} 
        className="rounded-lg overflow-hidden border border-red-900/50 shadow-[0_0_20px_rgba(220,38,38,0.2)]"
        style={{ width: '400px', height: '300px' }} 
      />
    </div>
  );
};

export default AgentTownGame;
