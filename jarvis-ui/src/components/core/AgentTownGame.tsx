import React, { useEffect, useRef } from 'react';
import Phaser from 'phaser';

interface AgentTownGameProps {
  agentStates: Record<string, string>;
}

const AgentTownGame: React.FC<AgentTownGameProps> = ({ agentStates }) => {
  const gameRef = useRef<HTMLDivElement>(null);
  const gameInstance = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    // We will use agentStates to move characters or change animations later
    console.log("Agent states updated:", agentStates);
  }, [agentStates]);

  useEffect(() => {
    if (!gameRef.current) return;

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: '100%',
      height: '100%',
      parent: gameRef.current,
      backgroundColor: 'transparent',
      transparent: true,
      scene: {
        preload: preload,
        create: create,
        update: update
      },
      scale: {
        mode: Phaser.Scale.RESIZE,
        autoCenter: Phaser.Scale.CENTER_BOTH
      },
      pixelArt: true
    };

    gameInstance.current = new Phaser.Game(config);

    function preload(this: Phaser.Scene) {
      // Load REAL Kenney Spritesheet
      this.load.spritesheet('rpg_tiles', '/assets/kenney_rpg-urban-pack/Tilemap/tilemap_packed.png', { 
        frameWidth: 16, 
        frameHeight: 16 
      });
      // Load the background map from Stitch
      this.load.image('bg_map', 'https://lh3.googleusercontent.com/aida-public/AB6AXuBjxZFWbUYi-1n7Rxq5u9p1vk2znEAdZ1_FpB8VqxaIxMmqPfZPgx0brCqLoSannbeNzjAaz7oYBvAn0kxgdWEa9iXGJ3Cri0DqNDkSMw-rUX1qZu93qtHjw_8aXu7RdTZfAZsYqCzU1Uo-L-ZVZuIiNONz7WQWdHxG_WLEmmNNiUjZVsBsUaY9xcTtv_-8knt4zl06BY7wDzbZ8Et-ZCA-rexAW2swwYZIC0I6AuTfpbefvkCyS4eI');
    }

    function create(this: Phaser.Scene) {
      const width = this.cameras.main.width;
      const height = this.cameras.main.height;

      // Draw background map
      const bg = this.add.image(width / 2, height / 2, 'bg_map');
      // Scale to cover
      const scaleX = width / bg.width;
      const scaleY = height / bg.height;
      const scale = Math.max(scaleX, scaleY);
      bg.setScale(scale).setAlpha(0.6);

      // Simple divider (dashed representation in Phaser)
      const graphics = this.add.graphics();
      graphics.lineStyle(1, 0x44e2f8, 0.2);
      
      // Draw a vertical dashed line
      graphics.beginPath();
      for(let i = 0; i < height; i += 10) {
        graphics.moveTo(width / 2, i);
        graphics.lineTo(width / 2, i + 5);
      }
      graphics.strokePath();

      // Room Labels
      this.add.text(10, 10, 'LOUNGE', { fontFamily: '"JetBrains Mono", monospace', fontSize: '12px', color: '#44e2f8' }).setAlpha(0.7);
      this.add.text(width - 40, 10, 'OPS', { fontFamily: '"JetBrains Mono", monospace', fontSize: '12px', color: '#44e2f8' }).setAlpha(0.7).setOrigin(1, 0);

      const spriteScale = 2.5; 
      
      // Real Sprite Rendering & Idle Animation
      const charFrame = 428; 

      const createAgent = (x: number, y: number, name: string, color: number) => {
        const sprite = this.add.sprite(x, y, 'rpg_tiles', charFrame).setScale(spriteScale);
        sprite.setTint(color);

        this.add.text(x, y - 25, name, { fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', color: '#ffffff' }).setOrigin(0.5).setAlpha(0.8);

        // Idle "Breathing" Animation via Tween
        this.tweens.add({
          targets: sprite,
          y: y - 3, 
          duration: 1000 + Math.random() * 500, 
          yoyo: true,
          repeat: -1,
          ease: 'Sine.easeInOut',
          delay: Math.random() * 500
        });

        return sprite;
      };

      // Create 2 Agents in the Gaming Lounge (Left side)
      createAgent(width * 0.30, height * 0.50, 'DEV', 0x44e2f8); // Cyan
      createAgent(width * 0.40, height * 0.60, 'OBS', 0xffb955); // Amber

      // Create 2 Agents in the Operations Office (Right side)
      createAgent(width * 0.60, height * 0.45, 'SYS', 0xffb3b2); // Crimson/Red
      createAgent(width * 0.80, height * 0.65, 'ACAD', 0x44ff44); // Green
    }

    function update(this: Phaser.Scene) {
      // Loop
    }

    return () => {
      if (gameInstance.current) {
        gameInstance.current.destroy(true);
        gameInstance.current = null;
      }
    };
  }, []);

  return (
    <div className="w-full h-full bg-transparent overflow-hidden absolute inset-0">
      <div ref={gameRef} className="w-full h-full absolute inset-0" />
    </div>
  );
};

export default AgentTownGame;
