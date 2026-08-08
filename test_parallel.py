"""
Test script for PARALLEL agent execution.
Sends two tasks simultaneously and measures timing to prove they run in parallel.
"""
import requests
import time
import threading
import json

API = "http://localhost:8000/api/chat"

results = {}

def send_task(name, message):
    start = time.time()
    print(f"[{name}] Sending: '{message}'")
    try:
        r = requests.post(API, json={"message": message}, timeout=60)
        elapsed = time.time() - start
        data = r.json()
        results[name] = {
            "status": r.status_code,
            "elapsed": round(elapsed, 2),
            "response": data.get("response", "")[:200]
        }
        print(f"[{name}] Done in {elapsed:.2f}s (status={r.status_code})")
    except Exception as e:
        elapsed = time.time() - start
        results[name] = {"status": "ERROR", "elapsed": round(elapsed, 2), "response": str(e)}
        print(f"[{name}] ERROR after {elapsed:.2f}s: {e}")

# Task 1: Dev-related
t1 = threading.Thread(target=send_task, args=("TASK_DEV", "What files are in the current directory? List them."))
# Task 2: System-related  
t2 = threading.Thread(target=send_task, args=("TASK_SYS", "What is the current system CPU and RAM usage?"))

overall_start = time.time()

t1.start()
t2.start()

t1.join()
t2.join()

overall_elapsed = time.time() - overall_start

print("\n" + "="*60)
print("PARALLEL EXECUTION RESULTS")
print("="*60)
for name, r in results.items():
    print(f"\n{name}:")
    print(f"  Status: {r['status']}")
    print(f"  Time:   {r['elapsed']}s")
    print(f"  Response: {r['response'][:150]}...")

print(f"\nTotal wall-clock time: {overall_elapsed:.2f}s")
individual_sum = sum(r["elapsed"] for r in results.values())
print(f"Sum of individual times: {individual_sum:.2f}s")

if overall_elapsed < individual_sum * 0.85:
    print("\n✅ CONFIRMED: Tasks ran in PARALLEL (wall time < sum of individual times)")
else:
    print("\n⚠️ Tasks may have run sequentially (wall time ≈ sum of individual times)")
    print("   This could happen if both tasks were routed to the same agent.")
