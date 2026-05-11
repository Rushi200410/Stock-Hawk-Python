import os
import json
import logging
from datetime import date
from kiteconnect import KiteConnect

import config

logger = logging.getLogger("auth")

class KiteAuthenticator:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.token_file = config.ACCESS_TOKEN_FILE

        # FIX 3 — initialise KiteConnect immediately in __init__
        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_url(self) -> str:
        """Returns the Zerodha login URL to get a request_token."""
        url = self.kite.login_url()
        logger.info(f"Login URL: {url}")
        return url

    def generate_session(self, request_token: str) -> str | None:
        """
        Exchanges request_token for a daily access_token.
        Saves token + today's date to file for reuse.
        Returns access_token string on success, None on failure.
        """
        try:
            data = self.kite.generate_session(
                request_token,
                api_secret=self.api_secret
            )
            access_token = data["access_token"]
            
            # Set on kite instance immediately
            self.kite.set_access_token(access_token)
            
            # FIX 2 — save token WITH today's date so we can detect expiry
            payload = {
                "access_token": access_token,
                "saved_date": date.today().isoformat(),
                "user_name": data.get("user_name", ""),
                "user_id": data.get("user_id", ""),
            }
            with open(self.token_file, "w") as f:
                json.dump(payload, f, indent=2)
            
            print(f"✅ Authentication successful — {data.get('user_name','')}")
            logger.info(f"Session generated for {data.get('user_name','')}")
            return access_token
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            logger.error(f"generate_session failed: {e}")
            return None

    def load_token(self) -> str | None:
        """
        Reads saved token from file IF it was saved today.
        Validates token by fetching profile.
        """
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    payload = json.load(f)
                    
                if payload.get("saved_date") != date.today().isoformat():
                    logger.info("Saved token is expired (not from today).")
                    return None
                    
                access_token = payload.get("access_token")
                if not access_token:
                    return None
                    
                self.kite.set_access_token(access_token)
                
                # Validate token by fetching profile (FIX 4 & 6)
                profile = self.kite.profile()
                print(f"✅ Token loaded successfully for {profile.get('user_name')}")
                return access_token
                
            except json.JSONDecodeError:
                logger.warning("Token file contains invalid JSON. Ignoring.")
            except Exception as e:
                logger.error(f"Saved token is invalid, expired, or failed to load: {e}")
                
        return None

    def get_options_data(self, instrument_tokens: list) -> dict | None:
        """
        Uses kite.quote() to fetch the LTP and OI for multiple strikes at once.
        Merged from KiteWorker with added error handling. (FIX 5 & 7)
        """
        if not self.kite or not self.kite.access_token:
            return None
        try:
            return self.kite.quote(instrument_tokens)
        except Exception as e:
            logger.error(f"Error fetching options data: {e}")
            return None