"""StockLens - bộ biểu đồ giá tương tác (Plotly) cho dashboard.

Tính năng:
  * Loại biểu đồ: Nến, Nến Heikin-Ashi, Thanh OHLC, Đường, Vùng.
  * Đường phủ lên giá: MA10/20/50/100/200, EMA20/50, Bollinger Bands(20,2), đường giá cao/thấp 52 tuần.
  * Khung phụ: Khối lượng (tô màu theo nến), RSI(14), MACD(12,26,9), Stochastic(14,3).
  * Khoảng thời gian 1M-3Y-Tất cả, thang giá tuyến tính/log, ẩn ngày nghỉ (không có khoảng trống).
Chỉ báo được tính trên TOÀN BỘ dữ liệu rồi mới cắt theo khoảng thời gian, nên đường MA/RSI ở đầu
khoảng hiển thị vẫn đúng. Công thức RSI/MACD giống src/technical_analysis.py để số liệu khớp nhau.

Dùng trong app:
    from src.charts import render_price_workbench
    render_price_workbench(df, currency="VND", key="overview")
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

UP, DOWN, FLAT = "#16A36F", "#E05252", "#E0A100"
CHART_TYPES = ["Nến", "Nến Heikin-Ashi", "Thanh OHLC", "Đường", "Vùng"]
RANGES = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "Tất cả": None}
OVERLAY_OPTIONS = ["MA10", "MA20", "MA50", "MA100", "MA200", "EMA20", "EMA50", "Bollinger", "Đỉnh/Đáy 52 tuần"]
PANEL_OPTIONS = ["Khối lượng", "RSI", "MACD", "Stochastic"]
MA_COLORS = {"MA10": "#9B8AF4", "MA20": "#15A988", "MA50": "#E69422", "MA100": "#D9548C", "MA200": "#1D4E89",
             "EMA20": "#0EA5E9", "EMA50": "#F97316"}
FONT = dict(family="Inter, Segoe UI, Arial", color="#42566E", size=11)


# ----------------------------------------------------------------------------- dữ liệu
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    need = ["Date", "Open", "High", "Low", "Close", "Volume"]
    if not isinstance(df, pd.DataFrame) or any(c not in df.columns for c in need):
        return pd.DataFrame(columns=need)
    d = df[need].copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    for c in need[1:]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values("Date")
    d["Volume"] = d["Volume"].fillna(0)
    return d.drop_duplicates("Date", keep="last").reset_index(drop=True)


def indicators(d: pd.DataFrame) -> pd.DataFrame:
    """Thêm các cột chỉ báo vào bản sao của d (đã qua prepare)."""
    x = d.copy()
    c = x["Close"]
    for n in (10, 20, 50, 100, 200):
        x[f"MA{n}"] = c.rolling(n).mean()
    for n in (20, 50):
        x[f"EMA{n}"] = c.ewm(span=n, adjust=False).mean()
    sd = c.rolling(20).std()
    x["BB_mid"], x["BB_up"], x["BB_low"] = x["MA20"], x["MA20"] + 2 * sd, x["MA20"] - 2 * sd
    delta = c.diff()
    gains, losses = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    x["RSI"] = 100 - 100 / (1 + gains / losses.replace(0, np.nan))
    x.loc[(losses == 0) & (gains > 0), "RSI"] = 100
    x.loc[(losses == 0) & (gains == 0), "RSI"] = 50
    x["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    x["MACD_Signal"] = x["MACD"].ewm(span=9, adjust=False).mean()
    x["MACD_Hist"] = x["MACD"] - x["MACD_Signal"]
    ll, hh = x["Low"].rolling(14).min(), x["High"].rolling(14).max()
    x["STOCH_K"] = (c - ll) / (hh - ll).replace(0, np.nan) * 100
    x["STOCH_D"] = x["STOCH_K"].rolling(3).mean()
    x["HIGH52"], x["LOW52"] = x["High"].rolling(252, min_periods=20).max(), x["Low"].rolling(252, min_periods=20).min()
    return x


def heikin_ashi(d: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame({"Date": d["Date"]})
    ha["Close"] = (d["Open"] + d["High"] + d["Low"] + d["Close"]) / 4
    opens = np.empty(len(d))
    if len(d):
        opens[0] = (d["Open"].iloc[0] + d["Close"].iloc[0]) / 2
        for i in range(1, len(d)):
            opens[i] = (opens[i - 1] + ha["Close"].iloc[i - 1]) / 2
    ha["Open"] = opens
    ha["High"] = np.maximum.reduce([d["High"].to_numpy(), ha["Open"].to_numpy(), ha["Close"].to_numpy()])
    ha["Low"] = np.minimum.reduce([d["Low"].to_numpy(), ha["Open"].to_numpy(), ha["Close"].to_numpy()])
    return ha


def _missing_days(dates: pd.Series) -> list[str]:
    if len(dates) < 2:
        return []
    full = pd.bdate_range(dates.min(), dates.max())
    return [x.strftime("%Y-%m-%d") for x in full.difference(pd.DatetimeIndex(dates).normalize())]


# ----------------------------------------------------------------------------- hình
def build_price_figure(df: pd.DataFrame, chart_type="Nến", overlays=("MA20", "MA50"), panels=("Khối lượng",),
                       range_label="1Y", log_scale=False, currency="VND", height=None) -> go.Figure:
    d = prepare(df)
    fig = go.Figure()
    if d.empty:
        fig.add_annotation(text="Chưa có dữ liệu giá để vẽ biểu đồ.", showarrow=False, x=.5, y=.5, xref="paper", yref="paper")
        fig.update_layout(height=260, paper_bgcolor="white", plot_bgcolor="white")
        return fig
    x = indicators(d)
    n = RANGES.get(range_label)
    view = x.tail(n) if n else x
    if len(view) < 2:
        view = x
    panels = [p for p in PANEL_OPTIONS if p in set(panels)]
    rows = 1 + len(panels)
    main_share = 0.58 if rows > 1 else 1.0
    other = (1 - main_share) / max(rows - 1, 1)
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[main_share] + [other] * (rows - 1))
    dates = view["Date"]

    # ---- giá chính
    src = heikin_ashi(view) if chart_type == "Nến Heikin-Ashi" else view
    hover_fmt = "%{x|%d/%m/%Y}<extra></extra>"
    if chart_type in ("Nến", "Nến Heikin-Ashi"):
        fig.add_trace(go.Candlestick(x=dates, open=src["Open"], high=src["High"], low=src["Low"], close=src["Close"],
                                     name="Giá" if chart_type == "Nến" else "Heikin-Ashi",
                                     increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
                                     decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
                                     whiskerwidth=.6), row=1, col=1)
    elif chart_type == "Thanh OHLC":
        fig.add_trace(go.Ohlc(x=dates, open=view["Open"], high=view["High"], low=view["Low"], close=view["Close"], name="OHLC",
                              increasing=dict(line=dict(color=UP)), decreasing=dict(line=dict(color=DOWN))), row=1, col=1)
    else:
        kw = dict(fill="tozeroy", fillcolor="rgba(22,117,229,.08)") if chart_type == "Vùng" else {}
        fig.add_trace(go.Scatter(x=dates, y=view["Close"], name="Giá đóng cửa", mode="lines",
                                 line=dict(color="#1675E5", width=2.2), hovertemplate=f"Đóng cửa: %{{y:,.0f}} {currency}<extra></extra>", **kw),
                      row=1, col=1)

    # ---- đường phủ
    ov = set(overlays)
    for name in ("MA10", "MA20", "MA50", "MA100", "MA200", "EMA20", "EMA50"):
        if name in ov and view[name].notna().any():
            fig.add_trace(go.Scatter(x=dates, y=view[name], name=name, mode="lines",
                                     line=dict(color=MA_COLORS[name], width=1.3, dash="dot" if name.startswith("EMA") else "solid"),
                                     hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>"), row=1, col=1)
    if "Bollinger" in ov and view["BB_up"].notna().any():
        fig.add_trace(go.Scatter(x=dates, y=view["BB_up"], name="BB trên", mode="lines", line=dict(color="rgba(80,110,160,.55)", width=1),
                                 hovertemplate="BB trên: %{y:,.0f}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=dates, y=view["BB_low"], name="BB dưới", mode="lines", line=dict(color="rgba(80,110,160,.55)", width=1),
                                 fill="tonexty", fillcolor="rgba(120,150,200,.10)", hovertemplate="BB dưới: %{y:,.0f}<extra></extra>"), row=1, col=1)
    if "Đỉnh/Đáy 52 tuần" in ov:
        hi, lo = view["High"].max(), view["Low"].min()
        for val, txt, col in ((hi, "Đỉnh kỳ", UP), (lo, "Đáy kỳ", DOWN)):
            fig.add_hline(y=val, line_dash="dash", line_color=col, line_width=1, opacity=.6, row=1, col=1,
                          annotation_text=f"{txt}: {val:,.0f}", annotation_position="top left", annotation_font=dict(size=10, color=col))

    # ---- giá cuối
    last = float(view["Close"].iloc[-1])
    prev = float(view["Close"].iloc[-2]) if len(view) > 1 else last
    col = UP if last >= prev else DOWN
    fig.add_hline(y=last, line_dash="dot", line_color=col, line_width=1, row=1, col=1,
                  annotation_text=f"{last:,.0f}", annotation_position="right", annotation_font=dict(size=11, color="white"),
                  annotation_bgcolor=col)

    # ---- khung phụ
    r = 2
    for p in panels:
        if p == "Khối lượng":
            colors = [UP if c >= o else DOWN for o, c in zip(view["Open"], view["Close"])]
            fig.add_trace(go.Bar(x=dates, y=view["Volume"], name="Khối lượng", marker_color=colors, opacity=.65,
                                 hovertemplate="KL: %{y:,.0f}<extra></extra>"), row=r, col=1)
            vma = view["Volume"].rolling(20).mean()
            fig.add_trace(go.Scatter(x=dates, y=vma, name="KL TB20", mode="lines", line=dict(color="#6B7F99", width=1),
                                     hovertemplate="KL TB20: %{y:,.0f}<extra></extra>"), row=r, col=1)
            fig.update_yaxes(title_text="Khối lượng", row=r, col=1)
        elif p == "RSI":
            fig.add_trace(go.Scatter(x=dates, y=view["RSI"], name="RSI(14)", mode="lines", line=dict(color="#7A5AF8", width=1.5),
                                     hovertemplate="RSI: %{y:.1f}<extra></extra>"), row=r, col=1)
            for lvl, c_ in ((70, DOWN), (30, UP)):
                fig.add_hline(y=lvl, line_dash="dash", line_color=c_, line_width=1, opacity=.55, row=r, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=r, col=1)
        elif p == "MACD":
            hist_c = [UP if v >= 0 else DOWN for v in view["MACD_Hist"].fillna(0)]
            fig.add_trace(go.Bar(x=dates, y=view["MACD_Hist"], name="Histogram", marker_color=hist_c, opacity=.55,
                                 hovertemplate="Hist: %{y:,.1f}<extra></extra>"), row=r, col=1)
            fig.add_trace(go.Scatter(x=dates, y=view["MACD"], name="MACD", mode="lines", line=dict(color="#146FD1", width=1.4),
                                     hovertemplate="MACD: %{y:,.1f}<extra></extra>"), row=r, col=1)
            fig.add_trace(go.Scatter(x=dates, y=view["MACD_Signal"], name="Signal", mode="lines", line=dict(color="#E69422", width=1.3),
                                     hovertemplate="Signal: %{y:,.1f}<extra></extra>"), row=r, col=1)
            fig.update_yaxes(title_text="MACD", row=r, col=1)
        elif p == "Stochastic":
            fig.add_trace(go.Scatter(x=dates, y=view["STOCH_K"], name="%K", mode="lines", line=dict(color="#146FD1", width=1.3),
                                     hovertemplate="%K: %{y:.1f}<extra></extra>"), row=r, col=1)
            fig.add_trace(go.Scatter(x=dates, y=view["STOCH_D"], name="%D", mode="lines", line=dict(color="#E69422", width=1.3),
                                     hovertemplate="%D: %{y:.1f}<extra></extra>"), row=r, col=1)
            for lvl, c_ in ((80, DOWN), (20, UP)):
                fig.add_hline(y=lvl, line_dash="dash", line_color=c_, line_width=1, opacity=.55, row=r, col=1)
            fig.update_yaxes(title_text="Stoch", range=[0, 100], row=r, col=1)
        r += 1

    # ---- trục + bố cục
    breaks = [dict(bounds=["sat", "mon"])]
    miss = _missing_days(dates)
    if miss and len(miss) < 400:
        breaks.append(dict(values=miss))
    fig.update_xaxes(rangebreaks=breaks, rangeslider_visible=False, showspikes=True, spikemode="across", spikesnap="cursor",
                     spikethickness=1, spikecolor="#9FB3C8", gridcolor="#EEF2F7", tickformat="%d/%m/%y")
    fig.update_yaxes(gridcolor="#E8EEF5", zeroline=False, showspikes=True, spikethickness=1, spikecolor="#9FB3C8")
    fig.update_yaxes(title_text=f"Giá ({currency})", type="log" if log_scale else "linear", tickformat=",.0f", row=1, col=1)
    fig.update_xaxes(title_text="", row=rows, col=1)
    fig.update_layout(height=height or (440 + 135 * len(panels)), margin=dict(l=62, r=70, t=18, b=40),
                      paper_bgcolor="white", plot_bgcolor="white", font=FONT, hovermode="x unified", dragmode="pan",
                      legend=dict(orientation="h", y=1.04, x=0, font=dict(size=10), bgcolor="rgba(255,255,255,.6)"),
                      hoverlabel=dict(font_size=11), bargap=0.15)
    return fig


# ----------------------------------------------------------------------------- Streamlit
def render_price_workbench(df: pd.DataFrame, currency: str = "VND", key: str = "pw",
                           default_type="Nến", default_overlays=("MA20", "MA50"),
                           default_panels=("Khối lượng",), default_range="1Y", show_summary=True, compact=False):
    """Vẽ bộ điều khiển (loại biểu đồ, thời gian, đường phủ, khung phụ) và biểu đồ tương tác."""
    import streamlit as st

    d = prepare(df)
    if d.empty:
        st.info("Chưa có dữ liệu giá để vẽ biểu đồ.")
        return None
    c1, c2, c3 = st.columns([1.3, 2.6, 0.9] if compact else [2.6, 2.6, 1.0])
    with c1:
        if compact:
            chart_type = st.selectbox("Loại biểu đồ", CHART_TYPES, index=CHART_TYPES.index(default_type), key=f"{key}_type")
        else:
            chart_type = st.radio("Loại biểu đồ", CHART_TYPES, index=CHART_TYPES.index(default_type), horizontal=True, key=f"{key}_type")
    with c2:
        range_label = st.radio("Khoảng thời gian", list(RANGES), index=list(RANGES).index(default_range), horizontal=True, key=f"{key}_range")
    with c3:
        log_scale = st.toggle("Thang log", value=False, key=f"{key}_log")
    c4, c5 = st.columns(2)
    with c4:
        overlays = st.multiselect("Đường trên biểu đồ giá", OVERLAY_OPTIONS, default=list(default_overlays), key=f"{key}_ov",
                                  placeholder="Chọn MA, EMA, Bollinger...")
    with c5:
        panels = st.multiselect("Khung chỉ báo phía dưới", PANEL_OPTIONS, default=list(default_panels), key=f"{key}_pn",
                                placeholder="Chọn khối lượng, RSI, MACD...")
    fig = build_price_figure(d, chart_type, overlays, panels, range_label, log_scale, currency)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": True,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
                            "toImageButtonOptions": {"filename": f"stocklens_{key}", "scale": 2}})
    if show_summary and len(d) >= 2:
        last, prev = d.iloc[-1], d.iloc[-2]
        chg = last["Close"] / prev["Close"] - 1 if prev["Close"] else 0
        st.caption(f"Phiên {last['Date']:%d/%m/%Y}: Mở {last['Open']:,.0f} · Cao {last['High']:,.0f} · Thấp {last['Low']:,.0f} · "
                   f"Đóng {last['Close']:,.0f} {currency} ({chg:+.2%}) · KL {last['Volume']:,.0f}. "
                   "Kéo để di chuyển, cuộn chuột để phóng to/thu nhỏ, nhấp đúp để đặt lại.")
    return fig
