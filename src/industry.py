"""Conservative, auditable local sector reference; NOT an official ICB export.

To cover new tickers, extend data/sector_reference.csv using verified public
issuer/exchange information. Unknown symbols remain unknown.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import csv

SECTOR_FILE = Path(__file__).resolve().parents[1] / 'data' / 'sector_reference.csv'

@lru_cache(maxsize=1)
def _registry():
    if not SECTOR_FILE.exists():
        return {}
    with SECTOR_FILE.open(encoding='utf-8-sig', newline='') as file:
        return {str(row.get('ticker') or '').strip().upper(): row for row in csv.DictReader(file) if row.get('ticker')}

def industry_for(ticker: str) -> dict:
    symbol = str(ticker or '').upper().replace('.VN', '').strip()
    row = _registry().get(symbol)
    if not row:
        return {'ticker': symbol, 'sector': None, 'industry': None, 'exchange': None,
                'group': None, 'source': 'Không có trong bộ phân ngành tham khảo'}
    return {'ticker': symbol, 'sector': row.get('sector') or None,
            'industry': row.get('industry') or None, 'exchange': row.get('exchange') or None,
            'group': row.get('group') or None, 'note': row.get('notes') or '',
            'source': 'Bảng phân ngành tham khảo data/sector_reference.csv (không phải ICB chính thức)'}

def same_group_peers(ticker: str, limit: int = 15) -> list[str]:
    info = industry_for(ticker)
    group = info.get('group')
    if not group:
        return []
    return [k for k, row in _registry().items() if k != info['ticker'] and row.get('group') == group][:limit]


def peer_candidate_groups(ticker: str, limit: int = 35) -> list[dict]:
    """Return verified narrow-to-broad local peer universes for fallback.

    The registry has industry and sector labels but no official VN30/VNMidcap
    membership, so the function never invents an index fallback.
    """
    info = industry_for(ticker)
    symbol, registry = info.get('ticker'), _registry()
    candidates = []
    industry = info.get('industry')
    if industry:
        peers = [key for key, row in registry.items()
                 if key != symbol and row.get('industry') == industry]
        candidates.append({"level": "industry", "label": industry, "symbols": peers[:limit]})
    group = info.get('group')
    if group:
        peers = [key for key, row in registry.items()
                 if key != symbol and row.get('group') == group]
        if not candidates or set(peers) != set(candidates[0]["symbols"]):
            candidates.append({"level": "sector", "label": info.get("sector") or group,
                               "symbols": peers[:limit]})
    return candidates
