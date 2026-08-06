import time
from core.llm_engine import LLMEngine

print("Initializing LLMEngine...")
engine = LLMEngine()

print("Sending 'Hello' to Groq...")
start = time.time()
response = engine.generate_response("Hello")
end = time.time()

print(f"\nResponse: {response}")
print(f"Time taken: {end - start:.2f} seconds")
