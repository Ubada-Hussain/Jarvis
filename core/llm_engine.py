import os
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class LLMEngine:
    """
    Wrapper class to communicate with Groq API (Cloud-based LLM).
    Fallback to local Ollama instance is kept as comments.
    """
    def __init__(self):
        # --- GROQ IMPLEMENTATION ---
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"
        if self.api_key and self.api_key != "your_key_here":
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None
            print("[WARN] GROQ_API_KEY not set in .env. LLM will not function.")

        # --- OLLAMA FALLBACK (Disabled) ---
        # self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
        # self._check_connection()

    # --- OLLAMA FALLBACK (Disabled) ---
    # def _check_connection(self):
    #     """Checks if the Ollama server is running."""
    #     try:
    #         response = requests.get(self.base_url, timeout=5)
    #         if response.status_code == 200:
    #             print(f"[OK] Connected to Ollama at {self.base_url}")
    #         else:
    #             print(f"[WARN] Ollama returned unexpected status: {response.status_code}")
    #     except requests.exceptions.ConnectionError:
    #         print(f"[ERROR] Could not connect to Ollama at {self.base_url}. Is it running?")
    #     except requests.exceptions.Timeout:
    #         print(f"[ERROR] Connection to Ollama at {self.base_url} timed out.")

    def generate_response(self, prompt, system_prompt=None, tools=None, tool_logic=None):
        """
        Sends text to Groq API and receives the generated response.
        If tools are provided, handles the tool calling loop automatically.
        
        Args:
            prompt (str): The user's input.
            system_prompt (str, optional): Instructions for the AI persona.
            tools (list, optional): List of tool schemas.
            tool_logic (dict, optional): Mapping of tool names to Python functions.
            
        Returns:
            str: The generated response from the LLM, or None if an error occurred.
        """
        if not self.client:
            return "Error: GROQ_API_KEY is not configured in .env file."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            # First API call
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
                "top_p": 1,
                "stream": False,
            }
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"
                
            completion = self.client.chat.completions.create(**api_params)
            response_message = completion.choices[0].message
            
            # Check if LLM wanted to call any tools
            tool_calls = response_message.tool_calls
            if tool_calls and tool_logic:
                # Append the assistant's tool call request to history
                messages.append(response_message)
                
                # Execute all tools
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = tool_logic.get(function_name)
                    
                    if function_to_call:
                        import json
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                            print(f"[LLM Tool Call] Executing '{function_name}' with args: {function_args}")
                            function_response = function_to_call(**function_args)
                        except Exception as e:
                            function_response = f"Error executing tool: {e}"
                        
                        # Append the tool's response to history
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        })
                
                # Second API call to get the final answer using tool results
                if tools:
                    api_params["tool_choice"] = "none" # Force it to answer now
                
                second_completion = self.client.chat.completions.create(**api_params)
                return second_completion.choices[0].message.content
                
            return response_message.content
        except Exception as e:
            import json
            import re
            
            error_str = str(e)
            if "tool_use_failed" in error_str and "failed_generation" in error_str:
                print(f"[LLM_ENGINE WARNING] Groq tool_use_failed bug detected. Attempting manual recovery...")
                try:
                    # Attempt to extract the <function=...> tag
                    match = re.search(r'<function=(\w+)\s+({.*?})\s*</function>', error_str)
                    if match and tool_logic:
                        func_name = match.group(1)
                        func_args_str = match.group(2)
                        print(f"[LLM_ENGINE RECOVERY] Extracted function: {func_name}, args: {func_args_str}")
                        
                        func_to_call = tool_logic.get(func_name)
                        if func_to_call:
                            args = json.loads(func_args_str)
                            result = func_to_call(**args)
                            return f"Action performed successfully: {result}"
                except Exception as inner_e:
                    print(f"[LLM_ENGINE RECOVERY ERROR] Failed to recover: {inner_e}")
                    
                return "I encountered an error trying to use a tool to fulfill your request. The Groq API failed to parse the action."

            import traceback
            traceback.print_exc()
            print(f"[LLM_ENGINE ERROR] Error during text generation with Groq: {e}")
            return None

        # --- OLLAMA FALLBACK (Disabled) ---
        # url = f"{self.base_url}/api/generate"
        # payload = {
        #     "model": self.ollama_model,
        #     "prompt": prompt,
        #     "stream": False
        # }
        # if system_prompt:
        #     payload["system"] = system_prompt
        # 
        # try:
        #     response = requests.post(url, json=payload, timeout=300)
        #     response.raise_for_status()
        #     return response.json().get("response", "")
        # except requests.exceptions.RequestException as e:
        #     print(f"❌ Error during text generation with Ollama: {e}")
        #     return None
