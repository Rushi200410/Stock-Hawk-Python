import os
import json
import config
from notifier import send_master_alert

def calculate_market_metrics(chain_data):
    """Calculates PCR and basic sentiment for the current chain."""
    total_ce_oi = sum(opt["CE"]["OI"] for opt in chain_data)
    total_pe_oi = sum(opt["PE"]["OI"] for opt in chain_data)

    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
    if pcr > 1.2: sentiment = "Extremely Bullish 🚀"
    elif pcr > 1.0: sentiment = "Bullish ✅"
    elif pcr < 0.8: sentiment = "Bearish 🔻"
    elif pcr < 0.6: sentiment = "Extremely Bearish 💀"
    else: sentiment = "Neutral ↔️"

    return {
        "pcr": pcr,
        "sentiment": sentiment,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
    }

def get_history(limit=100):
    """Loads the last N snapshots to analyze trends."""
    if not os.path.exists(config.SNAPSHOT_FOLDER):
        return []

    files = [os.path.join(config.SNAPSHOT_FOLDER, f) for f in os.listdir(config.SNAPSHOT_FOLDER)]
    files.sort(key=os.path.getmtime, reverse=True)

    history = []
    for path in files[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as snap_file:
                history.append(json.load(snap_file))
        except Exception:
            continue
    return history

def check_trend(history):
    """Detects if the market is trending up or down."""
    if len(history) < 5:
        return "Neutral"

    prices = [h["data"]["NIFTY"]["price"] for h in history[:5]]

    if all(x < y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bullish 📈"
    if all(x > y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bearish 📉"

    return "Sideways"


def check_for_patterns():
    """Detects a simple SMA crossover pattern and logs alerts."""
    history = get_history(limit=50)

    if len(history) < 20:
        print(f"⏳ Building Trend Data... ({len(history)}/20)")
        return

    latest_snap = history[0]
    
    for sym in config.SYMBOLS:
        current_price = latest_snap["data"][sym]["price"]
        recent_prices = [h["data"][sym]["price"] for h in history[:20]]
        sma_20 = sum(recent_prices) / len(recent_prices)
        prev_price = history[1]["data"][sym]["price"]

        if prev_price <= sma_20 and current_price > sma_20:
            msg = f"BULLISH CROSSOVER: {sym} crossed above SMA-20 at {current_price}!"
            print(msg)
            send_master_alert(msg, symbol=sym, pattern="SMA_CROSS_UP")
        elif prev_price >= sma_20 and current_price < sma_20:
            msg = f"BEARISH CROSSOVER: {sym} dropped below SMA-20 at {current_price}!"
            print(msg)
            send_master_alert(msg, symbol=sym, pattern="SMA_CROSS_DOWN")


def compare_milestones(current_data, interval_mins):
    """Generates a text report comparing current prices with the last saved milestone."""
    if not os.path.exists(config.MILESTONE_FOLDER):
        return None

    prefix = f"{interval_mins}m_"
    files = [
        os.path.join(config.MILESTONE_FOLDER, f)
        for f in os.listdir(config.MILESTONE_FOLDER)
        if f.startswith(prefix)
    ]
    files.sort(key=os.path.getmtime, reverse=True)

    if len(files) < 2:
        return f"First milestone for {interval_mins}m recorded. Waiting for next interval to compare."

    try:
        with open(files[1], "r", encoding="utf-8") as prev_file:
            prev_milestone = json.load(prev_file)
            prev_data = prev_milestone.get("data", {})
    except Exception as e:
        print(f"Error loading previous milestone: {e}")
        return None

    reports = [f"{interval_mins} Min Market Report"]
    for sym in current_data:
        curr_price = current_data[sym]["price"]
        if sym in prev_data:
            prev_price = prev_data[sym]["price"]
            diff = round(curr_price - prev_price, 2)
            status = "INCREASED" if diff > 0 else ("DECREASED" if diff < 0 else "UNCHANGED")
            reports.append(f"- {sym}: {status} by {abs(diff)} (Now: {curr_price})")

    return "\n".join(reports) if len(reports) > 1 else None


def get_live_expiries():
    """Generates a list of valid expiry dates based on 2026 rules."""
    return {
        "NIFTY": ["2026-05-12", "2026-05-19", "2026-05-26"],
        "BANKNIFTY": ["2026-05-12", "2026-05-19", "2026-05-26"],
        "CRUDEOIL": ["2026-05-18", "2026-06-16"],
    }
