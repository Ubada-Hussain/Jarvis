import time
import psutil

def run_observer_agent():
    print("[ObserverAgent] Starting background monitoring...")
    print("[ObserverAgent] Monitoring interval: 2 seconds")
    print("[ObserverAgent] CPU Threshold: 10% (for testing purposes)")
    print("[ObserverAgent] ----------------------------------------")
    
    for i in range(3):
        time.sleep(2)
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        
        print(f"[ObserverAgent] Checking system health... CPU: {cpu}% | RAM: {ram}%")
        
        # Production threshold
        if cpu > 85.0 or ram > 90.0:
            print(f">>> [LIVE EVENT FEED WARNING]: High Resource Usage Detected! (CPU: {cpu}%) <<<")
        else:
            print(">>> [LIVE EVENT FEED]: System Normal.")

if __name__ == '__main__':
    run_observer_agent()
