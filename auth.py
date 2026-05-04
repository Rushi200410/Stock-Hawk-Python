# =============================================================
# auth.py — Kite Connect Authentication
# Handles login URL, token generation, token storage,
# token validation, and session management.
# =============================================================

import json
import logging
import os
import sys
from datetime import date, datetime

from kiteconnect import KiteConnect

import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('auth')


class KiteAuth:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.token_file = config.ACCESS_TOKEN_FILE
        self.kite = KiteConnect(api_key=self.api_key)
        self._access_token = None

    def get_login_url(self) -> str:
        url = self.kite.login_url()
        logger.info('Login URL generated')
        return url

    def generate_session(self, request_token: str) -> dict:
        try:
            data = self.kite.generate_session(
                request_token,
                api_secret=self.api_secret,
            )
            access_token = data['access_token']
            self._save_token(access_token, data)
            self.kite.set_access_token(access_token)
            self._access_token = access_token
            logger.info(
                'Session generated for user: %s',
                data.get('user_name', 'unknown'),
            )
            return {
                'success': True,
                'access_token': access_token,
                'user_id': data.get('user_id', ''),
                'user_name': data.get('user_name', ''),
                'user_type': data.get('user_type', ''),
                'broker': data.get('broker', 'ZERODHA'),
                'login_time': str(data.get('login_time', '')),
            }
        except Exception as e:
            logger.error('generate_session failed: %s', e)
            return {'success': False, 'error': str(e)}

    def set_access_token(self, access_token: str) -> dict:
        try:
            self.kite.set_access_token(access_token)
            profile = self.kite.profile()
            self._access_token = access_token
            self._save_token(access_token, profile)
            logger.info('Access token set for: %s', profile.get('user_name', 'unknown'))
            return {
                'success': True,
                'access_token': access_token,
                'user_id': profile.get('user_id', ''),
                'user_name': profile.get('user_name', ''),
                'broker': profile.get('broker', 'ZERODHA'),
                'email': profile.get('email', ''),
            }
        except Exception as e:
            logger.error('set_access_token failed — token may be invalid: %s', e)
            return {'success': False, 'error': str(e)}

    def load_saved_token(self) -> bool:
        try:
            if not os.path.exists(self.token_file):
                logger.info('No saved token found — login required')
                return False
            with open(self.token_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            saved_date = data.get('saved_date', '')
            today = date.today().isoformat()
            if saved_date != today:
                logger.info('Saved token is from %s — expired', saved_date)
                return False
            access_token = data.get('access_token', '')
            if not access_token:
                logger.warning('Token file exists but access_token is empty')
                return False
            self.kite.set_access_token(access_token)
            self.kite.profile()
            self._access_token = access_token
            logger.info('Restored session from saved token')
            return True
        except Exception as e:
            logger.warning('Could not restore saved token: %s', e)
            return False

    def get_kite(self) -> KiteConnect:
        if not self._access_token:
            raise RuntimeError(
                'Not authenticated. Call set_access_token() or generate_session() first.'
            )
        return self.kite

    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def get_profile(self) -> dict:
        try:
            return self.kite.profile()
        except Exception as e:
            logger.error('get_profile failed: %s', e)
            return {}

    def logout(self) -> bool:
        try:
            self.kite.invalidate_access_token()
            self._access_token = None
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
            logger.info('Logged out successfully')
            return True
        except Exception as e:
            logger.error('Logout failed: %s', e)
            return False

    def _save_token(self, access_token: str, extra_data: dict = None):
        payload = {
            'access_token': access_token,
            'saved_date': date.today().isoformat(),
            'saved_at': datetime.now().isoformat(),
        }
        if extra_data:
            payload['user_id'] = extra_data.get('user_id', '')
            payload['user_name'] = extra_data.get('user_name', '')
            payload['broker'] = extra_data.get('broker', 'ZERODHA')
        try:
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            logger.info('Token saved to %s', self.token_file)
        except Exception as e:
            logger.error('Failed to save token: %s', e)

    def _load_token_data(self) -> dict:
        if not os.path.exists(self.token_file):
            return {}
        try:
            with open(self.token_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning('Failed to read token file: %s', e)
            return {}


kite_auth = KiteAuth()


if __name__ == '__main__':
    print('\n' + '=' * 50)
    print(' Kite OI Dashboard — Auth Test')
    print('=' * 50)

    if kite_auth.load_saved_token():
        profile = kite_auth.get_profile()
        print('\n✅ Session restored from saved token')
        print(' User :', profile.get('user_name'))
        print(' User ID :', profile.get('user_id'))
        print(' Broker :', profile.get('broker'))
        print(' Email :', profile.get('email'))
        sys.exit(0)

    if len(sys.argv) > 1:
        request_token = sys.argv[1]
        print('\nGenerating session with request_token: %s…' % request_token[:10])
        result = kite_auth.generate_session(request_token)
        if result['success']:
            print('✅ Session created for:', result['user_name'])
        else:
            print('❌ Error:', result['error'])
        sys.exit(0)

    print('\n⚠️ No valid saved token found.')
    print('\nOption A — Login via browser:')
    print(' 1. Open this URL in your browser:\n')
    print(' %s\n' % kite_auth.get_login_url())
    print(' 2. Log in with your Zerodha credentials')
    print(' 3. Copy the "request_token" from the redirect URL')
    print(' 4. Run: python auth.py <request_token>\n')
    print('Option B — Paste access token directly:')
    token = input('Paste access token (or press Enter to skip): ').strip()
    if token:
        result = kite_auth.set_access_token(token)
        if result['success']:
            print('\n✅ Connected as:', result.get('user_name'))
            print(' Broker:', result.get('broker'))
        else:
            print('\n❌ Failed:', result.get('error'))
    else:
        print('\nSkipped. Run main.py to start the dashboard.')
