import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def transcribe_audio(audio_file_path: str) -> str:
    """
    Uses Groq's whisper-large-v3-turbo to transcribe the audio file.
    Automatically detects language (English, Urdu, Punjabi, etc.).
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
    return transcription
