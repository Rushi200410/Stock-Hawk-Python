import os
import json
import config
from notifier import send_telegram_msg

def get_history(limit=100):
    """Loads the last N snapshots to analyze trends."""
    # Ensure the folder exists before listing
    if not os.path.exists(config.SNAPSHOT_FOLDER):
        return []
        
    files = [os.path.join(config.SNAPSHOT_FOLDER, f) for f in os.listdir(config.SNAPSHOT_FOLDER)]
    files.sort(key=os.path.getmtime, reverse=True)
    
    history = []
    for f in files[:limit]:
        try:
            with open(f, 'r') as snap_file:
                history.append(json.load(snap_file))
        except Exception:
            continue
    return history

def check_for_patterns():
    history = get_history(limit=50) 
    
    if len(history) < 10:
        print(f"⏳ Collecting data... (Current: {len(history)}/10)")
        return

    latest_snap = history[0]
    
    for sym in config.SYMBOLS:
        current_price = latest_snap['data'][sym]['price']
        all_past_prices = [h['data'][sym]['price'] for h in history[1:]]
        
        max_price = max(all_past_prices)
        min_price = min(all_past_prices)

        if current_price > max_price:
            msg = f"🔥 *PATTERN HIT*: {sym} reached a NEW HIGH of {current_price}!"
            print(msg)
            send_telegram_msg(msg)
            
        elif current_price < min_price:
            msg = f"🧊 *PATTERN HIT*: {sym} reached a NEW LOW of {current_price}!"
            print(msg)
            send_telegram_msg(msg)