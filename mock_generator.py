import time
import random
from datetime import datetime
from snapshot import snapshot_manager
import config

def start_simulation_once():
    market_snapshot = {}
    for sym in config.SYMBOLS:
        # Generate a random price
        fake_price = 24000 + random.uniform(-10, 10)
        market_snapshot[sym] = {
            "price": round(fake_price, 2),
            "time": datetime.now().strftime("%H:%M:%S")
        }
    
    snapshot_manager.save(market_snapshot)
    print(f"📊 Recorded Data at {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    print("🚀 Market Simulator Started... (Ctrl+C to stop)")
    while True:
        start_simulation_once()
        time.sleep(config.FETCH_INTERVAL)