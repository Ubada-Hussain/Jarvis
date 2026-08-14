import asyncio
import edge_tts
import os

TEXT = "System status is nominal. Sir, this is how I sound with a fifteen percent slower speech rate."
VOICES = [
    "en-US-GuyNeural",
    "en-US-EricNeural",
    "en-GB-RyanNeural",
    "en-US-BrianNeural",
    "en-US-SteffanNeural"
]
RATE = "-15%"
OUTPUT_DIR = r"C:\Users\ubasa\.gemini\antigravity-ide\brain\2d3e32ee-0e4e-4a8d-99c5-0b798fb5e055\scratch"

async def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for voice in VOICES:
        output_path = os.path.join(OUTPUT_DIR, f"{voice}.mp3")
        print(f"Generating {voice}...")
        communicate = edge_tts.Communicate(TEXT, voice, rate=RATE)
        try:
            await communicate.save(output_path)
            print(f"Saved {output_path}")
        except Exception as e:
            print(f"Failed {voice}: {e}")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(generate())
