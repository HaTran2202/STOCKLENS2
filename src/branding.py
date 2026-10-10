"""StockLens - logo doanh nghiệp (không bao giờ để ảnh vỡ).

Thứ tự ưu tiên:
  1. Logo do bạn tự đặt: assets/logos/<MÃ>.png|jpg|webp|svg
  2. Logo đã tải về trước đó (cache): assets/logos/cache/<MÃ>.png
  3. Tải favicon/logo theo tên miền doanh nghiệp (Google s2, DuckDuckGo) rồi lưu cache
  4. Monogram (chữ cái đầu trong khối màu) - luôn có, không phụ thuộc mạng

Lưu ý: logo.clearbit.com đã ngừng hoạt động nên không còn được dùng.
"""
from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

BASE = Path(__file__).resolve().parent.parent
LOGO_DIRS = [BASE / "assets" / "logos", BASE / "assets" / "company_images", BASE / "logos"]
CACHE_DIR = BASE / "assets" / "logos" / "cache"
EXTS = ("png", "jpg", "jpeg", "webp", "svg")
PALETTE = ["#176FD1", "#11A99F", "#7B61D9", "#E0912B", "#D4546A", "#2F8F5B", "#0B2B55", "#5B6EE1"]


def _domain_from(website: str | None) -> Optional[str]:
    if not website:
        return None
    d = website.replace("https://", "").replace("http://", "").split("/")[0]
    return d.replace("www.", "").strip() or None


def _find_local(ticker: str) -> Optional[Path]:
    for folder in LOGO_DIRS + [CACHE_DIR]:
        for ext in EXTS:
            p = folder / f"{ticker.upper()}.{ext}"
            if p.exists() and p.stat().st_size > 200:
                return p
    return None


def _download(domain: str) -> Optional[bytes]:
    if requests is None or not domain:
        return None
    urls = [
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        f"https://icons.duckduckgo.com/ip3/{domain}.ico",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200 and len(r.content) > 400:
                return r.content
        except Exception:
            continue
    return None


def _to_png(raw: bytes) -> Optional[bytes]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None


def get_logo_path(ticker: str, website: str | None = None, domain: str | None = None) -> Optional[Path]:
    """Trả về đường dẫn file logo thật (nếu có/ tải được), ngược lại None."""
    p = _find_local(ticker)
    if p:
        return p
    dom = domain or _domain_from(website)
    raw = _download(dom) if dom else None
    png = _to_png(raw) if raw else None
    if png:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = CACHE_DIR / f"{ticker.upper()}.png"
        target.write_bytes(png)
        return target
    return None


def monogram_color(ticker: str) -> str:
    h = int(hashlib.md5(ticker.upper().encode()).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]


def monogram_png(ticker: str, size: int = 256) -> bytes:
    """Ảnh PNG monogram dùng cho PDF."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=monogram_color(ticker))
    text = ticker.upper()[:4]
    font = None
    try:
        import matplotlib
        fp = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
        fsize = int(size * (0.44 if len(text) <= 2 else 0.32 if len(text) == 3 else 0.26))
        font = ImageFont.truetype(str(fp), fsize)
    except Exception:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), text, fill="white", font=font)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def logo_bytes(ticker: str, website: str | None = None, domain: str | None = None) -> bytes:
    """Luôn trả về bytes ảnh (logo thật hoặc monogram) - dùng cho PDF."""
    p = get_logo_path(ticker, website, domain)
    if p:
        try:
            if p.suffix.lower() == ".svg":
                # SVG chỉ dùng trực tiếp được trong dashboard; PDF cần raster.
                from reportlab.graphics import renderPM
                from svglib.svglib import svg2rlg
                drawing = svg2rlg(str(p))
                if drawing:
                    return renderPM.drawToString(drawing, fmt="PNG")
            return p.read_bytes()
        except Exception:
            pass
    return monogram_png(ticker)


def logo_data_uri(ticker: str, website: str | None = None, domain: str | None = None) -> str:
    """Luôn trả về data URI (logo thật hoặc monogram SVG) - dùng cho dashboard."""
    p = get_logo_path(ticker, website, domain)
    if p:
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    color = monogram_color(ticker)
    text = ticker.upper()[:4]
    fs = 40 if len(text) <= 2 else 30 if len(text) == 3 else 24
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
           f"<rect width='96' height='96' rx='20' fill='{color}'/>"
           f"<text x='48' y='48' text-anchor='middle' dominant-baseline='central' "
           f"font-family='Arial,Helvetica,sans-serif' font-weight='700' font-size='{fs}' fill='white'>{text}</text></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")
