import os
import requests
from dotenv import load_dotenv

load_dotenv()

class LLMEngine:
    """
    Wrapper class to communicate with a local Ollama instance.
    """
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3")
        self._check_connection()

    def _check_connection(self):
        """Checks if the Ollama server is running."""
        try:
            response = requests.get(self.base_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Successfully connected to Ollama server at {self.base_url}")
            else:
                print(f"⚠️ Ollama server returned unexpected status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Error: Could not connect to Ollama server at {self.base_url}. Is it running?")
        except requests.exceptions.Timeout:
            print(f"❌ Error: Connection to Ollama server at {self.base_url} timed out.")

    def generate_response(self, prompt, system_prompt=None):
        """
        Sends text to Ollama and receives the generated response.
        
        Args:
            prompt (str): The user's input.
            system_prompt (str, optional): Instructions for the AI persona.
            
        Returns:
            str: The generated response from the LLM, or None if an error occurred.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error during text generation with Ollama: {e}")
            return None
