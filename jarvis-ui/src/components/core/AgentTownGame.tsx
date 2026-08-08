import React, { useEffect, useRef } from 'react';
import Phaser from 'phaser';

interface AgentTownGameProps {
  agentStates: Record<string, string>;
}

const AgentTownGame: React.FC<AgentTownGameProps> = ({ agentStates }) => {
  const gameRef = useRef<HTMLDivElement>(null);
  const gameInstance = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    // We will use agentStates in Phase G3/G4 to move characters
    console.log("Agent states updated:", agentStates);
  }, [agentStates]);

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
      },
      pixelArt: true // Ensures pixel art is crisp, no blur!
    };

    gameInstance.current = new Phaser.Game(config);

    function preload(this: Phaser.Scene) {
      // Phase G2: Load REAL Kenney Spritesheet
      this.load.spritesheet('rpg_tiles', '/assets/kenney_rpg-urban-pack/Tilemap/tilemap_packed.png', { 
        frameWidth: 16, 
        frameHeight: 16 
      });
    }

    function create(this: Phaser.Scene) {
      const width = this.cameras.main.width;
      const height = this.cameras.main.height;

      // Draw Gaming Room (Left)
      const gamingRoom = this.add.rectangle(width * 0.25, height / 2, width / 2, height, 0x11111b);
      gamingRoom.setStrokeStyle(2, 0x06b6d4, 0.3);

      // Draw Office Room (Right)
      const officeRoom = this.add.rectangle(width * 0.75, height / 2, width / 2, height, 0x1a1a24);
      officeRoom.setStrokeStyle(2, 0xef4444, 0.3);

      // Room Labels
      this.add.text(20, 20, 'GAMING LOUNGE (IDLE)', { fontFamily: 'monospace', fontSize: '12px', color: '#06b6d4' }).setAlpha(0.6);
      this.add.text(width / 2 + 20, 20, 'OPERATIONS OFFICE (WORKING)', { fontFamily: 'monospace', fontSize: '12px', color: '#ef4444' }).setAlpha(0.6);

      // Simple divider
      this.add.line(0, 0, width / 2, 0, width / 2, height, 0xffffff, 0.1).setOrigin(0);

      const spriteScale = 2.5; 
      const startX = width * 0.20;
      const startY = height * 0.4;
      const spacing = 80;

      // --- PHASE G2.5: Furnishing Rooms ---
      // NOTE: RPG Urban Pack is an OUTDOOR tileset (roads, cars, trees, vendors).
      // It does NOT have indoor TVs, couches, or computers. 
      // We are using creative outdoor equivalents for now!
      
      // GAMING LOUNGE FURNITURE
      const loungeCenter = width * 0.25;
      // "Arcade Machine" (Blue Vending Machine - Index 305)
      this.add.sprite(loungeCenter, height * 0.25, 'rpg_tiles', 305).setScale(spriteScale);
      // "Couch" (Wooden crate/bench - Index 274)
      this.add.sprite(loungeCenter, height * 0.35, 'rpg_tiles', 274).setScale(spriteScale);
      // "Plant" (Small tree - Index 286)
      this.add.sprite(loungeCenter - 60, height * 0.25, 'rpg_tiles', 286).setScale(spriteScale);
      this.add.sprite(loungeCenter + 60, height * 0.25, 'rpg_tiles', 286).setScale(spriteScale);

      // OPERATIONS OFFICE FURNITURE
      const officeStartX = width * 0.65;
      const deskSpacingX = 100;
      const deskSpacingY = 100;
      
      for (let row = 0; row < 2; row++) {
        for (let col = 0; col < 2; col++) {
          const x = officeStartX + (col * deskSpacingX);
          const y = (height * 0.3) + (row * deskSpacingY);
          
          // "Desk" (Wooden Counter - Index 273)
          this.add.sprite(x, y, 'rpg_tiles', 273).setScale(spriteScale);
          // "Computer Monitor" (Small yellow terminal - Index 307)
          this.add.sprite(x, y - 15, 'rpg_tiles', 307).setScale(spriteScale);
          // "Chair" (Small stool/bin - Index 278)
          this.add.sprite(x, y + 25, 'rpg_tiles', 278).setScale(spriteScale);
        }
      }

      // --- PHASE G2: Real Sprite Rendering & Idle Animation ---
      // Using index 428 which is a real front-facing generic character!
      const charFrame = 428; 

      const createAgent = (x: number, y: number, name: string, color: number) => {
        const sprite = this.add.sprite(x, y, 'rpg_tiles', charFrame).setScale(spriteScale);
        
        // Tint colors only the non-transparent pixels
        sprite.setTint(color);

        this.add.text(x, y - 25, name, { fontSize: '10px', color: '#ffffff' }).setOrigin(0.5);

        // Idle "Breathing" Animation via Tween
        this.tweens.add({
          targets: sprite,
          y: y - 3, 
          duration: 1000 + Math.random() * 500, 
          yoyo: true,
          repeat: -1,
          ease: 'Sine.easeInOut'
        });

        return sprite;
      };

      // Create 4 Agents in the Gaming Lounge
      createAgent(startX, startY, 'DEV', 0xff4444); 
      createAgent(startX + spacing, startY, 'SYS', 0x44ffff); 
      createAgent(startX, startY + spacing, 'ACAD', 0x44ff44); 
      createAgent(startX + spacing, startY + spacing, 'OBS', 0xffb347); 
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
    <div className="w-full h-full bg-[#050505] rounded-b-lg overflow-hidden">
      <div ref={gameRef} className="w-full h-full" />
    </div>
  );
};

export default AgentTownGame;
