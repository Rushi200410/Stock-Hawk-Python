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

        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_url(self) -> str:
        """Returns the Zerodha login URL to get a request_token."""
        url = self.kite.login_url()
        logger.info("Login URL: %s", url)
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
                api_secret=self.api_secret,
            )
            access_token = data["access_token"]

            self.kite.set_access_token(access_token)

            payload = {
                "access_token": access_token,
                "saved_date": date.today().isoformat(),
                "user_name": data.get("user_name", ""),
                "user_id": data.get("user_id", ""),
            }
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            print(f"Authentication successful - {data.get('user_name', '')}")
            logger.info("Session generated for %s", data.get("user_name", ""))
            return access_token

        except Exception as e:
            print(f"Authentication failed: {e}")
            logger.error("generate_session failed: %s", e)
            return None

    def load_token(self, validate: bool = False) -> str | None:
        """
        Reads saved token from file if it was saved today.
        Validation is optional so startup stays fast.
        """
        if not os.path.exists(self.token_file):
            return None

        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if payload.get("saved_date") != date.today().isoformat():
                logger.info("Saved token is expired (not from today).")
                return None

            access_token = payload.get("access_token")
            if not access_token:
                return None

            self.kite.set_access_token(access_token)

            if validate:
                profile = self.kite.profile()
                print(f"Token loaded successfully for {profile.get('user_name')}")
            else:
                print("Token loaded successfully")
            return access_token

        except json.JSONDecodeError:
            logger.warning("Token file contains invalid JSON. Ignoring.")
        except Exception as e:
            logger.error("Saved token is invalid, expired, or failed to load: %s", e)

        return None

    def get_options_data(self, instrument_tokens: list) -> dict | None:
        """
        Uses kite.quote() to fetch the LTP and OI for multiple strikes at once.
        """
        if not self.kite or not self.kite.access_token:
            return None
        try:
            return self.kite.quote(instrument_tokens)
        except Exception as e:
            logger.error("Error fetching options data: %s", e)
            return None
