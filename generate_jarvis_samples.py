import asyncio
import edge_tts
import os

PROFILES = [
    ("ryan_normal", "en-GB-RyanNeural", "+0Hz", "+0%"),
    ("ryan_low", "en-GB-RyanNeural", "-5Hz", "+0%"),
    ("thomas_normal", "en-GB-ThomasNeural", "+0Hz", "+0%"),
    ("thomas_low", "en-GB-ThomasNeural", "-5Hz", "+0%"),
]

TEXT = "Good morning, sir. System status is nominal, and all protocols are online. How may I assist you today?"
OUTPUT_DIR = r"C:\Users\ubasa\.gemini\antigravity-ide\brain\2d3e32ee-0e4e-4a8d-99c5-0b798fb5e055\scratch"

async def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name, voice, pitch, rate in PROFILES:
        output_path = os.path.join(OUTPUT_DIR, f"jarvis_{name}.mp3")
        print(f"Generating {name}...")
        communicate = edge_tts.Communicate(TEXT, voice, rate=rate, pitch=pitch)
        try:
            await communicate.save(output_path)
        except Exception as e:
            print(f"Failed {name}: {e}")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(generate())
