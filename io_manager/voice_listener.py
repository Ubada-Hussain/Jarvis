import threading
import queue
import time
import numpy as np

try:
    import sounddevice as sd
    from openwakeword.model import Model
    WAKEWORD_AVAILABLE = True
except ImportError:
    WAKEWORD_AVAILABLE = False
    print("[WARNING] openwakeword or sounddevice not installed. Wake word disabled.")

class WakeWordListener:
    def __init__(self, on_wake_word_detected, chunk_size=1280, sample_rate=16000):
        self.on_wake_word_detected = on_wake_word_detected
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.model = None
        self.thread = None

    def audio_callback(self, indata, frames, time, status):
        """This is called for each audio block by sounddevice."""
        if self.is_running:
            self.audio_queue.put(bytes(indata))

    def _listen_loop(self):
        try:
            # We'll try to load "hey_jarvis", if not available we'll fallback to "alexa"
            available_models = ["hey_jarvis", "alexa", "hey_mycroft", "timer"]
            target_model = None
            
            # Load the model
            self.model = Model()
            for m in available_models:
                if m in self.model.models.keys():
                    target_model = m
                    break
            
            if not target_model:
                print("[WakeWord] No suitable pre-trained model found. Falling back to default.")
                target_model = list(self.model.models.keys())[0]

            print(f"[WakeWord] Listening for wake word: '{target_model}'")

            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=self.chunk_size, 
                                   channels=1, dtype='int16',
                                   callback=self.audio_callback):
                while self.is_running:
                    try:
                        audio_chunk = self.audio_queue.get(timeout=0.5)
                        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                        prediction = self.model.predict(audio_data)
                        
                        # Check score for the target model
                        if prediction and target_model in prediction:
                            score = prediction[target_model]
                            if score > 0.5:
                                print(f"[WakeWord] '{target_model}' detected! Score: {score}")
                                if self.on_wake_word_detected:
                                    self.on_wake_word_detected()
                                # Debounce after detection
                                time.sleep(2)
                                # Clear the queue to ignore pending audio
                                while not self.audio_queue.empty():
                                    self.audio_queue.get()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        print(f"[WakeWord] Error in prediction loop: {e}")
                        time.sleep(1)
                        
        except Exception as e:
            print(f"[WakeWord] Failed to start audio stream: {e}")

    def start(self):
        if not WAKEWORD_AVAILABLE:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
