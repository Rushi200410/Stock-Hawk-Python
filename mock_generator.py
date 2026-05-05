import time
import random
from datetime import datetime
from snapshot import snapshot_manager
import config

# We store the "current" price in a variable so it persists between loops
current_prices = {
    "NIFTY": 24000.0,
    "BANKNIFTY": 48000.0
}

def start_simulation_once():
    """Generates one realistic price movement for all symbols."""
    market_snapshot = {}
    
    for sym in config.SYMBOLS:
        # Get the last price we recorded
        last_price = current_prices.get(sym, 24000.0)
        
        # Calculate a small 'step' (between -2 and +2)
        # This makes the price move smoothly instead of jumping randomly
        change = random.uniform(-2.0, 2.0)
        new_price = round(last_price + change, 2)
        
        # Update our memory for the next loop
        current_prices[sym] = new_price
        
        market_snapshot[sym] = {
            "price": new_price,
            "time": datetime.now().strftime("%H:%M:%S")
        }
    
    # Save this realistic snapshot
    snapshot_manager.save(market_snapshot)
    print(f"📊 Recorded Realistic Data at {datetime.now().strftime('%H:%M:%S')}")
