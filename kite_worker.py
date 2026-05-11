import config
from kiteconnect import KiteConnect

class KiteWorker:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.kite = None
        self.access_token = None

    def initialize(self):
        """Initializes the Kite object with your API_KEY."""
        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_url(self):
        """Returns the login URL to get a request_token."""
        if not self.kite:
            self.initialize()
        return self.kite.login_url()

    def generate_session(self, request_token):
        """Exchanges the token for an access_token (which lasts for 1 day)."""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Save the access token to a text file for reusing within the same day
            with open(config.ACCESS_TOKEN_FILE, 'w') as f:
                f.write(self.access_token)
                
            return True
        except Exception as e:
            print(f"Error generating Kite session: {e}")
            return False

    def get_options_data(self, instrument_tokens):
        """Uses kite.quote() to fetch the LTP and OI for multiple strikes at once."""
        if not self.kite or not self.access_token:
            return None
        return self.kite.quote(instrument_tokens)