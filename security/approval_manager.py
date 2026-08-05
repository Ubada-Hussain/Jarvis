from io_manager.voice_synth import VoiceSynthesizer

class ApprovalManager:
    def __init__(self, voice_synth: VoiceSynthesizer):
        self.voice_synth = voice_synth

    def require_approval(self, action_description: str) -> bool:
        """
        Pauses execution to ask for human approval before proceeding.
        Returns True if approved, False otherwise.
        """
        prompt = f"Sir, do you want me to proceed with this action: {action_description}?"
        self.voice_synth.speak(prompt)
        
        while True:
            try:
                user_input = input(f"\n[APPROVAL REQUIRED] {action_description}\nProceed? (Y/N): ").strip().lower()
                if user_input in ['y', 'yes']:
                    print("[ApprovalManager] Action approved.")
                    return True
                elif user_input in ['n', 'no']:
                    print("[ApprovalManager] Action aborted by user.")
                    return False
                else:
                    print("[ApprovalManager] Invalid input. Please type 'Y' or 'N'.")
            except KeyboardInterrupt:
                print("\n[ApprovalManager] Action aborted by user interrupt.")
                return False
