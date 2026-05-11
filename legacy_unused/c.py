from kiteconnect import KiteConnect
import config

kite = KiteConnect(api_key=config.API_KEY)
kite.set_access_token("S9eysvY19648je0yK99AaFkAZ7FECEtL")

# Test it works
profile = kite.profile()
print("Logged in as:", profile["user_name"])