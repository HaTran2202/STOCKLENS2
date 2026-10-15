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
    from src.branding import get_logo, logo_bytes
    from src.thesis import build_thesis
except ImportError:  # chạy trực tiếp trong thư mục src
    from branding import get_logo, logo_bytes
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
    add("body", fontSize=9.1, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=5)
    add("small", fontSize=7.8, leading=10.4, textColor=C(MUTED))
    add("tiny", fontSize=6.5, leading=8.5, textColor=C(MUTED))
    add("sec", fontName="SL-B", fontSize=17.5, leading=22, textColor=C(NAVY), spaceBefore=2, spaceAfter=4, keepWithNext=1)
    add("subsec", fontSize=8.8, leading=12, textColor=C(MUTED), spaceAfter=8, keepWithNext=1)
    add("h2", fontName="SL-B", fontSize=10.6, leading=13.5, textColor=C(BLUE), spaceBefore=7, spaceAfter=5, keepWithNext=1)
    add("kl", fontName="SL-B", fontSize=7.1, leading=9.6, textColor=C(MUTED))
    add("kv", fontName="SL-B", fontSize=15, leading=18.5, textColor=C(NAVY))
    add("ks", fontSize=6.9, leading=9, textColor=C(MUTED))
    add("cell", fontSize=8.2, leading=10.8)
    add("cellb", fontName="SL-B", fontSize=8.2, leading=10.8, textColor=C(NAVY))
    add("cellr", fontSize=8.1, leading=10.8, alignment=TA_RIGHT)
    add("cellh", fontName="SL-B", fontSize=8.1, leading=10.8, textColor=C(NAVY))
    add("cover_t", fontName="SL-B", fontSize=24, leading=28, textColor=C(NAVY))
    add("cover_n", fontSize=11, leading=14, textColor=C("#385576"))
    add("rec_t", fontName="SL-B", fontSize=15, leading=18)
    add("toc0", fontSize=9.5, leading=21, leftIndent=0, rightIndent=18, textColor=C(TEXT), spaceAfter=3)
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


_VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")
_WARNING_VI = (
    (("no period_date", "period_date", "market_cap/shares"), "Chỉ số định giá từ snapshot CSV thiếu ngày cập nhật; cần kiểm chứng giá, kỳ EPS/BVPS trước khi kết luận."),
    (("snapshot", "valuation ratio"), "Tỷ số định giá lấy từ snapshot CSV; snapshot không kèm ngày công bố nên chỉ mang tính tham chiếu."),
    (("reported", "ratio source"), "Chỉ số tài chính từ nguồn dữ liệu có thể dùng định nghĩa khác báo cáo kiểm toán."),
    (("market_cap", "shares", "cổ phiếu"), "Thiếu vốn hóa hoặc số cổ phiếu nên không quy đổi được giá trị thị trường."),
)


def _vi_warning(text):
    """Keep already-Vietnamese warnings; translate known English provider notes."""
    text = str(text or "")
    if not text or any(ch in _VI_CHARS for ch in text.lower()):
        return text
    low = text.lower()
    for keys, vi in _WARNING_VI:
        if any(k in low for k in keys):
            return vi
    return text


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


def _working_capital(fd):
    """Vốn lưu động từ BCTC gốc: TSNH - Nợ ngắn hạn và hệ số thanh toán ngắn hạn.

    Chỉ dùng số liệu hợp nhất đã có trong CSV, không suy diễn khi thiếu kỳ/năm.
    """
    bs = ((fd or {}).get("_raw") or {}).get("balance_sheet")
    if not isinstance(bs, pd.DataFrame) or "item_id" not in bs.columns:
        return {"available": False}
    years = [c for c in bs.columns if c not in ("item", "item_id", "unit")]
    years = sorted(str(y) for y in years)
    pick = {}
    for iid in ("current_assets", "current_liabilities"):
        rows = bs[bs["item_id"] == iid]
        if not rows.empty:
            pick[iid] = rows.iloc[0]
    if "current_assets" not in pick or "current_liabilities" not in pick:
        return {"available": False}
    series = []
    for y in years:
        ca, cl = _f(pick["current_assets"].get(y)), _f(pick["current_liabilities"].get(y))
        if ca is None or cl is None:
            continue
        series.append({"year": y, "nwc": ca - cl, "current_ratio": ca / cl if cl else None})
    if not series:
        return {"available": False}
    latest, prior = series[-1], (series[-2] if len(series) > 1 else None)
    change = None
    if prior and prior["nwc"]:
        change = latest["nwc"] / prior["nwc"] - 1
    return {"available": True, "series": series, "latest": latest, "prior": prior, "nwc_change": change}


def _raw_series(fd, item_id):
    """Giá trị theo năm của một chỉ tiêu trong BCTC gốc (nhóm theo item_id)."""
    for df in ((fd or {}).get("_raw") or {}).values():
        if isinstance(df, pd.DataFrame) and "item_id" in df.columns and (df["item_id"] == item_id).any():
            row = df[df["item_id"] == item_id].iloc[0]
            out = {}
            for y in df.columns:
                if str(y) in ("item", "item_id", "unit"):
                    continue
                value = _f(row.get(y))
                if value is not None:
                    out[str(y)] = value
            return out
    return {}


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


def chart_price(data, width=CONTENT_W, h=2.7):
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


def chart_rsi_macd(data, width=CONTENT_W, h=2.1):
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


def chart_fin(hist, width=CONTENT_W, h=2.1):
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


def chart_balance(hist, width=CONTENT_W, h=1.8):
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


def chart_valuation(hist, v, width=CONTENT_W, h=1.9):
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


def chart_components(comp, width=CONTENT_W * 0.58, h=1.9):
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


def chart_profiles(profile_scores, current, width=CONTENT_W * 0.38, h=1.9):
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
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, splitByRow=1, hAlign="LEFT")
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
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
             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]
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
    # Bản rút gọn: bìa được vẽ vector ở trang 1 (cover_data), không dựng thêm
    # trang mục lục riêng để báo cáo gọn trong khoảng 8–10 trang.
    return [PageBreak()]


def _wrap_draw(canv, text, style, x, top, width, limit_height=None):
    p = Paragraph(escape(str(text or "")), style)
    _, ph = p.wrap(width, 1000)
    if limit_height and ph > limit_height:
        # Không để thông tin dài tràn vào phần khác của bìa; giữ thông tin quan trọng ở PDF bên trong.
        p = Paragraph(escape(str(text or "")[:190].rsplit(" ", 1)[0] + "…"), style)
        _, ph = p.wrap(width, 1000)
    p.drawOn(canv, x, top - ph)
    return ph


def _fmt_date(value):
    """dd/mm/yyyy cho ngày dạng ISO; giữ nguyên nếu không parse được (không bịa ngày)."""
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s[:10]).strftime("%d/%m/%Y")
    except Exception:
        return s


def _cover_dates(period_text):
    """Tách khoảng thời gian phân tích thành (bắt đầu, kết thúc) đã định dạng."""
    parts = re.split(r"→|->|–|—", str(period_text or ""))
    if len(parts) >= 2:
        return _fmt_date(parts[0]), _fmt_date(parts[1])
    return _fmt_date(period_text), ""


def _sl_mark(canv, x, y, height):
    """Vẽ mark 4 thanh tăng dần của StockLens (vector, gradient teal→xanh→navy).

    Gradient được vẽ thủ công bằng các dải ngang để hiển thị ổn định trên mọi
    trình đọc PDF (không phụ thuộc shading của reportlab).
    """
    unit = height / 29.0
    bw, gap = 5 * unit, 3 * unit
    stops = ((0.0, (40, 185, 178)), (0.58, (26, 131, 215)), (1.0, (11, 43, 85)))

    def _col(t):
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t <= t1 or i == len(stops) - 2:
                f = 0.0 if t1 == t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
                return colors.Color(*[(c0[k] + (c1[k] - c0[k]) * f) / 255 for k in range(3)])
        return colors.Color(11 / 255, 43 / 255, 85 / 255)

    slices = 14
    bx = x
    for hh in (10, 17, 24, 29):
        bh = hh * unit
        for s in range(slices):
            canv.setFillColor(_col((s + 0.5) / slices))
            canv.rect(bx, y + bh * s / slices, bw, bh / slices + 0.2, fill=1, stroke=0)
        bx += bw + gap


def _vgrad(canv, x, y, w, h, c_bottom, c_top, steps=48):
    """Tô nền chuyển sắc dọc bằng các dải ngang.

    Shading của reportlab không render ổn định trên một số trình đọc PDF, nên
    gradient được dựng thủ công để bảo đảm hiển thị giống nhau mọi nơi.
    """
    steps = max(2, int(steps))
    for i in range(steps):
        t = (i + 0.5) / steps
        canv.setFillColor(colors.Color(
            c_bottom.red + (c_top.red - c_bottom.red) * t,
            c_bottom.green + (c_top.green - c_bottom.green) * t,
            c_bottom.blue + (c_top.blue - c_bottom.blue) * t))
        canv.rect(x, y + h * i / steps, w, h / steps + 0.45, fill=1, stroke=0)


def _grad_fill(canv, path, x, y, w, h, c_bottom, c_top, steps=64):
    """Tô chuyển sắc vào một path bất kỳ (qua clip) để tạo chiều sâu cho vùng dữ liệu."""
    canv.saveState()
    canv.clipPath(path, stroke=0, fill=0)
    _vgrad(canv, x, y, w, h, c_bottom, c_top, steps)
    canv.restoreState()


def _chip(canv, x, y, text, col, hh=7.0):
    """Nhãn nhỏ dạng viên thuốc cho sàn/ngành."""
    pw = canv.stringWidth(text, "SL-B", 7.2) + 6 * mm
    canv.setFillColor(C("#E9F3FC")); canv.setStrokeColor(C("#D5E7F7")); canv.setLineWidth(0.6)
    canv.roundRect(x, y, pw, hh * mm, 2 * mm, fill=1, stroke=1)
    canv.setFillColor(col); canv.setFont("SL-B", 7.2)
    canv.drawString(x + 3 * mm, y + 2.6 * mm, text)
    return pw


def _ring(canv, cx, cy, r, frac, color, track_c, lw=3.0):
    """Vòng tiến độ gọn gàng cho Investment Score."""
    canv.setLineCap(1)
    canv.setLineWidth(lw)
    canv.setStrokeColor(track_c)
    canv.circle(cx, cy, r, fill=0, stroke=1)
    if frac is not None and frac > 0:
        canv.setStrokeColor(color)
        canv.arc(cx - r, cy - r, cx + r, cy + r, 90, -360.0 * max(0.0, min(1.0, frac)))


def _cal_icon(canv, x, y, s, col):
    """Icon lịch nhỏ cho khu vực ngày tháng."""
    canv.setStrokeColor(col); canv.setLineWidth(0.9)
    canv.roundRect(x, y, s, s, s * 0.22, fill=0, stroke=1)
    canv.line(x, y + s * 0.70, x + s, y + s * 0.70)
    canv.setFillColor(col)
    canv.circle(x + s * 0.34, y + s * 0.40, s * 0.085, fill=1, stroke=0)
    canv.circle(x + s * 0.66, y + s * 0.40, s * 0.085, fill=1, stroke=0)


def _clean(value, default=""):
    """Chuẩn hoá chuỗi: bìa không bao giờ hiển thị None/nan/rỗng."""
    s = str(value if value is not None else "").strip()
    if not s or s.lower() in {"none", "nan", "null", "nat"}:
        return default
    return s


def _text(canv, x, y, text, font, size, color, align="left", cs=0.0):
    """Vẽ text kèm tuỳ chọn giãn chữ.

    Không dùng text object + Tc vì trạng thái Tc rò rỉ sang các lệnh text sau
    (làm giãn cả tên doanh nghiệp). Giãn chữ được dựng thủ công theo từng ký tự.
    """
    canv.setFillColor(color)
    canv.setFont(font, size)
    if not cs:
        if align == "right":
            canv.drawRightString(x, y, text)
        elif align == "center":
            canv.drawCentredString(x, y, text)
        else:
            canv.drawString(x, y, text)
        return
    total = canv.stringWidth(text, font, size) + cs * max(0, len(text) - 1)
    cx = x - total if align == "right" else x - total / 2.0 if align == "center" else x
    for ch in text:
        canv.drawString(cx, y, ch)
        cx += canv.stringWidth(ch, font, size) + cs


def _draw_cover_page(canv, ticker, period_text, profile, results, summary, company, th):
    """Bìa Premium Equity Research (dùng chung cho mọi ticker).

    Thứ tự thị giác: thương hiệu → hero doanh nghiệp (logo thật theo ticker + watermark)
    → vùng đồ họa tài chính hòa vào nền → hai thẻ lớn (Quan điểm đầu tư, Investment Score)
    → ngày/phạm vi phân tích → footer. Logo lấy động qua branding (cache + fallback
    monogram); không hardcode doanh nghiệp, giá, điểm số hay quan điểm đầu tư.
    """
    w, h = A4
    x0, x1 = 18 * mm, w - 18 * mm
    cw = x1 - x0
    WHITE = colors.white
    INK, BLUE = C("#0B2545"), C("#1F6FB2")
    BLUE2, CYAN = C("#2E8FD6"), C("#14B8AE")
    LINE, MUTED, TEXT = C("#DCE7F2"), C("#6B7E95"), C("#26405C")
    GRID = C("#E6F0FA")

    company = company or {}
    results = results or {}
    summary = summary or {}
    rec = (th or {}).get("recommendation") or {}
    tech = results.get("technical") or {}
    tk = str(ticker or "").upper() or "—"

    canv.saveState()
    canv.setFillColor(WHITE); canv.rect(0, 0, w, h, fill=1, stroke=0)

    # Lớp nền tạo chiều sâu: dải chuyển sắc ở đỉnh + mảng tròn sáng rất nhạt góc phải.
    _vgrad(canv, 0, h - 94 * mm, w, 94 * mm, WHITE, C("#E6F1FB"), steps=64)
    canv.setFillColor(C("#DDEBFA"))
    canv.circle(w - 14 * mm, h - 4 * mm, 54 * mm, fill=1, stroke=0)

    # Watermark ticker cỡ lớn, rất nhạt (tự co theo độ dài, không làm giảm khả năng đọc).
    canv.saveState()
    wp = canv.beginPath(); wp.rect(0, h - 94 * mm, w, 94 * mm)
    canv.clipPath(wp, stroke=0, fill=0)
    wmw = canv.stringWidth(tk, "SL-B", 100)
    wsize = max(30.0, min(104.0, (140 * mm) / ((wmw / 100.0) or 1.0)))
    canv.setFillColor(C("#E1EFFB")); canv.setFont("SL-B", wsize)
    canv.drawRightString(x1, h - 72 * mm, tk)
    canv.restoreState()

    # ---------------------------------------------------------------- A. Header thương hiệu
    _sl_mark(canv, x0, h - 16.6 * mm, 8.4 * mm)
    _text(canv, x0 + 11 * mm, h - 15.4 * mm, "STOCKLENS", "SL-B", 14.5, INK, cs=0.5)
    _text(canv, x0 + 11 * mm, h - 19.3 * mm, "BÁO CÁO PHÂN TÍCH CƠ HỘI ĐẦU TƯ", "SL", 6.3, MUTED)
    _text(canv, x1, h - 15.4 * mm, "EQUITY RESEARCH", "SL-B", 7.4, BLUE, align="right", cs=1.1)
    canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
    canv.line(x0, h - 24 * mm, x1, h - 24 * mm)
    canv.setStrokeColor(CYAN); canv.setLineWidth(2.2)
    canv.line(x0, h - 24 * mm, x0 + 26 * mm, h - 24 * mm)

    # ---------------------------------------------------------------- B. Hero doanh nghiệp
    box = 30 * mm
    bx, by = x0, h - 60 * mm
    canv.setFillColor(WHITE); canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
    canv.roundRect(bx, by, box, box, 4 * mm, fill=1, stroke=1)
    try:  # logo thật theo ticker (branding: cache → nguồn đã xác minh → monogram)
        logo = logo_bytes(ticker, company.get("website"))
        pad = 4.5 * mm
        canv.drawImage(ImageReader(io.BytesIO(logo)), bx + pad, by + pad,
                       width=box - 2 * pad, height=box - 2 * pad,
                       preserveAspectRatio=True, mask="auto", anchor="c")
    except Exception:
        pass
    tx = x0 + box + 9 * mm
    tw = x1 - tx - 2 * mm
    tsize = 42 if len(tk) <= 3 else 34 if len(tk) <= 5 else 25
    canv.setFillColor(INK); canv.setFont("SL-B", tsize)
    canv.drawString(tx, h - 46 * mm, tk)
    name_style = ParagraphStyle("cover_name", fontName="SL", fontSize=13, leading=16.5,
                                textColor=TEXT)
    _wrap_draw(canv, _clean(company.get("name"), tk), name_style, tx, h - 50 * mm, tw,
               limit_height=12 * mm)
    ex = _clean(company.get("exchange"), "chưa xác minh")
    sec = _clean(company.get("sector"), "chưa xác minh")
    pw = _chip(canv, tx, h - 73 * mm, f"Sàn {ex}"[:36], BLUE)
    _chip(canv, tx + pw + 4 * mm, h - 73 * mm, f"Ngành {sec}"[:36], CYAN)
    canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
    canv.line(x0, h - 84 * mm, x1, h - 84 * mm)

    # ---------------------------------------------------------------- C. Đồ họa tài chính
    ix, iw = x0, cw
    y_top, y_base = h - 102 * mm, h - 172 * mm
    closes, vols = None, None
    data = tech.get("data")
    if isinstance(data, pd.DataFrame) and "Close" in data and len(data) >= 8:
        d = data.copy()
        d["Close"] = pd.to_numeric(d["Close"], errors="coerce")
        d = d.dropna(subset=["Close"]).tail(252)
        if len(d) >= 8:
            vv = (pd.to_numeric(d["Volume"], errors="coerce").fillna(0).astype(float).tolist()
                  if "Volume" in d else None)
            vals = d["Close"].astype(float).tolist()
            if len(vals) > 96:  # giảm mẫu cho đường bìa gọn hơn (vẫn là giá trị THỰC)
                step = max(1, len(vals) // 96)
                idx = list(range(0, len(vals), step))
                if idx[-1] != len(vals) - 1:
                    idx.append(len(vals) - 1)
                vals = [vals[i] for i in idx]
                vv = [vv[i] for i in idx] if vv else None
            closes, vols = vals, vv

    pstart, pend = _cover_dates(period_text)
    canv.setStrokeColor(GRID); canv.setLineWidth(0.45)
    for k in range(1, 4):
        gy = y_base + (y_top - y_base) * k / 4
        canv.line(ix, gy, ix + iw, gy)
    for k in range(1, 7):
        canv.line(ix + iw * k / 7, y_base, ix + iw * k / 7, y_top)

    if closes:  # chỉ dùng chuỗi giá THỰC của đúng mã và đúng kỳ phân tích
        lo, hi = min(closes), max(closes)
        span = (hi - lo) or 1.0
        n = len(closes)
        pts = [(ix + iw * i / (n - 1), y_base + (y_top - y_base) * (v - lo) / span)
               for i, v in enumerate(closes)]
        if vols:  # cột khối lượng thực, rất nhạt, nằm dưới vùng giá
            vmax = max(vols) or 1.0
            bwv = max(0.6, iw / n * 0.55)
            for i, vv_ in enumerate(vols):
                hh = 8 * mm * (vv_ / vmax)
                if hh > 0.2:
                    canv.setFillColor(C("#DCEBF8"))
                    canv.rect(ix + iw * i / (n - 1) - bwv / 2, y_base - 9.5 * mm, bwv, hh,
                              fill=1, stroke=0)
        ap = canv.beginPath(); ap.moveTo(pts[0][0], y_base)
        for px, py in pts:
            ap.lineTo(px, py)
        ap.lineTo(pts[-1][0], y_base); ap.close()
        _grad_fill(canv, ap, ix, y_base, iw, y_top - y_base, C("#F8FBFF"), C("#CBE4F8"), steps=72)
        lp = canv.beginPath(); lp.moveTo(*pts[0])
        for px, py in pts[1:]:
            lp.lineTo(px, py)
        canv.saveState()  # vệt sáng mềm dưới đường giá (chiều sâu, dùng tiết chế)
        canv.setStrokeAlpha(0.15); canv.setStrokeColor(BLUE); canv.setLineWidth(5.2)
        canv.setLineJoin(1); canv.setLineCap(1); canv.drawPath(lp, fill=0, stroke=1)
        canv.restoreState()
        canv.setStrokeColor(BLUE); canv.setLineWidth(1.9)
        canv.setLineJoin(1); canv.setLineCap(1); canv.drawPath(lp, fill=0, stroke=1)
        canv.setFillColor(WHITE); canv.circle(pts[-1][0], pts[-1][1], 3.1, fill=1, stroke=0)
        canv.setFillColor(BLUE); canv.circle(pts[-1][0], pts[-1][1], 2.0, fill=1, stroke=0)
        canv.setStrokeColor(LINE); canv.setLineWidth(0.7)
        canv.line(ix, y_base, ix + iw, y_base)
    else:
        # Không đủ dữ liệu giá: minh họa tài chính trừu tượng, KHÔNG nhãn/trục số liệu.
        fracs = (0.32, 0.50, 0.40, 0.64, 0.47, 0.78, 0.56, 0.88, 0.62, 0.74, 0.52, 0.70)
        nb = len(fracs)
        bw2 = iw / (nb * 1.7)
        gp = (iw - nb * bw2) / (nb - 1)
        tops = []
        for i, fr in enumerate(fracs):
            bx2 = ix + i * (bw2 + gp)
            bh = (y_top - y_base) * fr
            canv.setFillColor(C("#D5E9F9"))
            canv.roundRect(bx2, y_base, bw2, bh, bw2 * 0.32, fill=1, stroke=0)
            tops.append((bx2 + bw2 / 2, y_base + bh))
        wp2 = canv.beginPath(); wp2.moveTo(*tops[0])
        for px, py in tops[1:]:
            wp2.lineTo(px, py)
        canv.setStrokeColor(C("#7FB6E6")); canv.setLineWidth(1.4)
        canv.setLineJoin(1); canv.setLineCap(1); canv.drawPath(wp2, fill=0, stroke=1)
        canv.setStrokeColor(LINE); canv.setLineWidth(0.7)
        canv.line(ix, y_base, ix + iw, y_base)

    _text(canv, ix, h - 94 * mm,
          "DIỄN BIẾN GIÁ" if closes else "HỌA TIẾT TÀI CHÍNH TRUNG TÍNH",
          "SL-B", 7.4, BLUE, cs=1.0)
    canv.setFillColor(MUTED); canv.setFont("SL", 7.4)
    if closes:
        rng = f"{pstart} – {pend}" if (pstart and pend) else "khoảng phân tích"
        canv.drawRightString(ix + iw, h - 94 * mm, f"Giá đóng cửa thực tế · {tk} · {rng}"[:96])
    else:
        canv.drawRightString(ix + iw, h - 94 * mm,
                             "Minh họa trừu tượng · không thể hiện số liệu thực")

    # ---------------------------------------------------------------- D. Hai thẻ lớn
    cards_top, cards_h, cgap = 194 * mm, 52 * mm, 8 * mm
    card_w = (cw - cgap) / 2
    ctop, cbot = h - cards_top, h - cards_top - cards_h
    score = _f(summary.get("score"))
    label_txt = _clean(summary.get("label"))
    stance = _clean(rec.get("stance"), "Chưa đủ dữ liệu")
    tone = str(rec.get("tone") or "neutral")
    tone_col = {"positive": C(GREEN), "neutral": C(AMBER), "caution": C(RED)}.get(tone, MUTED)

    def _card(cx, accent):
        canv.setFillColor(WHITE); canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
        canv.roundRect(cx, cbot, card_w, cards_h, 4 * mm, fill=1, stroke=1)
        canv.setFillColor(accent)
        canv.roundRect(cx + 6 * mm, ctop - 12 * mm, 1.5 * mm, 16 * mm, 0.75 * mm, fill=1, stroke=0)

    # Thẻ 1 — Quan điểm đầu tư (kết luận thực tế từ hệ thống)
    cx1 = x0
    _card(cx1, tone_col)
    _text(canv, cx1 + 11 * mm, ctop - 9 * mm, "QUAN ĐIỂM ĐẦU TƯ", "SL-B", 7.4, BLUE, cs=0.8)
    vs = 28 if len(stance) <= 10 else 22 if len(stance) <= 14 else 17
    canv.setFillColor(tone_col); canv.setFont("SL-B", vs)
    canv.drawString(cx1 + 11 * mm, ctop - 30 * mm, stance)
    canv.setFillColor(MUTED); canv.setFont("SL", 9)
    canv.drawString(cx1 + 11 * mm, ctop - 42 * mm,
                    f"Hồ sơ {_clean(profile)}" if _clean(profile) else "Theo hồ sơ nhà đầu tư")

    # Thẻ 2 — StockLens Investment Score (vòng tiến độ theo thang điểm hiện hành)
    cx2 = x0 + card_w + cgap
    _card(cx2, BLUE)
    _text(canv, cx2 + 11 * mm, ctop - 9 * mm, "STOCKLENS INVESTMENT SCORE", "SL-B", 7.4, BLUE, cs=0.8)
    rcx, rcy, rr = cx2 + 22 * mm, ctop - 32 * mm, 12 * mm
    frac = (score / 100.0) if score is not None else None
    ring_col = BLUE
    if score is not None:  # màu theo chính phân loại chính thức của StockLens
        ring_col = C(GREEN) if score >= 80 else BLUE if score >= 65 else C(AMBER) if score >= 50 else C(RED)
    _ring(canv, rcx, rcy, rr, frac, ring_col, C("#E4EFF9"), lw=3.0)
    if score is not None:
        canv.setFillColor(INK); canv.setFont("SL-B", 18)
        canv.drawCentredString(rcx, rcy - 6.2, f"{score:.1f}")
    else:
        canv.setFillColor(MUTED); canv.setFont("SL-B", 14)
        canv.drawCentredString(rcx, rcy - 5, "N/A")
    canv.setFillColor(TEXT); canv.setFont("SL-B", 8.8)
    canv.drawString(cx2 + 40 * mm, ctop - 27 * mm, "Thang điểm 0 – 100")
    if score is not None and label_txt:
        _wrap_draw(canv, label_txt,
                   ParagraphStyle("cv_lab", fontName="SL-B", fontSize=10, leading=13, textColor=ring_col),
                   cx2 + 40 * mm, ctop - 31 * mm, 38 * mm, limit_height=24 * mm)
    else:
        _wrap_draw(canv, "Chưa đủ dữ liệu để tính điểm" if score is None else "Chưa có phân loại",
                   ParagraphStyle("cv_lab2", fontName="SL", fontSize=8.4, leading=11, textColor=MUTED),
                   cx2 + 40 * mm, ctop - 31 * mm, 38 * mm, limit_height=24 * mm)

    # ---------------------------------------------------------------- E. Ngày & phạm vi phân tích
    dtop = 256 * mm
    canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
    canv.line(x0, h - dtop, x1, h - dtop)
    rng = f"{pstart} – {pend}" if (pstart and pend) else (pstart or "Chưa xác định")
    last_date = _fmt_date(_clean(company.get("last_date")))
    items = (
        ("KỲ PHÂN TÍCH", rng),
        ("DỮ LIỆU CẬP NHẬT", last_date or "Chưa có dữ liệu"),
        ("PHÁT HÀNH", datetime.now().strftime("%d/%m/%Y")),
    )
    colw = cw / 3
    for i, (lab, val) in enumerate(items):
        cx = x0 + i * colw
        _cal_icon(canv, cx, h - 268 * mm, 5 * mm, BLUE2)
        _text(canv, cx + 7.5 * mm, h - 264.5 * mm, lab, "SL-B", 6.5, MUTED, cs=0.5)
        canv.setFillColor(INK); canv.setFont("SL-B", 9.4)
        canv.drawString(cx + 7.5 * mm, h - 271 * mm, str(val)[:26])

    # ---------------------------------------------------------------- F. Footer
    # dải cong rất nhẹ sát đáy trang (tạo chiều sâu, không chồng nội dung/footer)
    bp = canv.beginPath()
    bp.moveTo(0, 6 * mm)
    bp.curveTo(w * 0.30, 3.5 * mm, w * 0.60, 1.2 * mm, w, 3.2 * mm)
    bp.lineTo(w, 0); bp.lineTo(0, 0); bp.close()
    canv.setFillColor(C("#EDF5FC")); canv.drawPath(bp, fill=1, stroke=0)
    canv.setStrokeColor(LINE); canv.setLineWidth(0.8)
    canv.line(x0, h - 280 * mm, x1, h - 280 * mm)
    _text(canv, x0, h - 287 * mm, "STOCKLENS", "SL-B", 8.2, INK, cs=0.5)
    canv.setFillColor(MUTED); canv.setFont("SL", 7.8)
    canv.drawString(x0 + 24 * mm, h - 287 * mm,
                    "·  Investment Intelligence Platform  ·  Báo cáo phân tích cổ phiếu")
    canv.drawRightString(x1, h - 287 * mm, "Trang 01")
    canv.restoreState()

# ----------------------------------------------------------------------------- các mục nội dung
def _sec_exec_summary(ticker, results, summary, fd, company, profile, th):
    t = results.get("technical") or {}
    v = results.get("valuation") or {}
    f = results.get("fundamental") or {}
    comp = summary.get("component_scores") or {}
    rec = (th or {}).get("recommendation") or {}
    fl = _section("Tóm tắt điều hành", "Điểm, luận điểm chính và trạng thái dữ liệu trên một trang")
    score = _f(summary.get("score"))
    ref = _f(v.get("peer_fair_value"))
    fl.append(_kpis([("Investment Score", "N/A" if score is None else f"{score:.1f}", f"Hồ sơ {profile}", _tone_color(score)),
                     ("Khuyến nghị tổng hợp", str(rec.get("stance") or "Chưa đủ dữ liệu"), "từ dữ liệu hiện có", NAVY),
                     ("Giá thị trường", _fmt(t.get("close"), 0, " VND"), "phiên gần nhất", TEAL),
                     ("P/E · P/B", f"{_fmt(v.get('pe'), 2, 'x')} · {_fmt(v.get('pb'), 2, 'x')}", "so với trung vị lịch sử", BLUE),
                     ("Peer Fair Value", "N/A" if ref is None else f"{ref:,.0f}", "VND (hàm ý)", PURPLE)]))
    fl.append(Paragraph("Tóm lược", ST["h2"]))
    hint = rec.get("hint")
    fl.append(_p(hint or "Chưa đủ dữ liệu để tóm tắt định hướng theo dõi.", "body"))
    pos = summary.get("positive_drivers") or (summary.get("why_this_score") or {}).get("positive_drivers") or []
    neg = summary.get("negative_drivers") or (summary.get("why_this_score") or {}).get("negative_drivers") or []
    fl += [Spacer(1, 5), _side_by_side(
        _callout("Điểm tựa tích cực", [_p(x, "small") for x in pos[:4]] or [_p("Chưa ghi nhận yếu tố tích cực nổi bật.", "small")], color=GREEN, bg="#EEF9F5", width=CONTENT_W * .47),
        _callout("Rủi ro & điểm trừ", [_p(x, "small") for x in neg[:4]] or [_p("Chưa ghi nhận rủi ro nổi bật.", "small")], color=RED, bg="#FFF3F4", width=CONTENT_W * .47),
        CONTENT_W * .5, CONTENT_W * .5, gap=8)]
    warnings = [_vi_warning(x) for x in (fd.get("qualityWarnings") or []) if x]
    missing = summary.get("missing") or []
    coverage = f.get("coverage")
    dq = [f"Bao phủ điểm: {len(comp)}/5 nhóm thành phần; thiếu: {', '.join(map(str, missing)) if missing else 'không'}.",
          f"Chỉ tiêu tài chính dùng được cho điểm cơ bản: {coverage if coverage is not None else 'N/A'}.",
          f"Cảnh báo chất lượng dữ liệu đang hiển thị: {len(warnings)}."]
    fl += [Spacer(1, 5), _callout("Trạng thái dữ liệu & phạm vi", [_p(x, "small") for x in dq + warnings[:3]], color=AMBER, bg="#FBF7EE")]
    fl += [Spacer(1, 5), _p(
        "Phân biệt nội dung: số liệu BCTC/thị trường là dữ liệu thực thu thập; điểm số, DuPont, peer và kịch bản là kết quả mô hình; "
        "nhận định/kết luận là diễn giải; giả định được ghi rõ tại chỗ. Báo cáo không đưa khuyến nghị mua, bán hay nắm giữ.", "small")]
    return fl


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
    fl += [Spacer(1, 6), _kpis(items)]
    # Bản rút gọn: biểu đồ giá nằm ở mục Kỹ thuật, số liệu tài chính chi tiết ở mục
    # Tài chính — không lặp lại ở đây để tránh trùng nội dung và giảm số trang.
    fl += [Spacer(1, 5 * mm), _p("Biểu đồ giá ở mục 05 (Kỹ thuật); số liệu tài chính chi tiết ở mục 03. Các khối dữ liệu có thể khác kỳ cập nhật — đối chiếu ngày và nguồn tại phần phương pháp.", "small")]
    return fl


def _sec_thesis(ticker, th):
    fl = _section("Luận điểm đầu tư & rủi ro cần lưu ý", "Cá nhân hóa theo mã cổ phiếu, dữ liệu mới nhất và hồ sơ nhà đầu tư")
    # Giới hạn 3 luận điểm/rủi ro nổi bật nhất để báo cáo gọn và dễ đọc.
    thesis = [x for x in (th.get("thesis") or []) if x][:3]
    risks = [x for x in (th.get("risks") or []) if x][:3]
    fl.append(Paragraph("Luận điểm đầu tư chính", ST["h2"]))
    fl += [_p(x) for x in thesis] or [_p("Chưa đủ dữ liệu để xây dựng luận điểm đầu tư.", "small")]
    fl.append(Paragraph("Rủi ro cần lưu ý", ST["h2"]))
    fl += [_p(x) for x in risks] or [_p("Chưa ghi nhận rủi ro nổi bật từ dữ liệu hiện có.", "small")]
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
        fl += [Spacer(1, 6), chart_price(d, h=2.6), Spacer(1, 4), chart_rsi_macd(d)]
    support, resistance = _f(t.get("support_level")), _f(t.get("resistance_level"))
    sd, rd = _f(t.get("distance_to_support_pct")), _f(t.get("distance_to_resistance_pct"))
    level_rows = [[Paragraph(h, ST["cellh"]) for h in ("Vùng", "Mức giá", "Khoảng cách", "Trạng thái")],
                  [_p("Hỗ trợ", "cellb"), _p(_fmt(support, 0, " VND"), "cellr"), _p("N/A" if sd is None else f"{sd:+.2f}%", "cellr"), _p("Pivot low / đáy 60 phiên" if support is not None else "Chưa đủ dữ liệu", "cell")],
                  [_p("Kháng cự", "cellb"), _p(_fmt(resistance, 0, " VND"), "cellr"), _p("N/A" if rd is None else f"{rd:+.2f}%", "cellr"), _p("Pivot high / đỉnh 60 phiên" if resistance is not None else "Chưa đủ dữ liệu", "cell")]]
    fl += [Spacer(1, 6), Paragraph("Vùng giá và tín hiệu", ST["h2"]), _tbl(level_rows, [CONTENT_W*.17, CONTENT_W*.25, CONTENT_W*.20, CONTENT_W*.38])]
    divergence = t.get("divergence") or {}
    tscore = _f(t.get("score"))
    state = (f"Technical Score: {'N/A' if tscore is None else f'{tscore:.1f}/100'}"
             f" · RSI: {t.get('rsi_state') or 'N/A'}"
             f" · Phân kỳ: {divergence.get('signal') or 'chưa phát hiện'}")
    # Một khối duy nhất: trạng thái + kịch bản hành động (gồm xác nhận/vô hiệu hóa).
    # Bỏ khối "Nhận định kỹ thuật" trước đây vì lặp lại gần như nguyên văn nội dung này.
    fl += [Spacer(1, 4), _callout("Trạng thái & kịch bản hành động", [_p(state, "small"), _p(t.get("action_scenario") or t.get("commentary") or "Chưa đủ dữ liệu để tạo kịch bản.")], color=TEAL, bg="#EEF9F8")]
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
        warnings = [_vi_warning(x) for x in fd.get("qualityWarnings", []) if x][:3]
        known = []
        for text in warnings:
            if text and text not in known:
                known.append(text)
        fl += [Spacer(1, 5), _callout("Lưu ý chất lượng dữ liệu", [_p(x, "small") for x in known], color=AMBER, bg="#FBF7EE")]
    if hist:
        # Một biểu đồ tài chính full-width (quy mô, lợi nhuận, ROE/ROA) để nhãn trục
        # không bị chồng; tổng tài sản/vốn chủ sở hữu đã có trong bảng bên dưới.
        fl += [Spacer(1, 6), chart_fin(hist, h=2.0)]
        wc = _working_capital(fd)
        if wc.get("available"):
            shown = wc["series"][-4:]
            wc_rows = [[Paragraph("Vốn lưu động (tỷ đồng)", ST["cellh"])]
                       + [Paragraph(f"<b>{x['year']}</b>", ST["cellr"]) for x in shown],
                       [_p("NWC = TSNH − Nợ ngắn hạn", "cell")]
                       + [Paragraph(_bn(x["nwc"]), ST["cellr"]) for x in shown],
                       [_p("Hệ số thanh toán ngắn hạn", "cell")]
                       + [Paragraph("N/A" if x["current_ratio"] is None else f"{x['current_ratio']:.2f}x", ST["cellr"]) for x in shown]]
            nwc = wc["latest"]["nwc"]
            cr = wc["latest"]["current_ratio"]
            trend = ""
            if wc.get("nwc_change") is not None:
                trend = f" NWC so với năm trước {wc['nwc_change']:+.1%}."
            wc_note = (f"NWC năm {wc['latest']['year']}: {_bn(nwc)} tỷ đồng"
                       + (f" · hệ số thanh toán ngắn hạn {cr:.2f}x" if cr is not None else "")
                       + "." + trend +
                       " Số liệu hợp nhất từ BCTC năm trong CSV; không điều chỉnh theo kỳ quý và không suy diễn khi thiếu năm.")
            fl += [Spacer(1, 5), KeepTogether([Paragraph("Vốn lưu động & thanh khoản ngắn hạn", ST["h2"]),
                                               _tbl(wc_rows, [CONTENT_W * .30] + [CONTENT_W * .70 / len(shown)] * len(shown)),
                                               Spacer(1, 3), _p(wc_note, "small")])]
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
        # Dòng tiền HĐKD và CAPEX lấy trực tiếp từ BCTC gốc, cùng bảng để dễ đối chiếu
        # (thay cho phụ lục BCTC dài trước đây).
        for label, item_id in (("Dòng tiền HĐKD", "operating_cash_flow"), ("CAPEX", "capital_expenditure")):
            series = _raw_series(fd, item_id)
            if not series:
                continue
            vals = [series.get(str(r.get("period"))) for r in hist]
            if all(v is None for v in vals):
                continue
            rows.append([_p(label, "cell")] + [Paragraph("N/A" if v is None else f"{v / 1e9:,.0f}", ST["cellr"]) for v in vals])
        n = len(hist)
        fl += [Spacer(1, 6), _tbl(rows, [CONTENT_W * .30] + [CONTENT_W * .70 / n] * n),
               _p("Dòng tiền và CAPEX đơn vị tỷ đồng, lấy từ BCTC hợp nhất cùng kỳ với các chỉ tiêu trên.", "small")]
    if f.get("commentary"):
        fl += [Spacer(1, 6), _callout("Nhận định tài chính", [_p(f["commentary"])], color=TEAL, bg="#EEF9F8")]
    analytics = f.get("financial_analytics") or {}
    dupont = analytics.get("dupont") or {}
    current = dupont.get("current") or {}
    previous = dupont.get("previous") or {}
    if any(_f(current.get(k)) is not None for k in ("net_margin", "asset_turnover", "equity_multiplier", "roe")):
        fl += [Spacer(1, 7), Paragraph("Phân rã ROE DuPont 3 yếu tố", ST["h2"])]
        keys = [("Biên LN ròng", "net_margin", True), ("Vòng quay tài sản", "asset_turnover", False),
                ("Đòn bẩy vốn chủ", "equity_multiplier", False), ("ROE", "roe", True)]
        rows = [[Paragraph("Chỉ tiêu", ST["cellh"]), Paragraph("Năm gần nhất", ST["cellh"]),
                 Paragraph("Năm trước", ST["cellh"]), Paragraph("Thay đổi YoY", ST["cellh"])] ]
        changes = dupont.get("factor_yoy_change") or {}
        for label, key, percent in keys:
            now, before = _f(current.get(key)), _f(previous.get(key))
            show = lambda value: "N/A" if value is None else (f"{value:.2%}" if percent else f"{value:.2f}x")
            change = _f(changes.get(key))
            rows.append([_p(label, "cell"), _p(show(now), "cellr"), _p(show(before), "cellr"),
                         _p("N/A" if change is None else f"{change:+.1%}", "cellr")])
        fl.append(_tbl(rows, [CONTENT_W*.34, CONTENT_W*.22, CONTENT_W*.22, CONTENT_W*.22]))
        if dupont.get("commentary"):
            fl += [Spacer(1, 4), _callout("Động lực thay đổi ROE", [_p(dupont["commentary"], "small")], color=BLUE, bg="#F3F8FF")]
    earnings = analytics.get("earnings_quality") or {}
    if earnings:
        ratio = _f(earnings.get("ocf_ratio"))
        level = str(earnings.get("level") or "missing").lower()
        color = RED if level == "high" else AMBER if level == "warning" else GREEN if level == "good" else MUTED
        ratio_text = "N/A" if ratio is None else f"{ratio:.1%}"
        fl += [Spacer(1, 6), _callout("Chất lượng lợi nhuận · OCF/LNST", [
            _p(f"OCF: {_bn(earnings.get('ocf'))} tỷ đồng · LNST: {_bn(earnings.get('net_income'))} tỷ đồng · OCF/LNST: {ratio_text}", "cellb"),
            _p(earnings.get("commentary") or "Chưa đủ dữ liệu để đánh giá OCF/LNST.", "small")], color=color,
            bg="#FFF3F4" if level == "high" else "#FBF7EE" if level == "warning" else "#EEF9F8" if level == "good" else "#F3F7FA")]
    return fl


def _sec_valuation(results, fd):
    v = results.get("valuation") or {}
    fallback_used = bool(v.get("valuation_fallback_used"))
    hist = _history(fd)
    fl = _section("Phân tích định giá", "Định giá lịch sử, so sánh cùng ngành và dải giá trị hàm ý")
    sc = _f(v.get("score"))
    peer = v.get("peer_valuation") or {}
    ref = _f(v.get("peer_fair_value") or peer.get("peer_fair_value") or peer.get("fair_value"))
    up = _f(v.get("peer_upside_downside"))
    if up is not None and abs(up) > 3:
        up /= 100
    fl.append(_kpis([("Valuation Score", "N/A" if sc is None else f"{sc:.1f}", _label(sc), _tone_color(sc)),
                     ("P/E tham chiếu FY" if fallback_used else "P/E hiện tại", _fmt(v.get("pe"), 2, "x"), f"Trung vị LS {_fmt(v.get('historical_pe_median'), 2, 'x')}", BLUE),
                     ("P/B tham chiếu FY" if fallback_used else "P/B hiện tại", _fmt(v.get("pb"), 2, "x"), f"Trung vị LS {_fmt(v.get('historical_pb_median'), 2, 'x')}", TEAL),
                     ("Peer Fair Value", "N/A" if ref is None else f"{ref:,.0f}", "VND (hàm ý)", PURPLE),
                     ("Chênh lệch", "N/A" if up is None else f"{up * 100:+.1f}%", "so với giá hiện tại", GREEN if (up or 0) >= 0 else RED)]))
    # ---- Lớp 1: định giá lịch sử
    fl.append(Paragraph("1. Định giá lịch sử (so với chính doanh nghiệp)", ST["h2"]))
    if hist:
        fl += [Spacer(1, 4), chart_valuation(hist, v)]
    else:
        fl.append(_p("Chưa có chuỗi P/E, P/B theo năm để so sánh lịch sử.", "small"))
    fl.append(_p(
        f"P/E {_fmt(v.get('pe'), 2, 'x')} so với trung vị lịch sử {_fmt(v.get('historical_pe_median'), 2, 'x')}; "
        f"P/B {_fmt(v.get('pb'), 2, 'x')} so với {_fmt(v.get('historical_pb_median'), 2, 'x')}. "
        "Bội số thấp hơn lịch sử chỉ là thông tin so sánh, không đồng nghĩa cổ phiếu rẻ nếu ROE, "
        "tăng trưởng hoặc chất lượng lợi nhuận đã thay đổi.", "small"))
    # ---- Lớp 2: định giá so sánh
    fl.append(Paragraph("2. Định giá so sánh (nhóm cùng ngành)", ST["h2"]))
    fallback = v.get("fallback") or peer.get("fallback") or {}
    fallback_active = bool(v.get("is_fallback", peer.get("is_fallback", fallback.get("is_fallback", False))))
    if fallback_active:
        level = v.get("fallback_level") or peer.get("fallback_level") or fallback.get("fallback_level") or "ngành mở rộng"
        note_text = v.get("fallback_note") or peer.get("fallback_note") or fallback.get("note") or "Mẫu ngành hẹp chưa đủ dữ liệu."
        fl += [Spacer(1, 3), _callout("Cảnh báo nhóm tham chiếu", [_p(f"Fallback: {level}. {note_text}", "small")], color=AMBER, bg="#FBF7EE")]
    peers = peer.get("peers")
    prow = []
    if isinstance(peers, pd.DataFrame):
        peers = peers.to_dict("records")
    if isinstance(peers, list):
        peers = _norm_cols([p for p in peers if isinstance(p, dict)], ("roe", "net_margin", "revenue_growth"))
        for p in peers[:5]:
            if isinstance(p, dict):
                code = p.get("symbol") or p.get("ticker") or p.get("Mã") or ""
                roe = _ratio(p.get("roe"))
                margin, growth = _ratio(p.get("net_margin")), _ratio(p.get("revenue_growth"))
                company_name = p.get("name") or p.get("company_name") or code
                prow.append([_p(code, "cellb"), _p(company_name, "cell"), Paragraph(_fmt(p.get("pe"), 2, "x"), ST["cellr"]),
                             Paragraph(_fmt(p.get("pb"), 2, "x"), ST["cellr"]), Paragraph("N/A" if roe is None else f"{roe * 100:.1f}%", ST["cellr"]),
                             Paragraph("N/A" if margin is None else f"{margin * 100:.1f}%", ST["cellr"]),
                             Paragraph("N/A" if growth is None else f"{growth * 100:.1f}%", ST["cellr"])])
    if prow:
        rows = [[Paragraph(h, ST["cellh"]) for h in ("Mã", "Doanh nghiệp", "P/E", "P/B", "ROE", "Biên LN", "Tăng trưởng DT")]] + prow
        fl += [Spacer(1, 3), _tbl(rows, [CONTENT_W*.09, CONTENT_W*.27, CONTENT_W*.12, CONTENT_W*.12, CONTENT_W*.12, CONTENT_W*.13, CONTENT_W*.15])]
        median_roe = _f(v.get("peer_median_roe", peer.get("peer_median_roe")))
        if median_roe is not None:
            fl.append(_p(f"Trung vị nhóm peer: ROE {median_roe:.2%} · P/E {_fmt(v.get('peer_median_pe', peer.get('peer_median_pe')), 2, 'x')} · P/B {_fmt(v.get('peer_median_pb', peer.get('peer_median_pb')), 2, 'x')}", "small"))
    else:
        fl.append(_p("Chưa có doanh nghiệp cùng ngành đủ dữ liệu để đối chiếu.", "small"))
    # ---- Lớp 3: dải giá trị hàm ý & độ nhạy
    fl.append(Paragraph("3. Giá trị hàm ý & độ nhạy (kịch bản tham chiếu)", ST["h2"]))
    scen = v.get("scenarios") or peer.get("scenarios") or {}
    if scen.get("available"):
        srows = [[Paragraph(h, ST["cellh"]) for h in ("Kịch bản", "Bội số P/E", "Bội số P/B", "Giá hàm ý (VND)", "Chênh lệch")]]
        for label, key in (("Bear (P25)", "bear"), ("Base (trung vị)", "base"), ("Bull (P75)", "bull")):
            band = scen.get(key) or {}
            band_up = _f(band.get("upside"))
            price_value = _f(band.get("price"))
            srows.append([_p(label, "cellb"), _p(_fmt(band.get("pe_multiple"), 2, "x"), "cellr"),
                          _p(_fmt(band.get("pb_multiple"), 2, "x"), "cellr"),
                          _p("N/A" if price_value is None else f"{price_value:,.0f}", "cellr"),
                          Paragraph("N/A" if band_up is None else f'<font color="{GREEN if band_up >= 0 else RED}">{band_up * 100:+.1f}%</font>', ST["cellr"])])
        fl += [Spacer(1, 3), _tbl(srows, [CONTENT_W*.24, CONTENT_W*.18, CONTENT_W*.18, CONTENT_W*.22, CONTENT_W*.18])]
        fl.append(_p((scen.get("assumption") or "") + " Không gán xác suất cho từng kịch bản; đây là độ nhạy theo bội số, không phải dự báo.", "small"))
    else:
        fl += [Spacer(1, 3), _callout("Chưa dựng được dải giá trị", [
            _p(scen.get("reason") or "Chưa đủ dữ liệu peer để dựng kịch bản.", "small")], color=MUTED, bg="#F3F7FA")]
    # Gộp hai nhận định (định giá nội tại & so sánh cùng ngành) vào một khối để gọn trang.
    comments = [x for x in (v.get("commentary"), v.get("peer_commentary") or peer.get("commentary")) if x]
    if comments:
        fl += [Spacer(1, 6), _callout("Nhận định định giá & so sánh cùng ngành", [_p(x) for x in comments], color=PURPLE, bg="#F6F3FF")]
    note = (
        "Snapshot không khớp nên P/E/P/B tham chiếu được tính từ giá hiện tại và BCTC năm gần nhất; EPS năm không phải EPS TTM."
        if fallback_used else
        "P/E, P/B snapshot CSV không có ngày công bố; chỉ được dùng khi giá hàm ý khớp thị trường."
    )
    fl += [Spacer(1, 4), _p(note + " Các con số trên là giá trị tham chiếu/độ nhạy khi mẫu đủ tin cậy, không phải giá mục tiêu hay khuyến nghị.", "small")]
    return fl


def _sec_news(results):
    n = results.get("news") or {}
    items = [i for i in (n.get("items") or []) if isinstance(i, dict)]
    fl = _section("Tin tức & triển vọng", "Tin gần đây về doanh nghiệp và sắc thái thông tin")
    sc = _f(n.get("score"))
    intelligence = n.get("intelligence") or {}
    cats = intelligence.get("categories") or {}
    cat_text = " · ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])) if cats else "Chưa đủ tin để phân loại chủ đề."
    left = [_kpis([("News Score", "N/A" if sc is None else f"{sc:.1f}", n.get("classification") or _label(sc), _tone_color(sc))], width=CONTENT_W * .6),
            Spacer(1, 5), _p(n.get("commentary") or "Chưa có nhận định tin tức.", "body"),
            Spacer(1, 4), _p("Phân loại chủ đề (heuristic theo tiêu đề): " + cat_text, "small")]
    fl.append(_side_by_side(left, chart_news(items) if items else Spacer(1, 1), CONTENT_W * .6 + 6, CONTENT_W * .4 - 6))
    smap = {"Positive": ("Tích cực", GREEN), "Negative": ("Tiêu cực", RED), "Neutral": ("Trung tính", MUTED)}
    rows = [[Paragraph(h, ST["cellh"]) for h in ("Ngày", "Chủ đề", "Loại", "Sắc thái", "Tiêu đề / nguồn")]]
    for i in sorted(items, key=lambda x: str(x.get("published") or ""), reverse=True)[:8]:
        lab, col = smap.get(i.get("sentiment"), ("N/A", MUTED))
        source = str(i.get("source_name") or "")
        title = str(i.get("title") or "")
        extra = f" ({source})" if source and source.lower() not in title.lower() else ""
        merged = int(i.get("duplicate_count") or 1)
        if merged > 1:
            extra += f" · gộp {merged} nguồn"
        rows.append([_p(str(i.get("published") or "")[:10], "cell"),
                     _p(i.get("category") or "Khác", "cell"),
                     _p("Nhận định" if i.get("is_opinion") else "Sự kiện", "cell"),
                     Paragraph(f'<font color="{col}"><b>{lab}</b></font>', ST["cell"]),
                     _p(title + extra, "cell")])
    if len(rows) > 1:
        fl += [Paragraph("Tin nổi bật (đã gộp tiêu đề trùng)", ST["h2"]),
               _tbl(rows, [CONTENT_W * .11, CONTENT_W * .14, CONTENT_W * .09, CONTENT_W * .09, CONTENT_W * .57])]
    fl += [Spacer(1, 5), _callout("Tác động kinh doanh & giới hạn", [
        _p(f"{intelligence.get('verified_events', 0)} tin dạng sự kiện · "
           f"{intelligence.get('opinion', 0)} tin nhận định/khuyến nghị · "
           f"{intelligence.get('price_only', 0)} tin chỉ phản ánh giá · "
           f"đã gộp {intelligence.get('duplicates_merged', 0)} tiêu đề trùng.", "small"),
        _p("Sắc thái và chủ đề được suy ra từ tiêu đề (heuristic), không phân tích toàn văn; "
           "sắc thái tiêu đề được tách riêng khỏi tác động kinh doanh thực tế. "
           "Tin nhận định/khuyến nghị không được coi là sự kiện đã xác minh.", "small")],
        color=AMBER, bg="#FBF7EE")]
    fl += [Spacer(1, 4), _p(f"Nguồn: {n.get('source') or 'Google News RSS'}. News Score là heuristic theo tiêu đề và độ mới, không phải mô hình NLP toàn văn.", "small")]
    return fl


def _sec_score(summary, profile, th, results=None):
    comp = summary.get("component_scores") or {}
    results = results or {}
    fl = _section("Investment Score & hồ sơ nhà đầu tư", "Cấu trúc điểm, mức đóng góp và góc nhìn theo khẩu vị rủi ro")
    fl.append(_side_by_side(chart_components(comp, h=1.9), chart_profiles(summary.get("profile_scores") or {}, profile, h=1.9), CONTENT_W * .6 + 4, CONTENT_W * .4 - 4))
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
    matrix = summary.get("weight_breakdown") or {}
    if matrix:
        fl.append(Paragraph("Bảng trọng số theo phong cách đầu tư", ST["h2"]))
        style_rows = [[Paragraph(h, ST["cellh"]) for h in ("Phong cách", "BCTC", "Định giá", "Kỹ thuật", "Tin tức", "Rủi ro")]]
        for style, detail in matrix.items():
            weights_for_style = detail.get("weights") or {}
            style_rows.append([_p(detail.get("label") or style, "cellb")] +
                              [_p(f"{(weights_for_style.get(k) or {}).get('weight_pct', 0)}%", "cellr")
                               for k in ("fundamental", "valuation", "technical", "news", "risk")])
        fl.append(_tbl(style_rows, [CONTENT_W*.24] + [CONTENT_W*.152]*5))
    positive = summary.get("positive_drivers") or (summary.get("why_this_score") or {}).get("positive_drivers") or []
    negative = summary.get("negative_drivers") or (summary.get("why_this_score") or {}).get("negative_drivers") or []
    pos_body = [_p(x, "small") for x in positive[:4]] or [_p("Chưa có luận điểm tích cực nổi bật từ dữ liệu hiện có.", "small")]
    neg_body = [_p(x, "small") for x in negative[:4]] or [_p("Chưa ghi nhận rủi ro nổi bật từ dữ liệu hiện có.", "small")]
    fl += [Spacer(1, 5), _side_by_side(_callout("Yếu tố kéo điểm lên", pos_body, color=GREEN, bg="#EEF9F5", width=CONTENT_W*.47),
                                       _callout("Yếu tố kéo điểm xuống", neg_body, color=RED, bg="#FFF3F4", width=CONTENT_W*.47),
                                       CONTENT_W*.5, CONTENT_W*.5, gap=8)]
    if summary.get("missing"):
        fl += [Spacer(1, 4), _callout("Cảnh báo dữ liệu", [_p("Thiếu thành phần: " + ", ".join(map(str, summary["missing"])) + ". StockLens không tự nội suy thành phần bị thiếu.")], color=RED, bg="#FFF3F4")]
    risk = results.get("risk") or {}
    risk_components = risk.get("component_scores") or {}
    risk_metrics = risk.get("metrics") or {}
    if risk_components or risk.get("method_note"):
        measured = []
        if risk_metrics.get("volatility_20_annualized") is not None:
            measured.append(f"biến động 20 phiên quy năm {_fmt(_f(risk_metrics.get('volatility_20_annualized')) * 100, 1, '%')}")
        if risk_metrics.get("max_drawdown_period") is not None:
            measured.append(f"mức sụt giảm tối đa trong kỳ {_fmt(_f(risk_metrics.get('max_drawdown_period')) * 100, 1, '%')}")
        risk_text = ("Risk/An toàn là ĐIỂM RỦI RO THỊ TRƯỜNG, chỉ đo: "
                     + ("; ".join(measured) if measured else "chưa đủ dữ liệu")
                     + ". Đây không phải rủi ro toàn diện của doanh nghiệp (không bao gồm rủi ro thanh khoản bảng cân đối, quản trị, pha loãng hay pháp lý).")
        fl += [Spacer(1, 5), _callout("Risk/An toàn đo lường gì", [_p(risk_text, "small")], color=AMBER, bg="#FBF7EE")]
    return fl


def _sec_method(results, summary):
    fl = _section("Phương pháp, nguồn dữ liệu & giới hạn")
    t = results.get("technical") or {}
    price_date = str(t.get("analysis_date") or datetime.now().strftime("%d/%m/%Y"))
    rows = [[Paragraph(h, ST["cellh"]) for h in ("Nhóm", "Nguồn & phương pháp", "Kỳ / cập nhật")],
            [_p("Giá & kỹ thuật", "cellb"),
             _p("DNSE OpenAPI (dự phòng vnstock). MA20/50, RSI(14), MACD(12,26,9), Volume/MA20, biến động, drawdown; hỗ trợ/kháng cự theo pivot 60 phiên.", "cell"),
             _p(price_date, "cell")],
            [_p("BCTC & cơ bản", "cellb"),
             _p("CSV stock.quanganh.org (BCTC FY 2020–2025; ngân hàng có NIM/NPL/CAR/CASA/LDR). Tiền chuẩn hóa về VND; không điền năm thiếu; điểm cơ bản bị chặn khi thiếu dữ liệu.", "cell"),
             _p("FY gần nhất trong CSV", "cell")],
            [_p("Định giá", "cellb"),
             _p("P/E, P/B CSV chỉ dùng khi giá hàm ý khớp giá quan sát; peer theo bảng nhóm ngành tham khảo (chưa phải ICB chuẩn); ẩn Peer Fair Value/kịch bản khi chất lượng không đạt.", "cell"),
             _p("Snapshot CSV không ngày (cảnh báo)", "cell")],
            [_p("Tin tức", "cellb"),
             _p("Google News RSS. Sắc thái, chủ đề, gộp tiêu đề trùng và tách tín hiệu giá/nhận định là heuristic theo tiêu đề, KHÔNG phân tích toàn văn.", "cell"),
             _p("120 ngày gần nhất", "cell")],
            [_p("Điểm & luận điểm", "cellb"),
             _p("25% Tài chính + 25% Định giá + 25% Kỹ thuật + 15% Tin tức + 10% Rủi ro/An toàn; hồ sơ dùng trọng số điều chỉnh (Thận trọng/Cân bằng/Tăng trưởng). Sinh tự động từ dữ liệu đã thu thập.", "cell"),
             _p("Tại thời điểm tạo", "cell")]]
    fl.append(_tbl(rows, [CONTENT_W * .16, CONTENT_W * .62, CONTENT_W * .22]))

    def_rows = [[Paragraph("Chỉ tiêu", ST["cellh"]), Paragraph("Định nghĩa & đơn vị", ST["cellh"])],
                [_p("Doanh thu / LNST", "cellb"), _p("Doanh thu thuần và LNST hợp nhất (toàn công ty), đơn vị VND; khác doanh thu tài chính và phần LNST thuộc cổ đông công ty mẹ.", "cell")],
                [_p("EPS / BVPS", "cellb"), _p("EPS = LNST / số cổ phiếu (năm BCTC gần nhất, không phải EPS TTM); BVPS = vốn chủ sở hữu / số cổ phiếu lưu hành.", "cell")],
                [_p("P/E, P/B, ROE, ROA", "cellb"), _p("P/E = giá/EPS; P/B = giá/BVPS; ROE = LNST/vốn chủ sở hữu; ROA = LNST/tổng tài sản. DuPont: ROE = biên LN ròng × vòng quay tài sản × đòn bẩy.", "cell")],
                [_p("Kịch bản giá", "cellb"), _p("Bear/Base/Bull = bách phân vị 25/50/75 của bội số P/E, P/B thực tế nhóm peer áp lên EPS/BVPS; không gán xác suất.", "cell")]]
    fl += [Spacer(1, 7), Paragraph("Định nghĩa chỉ tiêu quan trọng", ST["h2"]), _tbl(def_rows, [CONTENT_W * .22, CONTENT_W * .78])]

    fl += [Spacer(1, 7), KeepTogether([Paragraph("Xử lý thiếu dữ liệu & xung đột nguồn", ST["h2"])] + _bullets([
        "Thiếu dữ liệu: hiển thị N/A kèm lý do; không suy diễn, không thay bằng số ước lượng, không tính 0 cho chỉ tiêu thiếu.",
        "Xung đột nguồn: khi hai nguồn khác kỳ/kết hợp/đơn vị, ưu tiên nguồn BCTC gắn kỳ công bố và cảnh báo; không trộn hai nguồn để lấp chỗ trống.",
        "Chỉ số định giá snapshot không ngày chỉ dùng khi giá hàm ý khớp giá quan sát; ngược lại tính lại từ giá hiện tại và đánh dấu rõ.",
        "Peer Fair Value và kịch bản bị ẩn khi mẫu peer quá nhỏ, ROE lệch lớn, hoặc tỷ số định giá là giá trị suy diễn (fallback).",
        "Investment Score chỉ tính khi đủ thành phần; thiếu thành phần trả N/A thay vì rút gọn trọng số âm thầm.",
    ]))]

    fl += [Spacer(1, 8), _callout("Giới hạn & tuyên bố miễn trừ", [_p(
        "Investment Score là mô hình heuristic phục vụ học tập, chưa backtest như chiến lược giao dịch. Dữ liệu bên thứ ba có thể thay đổi, chậm cập nhật hoặc thiếu; báo cáo hiển thị N/A thay vì tự điền. "
        "Peer Fair Value và kịch bản chỉ là giá trị hàm ý/độ nhạy tương đối, không phải giá mục tiêu. Nội dung không cấu thành khuyến nghị mua, bán, nắm giữ hay tư vấn đầu tư cá nhân.")], color=RED, bg="#FFF6F7")]
    fl += [Spacer(1, 6), _p(
        f"Báo cáo tạo ngày {datetime.now().strftime('%d/%m/%Y')}. Kiểm tra định kỳ: KQKD quý mới, giá và thanh khoản, cùng nguồn BCTC gốc trước khi dùng số liệu cho bất kỳ quyết định nào.", "small")]
    return fl


# ----------------------------------------------------------------------------- tài liệu + đánh số trang
class _Doc(BaseDocTemplate):
    def __init__(self, buf, ticker, cover_data=None, logo=None, **kw):
        super().__init__(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=17 * mm,
                         title=f"StockLens - {ticker}", author="StockLens", **kw)
        self.ticker = ticker
        self.cover_data = cover_data
        self.logo = logo
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
        # Logo doanh nghiệp cỡ nhỏ ở góc phải header (giữ đúng tỉ lệ, không che nội dung).
        if self.logo:
            try:
                box = 11 * mm
                x0 = w - 18 * mm - box
                canv.setFillColor(colors.white)
                canv.roundRect(x0, h - 13.2 * mm, box, box, 2 * mm, fill=1, stroke=0)
                pad = 1.4 * mm
                canv.drawImage(ImageReader(io.BytesIO(self.logo)), x0 + pad, h - 13.2 * mm + pad,
                               width=box - 2 * pad, height=box - 2 * pad,
                               preserveAspectRatio=True, mask="auto", anchor="c")
            except Exception:
                pass
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
    toc.levelStyles = [ParagraphStyle("toc0", parent=ST["toc0"], fontName="SL", fontSize=9.5,
                                      leading=21, leftIndent=0, rightIndent=18, firstLineIndent=0,
                                      spaceBefore=2, spaceAfter=3)]

    plan = [("overview", "Tổng quan doanh nghiệp và ngành")]
    plan.insert(0, ("exec", "Tóm tắt điều hành"))
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
        "exec": lambda: _sec_exec_summary(ticker, results, summary, fd, company, profile, th),
        "overview": lambda: _sec_overview(ticker, company, results, summary, fd, profile),
        "thesis": lambda: _sec_thesis(ticker, th),
        "technical": lambda: _sec_technical(results),
        "fundamental": lambda: _sec_fundamental(results, summary, fd, company),
        "valuation": lambda: _sec_valuation(results, fd),
        "news": lambda: _sec_news(results),
        "score": lambda: _sec_score(summary, profile, th, results),
        "method": lambda: _sec_method(results, summary),
    }

    story = _cover(ticker, period_text, profile, results, summary, company, fd, th, toc)
    # Mục lục gọn 2 dòng ở đầu trang 2 (không chiếm trọn một trang riêng) để vừa
    # giữ điều hướng "Nội dung nghiên cứu" vừa rút ngắn số trang.
    story.append(Paragraph("Nội dung nghiên cứu", ST["h2"]))
    story.append(Paragraph("  ·  ".join(f"{i:02d} {title}" for i, (_k, title) in enumerate(plan, 1)), ST["small"]))
    story.append(Spacer(1, 7))
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
        # Bản rút gọn: để các mục chảy liền mạch (tiêu đề có keepWithNext) thay vì
        # ép mỗi mục sang trang mới, nhằm giảm số trang và tránh trang thưa.
        if i < len(plan):
            story.append(Spacer(1, 9))

    buf = io.BytesIO()
    try:
        _logo, _logo_info = get_logo(ticker, company.get("website"))
    except Exception:
        _logo, _logo_info = logo_bytes(ticker, company.get("website")), {"source": "monogram"}
    doc = _Doc(buf, ticker, cover_data=(ticker, period_text, profile, results, summary, company, th),
               logo=_logo)
    doc.multiBuild(story, canvasmaker=_Numbered)
    return buf.getvalue()
