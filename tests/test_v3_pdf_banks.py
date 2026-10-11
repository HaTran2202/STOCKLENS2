"""PDF end-to-end smoke tests with synthetic price data, not investment data."""
import io
import pandas as pd
import pytest
from src.csv_data import get_csv_financial_data,reconcile_market_snapshot
from src.valuation import analyze_valuation
from src.fundamental_analysis import analyze_fundamental
from src.scoring import score_all
from src.report import generate_pdf
from src.industry import industry_for

@pytest.mark.parametrize('ticker,price',[('FPT',57900),('GVR',32850),('MBB',25000)])
def test_pdf_generation_for_both_business_types(ticker,price):
    d=reconcile_market_snapshot(get_csv_financial_data(ticker), price)
    group=industry_for(ticker)
    prices=[price*1.2-i*price*.0015 for i in range(120)]
    frame=pd.DataFrame({'Date':pd.date_range('2026-01-01',periods=120,freq='B'),
        'Close':prices,'MA20':prices,'MA50':prices,'Volume':[500000]*120})
    results={'fundamental':analyze_fundamental(d),
        'valuation':analyze_valuation(d,ticker,price),
        'technical':{'data_available':True,'data':frame,'close':price,'ma20':price*1.04,
          'ma50':price*1.08,'rsi':41.2,'volume_ratio':1.1,'macd':-10,'score':50,
          'signals':{'MA':{'signal':'Neutral','score':50}},'commentary':'Biểu đồ giả lập chỉ dùng để kiểm thử.'},
        'news':{'score':None,'data_available':False,'items':[], 'commentary':'Không kiểm tra dữ liệu tin tức ở chế độ offline.'},
        'risk':{'score':50,'data_available':True}}
    summary=score_all(results)
    company={'name':ticker,'exchange':group['exchange'],'sector':group['industry'],
         'report_period':'2025','market_cap':d.get('marketCap'),'pe':d.get('trailingPE'),
         'pb':d.get('priceToBook'),'last_date':'N/A (giá giả lập kiểm thử)'}
    pdf=generate_pdf(ticker,'2024-01-01 đến 2026-10-09',results,summary,
        ['fundamental','valuation','technical','news','score','method'],'Cân bằng',company,d)
    assert pdf.startswith(b'%PDF') and len(pdf)>30000
    fitz=pytest.importorskip('fitz')
    document=fitz.open(stream=pdf,filetype='pdf')
    text='\n'.join(page.get_text() for page in document)
    assert 'Định giá và doanh nghiệp so sánh' in text
    assert 'Phân tích tình hình tài chính' in text
    assert group['industry'] in text
    assert 'BÁO CÁO PHÂN TÍCH CƠ HỘI ĐẦU TƯ' in document[0].get_text()
    assert 'Nội dung nghiên cứu' in document[1].get_text()
    assert len(document) >= 8
    if ticker=='MBB':
        assert 'NIM' in text and 'NPL' in text and 'CAR' in text
    assert text.find('Phân tích tình hình tài chính')<text.find('Định giá và doanh nghiệp so sánh')
