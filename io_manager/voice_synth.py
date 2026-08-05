import pyttsx3

class VoiceSynthesizer:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            # Optional: configure voice properties
            self.engine.setProperty('rate', 170)  # Speed percent (can go over 100)
            self.engine.setProperty('volume', 0.9)  # Volume 0-1
        except Exception as e:
            print(f"[VoiceSynthesizer ERROR] Failed to initialize pyttsx3: {e}")
            self.engine = None

    def speak(self, text: str):
        """
        Uses the TTS engine to speak the provided text synchronously.
        """
        if self.engine:
            try:
                print(f"[JARVIS VOICE]: {text}")
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"[VoiceSynthesizer ERROR] Failed to speak: {e}")
        else:
            print(f"[JARVIS (No Voice)]: {text}")
