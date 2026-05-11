import os
import json
from kiteconnect import KiteConnect
import config

class KiteAuthenticator:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.token_file = config.ACCESS_TOKEN_FILE
        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_url(self):
        """Generates the URL for manual login."""
        return self.kite.login_url()

    def generate_session(self, request_token):
        """Exchanges request_token for a permanent daily access_token."""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = data["access_token"]
            
            # Save token to your existing access_token.txt
            with open(self.token_file, "w") as f:
                f.write(access_token)
            
            print("✅ Authentication Successful!")
            return access_token
        except Exception as e:
            print(f"❌ Authentication Failed: {e}")
            return None

    def load_token(self):
        """Reads the token from your file if it exists."""
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                return f.read().strip()
        return None