import asyncio
import time
import edge_tts
import os

text = "Hello, I am JARVIS. How can I assist you today?"
voices_to_test = [
    "en-US-ChristopherNeural",
    "en-US-GuyNeural",
    "en-US-EricNeural",
    "en-US-RogerNeural",
    "ur-PK-AsadNeural"
]

async def test_voice(voice):
    print(f"\nTesting voice: {voice}")
    start_time = time.time()
    if voice.startswith("ur"):
        test_text = "ہیلو، میں جاروس ہوں۔ میں آج آپ کی کیا مدد کر سکتا ہوں؟"
    else:
        test_text = text
    communicate = edge_tts.Communicate(test_text, voice)
    output_path = f"sample_{voice}.mp3"
    await communicate.save(output_path)
    end_time = time.time()
    
    latency = end_time - start_time
    print(f"Latency: {latency:.2f} seconds")
    print(f"Saved to {output_path}")

async def main():
    for voice in voices_to_test:
        await test_voice(voice)

if __name__ == "__main__":
    asyncio.run(main())
