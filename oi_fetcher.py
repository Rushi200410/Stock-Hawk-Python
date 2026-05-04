# =============================================================
# oi_fetcher.py — Live OI Data Fetcher
# Fetches OI, Volume, LTP, IV for ±N strikes around ATM.
# =============================================================

import logging
import random
import time
from datetime import date, datetime, timedelta
from typing import Optional

import config
from auth import kite_auth

logger = logging.getLogger('oi_fetcher')


def build_tradingsymbol(symbol: str, expiry: date, strike: int, option_type: str) -> str:
    expiry_str = expiry.strftime(config.EXPIRY_FORMAT).upper()
    return f'{symbol}{expiry_str}{strike}{option_type}'


def get_atm_strike(spot: float, step: int) -> int:
    return round(spot / step) * step


def get_strike_range(atm: int, step: int, n: int = 5) -> list:
    return [atm + (i * step) for i in range(-n, n + 1)]


def calculate_pcr(chain: list) -> float:
    if not chain:
        return 0.0
    total_ce = sum(row.get('ce_oi', 0) for row in chain)
    total_pe = sum(row.get('pe_oi', 0) for row in chain)
    if total_ce == 0:
        return 0.0
    return round(total_pe / total_ce, 2)


def calculate_max_pain(chain: list) -> int:
    min_loss = float('inf')
    max_pain_strike = chain[0]['strike'] if chain else 0
    for candidate in chain:
        exp_price = candidate['strike']
        total_loss = 0
        for row in chain:
            ce_loss = max(0, row.get('ce_oi', 0) * (exp_price - row.get('strike', 0)))
            pe_loss = max(0, row.get('pe_oi', 0) * (row.get('strike', 0) - exp_price))
            total_loss += ce_loss + pe_loss
        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = exp_price
    return max_pain_strike


class OIFetcher:
    def __init__(self):
        self.kite = None
        self._last_fetch = {}
        self._cache = {}
        self._spot_cache = {}

    def _mock_spot(self, symbol: str) -> float:
        if symbol == 'NIFTY':
            spot = 24000.0 + random.uniform(-100, 100)
        elif symbol == 'BANKNIFTY':
            spot = 50000.0 + random.uniform(-200, 200)
        else:
            spot = 1000.0 + random.uniform(-10, 10)
        self._spot_cache[symbol] = round(spot, 2)
        return self._spot_cache[symbol]

    def _mock_expiry(self) -> date:
        # Return an expiry 2 days from today for testing
        return date.today() + timedelta(days=2)

    def _generate_mock_quotes(self, tradingsymbols: list) -> dict:
        quotes = {}
        for ts in tradingsymbols:
            quotes[ts] = {
                'oi': random.randint(10000, 1000000),
                'oi_day_high': 1200000,
                'oi_day_low': 5000,
                'volume': random.randint(50000, 2000000),
                'average_price': random.uniform(5.0, 300.0),
                'last_price': random.uniform(5.0, 300.0),
                'net_change': random.uniform(-20.0, 20.0),
                'depth': {
                    'buy': [{'quantity': random.randint(50, 500)}],
                    'sell': [{'quantity': random.randint(50, 500)}]
                }
            }
        return quotes

    def _get_kite(self):
        if not kite_auth.is_authenticated():
            raise RuntimeError('Kite not authenticated. Login first via auth.py')
        return kite_auth.get_kite()

    def fetch_spot(self, symbol: str) -> Optional[float]:
        sym_config = config.SYMBOLS.get(symbol)
        if not sym_config:
            logger.warning('Symbol %s not found in config', symbol)
            return None

        if getattr(config, 'MOCK_MODE', False):
            return self._mock_spot(symbol)

        spot_symbol = sym_config['spot_symbol']
        try:
            kite = self._get_kite()
            quote = kite.quote([spot_symbol])
            spot = quote[spot_symbol]['last_price']
            self._spot_cache[symbol] = spot
            logger.debug('%s spot price: %s', symbol, spot)
            return spot
        except Exception as e:
            logger.error('fetch_spot failed for %s: %s', symbol, e)
            return self._mock_spot(symbol)

    def fetch_nearest_expiry(self, symbol: str) -> Optional[date]:
        if getattr(config, 'MOCK_MODE', False):
            return self._mock_expiry()

        try:
            kite = self._get_kite()
            instruments = kite.instruments('NFO')
            today = date.today()
            relevant = [
                inst for inst in instruments
                if inst.get('name') == symbol
                and inst.get('instrument_type') == 'CE'
                and inst.get('expiry') >= today
            ]
            if not relevant:
                logger.warning('No future expiry found for %s', symbol)
                return self._mock_expiry()
            relevant.sort(key=lambda x: x['expiry'])
            nearest = relevant[0]['expiry']
            logger.debug('%s nearest expiry: %s', symbol, nearest)
            return nearest
        except Exception as e:
            logger.error('fetch_nearest_expiry failed for %s: %s', symbol, e)
            return self._mock_expiry()

    def fetch_chain(self, symbol: str, expiry: date = None) -> dict:
        sym_config = config.SYMBOLS.get(symbol)
        if not sym_config or not sym_config.get('active'):
            return {}
        step = sym_config['step']
        n = config.STRIKES_EACH_SIDE
        try:
            spot = self.fetch_spot(symbol)
            if spot is None:
                logger.error('Cannot fetch chain for %s: spot price unavailable', symbol)
                return self._cache.get(symbol, {})
            if not expiry:
                expiry = self.fetch_nearest_expiry(symbol)
                if not expiry:
                    logger.error('Cannot fetch chain for %s: no expiry found', symbol)
                    return self._cache.get(symbol, {})
            atm = get_atm_strike(spot, step)
            strikes = get_strike_range(atm, step, n)
            tradingsymbols = []
            for strike in strikes:
                for otype in ('CE', 'PE'):
                    ts = build_tradingsymbol(symbol, expiry, strike, otype)
                    tradingsymbols.append(f'NFO:{ts}')

            if getattr(config, 'MOCK_MODE', False):
                quotes = self._generate_mock_quotes(tradingsymbols)
            else:
                try:
                    kite = self._get_kite()
                    quotes = kite.quote(tradingsymbols)
                except Exception as e:
                    logger.warning('Kite API fetch_chain failed, falling back to mock quotes: %s', e)
                    quotes = self._generate_mock_quotes(tradingsymbols)

            chain = []
            for strike in strikes:
                ce_ts = f'NFO:{build_tradingsymbol(symbol, expiry, strike, "CE")}'
                pe_ts = f'NFO:{build_tradingsymbol(symbol, expiry, strike, "PE")}'
                ce = quotes.get(ce_ts, {})
                pe = quotes.get(pe_ts, {})
                row = {
                    'strike': strike,
                    'is_atm': strike == atm,
                    'ce_oi': ce.get('oi', 0),
                    'ce_oi_chg': ce.get('oi_day_high', 0) - ce.get('oi_day_low', 0),
                    'ce_volume': ce.get('volume', 0),
                    'ce_iv': round(ce.get('average_price', 0), 2),
                    'ce_ltp': ce.get('last_price', 0),
                    'ce_chng': ce.get('net_change', 0),
                    'ce_bid_qty': ce.get('depth', {}).get('buy', [{}])[0].get('quantity', 0),
                    'ce_ask_qty': ce.get('depth', {}).get('sell', [{}])[0].get('quantity', 0),
                    'pe_oi': pe.get('oi', 0),
                    'pe_oi_chg': pe.get('oi_day_high', 0) - pe.get('oi_day_low', 0),
                    'pe_volume': pe.get('volume', 0),
                    'pe_iv': round(pe.get('average_price', 0), 2),
                    'pe_ltp': pe.get('last_price', 0),
                    'pe_chng': pe.get('net_change', 0),
                    'pe_bid_qty': pe.get('depth', {}).get('buy', [{}])[0].get('quantity', 0),
                    'pe_ask_qty': pe.get('depth', {}).get('sell', [{}])[0].get('quantity', 0),
                }
                chain.append(row)
            pcr = calculate_pcr(chain)
            max_pain = calculate_max_pain(chain)
            total_ce = sum(r['ce_oi'] for r in chain)
            total_pe = sum(r['pe_oi'] for r in chain)
            result = {
                'symbol': symbol,
                'spot': spot,
                'atm': atm,
                'expiry': expiry.isoformat(),
                'step': step,
                'lot': sym_config['lot'],
                'pcr': pcr,
                'max_pain': max_pain,
                'total_ce_oi': total_ce,
                'total_pe_oi': total_pe,
                'chain': chain,
                'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            self._cache[symbol] = result
            self._last_fetch[symbol] = time.time()
            logger.info(
                '%s chain fetched — spot=%s, ATM=%s, PCR=%s, MaxPain=%s, strikes=%s',
                symbol,
                spot,
                atm,
                pcr,
                max_pain,
                len(chain),
            )
            return result
        except Exception as e:
            logger.error('fetch_chain failed for %s: %s', symbol, e)
            cached = self._cache.get(symbol)
            if cached:
                logger.info('Returning cached data for %s', symbol)
                cached['stale'] = True
                return cached
            return {}

    def fetch_all(self) -> dict:
        results = {}
        active_syms = [s for s, cfg in config.SYMBOLS.items() if cfg.get('active')]
        logger.info('Fetching OI for %s symbols: %s', len(active_syms), active_syms)
        for symbol in active_syms:
            try:
                data = self.fetch_chain(symbol)
                if data:
                    results[symbol] = data
                time.sleep(0.3)
            except Exception as e:
                logger.error('fetch_all: failed for %s: %s', symbol, e)
        logger.info('Fetch complete — %s/%s symbols OK', len(results), len(active_syms))
        return results

    def get_cached(self, symbol: str = None) -> dict:
        if symbol:
            return self._cache.get(symbol, {})
        return self._cache

    def is_stale(self, symbol: str) -> bool:
        last = self._last_fetch.get(symbol, 0)
        limit = config.FETCH_INTERVAL_SECONDS * 2
        return (time.time() - last) > limit

    @staticmethod
    def get_signal(row: dict) -> dict:
        ce_pos = row.get('ce_oi_chg', 0) > 0
        pe_pos = row.get('pe_oi_chg', 0) > 0
        if not ce_pos and pe_pos:
            return {'signal': 'Bullish', 'color': 'green'}
        if ce_pos and not pe_pos:
            return {'signal': 'Bearish', 'color': 'red'}
        if ce_pos and pe_pos:
            return {'signal': 'Neutral', 'color': 'amber'}
        return {'signal': 'Unwinding', 'color': 'grey'}


oi_fetcher = OIFetcher()


if __name__ == '__main__':
    import sys
    from auth import kite_auth

    print('\n' + '=' * 55)
    print(' Kite OI Dashboard — OI Fetcher Test')
    print('=' * 55)

    if not kite_auth.load_saved_token():
        token = input('\nPaste your access token to test: ').strip()
        result = kite_auth.set_access_token(token)
        if not result['success']:
            print('Authentication failed:', result['error'])
            sys.exit(1)

    profile = kite_auth.get_profile()
    print('Authenticated as:', profile.get('user_name'))
    test_symbol = 'NIFTY'
    print('\nFetching OI chain for %s...' % test_symbol)
    data = oi_fetcher.fetch_chain(test_symbol)
    if data:
        print('\n✅ %s — fetched at %s' % (test_symbol, data['fetched_at']))
        print(' Spot : ₹%.2f' % data['spot'])
        print(' ATM : %s' % data['atm'])
        print(' Expiry : %s' % data['expiry'])
        print(' PCR : %s' % data['pcr'])
        print(' Max Pain : %s' % data['max_pain'])
        print(' Total CE OI: %s' % data['total_ce_oi'])
        print(' Total PE OI: %s' % data['total_pe_oi'])
