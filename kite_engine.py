from datetime import datetime

import config
import hawk_engine
from kite_auth import KiteAuthenticator
from kiteconnect import KiteTicker

# Initialize the real Kite connection and load the saved token safely.
auth = KiteAuthenticator()
auth.load_token()
kite = auth.kite

# Cached instrument lookup for fast symbol resolution.
instrument_lookup = {}
instruments_loaded = False


def load_instruments():
    """Downloads and caches the instrument list once."""
    global instruments_loaded, instrument_lookup
    if instruments_loaded:
        return

    if not kite or not kite.access_token:
        return

    print("Downloading instrument list...")
    instrument_lookup = {}

    for exchange in ("NFO", "NSE", "MCX"):
        try:
            for row in kite.instruments(exchange):
                tradingsymbol = row.get("tradingsymbol")
                token = row.get("instrument_token")
                if tradingsymbol and token is not None:
                    instrument_lookup[(exchange, tradingsymbol)] = int(token)
        except Exception as e:
            print(f"Instrument load error for {exchange}: {e}")

    instruments_loaded = True


def _build_option_symbol(symbol, expiry, strike, option_type):
    """Builds a tradingsymbol string for NSE/MCX contracts."""
    exp_dt = datetime.strptime(expiry, "%Y-%m-%d")

    if symbol == "CRUDEOIL":
        year = str(exp_dt.year)[-2:]
        month_name = exp_dt.strftime("%b").upper()
        tradingsymbol = f"CRUDEOIL{year}{month_name}{int(strike)}{option_type}"
        exchange = "MCX"
    else:
        year = str(exp_dt.year)[-2:]
        month = exp_dt.month
        day = f"{exp_dt.day:02d}"
        tradingsymbol = f"{symbol}{year}{month}{day}{int(strike)}{option_type}"
        exchange = "NFO"

    return exchange, tradingsymbol


def get_token_and_symbol(symbol, expiry, strike, option_type):
    """Resolves an instrument token from the cached lookup table."""
    if not instrument_lookup:
        return None, None

    exchange, tradingsymbol = _build_option_symbol(symbol, expiry, strike, option_type)
    token = instrument_lookup.get((exchange, tradingsymbol))
    if token is not None:
        return token, tradingsymbol
    return None, None


def fetch_real_market_data(kite_instance=None, symbol=None, expiry=None, depth=6):
    """Fetches LTP and OI for the requested symbols with a small strike window."""
    k = kite_instance if kite_instance else kite
    if not k or not k.access_token:
        print("Kite Engine Error: No access token found. Please authenticate first.")
        return None

    try:
        load_instruments()
        if not instrument_lookup:
            return None

        base_quotes = ["NSE:NIFTY 50", "NSE:NIFTY BANK", "MCX:CRUDEOIL26MAYFUT"]
        quotes = k.quote(base_quotes)

        symbols_to_fetch = [symbol] if symbol else config.SYMBOLS + ["CRUDEOIL"]
        market_snapshot = {}

        for sym in symbols_to_fetch:
            tradingsymbol = {
                "NIFTY": "NSE:NIFTY 50",
                "BANKNIFTY": "NSE:NIFTY BANK",
                "CRUDEOIL": "MCX:CRUDEOIL26MAYFUT",
            }.get(sym)

            if not tradingsymbol or tradingsymbol not in quotes:
                continue

            spot_price = quotes[tradingsymbol]["last_price"]
            options_chain = []

            if sym in ("NIFTY", "BANKNIFTY", "CRUDEOIL"):
                strike_step = 50 if sym == "NIFTY" else 100
                atm_strike = round(spot_price / strike_step) * strike_step

                expiries = hawk_engine.get_live_expiries().get(sym, [])
                current_expiry = expiry if expiry else (expiries[0] if expiries else None)
                if not current_expiry:
                    continue

                tokens_to_fetch = set()
                strike_map = {}
                exchange_prefix = "MCX" if sym == "CRUDEOIL" else "NFO"
                strike_window = max(3, int(depth))

                for i in range(-strike_window, strike_window + 1):
                    strike = atm_strike + (i * strike_step)
                    ce_token, ce_sym = get_token_and_symbol(sym, current_expiry, strike, "CE")
                    pe_token, pe_sym = get_token_and_symbol(sym, current_expiry, strike, "PE")

                    strike_map[strike] = {
                        "isATM": strike == atm_strike,
                        "CE_sym": f"{exchange_prefix}:{ce_sym}" if ce_sym else None,
                        "PE_sym": f"{exchange_prefix}:{pe_sym}" if pe_sym else None,
                    }

                    if ce_sym:
                        tokens_to_fetch.add(f"{exchange_prefix}:{ce_sym}")
                    if pe_sym:
                        tokens_to_fetch.add(f"{exchange_prefix}:{pe_sym}")

                opt_quotes = k.quote(list(tokens_to_fetch)) if tokens_to_fetch else {}

                for strike, data in strike_map.items():
                    ce_sym = data["CE_sym"]
                    pe_sym = data["PE_sym"]
                    ce_data = opt_quotes.get(ce_sym, {}) if ce_sym else {}
                    pe_data = opt_quotes.get(pe_sym, {}) if pe_sym else {}

                    options_chain.append(
                        {
                            "strikePrice": strike,
                            "isATM": data["isATM"],
                            "CE": {
                                "LTP": ce_data.get("last_price", 0),
                                "OI": ce_data.get("oi", 0),
                                "changeInOI": 0,
                            },
                            "PE": {
                                "LTP": pe_data.get("last_price", 0),
                                "OI": pe_data.get("oi", 0),
                                "changeInOI": 0,
                            },
                        }
                    )

            market_snapshot[sym] = {
                "price": spot_price,
                "time": datetime.now().strftime("%H:%M:%S"),
                "optionsChain": options_chain,
            }

        return market_snapshot

    except Exception as e:
        print(f"Kite Data Error: {e}")
        return None


def start_ticker(api_key, access_token):
    """Starts a small background ticker subscription."""
    kws = KiteTicker(api_key, access_token)

    def on_ticks(ws, ticks):
        for tick in ticks:
            print(f"Live Tick - {tick['instrument_token']}: {tick['last_price']}")

    def on_connect(ws, response):
        ws.subscribe([256265, 260105])
        ws.set_mode(ws.MODE_FULL, [256265, 260105])

    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.connect(threaded=True)


if kite.access_token:
    # start_ticker(config.API_KEY, kite.access_token)
    pass
