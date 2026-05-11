from kiteconnect import KiteConnect

api_key    = "kuv63vy7loc6bl0d"
api_secret = "6r64c7mqd4gqpcvt8aexqxd36lbc13tp"
request_token = "bawmrTNr7qFPpIkFyDbk6PLPN0qUFSNI"

kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)

access_token = data["access_token"]
print("Access Token:", access_token)