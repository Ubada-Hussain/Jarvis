import asyncio
import edge_tts
import os

PROFILES = [
    ("young_man", "en-US-ChristopherNeural", "+0Hz", "+0%"),
    ("young_woman", "en-US-AriaNeural", "+0Hz", "+0%"),
    ("old_man", "en-GB-RyanNeural", "-10Hz", "-10%"),
    ("old_woman", "en-GB-SoniaNeural", "-10Hz", "-10%"),
    ("kid", "en-US-AnaNeural", "+20Hz", "+10%"),
    ("flirty", "en-US-AriaNeural", "+5Hz", "-20%"),
]

TEXT = "Hello there. I am your personal assistant, JARVIS. How can I help you today?"
OUTPUT_DIR = r"C:\Users\ubasa\.gemini\antigravity-ide\brain\2d3e32ee-0e4e-4a8d-99c5-0b798fb5e055\scratch"

async def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name, voice, pitch, rate in PROFILES:
        output_path = os.path.join(OUTPUT_DIR, f"profile_{name}.mp3")
        print(f"Generating {name}...")
        communicate = edge_tts.Communicate(TEXT, voice, rate=rate, pitch=pitch)
        try:
            await communicate.save(output_path)
        except Exception as e:
            print(f"Failed {name}: {e}")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(generate())
