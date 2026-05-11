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

# Store the options chain state so we can calculate change in OI
current_options_chain = {
    "NIFTY": {},
    "BANKNIFTY": {}
}

def start_simulation_once():
    """Generates one realistic price movement and an options chain for all symbols."""
    market_snapshot = {}
    
    for sym in config.SYMBOLS:
        # Get the last price we recorded
        last_price = current_prices.get(sym, 0.0)
        
        # Calculate a small 'step' (between -2 and +2)
        # This makes the price move smoothly instead of jumping randomly
        change = random.uniform(-2.0, 2.0)
        new_price = round(max(0.05, last_price + change), 2)
        
        # Update our memory for the next loop
        current_prices[sym] = new_price
        
        # --- NEW LOGIC: Generate 10 Strikes Options Chain ---
        strike_step = 50 if sym == "NIFTY" else 100
        # Find ATM (At The Money) strike
        atm_strike = round(new_price / strike_step) * strike_step
        
        # Generate 15 strikes below and 15 above ATM so the UI has enough data
        strikes = [atm_strike + (i * strike_step) for i in range(-15, 15)]
        
        options_chain_data = []
        
        for strike in strikes:
            is_atm = bool(strike == atm_strike)
            # Initialize persistent data if this strike is new
            if strike not in current_options_chain[sym]:
                current_options_chain[sym][strike] = {
                    "CE": {"LTP": random.uniform(50, 200), "OI": random.randint(10000, 500000)},
                    "PE": {"LTP": random.uniform(50, 200), "OI": random.randint(10000, 500000)}
                }
            
            # Simulate CE changes
            old_ce_oi = current_options_chain[sym][strike]["CE"]["OI"]
            ce_oi_change = random.randint(-5000, 5000)
            new_ce_oi = max(0, old_ce_oi + ce_oi_change)
            old_ce_ltp = current_options_chain[sym][strike]["CE"]["LTP"]
            new_ce_ltp = max(0.05, round(old_ce_ltp + random.uniform(-5.0, 5.0), 2))
            
            # Update memory and capture
            current_options_chain[sym][strike]["CE"].update({"OI": new_ce_oi, "LTP": new_ce_ltp})
            
            # Simulate PE changes
            old_pe_oi = current_options_chain[sym][strike]["PE"]["OI"]
            pe_oi_change = random.randint(-5000, 5000)
            new_pe_oi = max(0, old_pe_oi + pe_oi_change)
            old_pe_ltp = current_options_chain[sym][strike]["PE"]["LTP"]
            new_pe_ltp = max(0.05, round(old_pe_ltp + random.uniform(-5.0, 5.0), 2))
            
            # Update memory and capture
            current_options_chain[sym][strike]["PE"].update({"OI": new_pe_oi, "LTP": new_pe_ltp})
            
            options_chain_data.append({
                "strikePrice": strike,
                "isATM": is_atm,
                "CE": {"LTP": new_ce_ltp, "OI": new_ce_oi, "changeInOI": ce_oi_change},
                "PE": {"LTP": new_pe_ltp, "OI": new_pe_oi, "changeInOI": pe_oi_change}
            })

        market_snapshot[sym] = {
            "price": new_price,
            "time": datetime.now().strftime("%H:%M:%S"),
            "optionsChain": options_chain_data
        }
    
    # Save this realistic snapshot
    snapshot_manager.save(market_snapshot)
    print(f"Recorded realistic data at {datetime.now().strftime('%H:%M:%S')}")
    return market_snapshot
