"""Peer comparison on a single downloaded CSV snapshot.

IMPORTANT: provider period_date is missing for the supplied snapshot. Peer
multiples are cross-sectional references only, NOT live or verified ICB peers.
Prices are deliberately hidden when earnings/share or peer quality is weak.
"""
from __future__ import annotations
import math
import statistics
from .csv_data import _cache_stamp, _load_tables, csv_dir, numeric, positive
from .industry import industry_for, same_group_peers


def _roe_fraction(v):
    """CSV ratios: decimal fraction (0.12 = 12%); leave missing untouched."""
    x = numeric(v)
    return x if x is None else (x / 100 if abs(x) > 1 else x)


def analyze_csv_peers(ticker, current_price=None, financial_data=None, max_peers=8):
    symbol = str(ticker or '').strip().upper().removesuffix('.VN')
    fin = financial_data or {}
    sector = industry_for(symbol)
    result = {
        'ticker':symbol, 'data_available':False, 'score':None,
        'classification':'Chưa đủ dữ liệu peer', 'source':'CSV stock.quanganh.org (snapshot không có ngày) + sector_reference.csv',
        'industry':sector.get('industry') or sector.get('sector'),
        'industry_icb_code':None, 'industry_icb_level':None,
        'peer_fair_value':None,'upside_downside':None, 'peer_median_pe':None,
        'indicative_peer_price':None,'indicative_upside':None,'indicative_label':None,
        'eps':None,'bvps':None,'eps_basis':None,'bvps_basis':None,
        'peer_median_pb':None, 'implied_price_pe':None, 'implied_price_pb':None,
        'peers':[], 'peer_quality':[], 'peer_quality_status':'Chưa đủ dữ liệu',
        'peer_quality_warnings':[], 'positives':[], 'risks':[], 'commentary':'', 'peer_count':0,
    }
    peer_symbols = same_group_peers(symbol, limit=35)
    if not peer_symbols:
        result['commentary']='Không có bảng phân ngành được xác minh cho mã này; cần bổ sung data/sector_reference.csv.'
        return result
    tables = _load_tables(str(csv_dir()), _cache_stamp())
    snapshots = tables['snapshot']; histories = tables['history']
    reference = snapshots.loc[snapshots['ticker']==symbol]
    reference = reference.iloc[0] if not reference.empty else None
    target_roe = _roe_fraction(reference.get('roe')) if reference is not None else _roe_fraction(fin.get('returnOnEquity'))
    target_cap = positive(reference.get('market_cap')) if reference is not None else None
    possible=[]
    for peer in peer_symbols:
        hits=snapshots.loc[snapshots['ticker']==peer]
        if hits.empty: continue
        row=hits.iloc[0]
        pe,pb=(numeric(row.get(k)) for k in ('pe','pb'))
        roe=_roe_fraction(row.get('roe'))
        if pe is None or pe<=0 or pe>=100 or pb is None or pb<=0 or pb>=15:
            continue
        # Period consistency: peers all come from same CSV snapshot export.
        cap=positive(row.get('market_cap'))
        similarity=abs(math.log(max(cap,1)/max(target_cap,1))) if cap and target_cap else 2.
        similarity+=abs((roe or 0)-(target_roe or 0))*5
        possible.append({'symbol':peer,'name':peer,'pe':pe,'pb':pb,'roe':roe,
                         'market_cap':cap,'similarity':similarity})
    peers=sorted(possible,key=lambda p:p['similarity'])[:max_peers]
    result['peers'] = peers
    result['peer_count'] = len(peers)
    result['peer_quality']=[{'symbol':p['symbol'],'status':'OK','flags':[]} for p in peers]
    if len(peers)<3:
        result['commentary']=f'Chỉ có {len(peers)} peers đủ P/E và P/B trong nhóm ngành tham khảo; cần ít nhất 3.'
        result['peer_quality_warnings'].append(result['commentary'])
        return result
    pe_med=statistics.median(p['pe'] for p in peers)
    pb_med=statistics.median(p['pb'] for p in peers)
    result['peer_median_pe']=pe_med
    result['peer_median_pb']=pb_med
    # Independently reported annual EPS may support an INDICATIVE P/E scenario.
    # It is NOT trailing EPS aligned with an undated peer market snapshot.
    source_eps = positive(fin.get('reportedAnnualEPS'))
    live_eps = positive(fin.get('trailingEps'))
    live_bvps = positive(fin.get('bookValue'))
    result['eps'] = live_eps or source_eps
    result['eps_basis'] = (fin.get('epsBasis') if live_eps else
                           f"EPS BCTC năm {fin.get('reportPeriod', 'chưa rõ')}, chưa đồng bộ thời điểm peers" if source_eps else None)
    result['bvps'] = live_bvps
    result['bvps_basis'] = fin.get('bvpsBasis') if live_bvps else None
    result['implied_price_pe'] = result['eps'] * pe_med if result['eps'] else None
    result['implied_price_pb'] = live_bvps * pb_med if live_bvps else None
    # These are arithmetic scenarios, NOT validated fair values.
    result['indicative_peer_price'] = result['implied_price_pe']
    result['indicative_label'] = 'Kịch bản P/E tham khảo, không phải giá mục tiêu' if result['indicative_peer_price'] else None
    market_price = positive(current_price)
    if market_price and result['indicative_peer_price']:
        result['indicative_upside'] = result['indicative_peer_price'] / market_price - 1
    target_pe=positive(fin.get('trailingPE'))
    target_pb=positive(fin.get('priceToBook'))
    if target_pe and target_pb:
        # Descriptive rank score only; it is not an investment recommendation.
        def relative_score(relative):
            return 100 if relative<=.75 else 80 if relative<=1 else 60 if relative<=1.20 else 35
        result['score']=round(.5*(relative_score(target_pe/pe_med)+relative_score(target_pb/pb_med)),2)
        result['classification']='So sánh multiples tham khảo'
        result['data_available']=True
    else:
        result['peer_quality_warnings'].append('Thiếu P/E hoặc P/B mục tiêu được đối chiếu với giá gần nhất.')
    peers_roe=[p['roe'] for p in peers if p['roe'] is not None]
    roe_gap=abs(statistics.median(peers_roe)-target_roe) if peers_roe and target_roe is not None else None
    has_negative=any(v<0 for v in peers_roe)
    dispersion=max(p['pe'] for p in peers)/min(p['pe'] for p in peers)
    if sector.get('note'):
        result['peer_quality_warnings'].append(sector['note'])
    if roe_gap is not None and roe_gap>.12:
        result['peer_quality_warnings'].append(f'ROE của mã và peer chênh nhau {roe_gap:.1%}; hạn chế diễn giải định giá.')
    if dispersion>4:
        result['peer_quality_warnings'].append('P/E peers phân tán rất lớn (>4 lần giữa cực trị).')
    if has_negative:
        result['peer_quality_warnings'].append('Có peer ROE âm.')
    result['peer_quality_warnings'].append('Các P/E, P/B của CSV không có ngày snapshot; không xác minh là tỷ số hiện tại.')
    # A peer reference price is shown only with enough valid peers, independent
    # P/E-P/B input verified against price, and comparable ROE. As-of caveat remains.
    price=positive(current_price)
    eps=live_eps
    bvps=live_bvps
    compatible=(len(peers)>=4 and not has_negative and dispersion<=4 and
                roe_gap is not None and roe_gap<=.12 and price and eps and bvps and
                fin.get('valuationRatioSourcePeriod'))
    if compatible:
        implied_pe=eps*pe_med; implied_pb=bvps*pb_med
        result['implied_price_pe']=implied_pe
        result['implied_price_pb']=implied_pb
        # Banking financial groups value P/B more prominently, software P/E more.
        w=.30 if sector.get('group')=='bank' else .70 if sector.get('group')=='information_technology' else .50
        fair=implied_pe*w+implied_pb*(1-w)
        result['peer_fair_value']=fair
        result['upside_downside']=fair/price-1
        result['peer_quality_status']='Tham khảo có điều kiện'
    else:
        result['peer_quality_status']='Chưa đủ tin cậy để ra giá tham chiếu'
        result['peer_quality_warnings'].append('Giữ bảng đối chiếu peers nhưng không xuất Peer Fair Value do không đạt tiêu chí chất lượng.')
    if target_pe and target_pb:
        result['commentary']=(f'So sánh {len(peers)} doanh nghiệp thuộc nhóm {result["industry"] or "cùng nhóm tham khảo"}: '
            f'P/E mục tiêu {target_pe:.2f}x so với median {pe_med:.2f}x; '
            f'P/B mục tiêu {target_pb:.2f}x so với median {pb_med:.2f}x. '
            'Các bội số là snapshot CSV không xác định ngày; đánh giá không phải định giá nội tại.')
    else:
        result['commentary']=(f'Đã lấy {len(peers)} peer cùng nhóm và median P/E {pe_med:.2f}x, P/B {pb_med:.2f}x, '
                              'nhưng mã mục tiêu thiếu tỷ số đủ tin cậy để so sánh tại giá mới.')
    result['risks'] = result['peer_quality_warnings'][:3]
    return result
