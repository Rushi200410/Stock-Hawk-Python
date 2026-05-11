from kiteconnect import KiteTicker
import config

class KiteTickerThread:
    def __init__(self, api_key, access_token):
        self.kws = KiteTicker(api_key, access_token)
        self.last_ltp = {}

    def on_ticks(self, ws, ticks):
        for tick in ticks:
            # Store the latest price in a global or shared dictionary
            self.last_ltp[tick['instrument_token']] = tick['last_price']

    def on_connect(self, ws, response):
        # Subscribe to NIFTY (256265), BANKNIFTY (260105), and CRUDE FUT (e.g. 53518343)
        ws.subscribe([256265, 260105]) 
        ws.set_mode(ws.MODE_FULL, [256265, 260105])

    def start(self):
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.connect(threaded=True)