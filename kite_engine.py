from kite_auth import KiteAuthenticator
from datetime import datetime
import config
from kiteconnect import KiteTicker

# Initialize the real Kite connection and load the saved token safely
auth = KiteAuthenticator()
auth.load_token()
kite = auth.kite

def fetch_real_market_data():
    """Fetches real-time LTP and OI for Equity and MCX."""
    if not kite.access_token:
        print("❌ Kite Engine Error: No access token found. Please authenticate first.")
        return None
        
    market_snapshot = {}
    try:
        # 1. Define instruments (Indices and MCX Crude)
        instruments = ["NSE:NIFTY 50", "NSE:NIFTY BANK", "MCX:CRUDEOIL24MAYFUT"]
        quotes = kite.quote(instruments)
        
        for sym in config.SYMBOLS + ["CRUDEOIL"]:
            tradingsymbol = {
                "NIFTY": "NSE:NIFTY 50",
                "BANKNIFTY": "NSE:NIFTY BANK",
                "CRUDEOIL": "MCX:CRUDEOIL24MAYFUT"
            }.get(sym)
            
            if not tradingsymbol or tradingsymbol not in quotes: continue
            
            spot_price = quotes[tradingsymbol]["last_price"]
            
            # 2. Logic for Option Chain (NIFTY/BANKNIFTY only)
            options_chain = []
            if sym in ["NIFTY", "BANKNIFTY"]:
                strike_step = 50 if sym == "NIFTY" else 100
                atm_strike = round(spot_price / strike_step) * strike_step
                # Populate basic chain for UI (Live OI/LTP requires fetching specific scrips)
                for i in range(-15, 15):
                    strike = atm_strike + (i * strike_step)
                    options_chain.append({
                        "strikePrice": strike,
                        "isATM": bool(strike == atm_strike),
                        "CE": {"LTP": 0, "OI": 0, "changeInOI": 0},
                        "PE": {"LTP": 0, "OI": 0, "changeInOI": 0}
                    })

            market_snapshot[sym] = {
                "price": spot_price,
                "time": datetime.now().strftime("%H:%M:%S"),
                "optionsChain": options_chain
            }
        return market_snapshot
    except Exception as e:
        print(f"❌ Kite Data Error: {e}")
        return None

# --- WebSocket Implementation (The "Live Ticker") ---
if kite.access_token:
    kws = KiteTicker(config.API_KEY, kite.access_token)

    def on_ticks(ws, ticks):
        """Callback for streaming ticks."""
        for tick in ticks:
            print(f"Live Tick - {tick['instrument_token']}: {tick['last_price']}")

    def on_connect(ws, response):
        # Subscribe to NIFTY (256265) and BANKNIFTY (260105) tokens
        ws.subscribe([256265, 260105])
        ws.set_mode(ws.MODE_FULL, [256265, 260105])

    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    # Uncomment the following line to start the ticker in background
    # kws.connect(threaded=True)
else:
    kws = None