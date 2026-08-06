import os
import uuid
import asyncio
from gtts import gTTS
import edge_tts

# Audio storage directory
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Voice Mappings
VOICES = {
    "en": "en-US-ChristopherNeural",  # English (Male)
    "ur": "ur-PK-AsadNeural",         # Urdu (Male)
}

async def _generate_edge_tts(text: str, voice: str, output_path: str):
    """Generates audio using edge-tts (async)."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_audio(text: str, language: str = "en") -> str:
    """
    Generates TTS audio for the given text and language.
    Returns the relative URL to the audio file.
    """
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    language = language.lower()
    
    if language in VOICES:
        # Use high-quality edge-tts for English and Urdu
        voice = VOICES[language]
        try:
            asyncio.run(_generate_edge_tts(text, voice, filepath))
        except Exception as e:
            print(f"[TTS ERROR] Edge-TTS failed: {e}. Falling back to gTTS.")
            # Fallback to gTTS if edge-tts fails
            tts = gTTS(text=text, lang=language)
            tts.save(filepath)
    else:
        # Use gTTS for Punjabi ('pa') and any other unsupported languages
        try:
            # gTTS expects 'pa' for Punjabi
            tts = gTTS(text=text, lang=language)
            tts.save(filepath)
        except Exception as e:
            print(f"[TTS ERROR] gTTS failed for language {language}: {e}")
            # Ultimate fallback to english
            tts = gTTS(text=text, lang="en")
            tts.save(filepath)
            
    # Return the relative URL path to be served by FastAPI
    return f"/static/audio/{filename}"
