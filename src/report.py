"""StockLens - Báo cáo nghiên cứu PDF (ReportLab + matplotlib).

generate_pdf(ticker, period_text, results, summary, sections, profile,
             company_info=None, financial_data=None) -> bytes

Điểm chính của bản này:
  * Trang bìa: logo (hoặc monogram), quan điểm StockLens, giá, điểm tổng hợp và MỤC LỤC có số trang.
  * Mục 2 "Luận điểm đầu tư & rủi ro cần lưu ý" được cá nhân hóa theo từng mã và hồ sơ nhà đầu tư.
  * Mọi biểu đồ dựng bằng matplotlib với kích thước đúng khung và chèn giữ nguyên tỷ lệ (không méo).
  * Chỉ đưa vào PDF các phần người dùng chọn; nguồn dữ liệu và phương pháp luôn có.
  * Số trang dạng "Trang x/N" chính xác.
"""
from __future__ import annotations

import io
import math
import os
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Wedge
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas as rl_canvas

try:
    from src.branding import logo_bytes
    from src.thesis import build_thesis
except ImportError:  # chạy trực tiếp trong thư mục src
    from branding import logo_bytes
    from thesis import build_thesis

# ----------------------------------------------------------------------------- phông chữ + màu
NAVY, BLUE, TEAL = "#0B2B55", "#176FD1", "#11B7AE"
TEXT, MUTED, LINE, SOFT = "#173150", "#6B7F99", "#D7E5F3", "#F4F8FC"
GREEN, AMBER, RED, PURPLE = "#16A36F", "#E99A19", "#D84F61", "#7B61D9"
C = lambda h: colors.HexColor(h)  # noqa: E731

_FONT_READY = False


def _register_fonts():
    global _FONT_READY
    if _FONT_READY:
        return
    dejavu = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf"),
        (str(dejavu / "DejaVuSans.ttf"), str(dejavu / "DejaVuSans-Bold.ttf"), str(dejavu / "DejaVuSans-Oblique.ttf")),
    ]
    for reg, bold, ital in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("SL", reg))
            pdfmetrics.registerFont(TTFont("SL-B", bold))
            pdfmetrics.registerFont(TTFont("SL-I", ital if os.path.exists(ital) else reg))
            pdfmetrics.registerFontFamily("SL", normal="SL", bold="SL-B", italic="SL-I", boldItalic="SL-B")
            _FONT_READY = True
            return
    raise RuntimeError("Không tìm thấy phông chữ hỗ trợ tiếng Việt.")


def _styles():
    s = {}
    def add(name, **kw):
        base = dict(fontName="SL", fontSize=9, leading=13, textColor=C(TEXT))
        base.update(kw)
        s[name] = ParagraphStyle(name, **base)
    add("body", alignment=TA_JUSTIFY, spaceAfter=5)
    add("small", fontSize=7.5, leading=10, textColor=C(MUTED))
    add("tiny", fontSize=6.5, leading=8.5, textColor=C(MUTED))
    add("sec", fontName="SL-B", fontSize=16, leading=20, textColor=C(NAVY), spaceBefore=0, spaceAfter=2)
    add("subsec", fontSize=8.5, leading=11, textColor=C(MUTED), spaceAfter=7)
    add("h2", fontName="SL-B", fontSize=11, leading=14, textColor=C(BLUE), spaceBefore=8, spaceAfter=4)
    add("kl", fontSize=7, leading=9, textColor=C(MUTED))
    add("kv", fontName="SL-B", fontSize=12.5, leading=15.5, textColor=C(NAVY))
    add("ks", fontSize=7, leading=9, textColor=C(MUTED))
    add("cell", fontSize=8, leading=10.5)
    add("cellb", fontName="SL-B", fontSize=8, leading=10.5, textColor=C(NAVY))
    add("cellr", fontSize=8, leading=10.5, alignment=TA_RIGHT)
    add("cellh", fontName="SL-B", fontSize=8, leading=10.5, textColor=C(NAVY))
    add("cover_t", fontName="SL-B", fontSize=24, leading=28, textColor=C(NAVY))
    add("cover_n", fontSize=11, leading=14, textColor=C("#385576"))
    add("rec_t", fontName="SL-B", fontSize=15, leading=18)
    add("toc0", fontSize=9.5, leading=15, leftIndent=0, textColor=C(TEXT))
    add("bullet", fontSize=8.8, leading=12.5, leftIndent=9, bulletIndent=0, spaceAfter=3, alignment=TA_JUSTIFY)
    return s


ST = None

# ----------------------------------------------------------------------------- tiện ích dữ liệu
def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _p(text, style="body"):
    return Paragraph(escape(str(text)), ST[style])


def _pm(markup, style="body"):  # markup đã tin cậy (<b>..</b>)
    return Paragraph(markup, ST[style])


def _fmt(v, d=1, suf=""):
    v = _f(v)
    return "N/A" if v is None else f"{v:,.{d}f}{suf}"


def _money(v):
    v = _f(v)
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"{v / 1e12:,.1f} nghìn tỷ"
    if abs(v) >= 1e9:
        return f"{v / 1e9:,.0f} tỷ"
    return f"{v:,.0f}"


def _bn(v):
    """Giá trị tiền dạng ngắn gọn cho ô KPI: 70,113 tỷ."""
    v = _f(v)
    return "N/A" if v is None else f"{v / 1e9:,.0f}"


def _ratio(x):
    v = _f(x)
    if v is None:
        return None
    return v / 100 if abs(v) > 1.5 else v


def _norm_cols(rows, keys):
    """Chuẩn hóa các cột tỷ lệ về dạng thập phân theo CẢ CỘT (tránh đoán sai với giá trị nhỏ như 1,2%)."""
    rows = [dict(r) for r in rows]
    for k in keys:
        vals = [abs(_f(r.get(k))) for r in rows if _f(r.get(k)) is not None]
        if vals and max(vals) > 1.5:
            for r in rows:
                if _f(r.get(k)) is not None:
                    r[k] = _f(r[k]) / 100
    return rows


def _history(fd):
    rows = [r for r in (fd or {}).get("financialHistory", []) or [] if isinstance(r, dict) and r.get("period") is not None]
    rows.sort(key=lambda r: str(r.get("period")))
    return _norm_cols(rows, ("roe", "roa"))


def _tone_color(score):
    s = _f(score)
    if s is None:
        return MUTED
    return GREEN if s >= 65 else AMBER if s >= 50 else RED


def _label(score):
    s = _f(score)
    if s is None:
        return "Chưa đủ dữ liệu"
    return "Cơ hội cao" if s >= 80 else "Tích cực" if s >= 65 else "Trung lập" if s >= 50 else "Thận trọng"


# ----------------------------------------------------------------------------- biểu đồ (giữ đúng tỷ lệ)
CONTENT_W = A4[0] - 36 * mm  # lề 18mm hai bên
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": "#C9D6E4",
                     "axes.labelcolor": "#42566E", "xtick.color": "#42566E", "ytick.color": "#42566E",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#E8EEF5", "grid.linewidth": 0.6})


def _fig_image(fig, width=CONTENT_W):
    """Lưu figure và chèn vào PDF theo đúng tỷ lệ thật của ảnh (không bị kéo giãn)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=220, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    iw, ih = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=width, height=width * ih / iw)


def _size(width_pt, h_in):
    return (width_pt / 72.0, h_in)


def chart_price(data, width=CONTENT_W, h=3.0):
    d = data.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date", "Close"]).tail(260)
    fig, (ax, av) = plt.subplots(2, 1, figsize=_size(width, h), sharex=True, gridspec_kw={"height_ratios": [3.2, 1]})
    ax.plot(d["Date"], d["Close"], color=BLUE, lw=1.4, label="Giá đóng cửa")
    for col, cl in (("MA20", "#E69422"), ("MA50", "#15A988")):
        if col in d and d[col].notna().any():
            ax.plot(d["Date"], d[col], color=cl, lw=1, label=col)
    ax.set_ylabel("Giá (VND)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(loc="upper left", ncol=3, frameon=False, fontsize=7)
    if "Volume" in d:
        av.bar(d["Date"], d["Volume"] / 1e6, color="#8CC9FF", width=1.0)
        av.set_ylabel("Triệu CP")
    av.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%Y"))
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_rsi_macd(data, width=CONTENT_W, h=2.5):
    d = data.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date"]).tail(180)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=_size(width, h))
    if "RSI" in d:
        a1.plot(d["Date"], d["RSI"], color=PURPLE, lw=1.2)
        a1.axhline(70, color=RED, ls="--", lw=0.8); a1.axhline(30, color=GREEN, ls="--", lw=0.8)
        a1.set_ylim(0, 100); a1.set_title("RSI (14)", fontsize=8, loc="left", color=NAVY)
    if "MACD" in d:
        if "MACD_Histogram" in d:
            hist = d["MACD_Histogram"].fillna(0)
            a2.bar(d["Date"], hist, color=[("#5BC4A6" if x >= 0 else "#EF8A8A") for x in hist], width=1.0, alpha=.7)
        a2.plot(d["Date"], d["MACD"], color=BLUE, lw=1.1, label="MACD")
        if "MACD_Signal" in d:
            a2.plot(d["Date"], d["MACD_Signal"], color="#E69422", lw=1.0, label="Signal")
        a2.legend(frameon=False, fontsize=6.5, loc="upper left")
        a2.set_title("MACD (12,26,9)", fontsize=8, loc="left", color=NAVY)
    for a in (a1, a2):
        a.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%y"))
        a.tick_params(axis="x", labelsize=6.5)
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_drawdown(data, width=CONTENT_W, h=2.0):
    d = data.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date", "Close"])
    dd = (d["Close"] / d["Close"].cummax() - 1) * 100
    fig, ax = plt.subplots(figsize=_size(width, h))
    ax.fill_between(d["Date"], dd, 0, color="#EF8A8A", alpha=.45)
    ax.plot(d["Date"], dd, color=RED, lw=.9)
    ax.set_ylabel("Mức giảm từ đỉnh (%)")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%Y"))
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_fin(hist, width=CONTENT_W, h=2.6):
    yrs = [str(r["period"]) for r in hist]
    rev = [(_f(r.get("revenue")) or 0) / 1e9 for r in hist]
    npf = [(_f(r.get("net_profit")) or 0) / 1e9 for r in hist]
    roe = [(_ratio(r.get("roe")) or 0) * 100 for r in hist]
    roa = [(_ratio(r.get("roa")) or 0) * 100 for r in hist]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=_size(width, h))
    x = range(len(yrs))
    a1.bar([i - .2 for i in x], rev, .4, color="#2F5D8A", label="Doanh thu / thu nhập HĐ")
    a1.bar([i + .2 for i in x], npf, .4, color="#E39B2D", label="LNST")
    a1.set_xticks(list(x)); a1.set_xticklabels(yrs); a1.set_ylabel("Tỷ đồng")
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.legend(frameon=False, fontsize=6.5, loc="upper left"); a1.set_title("Quy mô & lợi nhuận", fontsize=8, loc="left", color=NAVY)
    a2.plot(list(x), roe, marker="o", color=BLUE, label="ROE"); a2.plot(list(x), roa, marker="s", color="#E39B2D", label="ROA")
    for i, v in enumerate(roe):
        a2.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=6.5)
    a2.set_xticks(list(x)); a2.set_xticklabels(yrs); a2.set_ylabel("%")
    a2.legend(frameon=False, fontsize=6.5, loc="best"); a2.set_title("Hiệu quả sinh lời", fontsize=8, loc="left", color=NAVY)
    a2.margins(y=0.25)
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_balance(hist, width=CONTENT_W, h=2.3):
    yrs = [str(r["period"]) for r in hist]
    ta = [(_f(r.get("total_assets")) or 0) / 1e9 for r in hist]
    eq = [(_f(r.get("equity")) or 0) / 1e9 for r in hist]
    fig, ax = plt.subplots(figsize=_size(width, h))
    x = range(len(yrs))
    ax.bar([i - .2 for i in x], ta, .4, color="#2F5D8A", label="Tổng tài sản")
    ax.bar([i + .2 for i in x], eq, .4, color="#11B7AE", label="Vốn chủ sở hữu")
    ax.set_xticks(list(x)); ax.set_xticklabels(yrs); ax.set_ylabel("Tỷ đồng")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_valuation(hist, v, width=CONTENT_W, h=2.3):
    yrs = [str(r["period"]) for r in hist]
    pe = [_f(r.get("pe")) for r in hist]
    pb = [_f(r.get("pb")) for r in hist]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=_size(width, h))
    for ax, ser, name, med, cl in ((a1, pe, "P/E lịch sử", _f(v.get("historical_pe_median")), BLUE),
                                   (a2, pb, "P/B lịch sử", _f(v.get("historical_pb_median")), TEAL)):
        xs = [i for i, y in enumerate(ser) if y is not None]
        ax.plot(xs, [ser[i] for i in xs], marker="o", color=cl)
        if med:
            ax.axhline(med, color=AMBER, ls="--", lw=.9, label=f"Trung vị {med:.2f}x")
            ax.legend(frameon=False, fontsize=6.5)
        ax.set_xticks(range(len(yrs))); ax.set_xticklabels(yrs); ax.set_title(name, fontsize=8, loc="left", color=NAVY)
        ax.margins(y=.25)
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_components(comp, width=CONTENT_W * 0.58, h=2.3):
    keys = [("fundamental", "Tài chính", BLUE), ("valuation", "Định giá", PURPLE), ("technical", "Kỹ thuật", TEAL),
            ("news", "Tin tức", AMBER), ("risk", "Rủi ro/An toàn", RED)]
    fig, ax = plt.subplots(figsize=_size(width, h))
    labels = [k[1] for k in keys]
    vals = [_f(comp.get(k[0])) or 0 for k in keys]
    bars = ax.barh(labels, vals, color=[k[2] for k in keys], height=.6)
    ax.set_xlim(0, 100); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    for b, k in zip(bars, keys):
        raw = _f(comp.get(k[0]))
        if raw is not None and raw > 80:
            ax.text(raw - 2, b.get_y() + b.get_height() / 2, f"{raw:.1f}", va="center", ha="right", fontsize=7.5, color="white", fontweight="bold")
        else:
            ax.text((raw or 0) + 2, b.get_y() + b.get_height() / 2, "N/A" if raw is None else f"{raw:.1f}", va="center", fontsize=7.5, color=NAVY)
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_profiles(profile_scores, current, width=CONTENT_W * 0.38, h=2.3):
    names = ["Thận trọng", "Cân bằng", "Tăng trưởng"]
    vals = [_f(profile_scores.get(n)) or 0 for n in names]
    fig, ax = plt.subplots(figsize=_size(width, h))
    bars = ax.bar(names, vals, color=[BLUE if n == current else "#B9CDE3" for n in names], width=.6)
    ax.set_ylim(0, 100); ax.tick_params(axis="x", labelsize=6.8)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.1f}", ha="center", fontsize=7.5, color=NAVY)
    fig.tight_layout()
    return _fig_image(fig, width)


def chart_gauge(score, size=1.55):
    fig, ax = plt.subplots(figsize=(size, size))
    s = _f(score)
    col = _tone_color(s)
    ax.add_patch(Wedge((0, 0), 1, 0, 360, width=.24, color="#E8EDF2"))
    if s is not None:
        ax.add_patch(Wedge((0, 0), 1, 90 - 3.6 * max(0, min(100, s)), 90, width=.24, color=col))
    ax.text(0, .06, "N/A" if s is None else f"{s:.0f}", ha="center", va="center", fontsize=22, fontweight="bold", color=NAVY)
    ax.text(0, -.38, "/100", ha="center", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal"); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    return _fig_image(fig, size * 72)


def chart_news(items, width=CONTENT_W * 0.36, h=1.9):
    cnt = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for i in items:
        if isinstance(i, dict) and i.get("sentiment") in cnt:
            cnt[i["sentiment"]] += 1
    fig, ax = plt.subplots(figsize=_size(width, h))
    ax.bar(["Tích cực", "Trung tính", "Tiêu cực"], list(cnt.values()), color=[GREEN, "#9AAFC6", RED], width=.6)
    ax.grid(axis="x", visible=False); ax.yaxis.get_major_locator().set_params(integer=True)
    for i, v in enumerate(cnt.values()):
        ax.text(i, v + .1, str(v), ha="center", fontsize=8, color=NAVY)
    fig.tight_layout()
    return _fig_image(fig, width)


# ----------------------------------------------------------------------------- thành phần bố cục
def _tbl(data, widths, header=True, align_right_from=None, zebra=True, extra=None):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("LINEBELOW", (0, 0), (-1, -1), .4, C(LINE))]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), C("#EAF3FC")), ("LINEBELOW", (0, 0), (-1, 0), .8, C(BLUE))]
    if zebra:
        for r in range(1 if header else 0, len(data)):
            if (r % 2) == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), C("#F8FBFE")))
    if extra:
        style += extra
    t.setStyle(TableStyle(style))
    return t


def _callout(title, body_flowables, color=BLUE, bg="#F3F8FF", width=CONTENT_W):
    inner = ([Paragraph(f'<font color="{color}"><b>{escape(title)}</b></font>', ST["h2"])] if title else []) + list(body_flowables)
    t = Table([[inner]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C(bg)), ("LINEBEFORE", (0, 0), (0, -1), 3, C(color)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _kpis(items, width=CONTENT_W):
    """items: [(label, value, sub, color)]"""
    n = len(items)
    cells = []
    for lab, val, sub, col in items:
        cells.append([Paragraph(escape(lab), ST["kl"]),
                      Paragraph(f'<font color="{col}">{escape(str(val))}</font>', ST["kv"]),
                      Paragraph(escape(sub or ""), ST["ks"])])
    t = Table([cells], colWidths=[width / n] * n)
    style = [("BACKGROUND", (0, 0), (-1, -1), C(SOFT)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for i, (_, _, _, col) in enumerate(items):
        style.append(("LINEBEFORE", (i, 0), (i, 0), 2.5, C(col)))
        if i:
            style.append(("LINEBEFORE", (i, 0), (i, 0), 2.5, C(col)))
    t.setStyle(TableStyle(style))
    return t


def _section(title, subtitle=""):
    out = [Paragraph(escape(title), ST["sec"])]
    if subtitle:
        out.append(Paragraph(escape(subtitle), ST["subsec"]))
    return out


def _bullets(lines, style="bullet"):
    return [Paragraph(escape(x), ST[style], bulletText="•") for x in lines if x]


def _side_by_side(left, right, wl, wr, gap=8):
    t = Table([[left, right]], colWidths=[wl, wr])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, 0), gap), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _price_stats(t, company):
    d = t.get("data")
    close = _f(t.get("close"))
    chg = hi = lo = vol = None
    if isinstance(d, pd.DataFrame) and "Close" in d and len(d):
        c = pd.to_numeric(d["Close"], errors="coerce").dropna()
        if len(c):
            close = close or float(c.iloc[-1])
            if len(c) > 1 and c.iloc[-2]:
                chg = float(c.iloc[-1] / c.iloc[-2] - 1)
            hi, lo = float(c.tail(252).max()), float(c.tail(252).min())
        if "Volume" in d:
            vol = _f(d["Volume"].iloc[-1])
    return close, chg, hi, lo, vol


# ----------------------------------------------------------------------------- trang bìa
def _cover(ticker, period_text, profile, results, summary, company, fd, th, toc):
    t = results.get("technical") or {}
    rec = th["recommendation"]
    close, chg, hi, lo, vol = _price_stats(t, company)
    name = company.get("name") or ticker
    web = company.get("website") or ""
    domain = None
    lg = logo_bytes(ticker, web)
    logo = Image(io.BytesIO(lg), width=22 * mm, height=22 * mm)
    logo._restrictSize(22 * mm, 22 * mm)  # giữ nguyên tỷ lệ logo, không ép thành hình vuông

    head = Table([[logo, [Paragraph("BÁO CÁO PHÂN TÍCH CỔ PHIẾU", ST["small"]),
                          Paragraph(escape(ticker), ST["cover_t"]),
                          Paragraph(escape(name), ST["cover_n"]),
                          Paragraph(escape(f"Sàn {company.get('exchange') or 'N/A'}  |  Ngành: {company.get('sector') or 'N/A'}  |  Hồ sơ: {profile}"), ST["small"])]]],
                 colWidths=[28 * mm, CONTENT_W - 28 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    tone_col = {"positive": GREEN, "neutral": AMBER, "caution": RED}.get(rec["tone"], MUTED)
    ref_txt = "Chưa có dữ liệu" if rec["ref_value"] is None else f"{rec['ref_value']:,.0f} VND" + (
        "" if rec["upside"] is None else f" ({rec['upside'] * 100:+.1f}%)")
    rec_box = [Paragraph("QUAN ĐIỂM STOCKLENS", ST["kl"]),
               Paragraph(f'<font color="{tone_col}">{escape(rec["stance"])} theo mô hình</font>', ST["rec_t"]),
               Spacer(1, 3),
               _pm(f"Investment Score ({escape(profile)}): <b>{_fmt(rec['score'], 1)}/100</b>", "cell"),
               _pm(f"Giá gần nhất: <b>{_fmt(rec['price'] or close, 0)} VND</b>", "cell"),
               _pm(f"Giá trị tham chiếu (peers): <b>{escape(ref_txt)}</b>", "cell"),
               Spacer(1, 3), Paragraph(escape(rec["hint"]), ST["small"])]
    gauge = chart_gauge(rec["score"])
    left = Table([[rec_box]], colWidths=[CONTENT_W * 0.64])
    left.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C("#F3F8FF")), ("LINEBEFORE", (0, 0), (0, -1), 3, C(tone_col)),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    mid = _side_by_side(left, gauge, CONTENT_W * 0.64 + 6, CONTENT_W * 0.36 - 6)

    mc = _f(company.get("market_cap"))
    k = [("Giá đóng cửa", f"{_fmt(close, 0)}", "VND" if close else "", NAVY),
         ("Biến động phiên", "N/A" if chg is None else f"{chg * 100:+.2f}%", "so với phiên trước", GREEN if (chg or 0) >= 0 else RED),
         ("Đỉnh 52 tuần", _fmt(hi, 0), "VND", NAVY),
         ("Đáy 52 tuần", _fmt(lo, 0), "VND", NAVY),
         ("P/E · P/B", f"{_fmt(company.get('pe') or (results.get('valuation') or {}).get('pe'), 1)} · {_fmt(company.get('pb') or (results.get('valuation') or {}).get('pb'), 1)}", "hiện tại", BLUE),
         ("Vốn hóa", "N/A" if mc is None else f"{mc / 1e9:,.0f}", "tỷ VND", PURPLE)]
    kp = _kpis(k)

    def first_sentence(txt, limit=190):
        txt = str(txt).strip()
        cut = txt.find(". ")
        out = txt if cut < 0 else txt[:cut + 1]
        return (out[:limit].rsplit(" ", 1)[0] + "…") if len(out) > limit else out
    hl = _bullets([first_sentence(x) for x in th["thesis"][:3]])
    rk = _bullets([first_sentence(x) for x in th["risks"][:2]])
    summary_box = _side_by_side(
        _callout("Luận điểm chính", hl or [_p("Chưa đủ dữ liệu.", "small")], color=GREEN, bg="#EEF9F4", width=CONTENT_W * .5 - 4),
        _callout("Rủi ro cần lưu ý", rk or [_p("Chưa ghi nhận rủi ro nổi bật.", "small")], color=RED, bg="#FFF3F4", width=CONTENT_W * .5 - 4),
        CONTENT_W * .5, CONTENT_W * .5, gap=8)

    toc_box = [Paragraph('<font color="%s"><b>MỤC LỤC</b></font>' % NAVY, ST["h2"]), toc]
    return [head, Spacer(1, 5 * mm), mid, Spacer(1, 3 * mm), kp, Spacer(1, 4 * mm), summary_box, Spacer(1, 3 * mm),
            Paragraph(escape(f"Khoảng dữ liệu: {period_text}   |   Ngày lập báo cáo: {datetime.now():%d/%m/%Y}"), ST["small"]),
            Spacer(1, 1 * mm)] + toc_box + [PageBreak()]


# ----------------------------------------------------------------------------- các mục nội dung
def _sec_overview(ticker, company, results, summary, fd, profile):
    t = results.get("technical") or {}
    fl = _section("Tổng quan doanh nghiệp", "Hồ sơ, giá thị trường và điểm số từng nhóm")
    desc = company.get("description") or ""
    rows = [[Paragraph("Tên doanh nghiệp", ST["cellb"]), _p(company.get("name") or ticker, "cell"), Paragraph("Sàn niêm yết", ST["cellb"]), _p(company.get("exchange") or "N/A", "cell")],
            [Paragraph("Ngành", ST["cellb"]), _p(company.get("sector") or "N/A", "cell"), Paragraph("Kỳ BCTC", ST["cellb"]), _p(company.get("report_period") or "N/A", "cell")],
            [Paragraph("Website", ST["cellb"]), _p(company.get("website") or "N/A", "cell"), Paragraph("Dữ liệu cập nhật", ST["cellb"]), _p(company.get("last_date") or "N/A", "cell")]]
    fl.append(_tbl(rows, [30 * mm, CONTENT_W / 2 - 30 * mm, 30 * mm, CONTENT_W / 2 - 30 * mm], header=False))
    if desc:
        # Company descriptions often arrive as one very long string with dash
        # separators. Turn those sections into spaced bullets for easier reading.
        clean_desc = re.sub(r"\s+", " ", str(desc)).strip()
        parts = [x.strip(" \t\r\n-•") for x in re.split(r"\s+-\s+(?=[A-ZÀ-Ỹ])", clean_desc) if x.strip(" \t\r\n-•")]
        if len(parts) <= 1:
            parts = [clean_desc]
        fl.append(Paragraph("Lĩnh vực hoạt động", ST["h2"]))
        fl += [Spacer(1, 2)] + _bullets(parts)
    comp = summary.get("component_scores") or {}
    items = []
    for key, lab in (("technical", "Kỹ thuật"), ("fundamental", "Tài chính"), ("valuation", "Định giá"), ("news", "Tin tức"), ("risk", "Rủi ro/An toàn")):
        sc = _f(comp.get(key))
        items.append((lab, "N/A" if sc is None else f"{sc:.1f}", _label(sc), _tone_color(sc)))
    fl += [Spacer(1, 6), _kpis(items), Paragraph("Diễn biến giá và khối lượng", ST["h2"])]
    d = t.get("data")
    if isinstance(d, pd.DataFrame) and "Close" in d and len(d) > 5:
        fl.append(chart_price(d))
    else:
        fl.append(_p("Chưa có dữ liệu giá để vẽ biểu đồ.", "small"))
    return fl


def _sec_thesis(ticker, th):
    fl = _section("Luận điểm đầu tư & rủi ro cần lưu ý", "Cá nhân hóa theo mã cổ phiếu, dữ liệu mới nhất và hồ sơ nhà đầu tư")
    fl.append(Paragraph("Luận điểm đầu tư chính", ST["h2"]))
    fl += [_p(x) for x in th["thesis"]] or [_p("Chưa đủ dữ liệu để xây dựng luận điểm đầu tư.", "small")]
    fl.append(Paragraph("Rủi ro cần lưu ý", ST["h2"]))
    fl += [_p(x) for x in th["risks"]] or [_p("Chưa ghi nhận rủi ro nổi bật từ dữ liệu hiện có.", "small")]
    fl += [Spacer(1, 4), _callout("Kết luận", [_p(th["conclusion"])], color=NAVY, bg="#F1F5FA")]
    return fl


def _sec_technical(results):
    t = results.get("technical") or {}
    fl = _section("Phân tích kỹ thuật", "Xu hướng, động lượng và thanh khoản")
    if t.get("error") or not t.get("data_available", True):
        return fl + [_p(t.get("error") or "Chưa đủ dữ liệu giá để phân tích kỹ thuật.", "small")]
    close, ma20, ma50, rsi, vr = (_f(t.get(k)) for k in ("close", "ma20", "ma50", "rsi", "volume_ratio"))
    fl.append(_kpis([("Giá đóng cửa", _fmt(close, 0), "VND", NAVY), ("MA20", _fmt(ma20, 0), "20 phiên", BLUE), ("MA50", _fmt(ma50, 0), "50 phiên", PURPLE),
                     ("RSI (14)", _fmt(rsi, 1), "động lượng", AMBER), ("Volume / MA20", _fmt(vr, 2, "x"), "thanh khoản", TEAL)]))
    d = t.get("data")
    if isinstance(d, pd.DataFrame) and len(d) > 5:
        fl += [Spacer(1, 6), chart_price(d, h=3.2), Spacer(1, 4), chart_rsi_macd(d)]
    sig = t.get("signals")
    if isinstance(sig, dict) and sig:
        rows = [[Paragraph("Chỉ báo", ST["cellh"]), Paragraph("Tín hiệu", ST["cellh"])]] + [[_p(k, "cell"), _p(v, "cell")] for k, v in sig.items()]
        fl += [Spacer(1, 6), _tbl(rows, [CONTENT_W * .5, CONTENT_W * .5])]
    if t.get("commentary"):
        fl += [Spacer(1, 6), _callout("Nhận định kỹ thuật", [_p(t["commentary"])])]
    return fl


def _sec_fundamental(results, summary, fd, company):
    f = results.get("fundamental") or {}
    hist = _history(fd)
    fl = _section("Phân tích tài chính", "Kết quả kinh doanh, hiệu quả sinh lời, cấu trúc tài sản và đòn bẩy")
    sc = _f(f.get("score"))
    last = hist[-1] if hist else {}
    bank = str(fd.get("financialBusinessType") or "").lower() == "bank"
    roe, roa = _ratio(last.get("roe")), _ratio(last.get("roa"))
    de = _f(fd.get("debtToEquity"))
    kp = [("Fundamental Score", "N/A" if sc is None else f"{sc:.1f}", _label(sc), _tone_color(sc)),
          ("Thu nhập HĐ" if bank else "Doanh thu", _bn(last.get("revenue")), f"tỷ đồng · năm {last.get('period', 'N/A')}", BLUE),
          ("LNST", _bn(last.get("net_profit")), f"tỷ đồng · năm {last.get('period', 'N/A')}", GREEN),
          ("ROE", "N/A" if roe is None else f"{roe * 100:.1f}%", "sinh lời VCSH", PURPLE),
          ("ROA", "N/A" if roa is None else f"{roa * 100:.1f}%", "sinh lời tài sản", AMBER)]
    fl.append(_kpis(kp))
    if hist:
        fl += [Spacer(1, 6), chart_fin(hist), Spacer(1, 4), chart_balance(hist)]
        hdr = [Paragraph("Chỉ tiêu (tỷ đồng)", ST["cellh"])] + [Paragraph(f"<b>{r['period']}</b>", ST["cellr"]) for r in hist]
        def row(label, key, scale=1e9, fmt="{:,.0f}", ratio=False):
            vals = []
            for r in hist:
                v = _ratio(r.get(key)) * 100 if ratio and _ratio(r.get(key)) is not None else _f(r.get(key))
                vals.append("N/A" if v is None else fmt.format(v / (1 if ratio else scale)))
            return [_p(label, "cell")] + [Paragraph(x, ST["cellr"]) for x in vals]
        rows = [hdr, row("Thu nhập HĐ" if bank else "Doanh thu thuần", "revenue"), row("Lợi nhuận sau thuế", "net_profit"),
                row("Tổng tài sản", "total_assets"), row("Vốn chủ sở hữu", "equity"),
                row("ROE (%)", "roe", fmt="{:.1f}", ratio=True), row("ROA (%)", "roa", fmt="{:.1f}", ratio=True)]
        n = len(hist)
        fl += [Spacer(1, 6), _tbl(rows, [CONTENT_W * .30] + [CONTENT_W * .70 / n] * n)]
    if f.get("commentary"):
        fl += [Spacer(1, 6), _callout("Nhận định tài chính", [_p(f["commentary"])], color=TEAL, bg="#EEF9F8")]
    # phụ lục BCTC trích từ dữ liệu gốc
    raw = fd.get("_raw") or {}
    appendix = []
    names = {"income": "Kết quả kinh doanh", "balance": "Bảng cân đối kế toán", "cash": "Lưu chuyển tiền tệ", "ratio": "Chỉ số tài chính"}
    for key, df in raw.items():
        if not isinstance(df, pd.DataFrame) or df.empty or "item" not in df.columns:
            continue
        pcols = [c for c in df.columns if c not in ("item", "item_id", "unit")]
        if not pcols:
            continue
        per = sorted(map(str, pcols))[-1]
        sub = df[["item", per]].copy()
        sub[per] = pd.to_numeric(sub[per], errors="coerce")
        sub = sub.dropna().head(10)
        if sub.empty:
            continue
        title = next((v for k, v in names.items() if k in str(key).lower()), str(key))
        rows = [[Paragraph(f"{title} - {per}", ST["cellh"]), Paragraph("Giá trị", ST["cellh"])]]
        for _, r in sub.iterrows():
            val = r[per]
            rows.append([_p(str(r["item"]), "cell"), Paragraph(f"{val / 1e9:,.1f}" if abs(val) >= 1e7 else f"{val:,.2f}", ST["cellr"])])
        appendix.append(KeepTogether([Spacer(1, 6), _tbl(rows, [CONTENT_W * .78, CONTENT_W * .22])]))
    if appendix:
        head = Paragraph("Trích yếu báo cáo tài chính (đơn vị: tỷ đồng nếu giá trị lớn)", ST["h2"])
        appendix[0] = KeepTogether([head, appendix[0]])
        fl += appendix
    return fl


def _sec_valuation(results, fd):
    v = results.get("valuation") or {}
    hist = _history(fd)
    fl = _section("Phân tích định giá", "Định giá so với lịch sử của chính doanh nghiệp và so với nhóm cùng ngành")
    sc = _f(v.get("score"))
    peer = v.get("peer_valuation") or {}
    ref = _f(v.get("peer_fair_value") or peer.get("peer_fair_value") or peer.get("fair_value"))
    up = _f(v.get("peer_upside_downside"))
    if up is not None and abs(up) > 3:
        up /= 100
    fl.append(_kpis([("Valuation Score", "N/A" if sc is None else f"{sc:.1f}", _label(sc), _tone_color(sc)),
                     ("P/E hiện tại", _fmt(v.get("pe"), 2, "x"), f"Trung vị LS {_fmt(v.get('historical_pe_median'), 2, 'x')}", BLUE),
                     ("P/B hiện tại", _fmt(v.get("pb"), 2, "x"), f"Trung vị LS {_fmt(v.get('historical_pb_median'), 2, 'x')}", TEAL),
                     ("Peer Fair Value", "N/A" if ref is None else f"{ref:,.0f}", "VND (hàm ý)", PURPLE),
                     ("Chênh lệch", "N/A" if up is None else f"{up * 100:+.1f}%", "so với giá hiện tại", GREEN if (up or 0) >= 0 else RED)]))
    if hist:
        fl += [Spacer(1, 6), chart_valuation(hist, v)]
    peers = peer.get("peers")
    prow = []
    if isinstance(peers, pd.DataFrame):
        peers = peers.to_dict("records")
    if isinstance(peers, list):
        peers = _norm_cols([p for p in peers if isinstance(p, dict)], ("roe",))
        for p in peers[:8]:
            if isinstance(p, dict):
                code = p.get("symbol") or p.get("ticker") or p.get("Mã") or ""
                roe = _ratio(p.get("roe"))
                prow.append([_p(code, "cell"), Paragraph(_fmt(p.get("pe"), 2, "x"), ST["cellr"]), Paragraph(_fmt(p.get("pb"), 2, "x"), ST["cellr"]),
                             Paragraph("N/A" if roe is None else f"{roe * 100:.1f}%", ST["cellr"]), _p(p.get("quality") or p.get("peer_quality") or "", "cell")])
    if prow:
        rows = [[Paragraph(h, ST["cellh"]) for h in ("Mã peer", "P/E", "P/B", "ROE", "Chất lượng")]] + prow
        fl += [Paragraph("So sánh với doanh nghiệp cùng ngành", ST["h2"]), _tbl(rows, [CONTENT_W * .2, CONTENT_W * .2, CONTENT_W * .2, CONTENT_W * .2, CONTENT_W * .2])]
    for ttl, text in (("Nhận định định giá", v.get("commentary")), ("Nhận định so sánh cùng ngành", v.get("peer_commentary") or peer.get("commentary"))):
        if text:
            fl += [Spacer(1, 6), _callout(ttl, [_p(text)], color=PURPLE, bg="#F6F3FF")]
    fl += [Spacer(1, 4), _p("Peer Fair Value là giá trị hàm ý theo bội số tương đối của nhóm cùng ngành, không phải giá mục tiêu và không phải định giá nội tại DCF.", "small")]
    return fl


def _sec_news(results):
    n = results.get("news") or {}
    items = [i for i in (n.get("items") or []) if isinstance(i, dict)]
    fl = _section("Tin tức & triển vọng", "Tin gần đây về doanh nghiệp và sắc thái thông tin")
    sc = _f(n.get("score"))
    left = [_kpis([("News Score", "N/A" if sc is None else f"{sc:.1f}", n.get("classification") or _label(sc), _tone_color(sc))], width=CONTENT_W * .6),
            Spacer(1, 5), _p(n.get("commentary") or "Chưa có nhận định tin tức.", "body")]
    fl.append(_side_by_side(left, chart_news(items) if items else Spacer(1, 1), CONTENT_W * .6 + 6, CONTENT_W * .4 - 6))
    smap = {"Positive": ("Tích cực", GREEN), "Negative": ("Tiêu cực", RED), "Neutral": ("Trung tính", MUTED)}
    rows = [[Paragraph(h, ST["cellh"]) for h in ("Ngày", "Sắc thái", "Tiêu đề / nguồn")]]
    for i in sorted(items, key=lambda x: str(x.get("published")), reverse=True)[:10]:
        lab, col = smap.get(i.get("sentiment"), ("N/A", MUTED))
        rows.append([_p(str(i.get("published") or "")[:10], "cell"), Paragraph(f'<font color="{col}"><b>{lab}</b></font>', ST["cell"]),
                     _p(i.get("title") or "", "cell")])
    if len(rows) > 1:
        fl += [Paragraph("Tin nổi bật", ST["h2"]), _tbl(rows, [CONTENT_W * .13, CONTENT_W * .14, CONTENT_W * .73])]
    fl += [Spacer(1, 4), _p(f"Nguồn: {n.get('source') or 'Google News RSS'}. News Score dùng heuristic theo tiêu đề và độ mới của tin, không phải mô hình NLP toàn văn.", "small")]
    return fl


def _sec_score(summary, profile, th):
    comp = summary.get("component_scores") or {}
    fl = _section("Investment Score & hồ sơ nhà đầu tư", "Cấu trúc điểm, mức đóng góp và góc nhìn theo khẩu vị rủi ro")
    fl.append(_side_by_side(chart_components(comp), chart_profiles(summary.get("profile_scores") or {}, profile), CONTENT_W * .6 + 4, CONTENT_W * .4 - 4))
    weights = {"fundamental": 25, "valuation": 25, "technical": 25, "news": 15, "risk": 10}
    names = {"fundamental": "Tài chính", "valuation": "Định giá", "technical": "Kỹ thuật", "news": "Tin tức", "risk": "Rủi ro/An toàn"}
    contrib = summary.get("contributions") or {}
    rows = [[Paragraph(h, ST["cellh"]) for h in ("Thành phần", "Điểm", "Trọng số", "Đóng góp")]]
    for k in weights:
        sc = _f(comp.get(k))
        c = _f(contrib.get(k))
        if c is None and sc is not None:
            c = sc * weights[k] / 100
        rows.append([_p(names[k], "cell"), Paragraph(_fmt(sc, 1), ST["cellr"]), Paragraph(f"{weights[k]}%", ST["cellr"]), Paragraph(_fmt(c, 2), ST["cellr"])])
    total = _f(summary.get("score"))
    rows.append([Paragraph("Investment Score", ST["cellb"]), Paragraph("", ST["cellr"]), Paragraph("100%", ST["cellr"]), Paragraph(f"<b>{_fmt(total, 2)}</b>", ST["cellr"])])
    fl += [Spacer(1, 6), _tbl(rows, [CONTENT_W * .4, CONTENT_W * .2, CONTENT_W * .2, CONTENT_W * .2])]
    pos = th.get("thesis", [])[:0]
    fl += [Spacer(1, 6), _callout("Vì sao ra điểm này", [_p(th["conclusion"])], color=BLUE)]
    if summary.get("missing"):
        fl += [Spacer(1, 4), _callout("Cảnh báo dữ liệu", [_p("Thiếu thành phần: " + ", ".join(map(str, summary["missing"])) + ". StockLens không tự nội suy thành phần bị thiếu.")], color=RED, bg="#FFF3F4")]
    return fl


def _sec_method(results, summary):
    fl = _section("Phương pháp, nguồn dữ liệu & giới hạn")
    rows = [[Paragraph("Khối", ST["cellh"]), Paragraph("Nguồn / phương pháp", ST["cellh"])],
            [_p("Giá & kỹ thuật", "cellb"), _p("DNSE OpenAPI (dự phòng vnstock Market); MA20, MA50, RSI(14), MACD(12,26,9), Volume/MA20, Volatility, Drawdown.", "cell")],
            [_p("BCTC & cơ bản", "cellb"), _p("vnstock/KBS; ROE, ROA, biên lợi nhuận, tăng trưởng, Debt/Equity; chỉ tiêu thiếu được loại khỏi mẫu số, không gán 0.", "cell")],
            [_p("Định giá", "cellb"), _p("P/E, P/B so với lịch sử doanh nghiệp; Peer Valuation theo trung vị P/E, P/B cùng ngành (phân loại ICB) khi đủ dữ liệu.", "cell")],
            [_p("Tin tức", "cellb"), _p("Google News RSS; sentiment heuristic theo tiêu đề và độ mới.", "cell")],
            [_p("Luận điểm & rủi ro", "cellb"), _p("Sinh tự động từ kết quả phân tích của từng mã và hồ sơ nhà đầu tư; không bổ sung dữ kiện ngoài dữ liệu đã thu thập (trừ ghi chú thủ công nếu có).", "cell")],
            [_p("Investment Score", "cellb"), _p("25% Tài chính + 25% Định giá + 25% Kỹ thuật + 15% Tin tức + 10% Rủi ro/An toàn; điểm theo hồ sơ dùng trọng số điều chỉnh.", "cell")]]
    fl.append(_tbl(rows, [CONTENT_W * .22, CONTENT_W * .78]))
    fl += [Spacer(1, 8), _callout("Giới hạn & tuyên bố miễn trừ", [_p(
        "Investment Score là mô hình heuristic phục vụ học tập, chưa được backtest như một chiến lược giao dịch. Dữ liệu bên thứ ba có thể thay đổi, "
        "chậm cập nhật hoặc thiếu; báo cáo hiển thị N/A thay vì tự điền số liệu. Peer Fair Value chỉ là giá trị hàm ý tương đối, không phải giá mục tiêu. "
        "Nội dung không cấu thành khuyến nghị mua, bán, nắm giữ chứng khoán hoặc tư vấn đầu tư cá nhân.")], color=RED, bg="#FFF6F7")]
    return fl


# ----------------------------------------------------------------------------- tài liệu + đánh số trang
class _Doc(BaseDocTemplate):
    def __init__(self, buf, ticker, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=17 * mm,
                         title=f"StockLens - {ticker}", author="StockLens", **kw)
        self.ticker = ticker
        self.addPageTemplates([PageTemplate(id="p", frames=[Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f",
                                                                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                                            onPage=self._decorate)])

    def _decorate(self, canv, doc):
        w, h = A4
        canv.saveState()
        canv.setFillColor(C(NAVY)); canv.setFont("SL-B", 9); canv.drawString(18 * mm, h - 11 * mm, "STOCKLENS")
        canv.setFillColor(C(MUTED)); canv.setFont("SL", 7.5)
        canv.drawString(18 * mm + 62, h - 11 * mm, "Investment Intelligence Platform")
        canv.drawRightString(w - 18 * mm, h - 11 * mm, f"Báo cáo phân tích cổ phiếu {self.ticker}")
        canv.setStrokeColor(C(LINE)); canv.setLineWidth(.6); canv.line(18 * mm, h - 13.5 * mm, w - 18 * mm, h - 13.5 * mm)
        canv.line(18 * mm, 13 * mm, w - 18 * mm, 13 * mm)
        canv.setFont("SL", 6.8)
        canv.drawString(18 * mm, 9 * mm, "Nguồn: DNSE OpenAPI | vnstock/KBS | Google News RSS  -  Dự án học tập, không phải khuyến nghị đầu tư")
        canv.restoreState()

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name == "sec":
            text = fl.getPlainText()
            key = f"sec{self.seq.nextf('sec')}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, text, self.page, key))


class _Numbered(rl_canvas.Canvas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            self.setFont("SL", 7.5)
            self.setFillColor(C(MUTED))
            self.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Trang {self._pageNumber}/{total}")
            super().showPage()
        super().save()


# ----------------------------------------------------------------------------- hàm chính
def generate_pdf(ticker, period_text, results, summary, sections, profile, company_info=None, financial_data=None):
    global ST
    _register_fonts()
    ST = _styles()
    results, summary = results or {}, summary or {}
    company, fd = company_info or {}, financial_data or {}
    sections = set(sections or [])
    t = results.get("technical") or {}
    close = _f(t.get("close"))
    th = build_thesis(ticker, company, results, summary, fd, profile, close)

    toc = TableOfContents()
    toc.dotsMinLevel = 0
    toc.levelStyles = [ParagraphStyle("toc0", parent=ST["toc0"], fontName="SL", fontSize=9.5, leading=16, leftIndent=0, firstLineIndent=0)]

    plan = [("overview", "Tổng quan doanh nghiệp"), ("thesis", "Luận điểm đầu tư & rủi ro cần lưu ý")]
    plan += [(k, n) for k, n in (("technical", "Phân tích kỹ thuật"), ("fundamental", "Phân tích tài chính"), ("valuation", "Phân tích định giá"),
                                 ("news", "Tin tức & triển vọng"), ("score", "Investment Score & hồ sơ nhà đầu tư")) if k in sections]
    plan.append(("method", "Phương pháp, nguồn dữ liệu & giới hạn"))

    builders = {
        "overview": lambda: _sec_overview(ticker, company, results, summary, fd, profile),
        "thesis": lambda: _sec_thesis(ticker, th),
        "technical": lambda: _sec_technical(results),
        "fundamental": lambda: _sec_fundamental(results, summary, fd, company),
        "valuation": lambda: _sec_valuation(results, fd),
        "news": lambda: _sec_news(results),
        "score": lambda: _sec_score(summary, profile, th),
        "method": lambda: _sec_method(results, summary),
    }

    story = _cover(ticker, period_text, profile, results, summary, company, fd, th, toc)
    for i, (key, title) in enumerate(plan, 1):
        try:
            body = builders[key]()
            # đánh số mục: thay tiêu đề đầu tiên (Paragraph style 'sec') bằng "i. title"
            for fl in body:
                if isinstance(fl, Paragraph) and fl.style.name == "sec":
                    body[body.index(fl)] = Paragraph(escape(f"{i}. {title}"), ST["sec"])
                    break
        except Exception as exc:  # không để một mục lỗi làm hỏng cả báo cáo
            body = [Paragraph(escape(f"{i}. {title}"), ST["sec"]), _p(f"Không dựng được mục này: {exc}", "small")]
        story += body
        if i < len(plan):
            story.append(PageBreak())

    buf = io.BytesIO()
    doc = _Doc(buf, ticker)
    doc.multiBuild(story, canvasmaker=_Numbered)
    return buf.getvalue()
