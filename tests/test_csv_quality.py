"""Offline smoke tests using CSV supplied with the project. Run: python -m pytest -q tests/test_csv_quality.py"""
import math
from pathlib import Path
import pytest
from src.csv_data import csv_ready, get_csv_financial_data, reconcile_market_snapshot
from src.fundamental_analysis import analyze_fundamental
from src.valuation import analyze_valuation

pytestmark = pytest.mark.skipif(not csv_ready(), reason='Missing five bundled CSV exports')

@pytest.mark.parametrize('ticker,revenue,profit,assets', [
    ('FPT', 70112.8251, 11232.3395, 88141.9916),
    ('GVR', 29078.0557, 5998.5609, 86282.4615),
])
def test_financial_2025_in_billions(ticker, revenue, profit, assets):
    row = get_csv_financial_data(ticker)
    assert row['reportPeriod'] == '2025'
    for key, expected in [('totalRevenue', revenue), ('netIncomeToCommon', profit), ('totalAssets', assets)]:
        assert row[key] / 1e9 == pytest.approx(expected, rel=0.001)
    assert row['source'].startswith('CSV')


def test_year_order_not_reversed():
    history = get_csv_financial_data('FPT')['financialHistory']
    rows = {r['period']:r for r in history}
    assert rows['2022']['revenue'] < rows['2023']['revenue'] < rows['2024']['revenue'] < rows['2025']['revenue']
    assert rows['2025']['net_profit'] > rows['2024']['net_profit']
    assert rows['2025']['equity'] is not None


def test_ratio_requires_market_price_match():
    data = get_csv_financial_data('FPT')
    assert data['trailingPE'] is None
    bad = reconcile_market_snapshot(data, 65000)
    assert bad['trailingPE'] is None and bad['priceToBook'] is None
    good = reconcile_market_snapshot(data, 57900)
    assert good['trailingPE'] is not None and good['priceToBook'] is not None
    assert 57900/good['trailingEps'] == pytest.approx(good['trailingPE'])
    assert 57900/good['bookValue'] == pytest.approx(good['priceToBook'])
    assert good['valuationRatiosAreLive'] is False


def test_fundamental_coverage_and_peer_runs_locally(monkeypatch):
    monkeypatch.delenv('STOCKLENS_ENABLE_PEER_API', raising=False)
    info = reconcile_market_snapshot(get_csv_financial_data('FPT'), 57900)
    fundamentals=analyze_fundamental(info)
    assert fundamentals['score'] is not None
    assert fundamentals['coverage']==6
    assert fundamentals['source'].startswith('CSV')
    valuation = analyze_valuation(info, 'FPT', 57900)
    assert valuation['peer_fair_value'] is None
    assert valuation['peer_score'] is not None
    assert len(valuation['peer_valuation']['peers']) >= 3


def test_missing_essentials_do_not_receive_score():
    info=get_csv_financial_data('FPT')
    info['totalAssets']=None
    result=analyze_fundamental(info)
    assert result['score'] is None
    assert result['quality_warnings']
