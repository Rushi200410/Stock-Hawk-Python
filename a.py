from kiteconnect import KiteConnect

# 1. Initialize
kite = KiteConnect(api_key="kuv63vy7loc6bl0d")
kite.set_access_token("S9eysvY19648je0yK99AaFkAZ7FECEtL")

# 2. Define Instrument
# Note: Ensure the symbol "CRUDEOIL24MAY8500CE" is exactly correct for the current expiry
trading_symbol = "MCX:CRUDEOIL26MAY9000CE" 

# 3. Fetch LTP
try:
    quote = kite.ltp(trading_symbol)
    ltp = quote[trading_symbol]['last_price']
    print(f"LTP for {trading_symbol}: {ltp}")
except KeyError:
    print(f"Error: Could not find symbol {trading_symbol}. Check if expiry or strike is correct.")
except Exception as e:
    print(f"An error occurred: {e}")
