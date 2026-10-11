"""Bank, sector, peer, and PDF regression checks on the shipped CSV exports."""
import pytest
from src.csv_data import get_csv_financial_data, reconcile_market_snapshot
from src.industry import industry_for, same_group_peers
from src.fundamental_analysis import analyze_fundamental
from src.valuation import analyze_valuation
from src.csv_peer import analyze_csv_peers


@pytest.mark.parametrize('ticker', ['VCB','BID','MBB','TCB'])
def test_bank_specific_statement_and_scores(ticker):
    d=get_csv_financial_data(ticker)
    assert d['financialBusinessType']=='bank'
    assert d['totalRevenue'] > 1e12  # Bank operating income ISB38
    assert d['totalAssets'] > 1e12 and d['totalEquity'] > 1e11
    assert d['nplRatio'] is not None and d['netInterestMargin'] is not None
    assert d['llrRatio'] is None  # Not present in source
    r=analyze_fundamental(d)
    assert r['is_bank'] and r['score'] is not None
    assert 'npl_ratio' in r['component_scores']
    assert 'current_ratio' not in r['component_scores']
    assert 'profit_margin' not in r['component_scores']


@pytest.mark.parametrize('ticker,sector', [('FPT','Dịch vụ CNTT và phần mềm'),
    ('MBB','Ngân hàng'),('HPG','Sản xuất thép'),('GVR','Cao su và khu công nghiệp')])
def test_sector_is_consistent(ticker,sector):
    assert industry_for(ticker)['industry']==sector
    assert get_csv_financial_data(ticker)['industry']==sector


def test_sector_unknown_never_guessed():
    assert industry_for('ZZZNONEXISTENT')['industry'] is None
    assert same_group_peers('ZZZNONEXISTENT')==[]


def test_peer_is_computed_offline_and_respects_quality():
    f=reconcile_market_snapshot(get_csv_financial_data('FPT'),57900)
    p=analyze_csv_peers('FPT',57900,f)
    assert p['source'].startswith('CSV')
    assert len(p['peers'])>=3
    assert p['peer_median_pe']>0 and p['peer_median_pb']>0
    assert p['score'] is not None
    assert p['peer_fair_value'] is None  # ROE too dissimilar
    bad = reconcile_market_snapshot(get_csv_financial_data('MBB'), 25000)
    bank = analyze_csv_peers('MBB',25000,bad)
    assert len(bank['peers'])>=3
    assert bank['peer_median_pe']>0
    assert bank['peer_fair_value'] is None


def test_pdf_chapter_order_and_app_invalidation():
    from pathlib import Path
    source=(Path(__file__).parents[1]/'src/report.py').read_text(encoding='utf-8')
    expected=['("overview", "Tổng quan doanh nghiệp và ngành")',
              '("fundamental", "Phân tích tình hình tài chính")',
              '("valuation", "Định giá và doanh nghiệp so sánh")',
              '("technical", "Phân tích kỹ thuật")',
              '("news", "Tin tức và triển vọng")',
              '("score", "Investment Score và hồ sơ nhà đầu tư")',
              '("thesis", "Rủi ro và kết luận đầu tư")']
    starts=[source.find(x) for x in expected]
    assert -1 not in starts and starts==sorted(starts)
    app=(Path(__file__).parents[1]/'app.py').read_text(encoding='utf-8')
    assert "st.session_state.pop('analysis', None)" in app
    assert "st.session_state.pop('custom_pdf', None)" in app
    assert "custom_pdf_key" in app
