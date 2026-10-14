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


def test_stale_snapshot_falls_back_to_annual_financials():
    data = get_csv_financial_data('FPT')
    assert data['trailingPE'] is None
    bad = reconcile_market_snapshot(data, 65000)
    assert bad['trailingPE'] == pytest.approx(65000 / data['reportedAnnualEPS'])
    assert bad['priceToBook'] == pytest.approx(
        65000 / (data['totalEquity'] / bad['sharesOutstanding'])
    )
    assert bad['valuationFallbackUsed'] is True
    assert any('không dùng P/E/P/B snapshot' in warning for warning in bad['qualityWarnings'])

    good = reconcile_market_snapshot(data, 57900)
    assert good['trailingPE'] is not None and good['priceToBook'] is not None
    assert 57900/good['trailingEps'] == pytest.approx(good['trailingPE'])
    assert 57900/good['bookValue'] == pytest.approx(good['priceToBook'])
    assert good['valuationRatiosAreLive'] is False
    assert good['valuationFallbackUsed'] is False


def test_loss_making_ticker_still_scores_valid_price_to_book():
    data = get_csv_financial_data('TCD')
    reconciled = reconcile_market_snapshot(data, 33000)

    assert data['reportedAnnualEPS'] < 0
    assert reconciled['trailingPE'] is None
    assert reconciled['priceToBook'] > 0
    assert reconciled['valuationFallbackUsed'] is True
    assert any('P/E không có ý nghĩa' in warning for warning in reconciled['qualityWarnings'])

    valuation = analyze_valuation(reconciled, 'TCD', 33000)
    assert valuation['score'] is not None
    assert 'pb_absolute' in valuation['component_scores']
    assert valuation['valuation_fallback_used'] is True


def test_ticker_missing_from_csv_uses_vnstock_fallback(monkeypatch):
    import src.vnstock_data as vnstock_data

    monkeypatch.setenv('STOCKLENS_FINANCIAL_SOURCE', 'csv')
    monkeypatch.setattr(
        vnstock_data,
        '_get_financial_data_vnstock',
        lambda ticker, period: {'ticker': ticker, 'source': 'test provider'},
    )

    result = vnstock_data.get_financial_data('NOTINCSV', period='year')
    assert result == {'ticker': 'NOTINCSV', 'source': 'test provider'}


def test_unsupported_csv_mapping_uses_vnstock_fallback(monkeypatch):
    import src.csv_data as csv_data
    import src.vnstock_data as vnstock_data

    monkeypatch.setenv('STOCKLENS_FINANCIAL_SOURCE', 'csv')

    def unsupported_ticker(*args, **kwargs):
        raise ValueError('has no mapped corporate revenue')

    monkeypatch.setattr(csv_data, 'get_csv_financial_data', unsupported_ticker)
    monkeypatch.setattr(
        vnstock_data,
        '_get_financial_data_vnstock',
        lambda ticker, period: {'ticker': ticker, 'source': 'test provider'},
    )

    result = vnstock_data.get_financial_data('UNSUPPORTED', period='year')
    assert result == {'ticker': 'UNSUPPORTED', 'source': 'test provider'}


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
