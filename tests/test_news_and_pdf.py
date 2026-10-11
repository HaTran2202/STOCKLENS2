"""Offline regression tests for sentiment and PDF structure.
Run: python -m pytest -q tests/test_news_and_pdf.py
"""
import sys
import types
import importlib.util
from pathlib import Path
import pytest

if importlib.util.find_spec('feedparser') is None:
    sys.modules.setdefault('feedparser', types.SimpleNamespace(parse=lambda url: types.SimpleNamespace(entries=[])))

from src.news_analysis import _classify_sentiment


def test_mixed_news_is_not_positive():
    title = 'FPT gánh 2 sức ép, mất 4,5 tỷ USD vốn hóa bất chấp lợi nhuận tăng vọt'
    d = _classify_sentiment(title)
    assert d['sentiment'] == 'Neutral'
    assert d['reason'] == 'mixed'


def test_negative_news():
    assert _classify_sentiment('Cổ phiếu FPT mất giá, giảm điểm 11 phiên liên tiếp')['sentiment'] == 'Negative'


def test_pdf_from_offline_csv(tmp_path):
    pytest.importorskip('reportlab')
    import pandas as pd
    from src.csv_data import csv_ready, get_csv_financial_data, reconcile_market_snapshot
    from src.fundamental_analysis import analyze_fundamental
    from src.valuation import analyze_valuation
    from src.scoring import score_all
    from src.report import generate_pdf
    if not csv_ready():
        pytest.skip('Five annual CSV exports are required')
    info = reconcile_market_snapshot(get_csv_financial_data('FPT'), 57900)
    prices = [78000-i*120 for i in range(120)]
    frame = pd.DataFrame({'Date':pd.date_range('2026-01-01',periods=120,freq='B'),
                          'Close':prices, 'MA20':prices, 'MA50':prices, 'Volume':[500000]*120})
    technical = {'data_available':True, 'data':frame, 'close':57900,'ma20':63000,
                 'ma50':64000,'rsi':25,'volume_ratio':1.2,'macd':-500,'score':20,
                 'signals': {'MA': {'signal':'Negative', 'score':0}},
                 'commentary': 'Test only; not a real market observation.'}
    results = {'technical':technical,
               'fundamental':analyze_fundamental(info),
               'valuation':analyze_valuation(info,'FPT',57900),
               'news':{'score':50,'data_available':True,'classification':'Trung tính','items':[],
                       'commentary':'Chưa đủ tin tức.'},
               'risk':{'score':50,'data_available':True}}
    summary = score_all(results)
    company = {'name':'FPT','exchange':'HOSE','sector':'Chưa xác minh phân ngành',
               'report_period':'2025','market_cap':info.get('marketCap'),
               'pe':info.get('trailingPE'),'pb':info.get('priceToBook'),
               'last_date':'2026-10-09'}
    pdf = generate_pdf('FPT','2024-01-01 đến 2026-10-09',results,summary,
                       ['technical','fundamental','valuation','news','score','method'],
                       'Cân bằng',company,info)
    assert pdf.startswith(b'%PDF') and len(pdf)>30000
