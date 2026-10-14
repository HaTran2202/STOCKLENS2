"""StockLens2 financial CSV adapter for the five stock.quanganh.org exports.

Reads FY values with explicit codes from the source (VND), never reverses years.
IMPORTANT: This adapter supports non-bank enterprises. Bank-specific accounting
is intentionally deferred to the vnstock/KBS fallback to avoid wrong mappings.
"""
from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'income': 'Income Statement.csv',
    'balance': 'Balance Sheet.csv',
    'cashflow': 'Cash Flow.csv',
    'history': 'Stock Metrics History.csv',
    'snapshot': 'Stock Metrics.csv',
}
COLS = {
    'income': ['ticker','period_kind','year','quarter','public_date','isa1','isa2','isa3','isa4','isa5','isa16','isa20','isa21','isa22','isa23','isb27','isb38'],
    'balance': ['ticker','period_kind','year','quarter','public_date','bsa1','bsa53','bsa54','bsa55','bsa78','bsa79','bsa96'],
    'cashflow': ['ticker','period_kind','year','quarter','public_date','cfa18','cfa19','cfa26','cfa32','cfa36'],
    'history': ['ticker','year_report','quarter_report','period_date','roe','roa','pe','pb','gross_margin','after_tax_margin','debt_to_equity','current_ratio','market_cap','shares','net_interest_margin','cir','car','casa_ratio','npl','ldr','loans_growth','deposit_growth'],
    'snapshot': ['ticker','period_date','roe','roa','pe','pb','gross_margin','after_tax_margin','debt_to_equity','current_ratio','market_cap','shares','net_interest_margin','cir','car','casa_ratio','npl','ldr','loans_growth','deposit_growth'],
}


def csv_dir() -> Path:
    """Pick the shipped CSV directory by default; allow an explicit override."""
    supplied = os.environ.get('STOCKLENS_CSV_DIR')
    if supplied:
        return Path(supplied).expanduser().resolve()
    for candidate in (ROOT / 'data' / 'raw', ROOT / 'data' / 'financials-market_2020-2026'):
        if all((candidate / name).is_file() and (candidate / name).stat().st_size > 0
               for name in FILES.values()):
            return candidate.resolve()
    return (ROOT / 'data' / 'financials-market_2020-2026').resolve()


def csv_ready() -> bool:
    base = csv_dir()
    return all((base / n).is_file() and (base / n).stat().st_size > 0 for n in FILES.values())


def numeric(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError, OverflowError):
        return None


def positive(v):
    n=numeric(v)
    return n if n is not None and n > 0 else None


def _cache_stamp():
    base=csv_dir()
    return tuple((n, (base / n).stat().st_mtime_ns if (base / n).exists() else None) for n in FILES.values())


@lru_cache(maxsize=3)
def _load_tables(directory: str, stamp: tuple):
    base=Path(directory)
    result={}
    for part, name in FILES.items():
        path=base / name
        if not path.is_file():
            raise FileNotFoundError(f'Missing CSV: {path}')
        if path.stat().st_size == 0:
            raise ValueError(f'File CSV rỗng: {path.name}; hãy tải lại file.')
        try:
            df = pd.read_csv(path, encoding='utf-8-sig', usecols=lambda col: col.strip().lower() in COLS[part], low_memory=False)
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f'CSV thiếu tiêu đề cột: {path.name}') from exc
        df.columns=[str(x).strip().lower() for x in df.columns]
        required = {'ticker'} if part == 'snapshot' else {'ticker', 'year_report'} if part == 'history' else {'ticker', 'year', 'period_kind'}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f'CSV {path.name} thiếu các cột bắt buộc: {sorted(missing)}')
        df['ticker']=df['ticker'].astype(str).str.strip().str.upper()
        result[part]=df
    return result


def _pick(table: pd.DataFrame, ticker: str, yr: int | None = None, *, field='year', kind=None):
    part=table.loc[table['ticker']==ticker].copy()
    if field in part and yr is not None:
        part=part.loc[pd.to_numeric(part[field],errors='coerce') == yr]
    if kind is not None:
        part=part.loc[part['period_kind'].astype(str).str.upper()==kind]
    if 'quarter' in part and kind=='YEAR':
        part=part.loc[pd.to_numeric(part['quarter'],errors='coerce').fillna(-1)==0]
    if 'quarter_report' in part:
        part=part.loc[pd.to_numeric(part['quarter_report'],errors='coerce').fillna(-1)==5]
    if part.empty:
        return None
    if 'public_date' in part:
        part=part.sort_values('public_date',ascending=False)
    if len(part)>1 and yr is not None:
        # Overlapping release rows for the same year require a clear choice;
        # use the latest publication timestamp, never blend values.
        pass
    return part.iloc[0]


def _parse_history_years(tables, ticker):
    income=tables['income']
    data=income.loc[(income['ticker']==ticker) & (income['period_kind'].astype(str).str.upper()=='YEAR')]
    years=[]
    for value in data['year'].dropna().unique():
        n=numeric(value)
        if n is not None and n.is_integer() and 2000<=n<=2100:
            years.append(int(n))
    return sorted(set(years))


def _statement_raw(years, rows):
    frame=[]
    for item_id, label, unit, values in rows:
        record={'item':label,'item_id':item_id,'unit':unit}
        record.update({str(y):values.get(y) for y in years})
        frame.append(record)
    return pd.DataFrame(frame)


def get_csv_financial_data(ticker: str, period: str='year') -> dict:
    """Return shape consumed by app.py, valuation.py, fundamental_analysis.py, report.py.

    Ratios from Stock Metrics.csv have no publication date; the raw snapshot P/E,
    P/B, capitalization are NOT returned as current until the independently
    fetched price is verified using reconcile_market_snapshot().
    """
    ticker=str(ticker).strip().upper().removesuffix('.VN')
    if not ticker:
        raise ValueError('Ticker cannot be empty')
    if period != 'year':
        raise ValueError('CSV export only includes yearly statements; choose year, or use KBS for quarter')
    tables = _load_tables(str(csv_dir()), _cache_stamp())
    years = _parse_history_years(tables, ticker)
    if not years:
        raise KeyError(f'Ticker {ticker} not present in Income Statement.csv')
    from .industry import industry_for
    classification = industry_for(ticker)
    latest_income = _pick(tables['income'], ticker, max(years), kind='YEAR')
    bank_operating_income = numeric(latest_income.get('isb38')) if latest_income is not None else None
    if classification.get('group') == 'bank' or (bank_operating_income is not None and bank_operating_income > 0):
        return _get_csv_bank_data(ticker, tables, years, classification)
    raw={}
    year_values={}
    for year in years:
        income=_pick(tables['income'],ticker,year,kind='YEAR')
        balance=_pick(tables['balance'],ticker,year,kind='YEAR')
        cash=_pick(tables['cashflow'],ticker,year,kind='YEAR')
        hist=_pick(tables['history'],ticker,year,field='year_report')
        def v(row,k): return numeric(row.get(k)) if row is not None else None
        # Accounting identities for ordinary enterprises: ISA3 net revenue, ISA20
        # group NPAT, ISA22 parent NPAT, BSA53 assets, BSA54 liabilities, BSA78 equity.
        r={'period':str(year),
           'revenue':v(income,'isa3'), 'gross_profit':v(income,'isa5'),
           'net_profit':v(income,'isa20'), 'parent_profit':v(income,'isa22'),
           'eps_fy':v(income,'isa23'), 'profit_before_tax':v(income,'isa16'),
           'total_assets':v(balance,'bsa53'), 'equity':v(balance,'bsa78'),
           'current_assets':v(balance,'bsa1'), 'total_liabilities':v(balance,'bsa54'),
           'current_liabilities':v(balance,'bsa55'),
           'operating_cash_flow':v(cash,'cfa18'), 'capex':v(cash,'cfa19'),
           'investing_cash_flow':v(cash,'cfa26'), 'financing_cash_flow':v(cash,'cfa32'),
           'cash_end':v(cash,'cfa36'),
           'roe':v(hist,'roe'), 'roa':v(hist,'roa'),
           'pe':v(hist,'pe'), 'pb':v(hist,'pb'),
           'current_ratio':v(hist,'current_ratio'), 'debt_to_equity':v(hist,'debt_to_equity'),
           'profit_margin':v(hist,'after_tax_margin'),
           'reported_at':str(income.get('public_date') or '')[:10] if income is not None else None}
        year_values[year]=r
    latest_year=max(years)
    latest=year_values[latest_year]
    if positive(latest['revenue']) is None:
        raise ValueError(f'{ticker} has no mapped corporate revenue (isa3); do not use corporate mapping for banks/insurers')
    warnings=[]
    # Check identity for every annual balance sheet: catching code mapping issues.
    for y,record in year_values.items():
        a,l,e=(record.get(k) for k in ('total_assets','total_liabilities','equity'))
        if all(numeric(t) is not None for t in (a,l,e)) and a:
            delta=abs(a-l-e)/abs(a)
            if delta > .005:
                raise ValueError(f'{ticker} {y}: assets != liabilities + equity ({delta:.2%} difference)')
    if len(years) < 2:
        warnings.append('Insufficient annual history for YoY growth')
    previous=year_values.get(latest_year-1)
    rv=latest.get('revenue')
    growth=(rv / previous['revenue']-1) if previous and positive(previous.get('revenue')) and rv else None
    cm=latest['net_profit']/rv if rv and latest['net_profit'] is not None else None
    ratios=latest
    # FPT's period 2025 revenue and profits match FY columns of source; never
    # infer earnings from the unrelated undated "current" snapshot at this stage.
    snapshot=_pick(tables['snapshot'], ticker)
    snap = {k:numeric(snapshot.get(k)) if snapshot is not None else None for k in ['pe','pb','shares','market_cap','roe','roa']}
    implied_price=snap['market_cap']/snap['shares'] if positive(snap['shares']) and positive(snap['market_cap']) else None
    snap_date=str(snapshot.get('period_date') or '').strip() if snapshot is not None else ''
    if snap_date.lower()=='nan':snap_date=''
    if not snap_date:
        warnings.append(
            'Current Stock Metrics snapshot has no period_date; use snapshot multiples only when '
            'the implied price matches the market, otherwise estimate from annual statements when possible.'
        )
    if latest.get('total_assets') is None or latest.get('equity') is None:
        warnings.append('Missing total assets or total equity in FY balance sheet')
    history=[{k:v for k,v in year_values[y].items() if k in ('period','revenue','gross_profit','net_profit','total_assets','equity','roe','roa','pe','pb')} for y in years]
    inc_fields=[('net_revenue','Doanh thu thuần','VND','revenue'),('gross_profit','Lợi nhuận gộp','VND','gross_profit'),('profit_before_tax','Lợi nhuận trước thuế','VND','profit_before_tax'),('net_profit','LNST hợp nhất','VND','net_profit'),('profit_to_parent','LNST thuộc cổ đông công ty mẹ','VND','parent_profit'),('eps','EPS cơ bản năm','VND/cp','eps_fy')]
    bs_fields=[('total_assets','Tổng tài sản','VND','total_assets'),('current_assets','Tài sản ngắn hạn','VND','current_assets'),('total_liabilities','Nợ phải trả','VND','total_liabilities'),('current_liabilities','Nợ ngắn hạn','VND','current_liabilities'),('total_equity','Vốn chủ sở hữu','VND','equity')]
    cf_fields=[('operating_cash_flow','Dòng tiền thuần HĐKD','VND','operating_cash_flow'),('capital_expenditure','Chi đầu tư TSCĐ (dòng tiền âm)','VND','capex'),('investing_cash_flow','Dòng tiền thuần HĐ đầu tư','VND','investing_cash_flow'),('financing_cash_flow','Dòng tiền thuần HĐ tài chính','VND','financing_cash_flow'),('cash_end','Tiền cuối kỳ','VND','cash_end')]
    ratio_fields=[('roe','ROE','ratio','roe'),('roa','ROA','ratio','roa'),('pe','P/E cuối năm theo nguồn','times','pe'),('pb','P/B cuối năm theo nguồn','times','pb'),('current_ratio','Current ratio','times','current_ratio'),('debt_to_equity','Debt to Equity','times','debt_to_equity')]
    def frame(fields):
        return _statement_raw(years,[(id,label,unit,{y:year_values[y].get(key) for y in years}) for id,label,unit,key in fields])
    raw={'income_statement':frame(inc_fields),'balance_sheet':frame(bs_fields),'cash_flow':frame(cf_fields),'ratios':frame(ratio_fields)}
    result={
      'ticker':ticker,'name':ticker,'exchange':classification.get('exchange'),'sector':classification.get('sector'),
      'industry':classification.get('industry'),'industrySource':classification.get('source'),'business_model':None,
      'financialBusinessType':'corporate','revenueMetricLabel':'Doanh thu','notApplicableMetrics':[],
      'returnOnEquity':latest.get('roe'),'returnOnAssets':latest.get('roa'),
      'profitMargins':cm,'revenueGrowth':growth,'debtToEquity':latest.get('debt_to_equity'),
      'currentRatio':latest.get('current_ratio'),'totalRevenue':latest.get('revenue'),
      'netIncomeToCommon':latest.get('net_profit'), # legacy means group NPAT here
      'netIncomeAttributableToParent':latest.get('parent_profit'),'grossProfit':latest.get('gross_profit'),
      'operatingCashFlow':latest.get('operating_cash_flow'), 'capitalExpenditures':latest.get('capex'),
      'totalAssets':latest.get('total_assets'),'currentAssets':latest.get('current_assets'),
      'totalLiabilities':latest.get('total_liabilities'),'currentLiabilities':latest.get('current_liabilities'),
      'totalEquity':latest.get('equity'),
      'trailingPE':None,'priceToBook':None,'forwardPE':None,'marketCap':None,
      'trailingEps':None,'bookValue':None, # avoid pairing annual EPS with unlabeled current ratios
      'reportedAnnualEPS':latest.get('eps_fy'),
       'reportedAnnualEPSPeriod':str(latest_year),
      'reportPeriod':str(latest_year),'financialStatementPeriod':str(latest_year),
      'balanceSheetPeriod':str(latest_year),'ratioPeriod':str(latest_year),'cashFlowPeriod':str(latest_year),
      'periodType':'year','source':f'CSV local stock.quanganh.org FY {latest_year}',
      'dataAvailable':True,'unitWarnings':[],'unitMetadataVerified':True,
      'valuationRatioSourcePeriod':None,'valuationRatiosAreLive':False,
      'qualityWarnings':warnings, 'criticalDataReady':latest.get('revenue') is not None and latest.get('net_profit') is not None,
      'netProfitBasis':'LNST hợp nhất (ISA20); profit attributable to parent reported separately (ISA22)',
      'financialHistory':history,'_raw':raw,
      '_csv_market_snapshot':{'pe':snap['pe'],'pb':snap['pb'],'market_cap':snap['market_cap'],
                              'shares':snap['shares'],'implied_price':implied_price,'period_date':snap_date},
      'csvDataYear':latest_year,'csvDataPath':str(csv_dir()),
    }
    return result


def _get_csv_bank_data(ticker, tables, years, classification):
    """Read bank-specific statement and ratios without manufacturing accounting fields.

    Source column ISB38 is reported bank total operating income; ISA20 is
    consolidated net income. Balance totals use reported BSA aggregates.
    Ratios NIM/CAR/NPL/CASA/LDR come DIRECTLY from provider-labelled CSV.
    LLR is not provided and MUST remain absent, not zero.
    """
    records = {}
    for year in years:
        inc = _pick(tables['income'], ticker, year, kind='YEAR')
        bal = _pick(tables['balance'], ticker, year, kind='YEAR')
        hist = _pick(tables['history'], ticker, year, field='year_report')
        def val(row, field): return numeric(row.get(field)) if row is not None else None
        record = {
            'period': str(year), 'revenue': val(inc, 'isb38'),
            'net_interest_income': val(inc, 'isb27'),
            'net_profit': val(inc, 'isa20'), 'parent_profit': val(inc, 'isa22'),
            'profit_before_tax': val(inc, 'isa16'), 'eps_fy': val(inc, 'isa23'),
            'total_assets': val(bal, 'bsa53'), 'total_liabilities': val(bal, 'bsa54'),
            'equity': val(bal, 'bsa78'),
            'roe': val(hist, 'roe'), 'roa': val(hist, 'roa'),
            'pe': val(hist, 'pe'), 'pb': val(hist, 'pb'),
            'net_interest_margin': val(hist, 'net_interest_margin'),
            'npl_ratio': val(hist, 'npl'), 'car': val(hist, 'car'),
            'casa_ratio': val(hist, 'casa_ratio'), 'ldr': val(hist, 'ldr'),
            'loans_growth': val(hist, 'loans_growth'),
            'deposit_growth': val(hist, 'deposit_growth'), 'cir': val(hist, 'cir')}
        records[year] = record
    latest_year = max(years); latest = records[latest_year]
    if positive(latest.get('revenue')) is None:
        raise ValueError(f'Ngân hàng {ticker} thiếu tổng thu nhập hoạt động ISB38; không thay bằng doanh thu ISA3')
    for year, row in records.items():
        a, l, eq = (row.get(k) for k in ('total_assets', 'total_liabilities', 'equity'))
        if a and l is not None and eq is not None and abs(a-l-eq)/abs(a) > .005:
            raise ValueError(f'{ticker} {year}: Tài sản khác Nợ + VCSH')
    snapshot = _pick(tables['snapshot'], ticker)
    snap = {k: numeric(snapshot.get(k)) if snapshot is not None else None
            for k in ['pe','pb','shares','market_cap','roe','roa']}
    implied = snap['market_cap']/snap['shares'] if positive(snap['shares']) and positive(snap['market_cap']) else None
    snapshot_date = str(snapshot.get('period_date') or '').strip() if snapshot is not None else ''
    if snapshot_date.lower() in ('nan','nat'): snapshot_date = ''
    warnings = []
    if not snapshot_date:
        warnings.append(
            'P/E P/B snapshot CSV chưa có ngày xác minh; nếu không khớp giá thị trường, '
            'hệ thống sẽ ước tính từ BCTC năm gần nhất khi đủ dữ liệu.'
        )
    if latest.get('npl_ratio') is None: warnings.append('Thiếu NPL của ngân hàng.')
    if latest.get('car') is None: warnings.append('Thiếu CAR của ngân hàng.')
    prev = records.get(latest_year-1)
    growth = (latest['revenue']/prev['revenue']-1) if prev and positive(prev.get('revenue')) else None
    history = [{k: v for k,v in records[y].items() if k in ('period','revenue','net_profit','total_assets','equity','roe','roa','pe','pb','net_interest_margin','npl_ratio','car','casa_ratio','ldr','loans_growth')}
               for y in sorted(years)]
    def raw_frame(fields):
        return _statement_raw(years, [(field, label, unit, {y:records[y].get(key) for y in years})
                                     for field,label,unit,key in fields])
    bank_raw = {
        'income_statement': raw_frame([('operating_income','Tổng thu nhập hoạt động','VND','revenue'),
              ('net_interest_income','Thu nhập lãi thuần','VND','net_interest_income'),
              ('net_profit','LNST hợp nhất','VND','net_profit'),
              ('parent_profit','LNST thuộc CĐ mẹ','VND','parent_profit')]),
        'balance_sheet': raw_frame([('total_assets','Tổng tài sản','VND','total_assets'),
             ('total_liabilities','Nợ phải trả','VND','total_liabilities'),
             ('total_equity','Vốn chủ sở hữu','VND','equity')]),
        'cash_flow': pd.DataFrame(),
        'ratios': raw_frame([('roe','ROE','ratio','roe'),('roa','ROA','ratio','roa'),
             ('nim','NIM','ratio','net_interest_margin'),('npl','NPL','ratio','npl_ratio'),
             ('car','CAR','ratio','car'),('casa','CASA','ratio','casa_ratio'),
             ('ldr','LDR','ratio','ldr'),('credit_growth','Tăng trưởng tín dụng','ratio','loans_growth')])}
    return {
        'ticker':ticker, 'name':ticker, 'sector':classification.get('sector') or 'Tài chính',
        'industry':classification.get('industry') or 'Ngân hàng',
        'exchange':classification.get('exchange'), 'industrySource':classification.get('source'),
        'financialBusinessType':'bank', 'revenueMetricLabel':'Tổng thu nhập hoạt động',
        'notApplicableMetrics':['gross_margin','current_ratio','debt_to_equity','profit_margin'],
        'totalRevenue':latest.get('revenue'), 'netIncomeToCommon':latest.get('net_profit'),
        'netIncomeAttributableToParent':latest.get('parent_profit'),
        'netInterestIncome':latest.get('net_interest_income'),
        'returnOnEquity':latest.get('roe'),'returnOnAssets':latest.get('roa'),
        'netInterestMargin':latest.get('net_interest_margin'), 'nplRatio':latest.get('npl_ratio'),
        'capitalAdequacyRatio':latest.get('car'), 'casaRatio':latest.get('casa_ratio'),
        'loanToDepositRatio':latest.get('ldr'), 'loansGrowth':latest.get('loans_growth'),
        'depositGrowth':latest.get('deposit_growth'), 'llrRatio':None,
        'totalAssets':latest.get('total_assets'), 'totalLiabilities':latest.get('total_liabilities'),
        'totalEquity':latest.get('equity'), 'revenueGrowth':growth,
        'trailingPE':None,'priceToBook':None,'trailingEps':None,'bookValue':None,'marketCap':None,
        'reportedAnnualEPS':latest.get('eps_fy'),
       'reportedAnnualEPSPeriod':str(latest_year),
        'reportPeriod':str(latest_year),'financialStatementPeriod':str(latest_year),
        'balanceSheetPeriod':str(latest_year),'ratioPeriod':str(latest_year),
        'periodType':'year','source':f'CSV local stock.quanganh.org ngân hàng FY {latest_year}',
        'dataAvailable':True, 'criticalDataReady':all(latest.get(k) is not None for k in ('net_profit','total_assets','equity')),
        'unitMetadataVerified':True, 'qualityWarnings':warnings, 'financialHistory':history,
        'netProfitBasis':'LNST hợp nhất ISA20; CĐ mẹ ISA22 riêng',
        '_raw':bank_raw, 'valuationRatiosAreLive':False, 'valuationRatioSourcePeriod':None,
        '_csv_market_snapshot':{'pe':snap['pe'],'pb':snap['pb'],'shares':snap['shares'],
                                'market_cap':snap['market_cap'],'implied_price':implied,'period_date':snapshot_date},
        'csvDataYear':latest_year, 'csvDataPath':str(csv_dir()),
    }


def reconcile_market_snapshot(info: dict, price: float, tolerance: float=.015) -> dict:
    """Use snapshot ratios only when their implied price matches the live quote.

    If the snapshot is absent, invalid, or stale, estimate ratios from the latest
    annual statements and the supplied market price instead of treating old
    snapshot multiples as current.
    """
    out=dict(info)
    snap=out.get('_csv_market_snapshot')
    if not isinstance(snap,dict):
        return out
    out['trailingPE']=None
    out['priceToBook']=None
    out['trailingEps']=None
    out['bookValue']=None
    out['marketCap']=None
    out['sharesOutstanding']=None
    out['valuationRatioSourcePeriod']=None
    out['valuationFallbackUsed']=False
    out.pop('epsBasis', None)
    out.pop('bvpsBasis', None)
    out.pop('trailingPEBasis', None)
    out.pop('priceToBookBasis', None)
    p=positive(price)
    implied_snapshot_price=positive(snap.get('implied_price'))
    warnings=list(out.get('qualityWarnings', []) or [])
    if not p:
        warnings.append('Thiếu giá thị trường hợp lệ; không thể cập nhật P/E hoặc P/B.')
        out['qualityWarnings']=warnings
        return out

    snapshot_matches = False
    if implied_snapshot_price:
        difference=abs(p-implied_snapshot_price)/p
        snapshot_matches=difference<=tolerance
        if not snapshot_matches:
            warnings.append(
                f'Giá hàm ý snapshot {implied_snapshot_price:,.0f} VND lệch giá thị trường '
                f'{p:,.0f} ({difference:.1%}); không dùng P/E/P/B snapshot.'
            )
    elif any(positive(snap.get(key)) for key in ('pe', 'pb')):
        warnings.append('Snapshot thiếu giá hàm ý để đối chiếu; không dùng P/E/P/B snapshot.')

    pe=None
    pb=None
    shares=None
    if snapshot_matches:
        pe=positive(snap.get('pe'))
        pb=positive(snap.get('pb'))
        shares=positive(snap.get('shares'))
        out['marketCap']=positive(snap.get('market_cap'))
        out['trailingEps']=(p/pe) if pe else None
        out['bookValue']=(p/pb) if pb else None
        out['epsBasis']='EPS hàm ý từ Stock Metrics snapshot không có ngày'
        out['bvpsBasis']='BVPS hàm ý từ Stock Metrics snapshot không có ngày'
        out['trailingPEBasis']='P/E snapshot đối chiếu giá thị trường'
        out['priceToBookBasis']='P/B snapshot đối chiếu giá thị trường'
        out['valuationRatioSourcePeriod']='Undated CSV snapshot matched to market price'
        warnings.append(
            'P/E/P/B snapshot đã khớp giá hàm ý với giá thị trường; snapshot không có ngày công bố.'
        )

    if pe is None or pb is None:
        annual_eps = numeric(out.get('reportedAnnualEPS'))
        annual_period = str(out.get('reportedAnnualEPSPeriod') or out.get('reportPeriod') or 'không rõ kỳ')
        if pe is None and annual_eps is not None and annual_eps > 0:
            pe=p/annual_eps
            out['trailingEps']=annual_eps
            out['epsBasis']=f'EPS BCTC năm {annual_period}; chưa phải EPS TTM'
            out['trailingPEBasis']=f'P/E tham chiếu = giá thị trường / EPS BCTC năm {annual_period}'

        if pb is None:
            shares_from_snapshot=positive(snap.get('shares'))
            parent_profit=numeric(out.get('netIncomeAttributableToParent'))
            weighted_shares=None
            if parent_profit is not None and annual_eps not in (None, 0):
                candidate=positive(parent_profit/annual_eps)
                if candidate is not None:
                    weighted_shares=candidate
            if shares_from_snapshot and weighted_shares:
                difference_in_shares=abs(shares_from_snapshot-weighted_shares)/weighted_shares
                shares=shares_from_snapshot if difference_in_shares<=.20 else weighted_shares
                if difference_in_shares>.20:
                    warnings.append(
                        'Số cổ phiếu snapshot lệch trên 20% so với LNST cổ đông mẹ/EPS năm; '
                        'dùng số cổ phiếu bình quân hàm ý từ BCTC để ước tính P/B.'
                    )
            else:
                shares=shares_from_snapshot or weighted_shares

            equity=positive(out.get('totalEquity'))
            if equity and shares:
                book_value=equity/shares
                if book_value>0:
                    pb=p/book_value
                    out['bookValue']=book_value
                    out['sharesOutstanding']=shares
                    out['priceToBookBasis']=(
                        f'P/B tham chiếu = giá thị trường / BVPS ước tính từ VCSH FY {annual_period} '
                        'và số cổ phiếu'
                    )

        fallback_used=pe is not None or pb is not None
        if fallback_used:
            out['valuationFallbackUsed']=True
            out['valuationRatioSourcePeriod']=f'FY {annual_period} statements + current market price (estimated ratios)'
            warnings.append(
                f'P/E/P/B thiếu hoặc snapshot không khớp: dùng EPS năm {annual_period} và/hoặc '
                'VCSH, số cổ phiếu để tính multiple tham chiếu theo giá hiện tại; đây không phải tỷ số TTM trực tiếp.'
            )
        if pe is None and annual_eps is not None and annual_eps <= 0:
            warnings.append(
                f'EPS năm {annual_period} không dương; P/E không có ý nghĩa và không được chấm điểm.'
            )

    out['trailingPE']=pe
    out['priceToBook']=pb
    out['currentPrice']=p
    out['valuationRatiosAreLive']=False
    out['valuationFallbackUsed']=bool(out.get('valuationFallbackUsed', False))
    if shares:
        out['sharesOutstanding']=shares
        out['marketCap']=p*shares
    out['qualityWarnings']=list(dict.fromkeys(warnings))
    return out
