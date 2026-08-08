import React, { useEffect, useRef } from 'react';
import Phaser from 'phaser';

const AgentTown: React.FC = () => {
  const gameRef = useRef<HTMLDivElement>(null);
  const gameInstance = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (!gameRef.current) return;

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: '100%',
      height: '100%',
      parent: gameRef.current,
      backgroundColor: '#050505',
      scene: {
        preload: preload,
        create: create,
        update: update
      },
      scale: {
        mode: Phaser.Scale.RESIZE,
        autoCenter: Phaser.Scale.CENTER_BOTH
      }
    };

    gameInstance.current = new Phaser.Game(config);

    function preload(this: Phaser.Scene) {
      // Phase G2: Load assets
      this.load.image('agent', '/assets/agent_base.png');
    }

    function create(this: Phaser.Scene) {
      const width = this.cameras.main.width;
      const height = this.cameras.main.height;

      // Draw Gaming Room (Left)
      const gamingRoom = this.add.rectangle(width * 0.25, height / 2, width / 2, height, 0x11111b);
      gamingRoom.setStrokeStyle(2, 0x06b6d4, 0.3); // Cyan neon border

      // Draw Office Room (Right)
      const officeRoom = this.add.rectangle(width * 0.75, height / 2, width / 2, height, 0x1a1a24);
      officeRoom.setStrokeStyle(2, 0xef4444, 0.3); // Red neon border

      // Room Labels
      this.add.text(20, 20, 'GAMING LOUNGE (IDLE)', { 
        fontFamily: 'monospace', 
        fontSize: '12px', 
        color: '#06b6d4' 
      }).setAlpha(0.6);

      this.add.text(width / 2 + 20, 20, 'OPERATIONS OFFICE (WORKING)', { 
        fontFamily: 'monospace', 
        fontSize: '12px', 
        color: '#ef4444' 
      }).setAlpha(0.6);

      // Simple divider
      this.add.line(0, 0, width / 2, 0, width / 2, height, 0xffffff, 0.1).setOrigin(0);

      // --- PHASE G2: Static Character Rendering ---
      // Scale down if the image is too large (assuming 512x512 generated image)
      const spriteScale = 0.1; 
      const startX = width * 0.15;
      const startY = height * 0.4;
      const spacing = 60;

      // DEV (Red)
      const devSprite = this.add.sprite(startX, startY, 'agent').setScale(spriteScale);
      devSprite.setTint(0xff4444);
      this.add.text(startX, startY - 30, 'DEV', { fontSize: '10px', color: '#ff4444' }).setOrigin(0.5);

      // SYS (Cyan)
      const sysSprite = this.add.sprite(startX + spacing, startY, 'agent').setScale(spriteScale);
      sysSprite.setTint(0x44ffff);
      this.add.text(startX + spacing, startY - 30, 'SYS', { fontSize: '10px', color: '#44ffff' }).setOrigin(0.5);

      // ACAD (Green)
      const acadSprite = this.add.sprite(startX, startY + spacing, 'agent').setScale(spriteScale);
      acadSprite.setTint(0x44ff44);
      this.add.text(startX, startY + spacing - 30, 'ACAD', { fontSize: '10px', color: '#44ff44' }).setOrigin(0.5);

      // OBS (Amber)
      const obsSprite = this.add.sprite(startX + spacing, startY + spacing, 'agent').setScale(spriteScale);
      obsSprite.setTint(0xffb347);
      this.add.text(startX + spacing, startY + spacing - 30, 'OBS', { fontSize: '10px', color: '#ffb347' }).setOrigin(0.5);
    }

    function update(this: Phaser.Scene) {
      // Phase G1: Game loop
    }

    return () => {
      if (gameInstance.current) {
        gameInstance.current.destroy(true);
        gameInstance.current = null;
      }
    };
  }, []);

  return (
    <div className="w-full h-full bg-[#050505] rounded-b-lg overflow-hidden">
      <div ref={gameRef} className="w-full h-full" />
    </div>
  );
};

export default AgentTown;
