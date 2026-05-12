from kite_auth import KiteAuthenticator
from datetime import datetime
import config
from kiteconnect import KiteTicker
import pandas as pd
import hawk_engine
from app_logger import logger

# Initialize the real Kite connection and load the saved token safely
auth = KiteAuthenticator()
auth.load_token()
kite = auth.kite

# Global variable to store instrument list in memory for fast lookup
instruments_df = None

def load_instruments():
    """Downloads and caches the instrument list for the day."""
    global instruments_df
    if instruments_df is not None: return
    logger.info("Downloading instrument list...")
    inst = kite.instruments("NFO") + kite.instruments("NSE") + kite.instruments("MCX")
    instruments_df = pd.DataFrame(inst)

def get_token_and_symbol(symbol, expiry, strike, option_type):
    global instruments_df
    if instruments_df is None: return None, None

    exp_dt = pd.to_datetime(expiry)
    
    if symbol == "CRUDEOIL":
        # MCX Option Format: CRUDEOILYYMMMDDstrikeCE (e.g., CRUDEOIL26MAY189000CE)
        # Note: Month is usually the short name 'MAY' or 'JUN'
        year = str(exp_dt.year)[-2:]
        month_name = exp_dt.strftime('%b').upper()
        # For Commodities, the symbol often omits the day for monthly contracts
        tradingsymbol = f"CRUDEOIL{year}{month_name}{int(strike)}{option_type}"
        exchange = "MCX"
    else:
        # NSE Option Format: NIFTY2651224000CE
        year = str(exp_dt.year)[-2:]
        month = exp_dt.month
        day = f"{exp_dt.day:02d}"
        tradingsymbol = f"{symbol}{year}{month}{day}{int(strike)}{option_type}"
        exchange = "NFO"
    # Important: Search by both Symbol and Exchange to avoid duplicates
    res = instruments_df[(instruments_df['tradingsymbol'] == tradingsymbol) & 
                         (instruments_df['exchange'] == exchange)]
                         
    if not res.empty:
        return int(res.iloc[0]['instrument_token']), tradingsymbol
    return None, None

def fetch_real_market_data(kite_instance=None, symbol=None, expiry=None):
    """Fetches real-time LTP and OI for Equity and MCX."""
    k = kite_instance if kite_instance else kite
    if not k or not k.access_token:
        logger.warning("Kite Engine Error: No access token found. Please authenticate first.")
        return None
        
    market_snapshot = {}
    try:
        load_instruments()
        # 1. Define instruments (Indices and MCX Crude)
        instruments = ["NSE:NIFTY 50", "NSE:NIFTY BANK", "MCX:CRUDEOIL26MAYFUT"]
        quotes = k.quote(instruments)
        
        symbols_to_fetch = [symbol] if symbol else config.SYMBOLS + ["CRUDEOIL"]
        
        for sym in symbols_to_fetch:
            tradingsymbol = {
                "NIFTY": "NSE:NIFTY 50",
                "BANKNIFTY": "NSE:NIFTY BANK",
                "CRUDEOIL": "MCX:CRUDEOIL26MAYFUT"
            }.get(sym)
            
            if not tradingsymbol or tradingsymbol not in quotes:
                continue
            
            spot_price = quotes[tradingsymbol]["last_price"]
            
            # 2. Logic for Option Chain
            options_chain = []
            if sym in ["NIFTY", "BANKNIFTY", "CRUDEOIL"]:
                strike_step = 50 if sym == "NIFTY" else 100
                atm_strike = round(spot_price / strike_step) * strike_step

                # Get the nearest expiry for this symbol dynamically
                expiries = hawk_engine.get_live_expiries().get(sym, [])
                current_expiry = expiry if expiry else (expiries[0] if expiries else None)
                if not current_expiry:
                    continue
                tokens_to_fetch = []
                strike_map = {}
                
                exchange_prefix = "MCX" if sym == "CRUDEOIL" else "NFO"
                
                for i in range(-15, 15):
                    strike = atm_strike + (i * strike_step)
                    ce_token, ce_sym = get_token_and_symbol(sym, current_expiry, strike, "CE")
                    pe_token, pe_sym = get_token_and_symbol(sym, current_expiry, strike, "PE")
                    
                    strike_map[strike] = {
                        "isATM": bool(strike == atm_strike),
                        "CE_sym": f"{exchange_prefix}:{ce_sym}" if ce_sym else None,
                        "PE_sym": f"{exchange_prefix}:{pe_sym}" if pe_sym else None
                    }
                    
                    if ce_sym: tokens_to_fetch.append(f"{exchange_prefix}:{ce_sym}")
                    if pe_sym: tokens_to_fetch.append(f"{exchange_prefix}:{pe_sym}")

                # 4. ONE SINGLE API CALL for the entire chain (Efficient!)
                opt_quotes = k.quote(tokens_to_fetch) if tokens_to_fetch else {}
                
                for strike, data in strike_map.items():
                    ce_sym = data["CE_sym"]
                    pe_sym = data["PE_sym"]
                    
                    ce_data = opt_quotes.get(ce_sym, {}) if ce_sym else {}
                    pe_data = opt_quotes.get(pe_sym, {}) if pe_sym else {}
                    
                    options_chain.append({
                        "strikePrice": strike,
                        "isATM": data["isATM"],
                        "CE": {
                            "LTP": ce_data.get("last_price", 0), 
                            "OI": ce_data.get("oi", 0), 
                            "changeInOI": 0
                        },
                        "PE": {
                            "LTP": pe_data.get("last_price", 0), 
                            "OI": pe_data.get("oi", 0), 
                            "changeInOI": 0
                        }
                    })

            market_snapshot[sym] = {
                "price": spot_price,
                "time": datetime.now().strftime("%H:%M:%S"),
                "optionsChain": options_chain
            }
        return market_snapshot
    except Exception as e:
        logger.error("Kite Data Error: %s", e)
        return None

# --- WebSocket Implementation (The "Live Ticker") ---
def start_ticker(api_key, access_token):
    kws = KiteTicker(api_key, access_token)

    def on_ticks(ws, ticks):
        """Callback for streaming ticks."""
        # Update your global 'current_prices' dictionary here if needed
        return

    def on_connect(ws, response):
        # Subscribe to NIFTY (256265) and BANKNIFTY (260105) tokens
        ws.subscribe([256265, 260105])
        ws.set_mode(ws.MODE_FULL, [256265, 260105])

    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.connect(threaded=True)

if kite.access_token:
    # Uncomment the line below to start streaming ticks instantly in the background!
    # start_ticker(config.API_KEY, kite.access_token)
    pass
