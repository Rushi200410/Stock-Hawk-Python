from kiteconnect import KiteConnect

api_key = "kuv63vy7loc6bl0d"
kite    = KiteConnect(api_key=api_key)

print(kite.login_url())
