# =============================================================

# config.py — Kite OI Dashboard Backend

# Central configuration: symbols, risk rules, system settings

# =============================================================

# ──────────────────────────────────────────

# KITE API CREDENTIALS

# Fill these in, or set as environment variables

# ──────────────────────────────────────────

API_KEY = "kuv63vy7loc6bl0d" # Your Kite Connect API key from kite.trade

API_SECRET = "6r64c7mqd4gqpcvt8aexqxd36lbc13tp" # Your API secret

ACCESS_TOKEN_FILE = "access_token.txt" # Stored after first login

# ──────────────────────────────────────────

# SERVER SETTINGS

# ──────────────────────────────────────────

SERVER_HOST = "0.0.0.0"

SERVER_PORT = 5000

DEBUG = False

# ──────────────────────────────────────────

# OI FETCH SETTINGS

# ──────────────────────────────────────────

FETCH_INTERVAL_SECONDS = 30 # How often to pull fresh OI data

STRIKES_EACH_SIDE = 5 # ±5 strikes around ATM

SNAPSHOT_FOLDER = "snapshots" # Folder where JSON snapshots are saved

# ──────────────────────────────────────────

# SYMBOL REGISTRY

# Add or remove symbols here freely.

# step = distance between strikes (e.g. Nifty = 50)

# lot = lot size for that symbol

# active = True means it gets fetched and snapshotted

# ──────────────────────────────────────────

SYMBOLS = {

"NIFTY": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:NIFTY 50",

"step": 50,

"lot": 50,

"type": "index",

"active": True,

},

"BANKNIFTY": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:NIFTY BANK",

"step": 100,

"lot": 15,

"type": "index",

"active": True,

},

"FINNIFTY": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:NIFTY FIN SERVICE",

"step": 50,

"lot": 40,

"type": "index",

"active": True,

},

"RELIANCE": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:RELIANCE",

"step": 20,

"lot": 250,

"type": "stock",

"active": True,

},

"TCS": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:TCS",

"step": 40,

"lot": 175,

"type": "stock",

"active": True,

},

"HDFCBANK": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:HDFCBANK",

"step": 20,

"lot": 550,

"type": "stock",

"active": False,

},

"INFY": {

"exchange": "NSE",

"segment": "NFO",

"spot_symbol": "NSE:INFY",

"step": 20,

"lot": 400,

"type": "stock",

"active": False,

},

}

# ──────────────────────────────────────────

# RISK RULES

# These are enforced by hawk_engine.py and

# relayed to the frontend for button locking

# ──────────────────────────────────────────

RISK = {

"total_capital": 500_000, # ₹ total trading capital

"max_pct_per_trade": 20, # max % of capital per trade

"max_open_positions": 3, # max simultaneous open trades

"direction_mode": "auto", # "auto" | "bull" | "bear" | "off"

}

# ──────────────────────────────────────────

# HAWK'S EYE ALERT THRESHOLDS

# ──────────────────────────────────────────

HAWK = {

"oi_change_pct_threshold": 20, # % OI change that triggers alert

"volume_spike_multiplier": 3, # volume × avg to flag spike

"pcr_bull_threshold": 1.4, # PCR above this = bullish extreme

"pcr_bear_threshold": 0.8, # PCR below this = bearish extreme

}

# ──────────────────────────────────────────

# EXPIRY HELPER

# Format used when building option symbols for Kite

# Example: NIFTY2450724400CE

# Kite tradingsymbol format: {SYMBOL}{YY}{MMM}{STRIKE}{CE/PE}

# ──────────────────────────────────────────

EXPIRY_FORMAT = "%y%b" # e.g. 24MAY — used in tradingsymbol builder

# ──────────────────────────────────────────

# LOGGING

# ──────────────────────────────────────────

LOG_LEVEL = "INFO" # DEBUG | INFO | WARNING | ERROR

LOG_FILE = "kite_dashboard.log"