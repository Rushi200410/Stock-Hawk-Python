import os
import json
import time
import config
from notifier import send_master_alert


_last_pattern_check = 0.0


def calculate_market_metrics(chain_data):
    """Calculates PCR and basic sentiment for the current chain."""
    total_ce_oi = sum(opt["CE"]["OI"] for opt in chain_data)
    total_pe_oi = sum(opt["PE"]["OI"] for opt in chain_data)

    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
    if pcr > 1.2:
        sentiment = "Extremely Bullish"
    elif pcr > 1.0:
        sentiment = "Bullish"
    elif pcr < 0.8:
        sentiment = "Bearish"
    elif pcr < 0.6:
        sentiment = "Extremely Bearish"
    else:
        sentiment = "Neutral"

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

    with os.scandir(config.SNAPSHOT_FOLDER) as entries:
        files = [entry.path for entry in entries if entry.is_file()]
    files.sort(key=os.path.getmtime, reverse=True)

    history = []
    for path in files[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as snap_file:
                history.append(json.load(snap_file))
        except Exception:
            continue
    return history


def _get_symbol_prices(history, sym, limit=None):
    """Extracts the most recent valid prices for a symbol from snapshot history."""
    prices = []
    for snap in history:
        symbol_data = snap.get("data", {}).get(sym)
        if not symbol_data:
            continue

        price = symbol_data.get("price")
        if isinstance(price, (int, float)):
            prices.append(price)

        if limit is not None and len(prices) >= limit:
            break

    return prices


def check_trend(history):
    """Detects if the market is trending up or down."""
    prices = _get_symbol_prices(history, "NIFTY", limit=5)
    if len(prices) < 5:
        return "Neutral"

    if all(x < y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bullish"
    if all(x > y for x, y in zip(prices[::-1], prices[::-1][1:])):
        return "Bearish"

    return "Sideways"


def check_for_patterns():
    """Detects a simple SMA crossover pattern and logs alerts."""
    global _last_pattern_check
    now = time.monotonic()
    if now - _last_pattern_check < 15:
        return
    _last_pattern_check = now

    history = get_history(limit=50)

    for sym in config.SYMBOLS:
        recent_prices = _get_symbol_prices(history, sym, limit=20)
        if len(recent_prices) < 20:
            print(f"Building trend data for {sym}... ({len(recent_prices)}/20)")
            continue

        current_price = recent_prices[0]
        sma_20 = sum(recent_prices) / len(recent_prices)
        prev_prices = _get_symbol_prices(history[1:], sym, limit=1)
        if not prev_prices:
            continue

        prev_price = prev_prices[0]

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
    with os.scandir(config.MILESTONE_FOLDER) as entries:
        files = [
            entry.path
            for entry in entries
            if entry.is_file() and entry.name.startswith(prefix)
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
