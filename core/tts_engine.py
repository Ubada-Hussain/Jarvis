import os
import uuid
import asyncio
from gtts import gTTS
import edge_tts

# Audio storage directory
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE_PROFILES = {
    "default": {"voice": "en-GB-RyanNeural", "rate": "+0%", "pitch": "+0Hz"},
    "young_man": {"voice": "en-US-ChristopherNeural", "rate": "+0%", "pitch": "+0Hz"},
    "young_woman": {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "old_man": {"voice": "en-GB-RyanNeural", "rate": "-10%", "pitch": "-10Hz"},
    "old_woman": {"voice": "en-GB-SoniaNeural", "rate": "-10%", "pitch": "-10Hz"},
    "kid": {"voice": "en-US-AnaNeural", "rate": "+10%", "pitch": "+20Hz"},
    "flirty": {"voice": "en-US-AriaNeural", "rate": "-20%", "pitch": "+5Hz"},
}

# Voice Mappings for non-English languages
LANG_VOICES = {
    "ur": {"voice": "ur-PK-AsadNeural", "rate": "+0%", "pitch": "+0Hz"},
    "hi": {"voice": "hi-IN-MadhurNeural", "rate": "+0%", "pitch": "+0Hz"},
}

CURRENT_PROFILE = "default"

def set_voice_profile(profile_name: str):
    global CURRENT_PROFILE
    if profile_name in VOICE_PROFILES:
        CURRENT_PROFILE = profile_name
        return True
    return False

async def _generate_edge_tts(text: str, voice: str, output_path: str, rate: str, pitch: str):
    """Generates audio using edge-tts (async)."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)

def generate_audio(text: str, language: str = "en") -> str:
    """
    Generates TTS audio for the given text and automatically detects language.
    """
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    # Auto-detect language
    try:
        from langdetect import detect
        detected_lang = detect(text)
        if detected_lang in ["ur", "hi", "pa", "en"]:
            language = detected_lang
    except Exception:
        pass
        
    language = language.lower()
    
    # Pick voice parameters
    if language == "en":
        params = VOICE_PROFILES.get(CURRENT_PROFILE, VOICE_PROFILES["default"])
    elif language in LANG_VOICES:
        params = LANG_VOICES[language]
    else:
        params = None

    if params:
        # Use high-quality edge-tts
        try:
            asyncio.run(_generate_edge_tts(text, params["voice"], filepath, params["rate"], params["pitch"]))
        except Exception as e:
            print(f"[TTS ERROR] Edge-TTS failed: {e}. Falling back to gTTS.")
            tts = gTTS(text=text, lang=language)
            tts.save(filepath)
    else:
        # Use gTTS for unsupported languages (like Punjabi 'pa')
        try:
            tts = gTTS(text=text, lang=language)
            tts.save(filepath)
        except Exception as e:
            print(f"[TTS ERROR] gTTS failed for language {language}: {e}")
            tts = gTTS(text=text, lang="en")
            tts.save(filepath)
            
    return f"/static/audio/{filename}"
