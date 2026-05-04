import os
import json
import config

def get_latest_snapshots(limit=2):
    """Gets the two most recent files from the snapshots folder."""
    files = [os.path.join(config.SNAPSHOT_FOLDER, f) for f in os.listdir(config.SNAPSHOT_FOLDER)]
    # Sort files by time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)
    return files[:limit]

def analyze_patterns():
    snaps = get_latest_snapshots()
    
    # We need at least two snapshots to compare "Now" vs "Then"
    if len(snaps) < 2:
        return

    with open(snaps[0], 'r') as f:
        latest = json.load(f)
    with open(snaps[1], 'r') as f:
        previous = json.load(f)

    for sym in config.SYMBOLS:
        price_now = latest['data'][sym]['price']
        price_before = previous['data'][sym]['price']
        
        # Calculate the difference
        diff = round(price_now - price_before, 2)
        
        if abs(diff) > 0.01: # If the price moved even a little bit
            direction = "🚀 UP" if diff > 0 else "🔻 DOWN"
            print(f"[{latest['timestamp']}] ALERT: {sym} moved {direction} by {abs(diff)}")