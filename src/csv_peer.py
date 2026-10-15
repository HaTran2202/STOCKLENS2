"""Peer comparison on a single downloaded CSV snapshot.

IMPORTANT: provider period_date is missing for the supplied snapshot. Peer
multiples are cross-sectional references only, NOT live or verified ICB peers.
Prices are deliberately hidden when earnings/share or peer quality is weak.
"""
from __future__ import annotations
import math
import statistics
from .csv_data import _cache_stamp, _load_tables, csv_dir, numeric, positive
from .industry import industry_for, peer_candidate_groups, same_group_peers


def _roe_fraction(v):
    """CSV ratios: decimal fraction (0.12 = 12%); leave missing untouched."""
    x = numeric(v)
    return x if x is None else (x / 100 if abs(x) > 1 else x)


def _percentile(values, q):
    """Linear-interpolation percentile of positive values; None if unusable."""
    vals = sorted(float(v) for v in values if v is not None and float(v) > 0)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = q * (len(vals) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def _peer_scenarios(peers, eps, bvps, price):
    """Bull/base/bear from the peer P/E and P/B distribution.

    Uses the 25th/50th/75th percentile of the ACTUAL peer multiples. No
    probability is assigned: these are reference bands, not forecasts.
    """
    pe_list = [p.get('pe') for p in peers]
    pb_list = [p.get('pb') for p in peers]
    if not pe_list and not pb_list:
        return {'available': False, 'reason': 'Không có bội số peer hợp lệ để dựng kịch bản.'}

    def price_at(pe_mult, pb_mult):
        methods = []
        if eps is not None and eps > 0 and pe_mult:
            methods.append(eps * pe_mult)
        if bvps and pb_mult:
            methods.append(bvps * pb_mult)
        return sum(methods) / len(methods) if methods else None

    def band(q):
        pe_mult, pb_mult = _percentile(pe_list, q), _percentile(pb_list, q)
        value = price_at(pe_mult, pb_mult)
        return {'pe_multiple': pe_mult, 'pb_multiple': pb_mult, 'price': value,
                'upside': (value / price - 1) if value is not None and price else None}

    bear, base, bull = band(0.25), band(0.5), band(0.75)
    if all(b['price'] is None for b in (bear, base, bull)):
        return {'available': False, 'reason': 'Thiếu EPS dương hoặc BVPS để quy đổi kịch bản.'}
    return {
        'available': True,
        'assumption': ('Kịch bản tham chiếu suy ra từ phân bố P/E, P/B thực tế của '
                       'nhóm peer (bách phân vị 25/50/75). Không gán xác suất và không '
                       'phải dự báo giá.'),
        'no_probability': True,
        'bear': bear, 'base': base, 'bull': bull,
    }


def analyze_csv_peers(ticker, current_price=None, financial_data=None, max_peers=8,
                      peer_symbols=None):
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
        'peer_median_pb':None, 'peer_median_roe':None,
        'pe_peers_median':None,'pb_peers_median':None,'roe_peers_median':None,
        'peers_table':[],'is_fallback':False,'fallback_level':None,'fallback_note':None,
        'fallback':{'is_fallback':False,'fallback_level':None,'note':None},
        'fair_value_pe':None,'fair_value_pb':None,'upside_commentary':None,
        'implied_price_pe':None, 'implied_price_pb':None,
        'peers':[], 'peer_quality':[], 'peer_quality_status':'Chưa đủ dữ liệu',
        'peer_quality_warnings':[], 'positives':[], 'risks':[], 'commentary':'', 'peer_count':0,
        'scenarios':{'available':False,'reason':'Chưa đủ dữ liệu để dựng kịch bản.'},
    }
    custom_selection = peer_symbols is not None
    candidate_groups = peer_candidate_groups(symbol, limit=35)
    automatic_symbols = candidate_groups[0]["symbols"] if candidate_groups else same_group_peers(symbol, limit=35)
    if custom_selection:
        selected_symbols = list(dict.fromkeys(
            str(value).strip().upper().removesuffix('.VN')
            for value in (peer_symbols or []) if str(value).strip()
        ))
        selected_symbols = [value for value in selected_symbols if value != symbol]
        groups = [{"level": "custom", "label": "Danh sách do người dùng chọn", "symbols": selected_symbols}]
        peer_symbols = selected_symbols
    else:
        peer_symbols = automatic_symbols
        groups = candidate_groups or [{"symbols": peer_symbols, "level": "sector", "label": sector.get("sector")}]
    if not peer_symbols:
        result['requested_peers'] = []
        result['commentary'] = ('Chưa chọn doanh nghiệp đối chiếu.' if custom_selection else
                                'Không có bảng phân ngành được xác minh cho mã này; cần bổ sung data/sector_reference.csv.')
        return result
    tables = _load_tables(str(csv_dir()), _cache_stamp())
    snapshots = tables['snapshot']; histories = tables['history']
    reference = snapshots.loc[snapshots['ticker']==symbol]
    reference = reference.iloc[0] if not reference.empty else None
    target_roe = _roe_fraction(reference.get('roe')) if reference is not None else _roe_fraction(fin.get('returnOnEquity'))
    target_cap = positive(reference.get('market_cap')) if reference is not None else None
    peers=[]
    selected_group = groups[0]
    fallback = False
    for group_index, group in enumerate(groups):
        possible=[]
        for peer in group.get("symbols", []):
            hits=snapshots.loc[snapshots['ticker']==peer]
            if hits.empty: continue
            row=hits.iloc[0]
            pe,pb=(numeric(row.get(k)) for k in ('pe','pb'))
            roe=_roe_fraction(row.get('roe'))
            if pe is None or pe<=0 or pe>=100 or pb is None or pb<=0 or pb>=15:
                continue
            cap=positive(row.get('market_cap'))
            similarity=abs(math.log(max(cap,1)/max(target_cap,1))) if cap and target_cap else 2.
            similarity+=abs((roe or 0)-(target_roe or 0))*5
            net_margin = None
            revenue_growth = None
            try:
                from .csv_data import get_csv_financial_data
                peer_fin = get_csv_financial_data(peer)
                peer_history = sorted(peer_fin.get('financialHistory') or [],
                                      key=lambda item: str(item.get('period') or ''))
                if peer_history:
                    latest_peer = peer_history[-1]
                    previous_peer = peer_history[-2] if len(peer_history) > 1 else {}
                    rev = numeric(latest_peer.get('revenue'))
                    profit = numeric(latest_peer.get('net_profit'))
                    old_rev = numeric(previous_peer.get('revenue'))
                    net_margin = profit / rev if profit is not None and rev not in (None, 0) else None
                    revenue_growth = rev / old_rev - 1 if rev is not None and old_rev not in (None, 0) else None
            except Exception:
                pass
            possible.append({'symbol':peer,'name':peer,'pe':pe,'pb':pb,'roe':roe,
                             'net_margin':net_margin,'revenue_growth':revenue_growth,
                             'market_cap':cap,'similarity':similarity})
        if not custom_selection:
            possible=sorted(possible,key=lambda p:p['similarity'])
        if len(possible)>=3 or group_index==len(groups)-1:
            peers=possible[:max_peers]
            selected_group=group
            fallback=group_index>0
            break
    result['is_fallback']=fallback
    result['fallback_level']=selected_group.get('label') if fallback else None
    if fallback:
        result['industry']=selected_group.get('label') or result['industry']
    result['fallback_note']=("Do chưa đủ 3 mã hợp lệ ở nhóm ngành hẹp, định giá peer tham chiếu theo nhóm ngành rộng hơn."
                             if fallback else None)
    result['fallback']={'is_fallback':fallback,'fallback_level':result['fallback_level'],
                        'note':result['fallback_note']}
    result['industry_reference_level']=selected_group.get('level')
    result['requested_peers'] = list(peer_symbols)
    result['peers'] = peers
    result['peer_count'] = len(peers)
    result['peer_quality']=[{'symbol':p['symbol'],'status':'OK','flags':[]} for p in peers]
    result['peers_table']=[{'ticker':p['symbol'],'company_name':p.get('name') or p['symbol'],
                            'pe':p.get('pe'),'pb':p.get('pb'),'roe':p.get('roe'),
                            'net_margin':p.get('net_margin'),'revenue_growth':p.get('revenue_growth')} for p in peers]
    early_eps = numeric(fin.get('reportedAnnualEPS'))
    if early_eps is not None and early_eps <= 0:
        result['peer_quality_warnings'].append('EPS không dương; bỏ qua giá trị hàm ý P/E do doanh nghiệp đang lỗ.')
    if len(peers)<3:
        result['commentary']=f'Chỉ có {len(peers)} peers đủ P/E và P/B trong nhóm ngành tham khảo; cần ít nhất 3.'
        result['peer_quality_warnings'].append(result['commentary'])
        return result
    pe_med=statistics.median(p['pe'] for p in peers)
    pb_med=statistics.median(p['pb'] for p in peers)
    result['peer_median_pe']=pe_med
    result['peer_median_pb']=pb_med
    result['peer_median_roe']=statistics.median(p['roe'] for p in peers if p.get('roe') is not None) if any(p.get('roe') is not None for p in peers) else None
    result['pe_peers_median']=pe_med
    result['pb_peers_median']=pb_med
    result['roe_peers_median']=result['peer_median_roe']
    result['peers_table']=[{'ticker':p['symbol'],'company_name':p.get('name') or p['symbol'],
                            'pe':p.get('pe'),'pb':p.get('pb'),'roe':p.get('roe'),
                            'net_margin':p.get('net_margin'),'revenue_growth':p.get('revenue_growth')} for p in peers[:5]]
    # Independently reported annual EPS may support an INDICATIVE P/E scenario.
    # It is NOT trailing EPS aligned with an undated peer market snapshot.
    reported_eps = numeric(fin.get('reportedAnnualEPS'))
    source_eps = positive(reported_eps)
    live_eps = positive(fin.get('trailingEps'))
    live_bvps = positive(fin.get('bookValue'))
    result['eps'] = live_eps or source_eps
    result['eps_basis'] = (fin.get('epsBasis') if live_eps else
                           f"EPS BCTC năm {fin.get('reportPeriod', 'chưa rõ')}, chưa đồng bộ thời điểm peers" if source_eps else None)
    result['bvps'] = live_bvps
    if reported_eps is not None and reported_eps <= 0 and not any('EPS không dương' in warning for warning in result['peer_quality_warnings']):
        result['peer_quality_warnings'].append('EPS không dương; bỏ qua giá trị hàm ý P/E do doanh nghiệp đang lỗ.')
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
    # Chỉ công bố Peer Fair Value khi tỷ số định giá của chính mã mục tiêu có
    # nguồn gốc rõ ràng (có kỳ công bố, KHÔNG dùng giá trị suy diễn/fallback),
    # cùng với mẫu peer đủ và ROE tương đồng. Tránh tạo "giá mục tiêu" từ
    # snapshot không ngày hoặc từ tỷ số nội suy.
    has_val_provenance = bool(fin.get('valuationRatioSourcePeriod')) and not fin.get('valuationFallbackUsed')
    compatible=(len(peers)>=3 and not has_negative and dispersion<=4 and
                roe_gap is not None and roe_gap<=.12 and price and
                (live_eps or source_eps or live_bvps) and bvps and
                has_val_provenance)
    if compatible:
        usable_eps = live_eps or source_eps
        implied_pe=usable_eps*pe_med if usable_eps is not None and usable_eps > 0 else None
        implied_pb=bvps*pb_med
        result['implied_price_pe']=implied_pe
        result['implied_price_pb']=implied_pb
        # Banking financial groups value P/B more prominently, software P/E more.
        methods=[value for value in (implied_pe, implied_pb) if value is not None]
        fair=sum(methods)/len(methods) if methods else None
        result['peer_fair_value']=fair
        result['fair_value_pe']=implied_pe
        result['fair_value_pb']=implied_pb
        result['upside_downside']=fair/price-1 if fair is not None else None
        upside=result['upside_downside']
        result['upside_commentary']=(None if upside is None else
            'Định giá tương đối hấp dẫn hơn so với mặt bằng chung cùng ngành.' if upside>.15 else
            'Định giá đang ở mức cao hơn (premium) so với các doanh nghiệp cùng ngành.' if upside<-.15 else
            'Định giá ở mức tương đương trung vị ngành.')
        result['peer_quality_status']='Tham khảo có điều kiện'
        result['scenarios']=_peer_scenarios(peers, usable_eps, bvps, price)
    else:
        result['peer_quality_status']='Chưa đủ tin cậy để ra giá tham chiếu'
        result['scenarios']={'available':False,
                             'reason':'Kịch bản chỉ được dựng khi nhóm peer đạt tiêu chí chất lượng (đủ peer, ROE tương đồng, tỷ số định giá có nguồn gốc).'}
        if not has_val_provenance:
            result['peer_quality_warnings'].append(
                'P/E, P/B của mã mục tiêu đang là giá trị suy diễn (fallback) từ giá hiện tại '
                'ghép EPS/BVPS BCTC; không dùng để tạo Peer Fair Value.'
            )
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
