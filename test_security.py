import time
import threading
import requests
import os

def run_test():
    # 1. Create dummy file
    with open("test.txt", "w") as f:
        f.write("test file for deletion")
    print("Created test.txt")

    # 2. Function to poll and respond
    def polling_thread(approve: bool):
        print(f"[POLLER] Started polling... (will {'approve' if approve else 'reject'})")
        while True:
            try:
                res = requests.get("http://127.0.0.1:8000/api/approval/status")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("pending_action"):
                        print(f"\n[POLLER] Detected pending action: {data['pending_action']}")
                        # Wait a bit, then respond
                        time.sleep(1)
                        print(f"[POLLER] Sending {'YES' if approve else 'NO'} response...")
                        requests.post("http://127.0.0.1:8000/api/approval/respond", json={"approved": approve})
                        return
            except Exception as e:
                pass
            time.sleep(1)

    print("\n--- TEST 1: Reject Deletion ---")
    t = threading.Thread(target=polling_thread, args=(False,))
    t.start()
    res = requests.post("http://127.0.0.1:8000/api/chat", json={"message": "delete test.txt file"})
    print(f"[CHAT] Response: {res.json()['response']}")
    t.join()
    print(f"File exists after rejection? {os.path.exists('test.txt')}")

    print("\n--- TEST 2: Approve Deletion ---")
    t2 = threading.Thread(target=polling_thread, args=(True,))
    t2.start()
    res = requests.post("http://127.0.0.1:8000/api/chat", json={"message": "delete test.txt file"})
    print(f"[CHAT] Response: {res.json()['response']}")
    t2.join()
    print(f"File exists after approval? {os.path.exists('test.txt')}")


if __name__ == "__main__":
    run_test()
