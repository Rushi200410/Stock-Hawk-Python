import os
import json
import config
from notifier import send_master_alert

def calculate_market_metrics(chain_data):
    """Calculates PCR and basic sentiment for the current chain."""
    total_ce_oi = sum(opt["CE"]["OI"] for opt in chain_data)
    total_pe_oi = sum(opt["PE"]["OI"] for opt in chain_data)
    
    # Avoid division by zero
    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
    
    # Basic Sentiment Logic
    if pcr > 1.2: sentiment = "Extremely Bullish 🚀"
    elif pcr > 1.0: sentiment = "Bullish ✅"
    elif pcr < 0.8: sentiment = "Bearish 🔻"
    elif pcr < 0.6: sentiment = "Extremely Bearish 💀"
    else: sentiment = "Neutral ↔️"
    
    return {
        "pcr": pcr,
        "sentiment": sentiment,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi
    }

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
    # Load last 50 snapshots for analysis
    history = get_history(limit=50) 
    
    if len(history) < 20:
        print(f"⏳ Building Trend Data... ({len(history)}/20)")
        return

    latest_snap = history[0]
    
    for sym in config.SYMBOLS:
        current_price = latest_snap['data'][sym]['price']
        
        # Calculate Moving Average (Average of last 20 prices)
        recent_prices = [h['data'][sym]['price'] for h in history[:20]]
        sma_20 = sum(recent_prices) / len(recent_prices)

        # PATTERN: SMA Crossover (Price breaks above the average)
        # We check if it was BELOW the SMA before, but is ABOVE it now
        prev_price = history[1]['data'][sym]['price']
        
        if prev_price <= sma_20 and current_price > sma_20:
            msg = f"🚀 *BULLISH CROSSOVER*: {sym} crossed above SMA-20 at {current_price}!"
            print(msg)
            send_master_alert(msg, symbol=sym, pattern="SMA_CROSS_UP")
            
        elif prev_price >= sma_20 and current_price < sma_20:
            msg = f"🔻 *BEARISH CROSSOVER*: {sym} dropped below SMA-20 at {current_price}!"
            print(msg)
            send_master_alert(msg, symbol=sym, pattern="SMA_CROSS_DOWN")

def compare_milestones(current_data, interval_mins):
    """Generates a text report comparing current prices with the last saved milestone."""
    if not os.path.exists(config.MILESTONE_FOLDER):
        return None
        
    # 1. Find files for this specific interval, sorted newest first
    prefix = f"{interval_mins}m_"
    files = [os.path.join(config.MILESTONE_FOLDER, f) for f in os.listdir(config.MILESTONE_FOLDER) if f.startswith(prefix)]
    files.sort(key=os.path.getmtime, reverse=True)
    
    # We need at least 2 files (the one we just saved, and the previous one) to compare
    if len(files) < 2:
        return f"⏳ First milestone for {interval_mins}m recorded. Waiting for next interval to compare."
        
    try:
        with open(files[1], 'r') as prev_file: # index 1 is the second newest
            prev_milestone = json.load(prev_file)
            prev_data = prev_milestone.get('data', {})
    except Exception as e:
        print(f"Error loading previous milestone: {e}")
        return None
        
    # 2 & 3. Calculate % change and format
    reports = [f"📊 *{interval_mins} Min Market Report*"]
    for sym in current_data:
        curr_price = current_data[sym]['price']
        if sym in prev_data:
            prev_price = prev_data[sym]['price']
            diff = round(curr_price - prev_price, 2)
            status = "INCREASED 🟢" if diff > 0 else ("DECREASED 🔴" if diff < 0 else "UNCHANGED ⚪")
            reports.append(f"• {sym}: {status} by {abs(diff)} (Now: {curr_price})")
    
    return "\n".join(reports) if len(reports) > 1 else None