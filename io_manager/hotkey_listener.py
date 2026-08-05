import keyboard
import time

class HotkeyListener:
    def __init__(self, hotkey="ctrl+space"):
        self.hotkey = hotkey

    def wait_for_trigger(self):
        """
        Blocks until the specific hotkey is pressed.
        Returns when the user presses the hotkey.
        """
        print(f"\n[SYSTEM] Press '{self.hotkey.upper()}' to speak with JARVIS, or 'ctrl+c' to exit.")
        # wait blocks until the hotkey is pressed
        keyboard.wait(self.hotkey)
        # Small delay to prevent the hotkey press from bleeding into the console input
        time.sleep(0.2)
        print("\n[SYSTEM] Hotkey detected! JARVIS is listening...")
