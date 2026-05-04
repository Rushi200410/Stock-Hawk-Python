# =============================================================
# snapshot.py — OI Snapshot Manager
# Saves, loads, lists, deletes and compares OI snapshots.
# =============================================================

import json
import logging
import os
from datetime import date, datetime
from typing import Optional

import config

logger = logging.getLogger('snapshot')


def pct_change(new_val: float, old_val: float) -> float:
    if old_val == 0:
        return 0.0
    return round(((new_val - old_val) / abs(old_val)) * 100, 2)


class SnapshotManager:
    def __init__(self):
        self.folder = config.SNAPSHOT_FOLDER
        self._ensure_folder()

    def _ensure_folder(self):
        if not os.path.exists(self.folder):
            os.makedirs(self.folder, exist_ok=True)
            logger.info('Created snapshot folder: %s', self.folder)

    def save(self, all_chain_data: dict, label: str = '') -> str:
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f'snap_{timestamp}.json'
        filepath = os.path.join(self.folder, filename)
        payload = {
            'id': timestamp,
            'date': now.strftime('%d %b %Y'),
            'time': now.strftime('%H:%M:%S'),
            'datetime': now.isoformat(),
            'label': label,
            'source': 'live' if _is_live() else 'mock',
            'symbol_count': len(all_chain_data),
            'symbols': list(all_chain_data.keys()),
            'data': all_chain_data,
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=str)
            logger.info(
                'Snapshot saved: %s (%s symbols, %.1f KB)',
                filename,
                len(all_chain_data),
                _file_size_kb(filepath),
            )
            return filepath
        except Exception as e:
            logger.error('Failed to save snapshot: %s', e)
            return ''

    def load(self, snapshot_id: str) -> dict:
        if os.path.exists(snapshot_id):
            filepath = snapshot_id
        else:
            filename = f'snap_{snapshot_id}.json'
            filepath = os.path.join(self.folder, filename)
        if not os.path.exists(filepath):
            logger.warning('Snapshot not found: %s', snapshot_id)
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug('Loaded snapshot: %s', filepath)
            return data
        except Exception as e:
            logger.error('Failed to load snapshot %s: %s', filepath, e)
            return {}

    def list_snapshots(self, limit: int = 50) -> list:
        self._ensure_folder()
        files = sorted(
            [
                f for f in os.listdir(self.folder)
                if f.startswith('snap_') and f.endswith('.json')
            ],
            reverse=True,
        )[:limit]
        result = []
        for fname in files:
            filepath = os.path.join(self.folder, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    snap = json.load(f)
                result.append({
                    'id': snap.get('id', ''),
                    'date': snap.get('date', ''),
                    'time': snap.get('time', ''),
                    'datetime': snap.get('datetime', ''),
                    'label': snap.get('label', ''),
                    'source': snap.get('source', 'mock'),
                    'symbol_count': snap.get('symbol_count', 0),
                    'symbols': snap.get('symbols', []),
                    'filename': fname,
                    'size_kb': _file_size_kb(filepath),
                })
            except Exception as e:
                logger.warning('Could not read metadata for %s: %s', fname, e)
        logger.debug('Listed %s snapshots', len(result))
        return result

    def delete(self, snapshot_id: str) -> bool:
        filename = f'snap_{snapshot_id}.json'
        filepath = os.path.join(self.folder, filename)
        if not os.path.exists(filepath):
            logger.warning('Cannot delete — not found: %s', snapshot_id)
            return False
        try:
            os.remove(filepath)
            logger.info('Deleted snapshot: %s', filename)
            return True
        except Exception as e:
            logger.error('Failed to delete %s: %s', filename, e)
            return False

    def delete_all(self) -> int:
        count = 0
        for fname in os.listdir(self.folder):
            if fname.startswith('snap_') and fname.endswith('.json'):
                try:
                    os.remove(os.path.join(self.folder, fname))
                    count += 1
                except Exception as e:
                    logger.warning('Could not delete %s: %s', fname, e)
        logger.info('Deleted %s snapshots', count)
        return count

    def get_latest_pair(self, symbol: str) -> tuple:
        all_snaps = self.list_snapshots(limit=100)
        matching = [s for s in all_snaps if symbol in s.get('symbols', [])]
        if len(matching) < 2:
            logger.info(
                'Not enough snapshots for %s comparison (found %s)',
                symbol,
                len(matching),
            )
            return None, None
        latest_data = self.load(matching[0]['id'])
        prev_data = self.load(matching[1]['id'])
        return latest_data, prev_data

    def compare(self, snap_a_id: str, snap_b_id: str, symbol: str) -> dict:
        snap_a = self.load(snap_a_id)
        snap_b = self.load(snap_b_id)
        if not snap_a or not snap_b:
            return {'error': 'One or both snapshots not found'}
        data_a = snap_a.get('data', {}).get(symbol)
        data_b = snap_b.get('data', {}).get(symbol)
        if not data_a or not data_b:
            return {'error': f'Symbol {symbol} not found in one or both snapshots'}
        chain_a = {row['strike']: row for row in data_a.get('chain', [])}
        chain_b = {row['strike']: row for row in data_b.get('chain', [])}
        common = sorted(set(chain_a.keys()) & set(chain_b.keys()))
        thr = config.HAWK['oi_change_pct_threshold']
        rows = []
        for strike in common:
            a = chain_a[strike]
            b = chain_b[strike]
            d_ce_oi = b.get('ce_oi', 0) - a.get('ce_oi', 0)
            d_pe_oi = b.get('pe_oi', 0) - a.get('pe_oi', 0)
            pct_ce = pct_change(b.get('ce_oi', 0), a.get('ce_oi', 0))
            pct_pe = pct_change(b.get('pe_oi', 0), a.get('pe_oi', 0))
            d_ce_vol = b.get('ce_volume', 0) - a.get('ce_volume', 0)
            d_pe_vol = b.get('pe_volume', 0) - a.get('pe_volume', 0)
            ce_built = d_ce_oi > 0
            pe_built = d_pe_oi > 0
            if not ce_built and pe_built:
                signal = 'Bullish'
            elif ce_built and not pe_built:
                signal = 'Bearish'
            elif ce_built and pe_built:
                signal = 'Mixed'
            else:
                signal = 'Unwinding'
            is_major = abs(pct_ce) >= thr or abs(pct_pe) >= thr
            rows.append({
                'strike': strike,
                'is_atm': a.get('is_atm', False),
                'd_ce_oi': d_ce_oi,
                'd_pe_oi': d_pe_oi,
                'pct_ce_oi': pct_ce,
                'pct_pe_oi': pct_pe,
                'd_ce_vol': d_ce_vol,
                'd_pe_vol': d_pe_vol,
                'signal': signal,
                'is_major': is_major,
                'ce_oi_a': a.get('ce_oi', 0),
                'ce_oi_b': b.get('ce_oi', 0),
                'pe_oi_a': a.get('pe_oi', 0),
                'pe_oi_b': b.get('pe_oi', 0),
            })
        bullish_count = sum(1 for r in rows if r['signal'] == 'Bullish')
        bearish_count = sum(1 for r in rows if r['signal'] == 'Bearish')
        overall_signal = (
            'Bullish' if bullish_count > bearish_count + 1 else
            'Bearish' if bearish_count > bullish_count + 1 else
            'Mixed'
        )
        return {
            'symbol': symbol,
            'overall_signal': overall_signal,
            'snap_a': {
                'id': snap_a_id,
                'time': snap_a.get('time'),
                'date': snap_a.get('date'),
            },
            'snap_b': {
                'id': snap_b_id,
                'time': snap_b.get('time'),
                'date': snap_b.get('date'),
            },
            'pcr_a': data_a.get('pcr', 0),
            'pcr_b': data_b.get('pcr', 0),
            'pcr_delta': round(data_b.get('pcr', 0) - data_a.get('pcr', 0), 2),
            'max_pain_a': data_a.get('max_pain', 0),
            'max_pain_b': data_b.get('max_pain', 0),
            'mp_delta': data_b.get('max_pain', 0) - data_a.get('max_pain', 0),
            'total_ce_a': data_a.get('total_ce_oi', 0),
            'total_ce_b': data_b.get('total_ce_oi', 0),
            'total_pe_a': data_a.get('total_pe_oi', 0),
            'total_pe_b': data_b.get('total_pe_oi', 0),
            'rows': rows,
            'major_strikes': [r for r in rows if r['is_major']],
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'compared_at': datetime.now().isoformat(),
        }

    def get_stats(self) -> dict:
        self._ensure_folder()
        files = [
            f for f in os.listdir(self.folder)
            if f.startswith('snap_') and f.endswith('.json')
        ]
        total_kb = sum(
            _file_size_kb(os.path.join(self.folder, f))
            for f in files
        )
        return {
            'count': len(files),
            'total_kb': round(total_kb, 1),
            'folder': os.path.abspath(self.folder),
        }


def _file_size_kb(filepath: str) -> float:
    try:
        return os.path.getsize(filepath) / 1024
    except Exception:
        return 0.0


def _is_live() -> bool:
    try:
        from auth import kite_auth
        return kite_auth.is_authenticated()
    except Exception:
        return False


snapshot_manager = SnapshotManager()


if __name__ == '__main__':
    print('\n' + '=' * 55)
    print(' Kite OI Dashboard — Snapshot Manager Test')
    print('=' * 55)
    stats = snapshot_manager.get_stats()
    print('\n📁 Folder : %s' % stats['folder'])
    print(' Snapshots : %s' % stats['count'])
    print(' Disk used : %s KB' % stats['total_kb'])
    snaps = snapshot_manager.list_snapshots(limit=10)
    if snaps:
        print('\n📋 Last %s snapshots:' % len(snaps))
        print(' %s %s %s %s %s' % ('ID'.ljust(18), 'Date'.ljust(13), 'Time'.ljust(10), 'Syms'.ljust(5), 'KB'.rjust(5)))
        for s in snaps:
            print(
                ' %s %s %s %s %s' % (
                    s['id'].ljust(18),
                    s['date'].ljust(13),
                    s['time'].ljust(10),
                    str(s['symbol_count']).ljust(5),
                    '%.1fK' % s['size_kb'],
                )
            )
        nifty_snaps = [s for s in snaps if 'NIFTY' in s.get('symbols', [])]
        if len(nifty_snaps) >= 2:
            a_id = nifty_snaps[1]['id']
            b_id = nifty_snaps[0]['id']
            print('\n🔄 Comparing %s → %s for NIFTY...' % (a_id, b_id))
            comp = snapshot_manager.compare(a_id, b_id, 'NIFTY')
            if 'error' not in comp:
                print(' Overall signal : %s' % comp['overall_signal'])
                print(' PCR : %s → %s (Δ%s)' % (comp['pcr_a'], comp['pcr_b'], comp['pcr_delta']))
                print(' Max Pain : %s → %s (Δ%s)' % (comp['max_pain_a'], comp['max_pain_b'], comp['mp_delta']))
                print(' Major strikes : %s' % len(comp['major_strikes']))
