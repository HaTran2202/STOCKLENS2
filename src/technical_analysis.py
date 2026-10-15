"""TV2: technical analysis. Accepts TV1 DataFrame, never fetches data."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def analyze_technical(price_df: pd.DataFrame, chart_dir='charts') -> dict:
    def unavailable(message):
        return {'data_available':False,'technical_score':None,'score':None,'label':'Unavailable',
                'positives':[],'risks':[],'technical_view':message,'commentary':message,
                'support_level':None,'resistance_level':None,
                'distance_to_support_pct':None,'distance_to_resistance_pct':None,
                'divergence':{'bullish':False,'bearish':False,'signal':None},
                'action_scenario':message,
                'charts':{},'error':message}
    required = ['Date','Open','High','Low','Close','Volume']
    if not isinstance(price_df, pd.DataFrame):
        return unavailable('Đầu vào không phải DataFrame.')
    missing = [c for c in required if c not in price_df]
    if missing:
        return unavailable('Thiếu cột: ' + ', '.join(missing))
    df = price_df[required].copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    for c in required[1:]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna().sort_values('Date').drop_duplicates('Date', keep='last')
    df = df[(df['Low']>0)&(df['Volume']>=0)&(df['High']>=df[['Open','Close','Low']].max(axis=1))&
            (df['Low']<=df[['Open','Close']].min(axis=1))].reset_index(drop=True)
    if len(df) < 51:
        return unavailable(f'Cần ít nhất 51 phiên hợp lệ; hiện có {len(df)}.')
    c = df['Close']
    df['MA20'] = c.rolling(20).mean()
    df['MA50'] = c.rolling(50).mean()
    delta = c.diff()
    gains, losses = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - 100/(1 + gains/losses.replace(0,np.nan))
    df.loc[(losses==0)&(gains>0),'RSI']=100
    df.loc[(losses==0)&(gains==0),'RSI']=50
    df['MACD'] = c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9,adjust=False).mean()
    df['MACD_Histogram'] = df['MACD']-df['MACD_Signal']
    df['AvgVolume20'] = df['Volume'].rolling(20).mean()
    df['VolumeRatio'] = df['Volume']/df['AvgVolume20'].replace(0,np.nan)
    df['DailyReturn'] = c.pct_change()
    df['Volatility20'] = df['DailyReturn'].rolling(20).std()*np.sqrt(252)
    last = df.iloc[-1]
    close, ma20, ma50 = (float(last[k]) for k in ('Close','MA20','MA50'))
    rsi, macd, signal = (float(last[k]) for k in ('RSI','MACD','MACD_Signal'))
    vol = float(last['Volatility20'])
    ratio = float(last['VolumeRatio']) if pd.notna(last['VolumeRatio']) else None
    if not all(np.isfinite(v) for v in (close,ma20,ma50,rsi,macd,signal,vol)):
        return unavailable('Một số chỉ báo không tính được.')
    recent = df.tail(60).reset_index(drop=True)
    pivot_highs, pivot_lows = [], []
    for idx in range(2, len(recent)-2):
        high = float(recent.iloc[idx]['High'])
        low = float(recent.iloc[idx]['Low'])
        if high >= float(recent.iloc[idx-2:idx+3]['High'].max()):
            pivot_highs.append(high)
        if low <= float(recent.iloc[idx-2:idx+3]['Low'].min()):
            pivot_lows.append(low)
    supports = [level for level in pivot_lows if level < close]
    resistances = [level for level in pivot_highs if level > close]
    support = max(supports) if supports else (
        float(recent['Low'].min()) if len(recent) >= 5 and float(recent['Low'].min()) < close else None
    )
    resistance = min(resistances) if resistances else (
        float(recent['High'].max()) if len(recent) >= 5 and float(recent['High'].max()) > close else None
    )
    distance_support = (support / close - 1) * 100 if support is not None and close else None
    distance_resistance = (resistance / close - 1) * 100 if resistance is not None and close else None

    low_pivots, high_pivots = [], []
    rsi_values = df['RSI'].to_numpy()
    for idx in range(max(2, len(df)-60), len(df)-2):
        low_window = df['Low'].iloc[idx-2:idx+3]
        high_window = df['High'].iloc[idx-2:idx+3]
        if float(df.iloc[idx]['Low']) <= float(low_window.min()) and np.isfinite(rsi_values[idx]):
            low_pivots.append((idx, float(df.iloc[idx]['Low']), float(rsi_values[idx])))
        if float(df.iloc[idx]['High']) >= float(high_window.max()) and np.isfinite(rsi_values[idx]):
            high_pivots.append((idx, float(df.iloc[idx]['High']), float(rsi_values[idx])))
    bullish_divergence = (len(low_pivots) >= 2 and low_pivots[-1][1] < low_pivots[-2][1]
                          and low_pivots[-1][2] > low_pivots[-2][2])
    bearish_divergence = (len(high_pivots) >= 2 and high_pivots[-1][1] > high_pivots[-2][1]
                          and high_pivots[-1][2] < high_pivots[-2][2])
    divergence_signal = 'Bullish' if bullish_divergence else 'Bearish' if bearish_divergence else None
    divergence = {
        'bullish':bullish_divergence, 'bearish':bearish_divergence, 'signal':divergence_signal,
        'note':'Phân kỳ dương: đáy giá thấp hơn nhưng RSI tạo đáy cao hơn.' if bullish_divergence else
               'Phân kỳ âm: đỉnh giá cao hơn nhưng RSI tạo đỉnh thấp hơn.' if bearish_divergence else None,
    }
    trend = ('Giá nằm trên MA20 và MA50; xu hướng ngắn/trung hạn tích cực.'
             if close > ma20 and close > ma50 else
             'Giá nằm dưới MA20 và MA50; xu hướng ngắn/trung hạn vẫn là giảm (Bearish).'
             if close < ma20 and close < ma50 else
             'Giá đang ở trạng thái đan xen quanh MA20/MA50; xu hướng chưa đồng thuận.')
    rsi_state = ('Vùng quá bán sâu (Oversold); đây là trạng thái điều kiện, cần xác nhận đảo chiều bằng giá và khối lượng, không đồng nghĩa sẽ hồi phục.'
                 if rsi < 20 else 'Vùng quá bán; cần tín hiệu xác nhận trước khi hành động.'
                 if rsi < 30 else 'Vùng quá mua; rủi ro điều chỉnh tăng.'
                 if rsi > 70 else 'RSI chưa ở vùng quá mua/quá bán.')
    action = f'{trend} RSI(14) {rsi:.1f}: {rsi_state}'
    if support is not None:
        action += f' Hỗ trợ gần nhất quanh {support:,.0f} VND/cp'
        action += f'; kháng cự gần nhất {resistance:,.0f} VND/cp.' if resistance is not None else '.'
    else:
        action += ' Chưa xác định được hỗ trợ lịch sử đáng tin cậy.'
    if rsi < 20 and not bullish_divergence:
        action += ' Trong xu hướng hiện tại, nên chờ giá cân bằng hoặc xuất hiện phân kỳ dương trước khi xem xét giải ngân.'
    if bullish_divergence:
        action += ' Có phân kỳ dương; chờ xác nhận bằng giá/khối lượng trước khi xem xét giải ngân.'
    elif bearish_divergence:
        action += ' Có phân kỳ âm; ưu tiên quản trị rủi ro nếu giá tiếp tục suy yếu.'
    # Điều kiện xác nhận / vô hiệu hóa theo mức giá cụ thể (khi có hỗ trợ, kháng cự).
    if resistance is not None:
        action += (f' XÁC NHẬN: kịch bản tích cực chỉ được xem là đúng khi giá đóng cửa vượt '
                   f'{resistance:,.0f} VND/cp kèm khối lượng từ 1.2x trung bình 20 phiên.')
    if support is not None:
        action += (f' VÔ HIỆU: kịch bản trên bị vô hiệu nếu giá đóng cửa dưới hỗ trợ '
                   f'{support:,.0f} VND/cp.')
    else:
        action += ' Chưa xác định được mức hỗ trợ để đặt điều kiện vô hiệu hóa.'

    positives, risks, signals = [], [], {}
    def add(name, status, score, reason=None):
        signals[name]={'signal':status,'score':score}
        if reason:
            (positives if status=='Positive' else risks).append(reason)
        return score
    if close>ma20>ma50:
        s_ma=add('MA','Positive',100,'Giá trên MA20 và MA20 trên MA50.')
    elif close<ma20<ma50:
        s_ma=add('MA','Negative',0,'Giá dưới MA20 và MA20 dưới MA50.')
    else:
        s_ma=add('MA','Neutral',50)
    if rsi>70:
        s_rsi=add('RSI','Negative',25,f'RSI {rsi:.1f}: vùng quá mua.')
    elif rsi<30:
        s_rsi=add('RSI','Neutral',50,f'RSI {rsi:.1f}: ' + ('vùng quá bán sâu (Oversold); trạng thái điều kiện, cần xác nhận bằng giá/khối lượng, không đồng nghĩa sẽ hồi.' if rsi<20 else 'vùng quá bán, cần thận trọng.'))
    else:
        s_rsi=add('RSI','Positive',100,f'RSI {rsi:.1f}: chưa vào vùng cực trị.')
    if macd>signal:
        s_macd=add('MACD','Positive',100,'MACD nằm trên đường tín hiệu.')
    elif macd<signal:
        s_macd=add('MACD','Negative',0,'MACD nằm dưới đường tín hiệu.')
    else:
        s_macd=add('MACD','Neutral',50)
    price_change=close-float(df.iloc[-2]['Close'])
    if ratio is not None and ratio>=1.2 and price_change>0:
        s_volume=add('Volume','Positive',100,'Khối lượng tăng cùng chiều giá.')
    elif ratio is not None and ratio>=1.2 and price_change<0:
        s_volume=add('Volume','Negative',25,'Khối lượng cao trong phiên giảm giá.')
    else:
        s_volume=add('Volume','Neutral',50)
    if vol<0.20:
        s_vol=add('Volatility','Positive',100,'Biến động 20 phiên ở mức thấp theo ngưỡng mô hình.')
    elif vol<=0.40:
        s_vol=add('Volatility','Neutral',50)
    else:
        s_vol=add('Volatility','Negative',0,f'Biến động thường niên hóa cao: {vol:.1%}.')
    if bullish_divergence:
        positives.append(divergence['note'])
    if bearish_divergence:
        risks.append(divergence['note'])
    score=round(.30*s_ma+.20*s_rsi+.25*s_macd+.10*s_volume+.15*s_vol,2)
    label='Positive' if score>=70 else 'Neutral' if score>=40 else 'Negative'
    view=(f'Technical Score {score}/100 ({label}). {action} Close {close:,.2f}; MA20 {ma20:,.2f}; '
          f'MA50 {ma50:,.2f}; RSI {rsi:.1f}; MACD {macd:.3f}; biến động {vol:.1%}. '
          'Đây là điểm heuristic, không phải dự báo chắc chắn.')
    out=Path(chart_dir); out.mkdir(parents=True,exist_ok=True)
    paths={}
    def save(fig,key):
        path=out/f'technical_{key}.png'
        fig.tight_layout(); fig.savefig(path,dpi=135,bbox_inches='tight'); plt.close(fig)
        paths[key]=str(path)
    fig,ax=plt.subplots(figsize=(9,3.5))
    for key in ['Close','MA20','MA50']:
        ax.plot(df['Date'],df[key],label=key)
    ax.legend(); ax.grid(alpha=.2); ax.set_title('Price & Moving Averages'); fig.autofmt_xdate(); save(fig,'price_ma')
    fig,ax=plt.subplots(figsize=(9,2.8))
    ax.plot(df['Date'],df['RSI']); ax.axhline(70,ls='--',color='red'); ax.axhline(30,ls='--',color='green')
    ax.set_ylim(0,100); ax.grid(alpha=.2); ax.set_title('RSI (14)'); fig.autofmt_xdate(); save(fig,'rsi')
    fig,ax=plt.subplots(figsize=(9,2.8))
    ax.plot(df['Date'],df['MACD'],label='MACD'); ax.plot(df['Date'],df['MACD_Signal'],label='Signal')
    ax.bar(df['Date'],df['MACD_Histogram'],alpha=.25,label='Histogram'); ax.legend(); ax.grid(alpha=.2)
    ax.set_title('MACD (12,26,9)'); fig.autofmt_xdate(); save(fig,'macd')
    return {'data_available':True,'technical_score':score,'score':score,'label':label,
            'analysis_date':str(last['Date'].date()),'observations':len(df),
            'close':close,'ma20':ma20,'ma50':ma50,'rsi':rsi,'macd':macd,'macd_signal':signal,
            'trend_state':trend,'rsi_state':rsi_state,'support_level':support,'resistance_level':resistance,
            'distance_to_support_pct':distance_support,'distance_to_resistance_pct':distance_resistance,
            'pivot_highs_60':pivot_highs,'pivot_lows_60':pivot_lows,
            'divergence':divergence,'action_scenario':action,
            'macd_histogram':float(last['MACD_Histogram']),'volume':float(last['Volume']),
            'avg_volume_20':float(last['AvgVolume20']),'volume_ratio':ratio,'volatility':vol,
            'signals':signals,'positives':positives,'risks':risks,'technical_view':view,
            'commentary':view,'charts':paths,'data':df}
