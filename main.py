import sys
from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.master_agent import MasterAgent
from io_manager.hotkey_listener import HotkeyListener
from io_manager.voice_synth import VoiceSynthesizer
from security.approval_manager import ApprovalManager

def main():
    print("==================================================")
    print("Initialize Phase 3: Voice & Security Active...")
    print("==================================================")
    
    # Initialize Core (Memory & LLM)
    memory = MemoryManager()
    llm = LLMEngine()
    
    # Initialize Phase 3 Components
    voice_synth = VoiceSynthesizer()
    approval_manager = ApprovalManager(voice_synth)
    hotkey_listener = HotkeyListener(hotkey="ctrl+space")
    
    # Initialize Master Agent with Approval Manager
    master_agent = MasterAgent(llm, memory, approval_manager)

    print("\n[SYSTEM] JARVIS Multi-Agent Core Ready.")
    
    # Greet user
    voice_synth.speak("JARVIS is online and ready for your command, sir.")

    while True:
        try:
            # Wait for hotkey instead of blocking on input immediately
            hotkey_listener.wait_for_trigger()
            
            user_input = input("\nYou: ")
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit']:
                print("\n[SYSTEM] Shutting down JARVIS...")
                voice_synth.speak("Shutting down. Goodbye, sir.")
                break
                
            if not user_input.strip():
                continue

            # Route the user input through the Master Agent
            response = master_agent.execute(user_input)
            
            if response:
                print(f"\nJARVIS: {response}")
                voice_synth.speak(response)
            else:
                print("\n[JARVIS ERROR]: Failed to generate a response.")
                
        except KeyboardInterrupt:
            print("\n\n[SYSTEM] Shutting down JARVIS...")
            break
        except Exception as e:
            print(f"\n[SYSTEM ERROR]: An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
