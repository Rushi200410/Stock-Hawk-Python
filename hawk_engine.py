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

def check_trend(history):
    """Detects if the market is trending Up or Down."""
    if len(history) < 5:
        return "Neutral"
    
    prices = [h['data']['NIFTY']['price'] for h in history[:5]]
    
    # If every new price is higher than the last one
    if all(x < y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bullish 📈"
    # If every new price is lower than the last one
    if all(x > y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bearish 📉"
        
    return "Sideways ↔️"

def check_for_patterns():
    # Look back at 100 snapshots to find the long-term High
    history = get_history(limit=100) 
    
    if len(history) < 20:
        print(f"⏳ Building Trend Data... ({len(history)}/20)")
        return

    latest_snap = history[0]
    # 'history[1:]' means "everything except the current price"
    past_history = history[1:] 
    
    for sym in config.SYMBOLS:
        current_price = latest_snap['data'][sym]['price']
        
        # Find the highest price in the whole history
        long_term_high = max([h['data'][sym]['price'] for h in past_history])
        
        if current_price > long_term_high:
            # This is a 'Breakout' pattern!
            msg = f"🚀 *BREAKOUT ALERT*: {sym} just broke its 100-period HIGH at {current_price}!"
            print(msg)
            send_telegram_msg(msg)