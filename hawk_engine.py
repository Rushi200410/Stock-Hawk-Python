import os
import json
import config
from notifier import send_telegram_msg

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
            send_telegram_msg(msg, symbol=sym, pattern="SMA_CROSS_UP")
            
        elif prev_price >= sma_20 and current_price < sma_20:
            msg = f"🔻 *BEARISH CROSSOVER*: {sym} dropped below SMA-20 at {current_price}!"
            print(msg)
            send_telegram_msg(msg, symbol=sym, pattern="SMA_CROSS_DOWN")