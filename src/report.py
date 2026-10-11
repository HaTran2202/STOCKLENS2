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
NAVY, BLUE, TEAL = "#0A1930", "#215C93", "#12A9A4"
TEXT, MUTED, LINE, SOFT = "#1B2F47", "#718097", "#DCE5ED", "#F3F7FA"
GREEN, AMBER, RED, PURPLE = "#0F9178", "#DCA14B", "#CD5262", "#6C6DB3"
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
    add("body", fontSize=9.2, leading=15.2, alignment=TA_JUSTIFY, spaceAfter=6)
    add("small", fontSize=7.8, leading=11.2, textColor=C(MUTED))
    add("tiny", fontSize=6.5, leading=8.5, textColor=C(MUTED))
    add("sec", fontName="SL-B", fontSize=19, leading=25, textColor=C(NAVY), spaceBefore=3, spaceAfter=5, keepWithNext=1)
    add("subsec", fontSize=9, leading=13, textColor=C(MUTED), spaceAfter=12, keepWithNext=1)
    add("h2", fontName="SL-B", fontSize=11.5, leading=15, textColor=C(BLUE), spaceBefore=10, spaceAfter=6, keepWithNext=1)
    add("kl", fontName="SL-B", fontSize=7.1, leading=10, textColor=C(MUTED))
    add("kv", fontName="SL-B", fontSize=16, leading=20, textColor=C(NAVY))
    add("ks", fontSize=6.9, leading=9.2, textColor=C(MUTED))
    add("cell", fontSize=8.2, leading=11.1)
    add("cellb", fontName="SL-B", fontSize=8.2, leading=11.1, textColor=C(NAVY))
    add("cellr", fontSize=8.1, leading=11.1, alignment=TA_RIGHT)
    add("cellh", fontName="SL-B", fontSize=8.1, leading=11.1, textColor=C(NAVY))
    add("cover_t", fontName="SL-B", fontSize=24, leading=28, textColor=C(NAVY))
    add("cover_n", fontSize=11, leading=14, textColor=C("#385576"))
    add("rec_t", fontName="SL-B", fontSize=15, leading=18)
    add("toc0", fontSize=10, leading=24, leftIndent=0, textColor=C(TEXT))
    add("bullet", fontSize=8.8, leading=13.7, leftIndent=9, bulletIndent=0, spaceAfter=4, alignment=TA_JUSTIFY)
    add("editor_toc_title", fontName="SL-B", fontSize=24, leading=29, textColor=C(NAVY), spaceAfter=9)
    add("editor_toc_intro", fontSize=10, leading=16, textColor=C(TEXT), spaceAfter=12)
    add("editor_kicker", fontName="SL-B", fontSize=8, leading=11, textColor=C(TEAL), spaceAfter=8)
    add("editor_summary", fontSize=10, leading=16.5, textColor=C(TEXT), spaceAfter=8)
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
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("LINEBELOW", (0, 0), (-1, -1), .4, C(LINE))]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), C("#EAF0F5")), ("LINEBELOW", (0, 0), (-1, 0), .9, C(TEAL))]
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
    style = [("BACKGROUND", (0, 0), (-1, -1), C("#F6F8FA")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 11), ("BOTTOMPADDING", (0, 0), (-1, -1), 11)]
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


# ----------------------------------------------------------------------------- biên tập báo cáo: bìa, mục lục
# Bìa được vẽ trực tiếp bằng vector để sắc nét khi phóng to và không phụ thuộc internet.
# Đồ thị trên bìa chỉ là hoạ tiết, KHÔNG được gọi là biểu đồ giá thực tế.
def _cover(ticker, period_text, profile, results, summary, company, fd, th, toc):
    v = results.get("valuation") or {}
    rec = th.get("recommendation") or {}
    name = company.get("name") or ticker
    t = results.get("technical") or {}
    score = _f(rec.get("score"))
    close, _, _, _, _ = _price_stats(t, company)
    stance = rec.get("stance") or "Chưa đủ dữ liệu"
    # Trang 1 được vẽ trong onPage, phần flowables chỉ tạo page break.
    # Trang 2 là spread thông tin điều hướng báo cáo.
    notes = [
        "Báo cáo được xây dựng tự động từ dữ liệu giá, báo cáo tài chính và tin tức.",
        "Điểm đầu tư là mô hình quy tắc tham khảo; không thay thế nghiên cứu doanh nghiệp.",
        "Chỉ tiêu thiếu dữ liệu hoặc định giá peers không đáng tin cậy được ghi N/A.",
    ]
    return [
        Spacer(1, 2 * mm), PageBreak(),
        Paragraph("RESEARCH / STOCKLENS", ST["editor_kicker"]),
        Spacer(1, 6 * mm),
        Paragraph("Nội dung nghiên cứu", ST["editor_toc_title"]),
        Paragraph(f"{escape(ticker)}  ·  {escape(str(name))}  |  Hồ sơ: {escape(str(profile))}", ST["editor_toc_intro"]),
        _kpis([
            ("ĐIỂM TỔNG HỢP", _fmt(score, 1) + "/100", stance, _tone_color(score)),
            ("THỊ GIÁ", _fmt(rec.get("price") or close, 0), "VND/cổ phiếu", BLUE),
            ("KỲ TÀI CHÍNH", str(fd.get("reportPeriod") or company.get("report_period") or "N/A"), "BCTC gần nhất trong dữ liệu", TEAL),
        ]),
        Spacer(1, 13 * mm),
        Paragraph("CẤU TRÚC BÁO CÁO", ST["editor_kicker"]),
        toc,
        Spacer(1, 11 * mm),
        _callout("Cách đọc báo cáo", [_p(x, "small") for x in notes], color=TEAL, bg="#F2F8F8"),
        Spacer(1, 6 * mm),
        _p("Dữ liệu có thể không đồng nhất về thời điểm; hãy đọc mục Phương pháp và giới hạn trước khi sử dụng điểm số.", "small"),
        PageBreak(),
    ]


def _wrap_draw(canv, text, style, x, top, width, limit_height=None):
    p = Paragraph(escape(str(text or "")), style)
    _, ph = p.wrap(width, 1000)
    if limit_height and ph > limit_height:
        # Không để thông tin dài tràn vào phần khác của bìa; giữ thông tin quan trọng ở PDF bên trong.
        p = Paragraph(escape(str(text or "")[:190].rsplit(" ", 1)[0] + "…"), style)
        _, ph = p.wrap(width, 1000)
    p.drawOn(canv, x, top - ph)
    return ph


def _draw_cover_page(canv, ticker, period_text, profile, results, summary, company, th):
    w, h = A4
    canv.saveState()
    canv.setFillColor(C(NAVY)); canv.rect(0, 0, w, h, fill=1, stroke=0)
    # Họa tiết kiến trúc tài chính trừu tượng, KHÔNG phải đường giá FPT.
    canv.setFillColor(C("#102844")); canv.roundRect(0, h * .46, w * 1.06, h * .27, 18, fill=1, stroke=0)
    canv.setStrokeColor(C("#22415B")); canv.setLineWidth(.7)
    for i in range(0, 18):
        xx = 26 * mm + i * 12.0 * mm
        canv.line(xx, h * .49, xx, h * .73)
    for j in range(6):
        yy = h * (.50 + j * .044)
        canv.line(0, yy, w, yy)
    # Dải nhịp công nghệ (đường trang trí không có thang số liệu)
    pts = [(0,h*.53),(w*.10,h*.56),(w*.22,h*.55),(w*.34,h*.62),(w*.46,h*.595),
           (w*.57,h*.65),(w*.67,h*.62),(w*.76,h*.69),(w*.84,h*.665),(w,h*.735)]
    path = canv.beginPath();path.moveTo(*pts[0]);
    for x,y in pts[1:]:path.lineTo(x,y)
    canv.setStrokeColor(C("#1AAEA8"));canv.setLineWidth(3.0);canv.drawPath(path,stroke=1,fill=0)
    for x,y in pts[1:-1:2]:
        canv.setFillColor(C("#A4E0DB"));canv.circle(x,y,3.1,fill=1,stroke=0)
    # Số chương mờ, độ sâu gần giống ngôn ngữ báo cáo biên tập.
    canv.setFillColor(C("#143151"));canv.setFont("SL-B", 146)
    canv.drawRightString(w-18*mm, h*.75, ticker[:4].upper())
    x = 20*mm
    canv.setFillColor(C("#59D2C6"));canv.setFont("SL-B", 10)
    canv.drawString(x, h-24*mm, "STOCKLENS    /    EQUITY RESEARCH")
    canv.setStrokeColor(C("#5DD1CB"));canv.setLineWidth(1.1)
    canv.line(x,h-28*mm,w-20*mm,h-28*mm)
    canv.setFillColor(colors.white);canv.setFont("SL",10)
    canv.drawString(x,h-43*mm,"BÁO CÁO PHÂN TÍCH CƠ HỘI ĐẦU TƯ")
    canv.setFont("SL-B",64)
    canv.drawString(x,h-70*mm,ticker)
    body = ParagraphStyle("cover_white",fontName="SL",fontSize=13.5,leading=19,textColor=C("#BFD2E0"))
    _wrap_draw(canv,company.get("name") or ticker,body,x,h-74*mm,165*mm)
    csector=str(company.get("sector") or "Chưa xác minh ngành")
    ex=str(company.get("exchange") or "Chưa xác minh sàn")
    canv.setFont("SL",9);canv.setFillColor(C("#D2E3EB"))
    canv.drawString(x,h-100*mm, f"{ex}     ·     {csector}"[:92])
    # Tóm tắt đánh giá bên dưới đồ thị trang trí
    rec = th.get("recommendation") or {}
    stance = rec.get("stance") or "Chưa đủ dữ liệu"
    score = _f(rec.get("score"))
    t=results.get("technical") or {}
    close=_f(rec.get("price")) or _f(t.get("close"))
    canv.setFillColor(C("#102844"));canv.roundRect(x, h*.32, w-2*x, 87, 12,fill=1,stroke=0)
    canv.setFillColor(C("#5DD1CB"));canv.setFont("SL-B",8)
    canv.drawString(x+14,h*.32+64,"QUAN ĐIỂM ĐẦU TƯ")
    canv.setFillColor(colors.white);canv.setFont("SL-B",20)
    canv.drawString(x+14,h*.32+37,str(stance)[:32])
    canv.setFont("SL",9);canv.setFillColor(C("#C0D4E1"))
    canv.drawString(x+14,h*.32+18,f"Hồ sơ {profile} · Score: {_fmt(score,1)}/100")
    canv.setFillColor(C("#5DD1CB"));canv.setFont("SL-B",27)
    canv.drawRightString(w-x-12,h*.32+38,_fmt(close,0))
    canv.setFont("SL",8);canv.setFillColor(C("#BAD7DB"))
    canv.drawRightString(w-x-12,h*.32+19,"VND / cổ phiếu")
    # Methodology/cập nhật
    canv.setFillColor(C("#A9C4D6"));canv.setFont("SL-B",8)
    canv.drawString(x,h*.26,"PHẠM VI PHÂN TÍCH")
    _wrap_draw(canv,period_text,ParagraphStyle("period",fontName="SL",fontSize=10,leading=14,textColor=colors.white),x,h*.245,w-2*x)
    canv.setFillColor(C("#B4CDDA"));canv.setFont("SL",8)
    canv.drawString(x, 30*mm, f"Công bố: {datetime.now():%d/%m/%Y}   ·   Đồ họa bìa mang tính biểu trưng")
    canv.setStrokeColor(C("#31506A"));canv.line(x,24*mm,w-x,24*mm)
    canv.setFillColor(C("#5DD1CB"));canv.setFont("SL-B",9)
    canv.drawString(x,18*mm,"STOCKLENS / INVESTMENT INTELLIGENCE PLATFORM")
    canv.restoreState()

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
    hist = _history(fd)
    if hist:
        last = hist[-1]
        highlight = []
        for title, key in (("DOANH THU / THU NHẬP", "revenue"), ("LỢI NHUẬN SAU THUẾ", "net_profit"), ("TỔNG TÀI SẢN", "total_assets")):
            if _f(last.get(key)) is not None:
                highlight.append((title, _bn(last.get(key)), f"tỷ đồng · FY{last.get('period')}", BLUE))
        if highlight:
            fl += [Spacer(1, 8 * mm), Paragraph("Dữ liệu tài chính gần nhất", ST["h2"]), _kpis(highlight)]
    fl += [Spacer(1, 5 * mm), _p("Biểu đồ thị trường và thông tin tài chính có thể có kỳ cập nhật khác nhau. Đối chiếu ngày dữ liệu và nguồn tại phần phương pháp.", "small")]
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
        labels = {'Positive':'Tích cực','Negative':'Tiêu cực','Neutral':'Trung lập'}
        rows = [[Paragraph(h, ST['cellh']) for h in ('Chỉ báo', 'Tín hiệu', 'Điểm')]]
        for key, val in sig.items():
            if isinstance(val, dict):
                label = labels.get(str(val.get('signal')), str(val.get('signal') or 'N/A'))
                score = _fmt(val.get('score'), 0)
            else:
                label, score = str(val), 'N/A'
            rows.append([_p(key, 'cell'), _p(label, 'cell'), _p(score, 'cell')])
        fl += [Spacer(1, 6), _tbl(rows, [CONTENT_W * .33]*3)]
    if t.get("commentary"):
        fl += [Spacer(1, 6), _callout("Nhận định kỹ thuật", [_p(t["commentary"])])]
    return fl


def _sec_fundamental(results, summary, fd, company):
    f = results.get("fundamental") or {}
    hist = _history(fd)[-4:]
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
    if bank:
        banking = [("NIM", fd.get('netInterestMargin')), ("NPL", fd.get('nplRatio')),
                   ("CAR", fd.get('capitalAdequacyRatio')), ("CASA", fd.get('casaRatio')),
                   ("LDR", fd.get('loanToDepositRatio'))]
        fl += [Spacer(1, 5), _kpis([(label, 'N/A' if _ratio(value) is None else f'{_ratio(value)*100:.2f}%',
                                     'Dữ liệu CSV FY, theo định nghĩa nguồn', BLUE)
                                    for label,value in banking])]
        fl += [Spacer(1, 4), _p('LLR chưa có dữ liệu: không tính hoặc suy đoán. LDR và CAR sử dụng định nghĩa của nhà cung cấp, cần đối chiếu báo cáo ngân hàng.', 'small')]
    if fd.get("qualityWarnings"):
        warnings = [str(x) for x in fd.get("qualityWarnings", []) if x][:3]
        # Thay cảnh báo kỹ thuật tiếng Anh thành diễn giải dễ hiểu cho người đọc.
        known = []
        for warning in warnings:
            low = warning.lower()
            if "period_date" in low or "snapshot" in low or "market_cap/shares" in low:
                text = "Chỉ số định giá từ CSV thiếu ngày cập nhật; cần kiểm chứng giá, kỳ EPS/BVPS trước khi kết luận."
            elif "reported" in low and "ratio" in low:
                text = "Chỉ số tài chính từ nguồn dữ liệu có thể dùng định nghĩa khác báo cáo kiểm toán."
            else:
                text = warning
            if text not in known:
                known.append(text)
        fl += [Spacer(1, 5), _callout("Lưu ý chất lượng dữ liệu", [_p(x, "small") for x in known], color=AMBER, bg="#FBF7EE")]
    if hist:
        fl += [Spacer(1, 6), chart_fin(hist)]
        if any(_f(x.get('total_assets')) is not None or _f(x.get('equity')) is not None for x in hist):
            fl += [Spacer(1, 4), chart_balance(hist)]
        else:
            fl += [Spacer(1, 3), _p('Chưa có dữ liệu tài sản/vốn chủ sở hữu để vẽ biểu đồ.', 'small')]
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
    # Phụ lục BCTC; trang riêng để tránh cảnh báo/mẩu bảng nằm lẻ loi ở cuối trang.
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
        keep = ['item', per] + (['unit'] if 'unit' in df.columns else [])
        sub = df[keep].copy()
        sub[per] = pd.to_numeric(sub[per], errors='coerce')
        sub = sub.dropna(subset=[per]).head(12)
        if sub.empty:
            continue
        title = next((v for k, v in names.items() if k in str(key).lower()), str(key))
        rows = [[Paragraph(f"{title} - {per}", ST["cellh"]), Paragraph("Giá trị", ST["cellh"])]]
        for _, r in sub.iterrows():
            val = float(r[per])
            unit = str(r.get('unit') or '')
            if unit.upper() == 'VND':
                shown = f'{val / 1e9:,.1f} tỷ đồng'
            elif unit.lower() in ('ratio', 'percent'):
                shown = f'{val * 100:.2f}%' if abs(val) <= 1 else f'{val:.2f}%'
            elif unit.lower() == 'vnd/cp':
                shown = f'{val:,.0f} VND/cp'
            else:
                shown = f'{val:,.2f}'
            rows.append([_p(str(r['item']), 'cell'), Paragraph(shown, ST['cellr'])])
        appendix.append([Spacer(1, 6), _tbl(rows, [(CONTENT_W / 2 - 5) * .62, (CONTENT_W / 2 - 5) * .38])])
    if appendix:
        head = [Paragraph("PHỤ LỤC / BCTC", ST["editor_kicker"]),
                Paragraph("Trích yếu báo cáo tài chính", ST["editor_toc_title"]),
                _p("Các số liệu dưới đây lấy từ chỉ tiêu trọng yếu có đơn vị và kỳ công bố được xác định.", "small")]
        # Trình bày 2 cột như trang tài chính của báo cáo thường niên, tránh trang phụ lục lẻ.
        fl += head
        half = CONTENT_W / 2
        for i in range(0, len(appendix), 2):
            left = appendix[i]
            right = appendix[i + 1] if i + 1 < len(appendix) else [Spacer(1, 2)]
            fl.append(_side_by_side(left, right, half, half, gap=10))
            fl.append(Spacer(1, 5))
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
    fl += [Spacer(1, 4), _p("P/E, P/B snapshot CSV không có ngày công bố; chỉ được dùng khi giá hàm ý khớp thị trường. Peer Fair Value chỉ là giá trị tham chiếu khi mẫu đủ tin cậy, không phải giá mục tiêu.", "small")]
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
            [_p("BCTC & cơ bản", "cellb"), _p("CSV stock.quanganh.org (BCTC FY 2020–2025, ngân hàng có ISB/BSB và chỉ số NIM/NPL/CAR/CASA/LDR); KBS tùy chọn. Dữ liệu tiền chuẩn hóa về VND; không tự điền năm thiếu; điểm tài chính bị chặn khi dữ liệu không đủ.", "cell")],
            [_p("Định giá", "cellb"), _p("P/E, P/B snapshot CSV chỉ được sử dụng khi mức giá hàm ý (vốn hóa / cổ phiếu) khớp giá quan sát; thiếu timestamp phải cảnh báo. Peers lấy theo bảng nhóm ngành tham khảo riêng, chưa phải ICB chuẩn; chỉ công bố giá hàm ý khi chất lượng phù hợp. Dữ liệu snapshot CSV thiếu ngày xác minh.", "cell")],
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
    def __init__(self, buf, ticker, cover_data=None, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=17 * mm,
                         title=f"StockLens - {ticker}", author="StockLens", **kw)
        self.ticker = ticker
        self.cover_data = cover_data
        self.addPageTemplates([PageTemplate(id="p", frames=[Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f",
                                                                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                                            onPage=self._decorate)])

    def _decorate(self, canv, doc):
        w, h = A4
        if self.page == 1 and self.cover_data is not None:
            _draw_cover_page(canv, *self.cover_data)
            return
        canv.saveState()
        canv.setFillColor(C(NAVY));canv.rect(0,h-15*mm,w,15*mm,fill=1,stroke=0)
        canv.setFont("SL-B",9);canv.setFillColor(colors.white)
        canv.drawString(18*mm,h-10*mm,"STOCKLENS")
        canv.setFont("SL",7);canv.setFillColor(C("#8FE0D9"))
        canv.drawString(49*mm,h-10*mm,"EQUITY RESEARCH  /  " + self.ticker)
        canv.setStrokeColor(C(TEAL));canv.setLineWidth(2)
        canv.line(18*mm,h-16*mm,39*mm,h-16*mm)
        canv.setStrokeColor(C(LINE));canv.setLineWidth(.6)
        canv.line(18*mm,14*mm,w-18*mm,14*mm)
        canv.setFillColor(C(MUTED));canv.setFont("SL",6.6)
        canv.drawString(18*mm,9.5*mm,"STOCKLENS  ·  Research Note  ·  Dữ liệu và phương pháp tại cuối báo cáo")
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
            if self._pageNumber > 1:
                self.setFont("SL", 7.5)
                self.setFillColor(C(MUTED))
                self.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"{self._pageNumber:02d} / {total:02d}")
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
    toc.levelStyles = [ParagraphStyle("toc0", parent=ST["toc0"], fontName="SL", fontSize=10, leading=24, leftIndent=0, firstLineIndent=0)]

    plan = [("overview", "Tổng quan doanh nghiệp và ngành")]
    plan += [(k, n) for k, n in (("fundamental", "Phân tích tình hình tài chính"),
                                 ("valuation", "Định giá và doanh nghiệp so sánh"),
                                 ("technical", "Phân tích kỹ thuật"),
                                 ("news", "Tin tức và triển vọng")) if k in sections]
    if "score" in sections:
        plan.extend([("score", "Investment Score và hồ sơ nhà đầu tư"),
                     ("thesis", "Rủi ro và kết luận đầu tư")])
    else:
        plan.append(("thesis", "Rủi ro và kết luận đầu tư"))
    plan.append(("method", "Phương pháp, nguồn dữ liệu và giới hạn"))

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
                    body[body.index(fl)] = Paragraph(f'<font color="{TEAL}">{i:02d}</font>  {escape(title)}', ST["sec"])
                    break
        except Exception as exc:  # không để một mục lỗi làm hỏng cả báo cáo
            body = [Paragraph(f'<font color="{TEAL}">{i:02d}</font>  {escape(title)}', ST["sec"]), _p(f"Không dựng được mục này: {exc}", "small")]
        story += body
        if i < len(plan):
            story.append(PageBreak())

    buf = io.BytesIO()
    doc = _Doc(buf, ticker, cover_data=(ticker, period_text, profile, results, summary, company, th))
    doc.multiBuild(story, canvasmaker=_Numbered)
    return buf.getvalue()
