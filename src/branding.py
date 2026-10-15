"""StockLens - logo doanh nghiệp theo mã cổ phiếu (tự động, có cache, không bao giờ ảnh vỡ).

Mục tiêu: khi xuất báo cáo, hệ thống tự tìm đúng logo của doanh nghiệp theo ticker mà
người dùng KHÔNG phải tải logo thủ công và KHÔNG phải tạo sẵn thư mục logo cho từng mã.

Thứ tự ưu tiên:
  1. Logo do người dùng tự đặt (override): assets/logos/<MÃ>.png|jpg|webp|svg
  2. Cache đã xác minh trước đó: assets/logos/cache/<MÃ>.png (+ file metadata .json)
  3. Nguồn trực tuyến đã kiểm chứng, keyed theo TÊN MIỀN doanh nghiệp:
       a. logo.dev CDN  (https://img.logo.dev/{domain}?token=...) nếu có token cấu hình
       b. Hunter.io CDN (https://logos.hunter.io/{domain}) - không cần khoá
       c. Ảnh thương hiệu trên chính website doanh nghiệp (apple-touch-icon / icon /
          og:image có tên chứa "logo") - nguồn thuộc sở hữu doanh nghiệp
  4. Monogram (huy hiệu chữ cái theo ticker) - luôn có, không phụ thuộc mạng.

Ánh xạ ticker -> tên miền được thực hiện tự động, không hardcode cho một mã:
  * data/company_domains.json  (seed, dùng được offline)
  * assets/logos/cache/_domains.json (tên miền học thêm trong lúc chạy)
  * tra cứu trực tuyến qua vnstock (Company.overview().website) khi chưa biết - best effort.

Nguyên tắc an toàn dữ liệu:
  * Không dùng favicon/ảnh không liên quan; mọi ảnh đều phải qua kiểm tra (HTTP, kích thước
    file, giải mã ảnh, kích thước pixel, tỷ lệ khung, không phải ảnh trắng/1x1).
  * Không ghi đè cache hợp lệ bằng ảnh chưa được xác minh.
  * Ticker được chuẩn hoá + kiểm tra trước khi dùng để tạo đường dẫn file.
  * Lỗi mạng/giới hạn API/URL hỏng đều được nuốt lỗi và rơi về bước kế tiếp.

Cấu hình tuỳ chọn (đều không bắt buộc):
  * LOGODEV_TOKEN / LOGO_DEV_TOKEN / LOGO_DEV_KEY : khoá publishable của logo.dev (pk_...)
  * STOCKLENS_LOGO_OFFLINE=1 : chạy hoàn toàn offline (chỉ dùng override + cache + monogram)
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:  # Một số CDN logo (Hunter) trả AVIF; plugin này đăng ký codec AVIF cho Pillow.
    import pillow_avif  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    pass

BASE = Path(__file__).resolve().parent.parent
LOGO_DIRS = [BASE / "assets" / "logos", BASE / "assets" / "company_images", BASE / "logos"]
CACHE_DIR = BASE / "assets" / "logos" / "cache"
DOMAIN_SEED_FILE = BASE / "data" / "company_domains.json"
DOMAIN_LEARNED_FILE = CACHE_DIR / "_domains.json"
EXTS = ("png", "jpg", "jpeg", "webp", "svg")
PALETTE = ["#176FD1", "#11A99F", "#7B61D9", "#E0912B", "#D4546A", "#2F8F5B", "#0B2B55", "#5B6EE1"]

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 StockLens/1.0")
HTTP_TIMEOUT = (5, 12)          # (connect, read) giây
CACHE_TTL_DAYS = 120            # sau thời gian này sẽ thử làm mới (không xoá cache cũ)
MIN_ONLINE_DIM = 64             # cạnh lớn nhất tối thiểu của ảnh tải về (lọc favicon quá nhỏ)
MIN_ONLINE_SIDE = 16            # cạnh nhỏ nhất tối thiểu
MAX_ASPECT = 8.0                # tỷ lệ khung tối đa (lọc ảnh dải/banner không liên quan)
MIN_FILE_BYTES = 300            # file ảnh nhỏ hơn mức này coi như lỗi / placeholder

# Fallback tối thiểu khi thiếu cả seed lẫn cache và không có mạng.
_MINIMAL_STATIC = {
    "FPT": "fpt.com", "HPG": "hoaphat.com.vn", "MWG": "mwg.vn", "VNM": "vinamilk.com.vn",
    "VCB": "vietcombank.com.vn", "TCB": "techcombank.com.vn", "MBB": "mbbank.com.vn",
    "ACB": "acb.com.vn", "BID": "bidv.com.vn", "CTG": "vietinbank.vn", "VPB": "vpbank.com.vn",
    "STB": "sacombank.com.vn", "SSI": "ssi.com.vn", "PNJ": "pnj.com.vn", "VIC": "vingroup.net",
    "VHM": "vinhomes.vn", "MSN": "masangroup.com", "GAS": "pvgas.com.vn", "SAB": "sabeco.com.vn",
}

_TICKER_RE = re.compile(r"^[A-Z0-9]{2,10}$")


# ----------------------------------------------------------------------------- tiện ích chung
def normalize_ticker(ticker: str) -> str:
    """Chuẩn hoá ticker: bỏ khoảng trắng, hậu tố sàn (.VN / -HOSE ...), viết hoa."""
    if ticker is None:
        return ""
    t = str(ticker).strip().upper()
    for sep in (".", " ", "/"):
        if sep in t:
            t = t.split(sep)[0]
    t = t.split("-")[0]
    return t


def _valid_ticker(ticker: str) -> bool:
    return bool(_TICKER_RE.match(ticker or ""))


def _domain_from(website: Optional[str]) -> Optional[str]:
    if not website:
        return None
    d = re.sub(r"^https?://", "", str(website).strip(), flags=re.I).split("/")[0]
    d = d.split(":")[0].replace("www.", "").strip().lower()
    return d or None


def _offline() -> bool:
    return str(os.getenv("STOCKLENS_LOGO_OFFLINE", "")).strip().lower() in {"1", "true", "yes"}


def _logodev_token() -> Optional[str]:
    for key in ("LOGODEV_TOKEN", "LOGO_DEV_TOKEN", "LOGO_DEV_KEY"):
        v = os.getenv(key)
        if v and v.strip():
            return v.strip()
    return None


# ----------------------------------------------------------------------------- HTTP tối giản
def _http_get(url: str, timeout=HTTP_TIMEOUT) -> tuple[int, bytes, str]:
    """GET an toàn. Trả (status, bytes, content_type). Lỗi mạng -> (0, b'', '')."""
    headers = {"User-Agent": USER_AGENT, "Accept": "image/*,text/html;q=0.8,*/*;q=0.5"}
    if requests is not None:
        try:
            r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
            return r.status_code, r.content or b"", r.headers.get("Content-Type", "")
        except Exception:
            return 0, b"", ""
    try:  # pragma: no cover - chỉ dùng khi thiếu requests
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout[1]) as resp:  # type: ignore[arg-type]
            return resp.getcode() or 200, resp.read(), resp.headers.get("Content-Type", "")
    except Exception:
        return 0, b"", ""


# ----------------------------------------------------------------------------- ảnh
def _svg_to_png(raw: bytes) -> Optional[bytes]:
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg
        drawing = svg2rlg(io.BytesIO(raw))
        if drawing:
            return renderPM.drawToString(drawing, fmt="PNG")
    except Exception:
        return None
    return None


def _looks_like_svg(raw: bytes) -> bool:
    head = raw[:512].lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in raw[:1024].lower())


def normalize_image(raw: bytes) -> Optional[dict]:
    """Giải mã + chuẩn hoá ảnh về PNG RGBA. Trả {'png','width','height','format'} hoặc None."""
    if not raw or len(raw) < MIN_FILE_BYTES:
        return None
    if _looks_like_svg(raw):
        png = _svg_to_png(raw)
        raw = png or b""
        if not raw:
            return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        fmt = img.format or "PNG"
        img = img.convert("RGBA")
        w, h = img.size
        if w <= 1 or h <= 1:
            return None
        out = io.BytesIO()
        img.save(out, format="PNG")
        return {"png": out.getvalue(), "width": int(w), "height": int(h), "format": fmt}
    except Exception:
        return None


def _passes_quality(info: Optional[dict], min_dim: int = MIN_ONLINE_DIM, min_side: int = MIN_ONLINE_SIDE) -> bool:
    if not info:
        return False
    w, h = info["width"], info["height"]
    if max(w, h) < min_dim or min(w, h) < min_side:
        return False
    if (max(w, h) / max(1, min(w, h))) > MAX_ASPECT:
        return False
    return True


def _is_low_detail(info: Optional[dict]) -> bool:
    """Ảnh nền/banner gradient mượt (mật độ cạnh rất thấp) -> không phải logo rõ ràng.

    Tránh trường hợp CDN logo trả về ảnh nền thương hiệu mờ nhạt thay vì logo
    (ví dụ Vietcombank). Logo thật (kể cả wordmark trên nền trắng) luôn có cạnh sắc.
    """
    if not info:
        return True
    try:
        from PIL import Image, ImageFilter
        src = Image.open(io.BytesIO(info["png"])).convert("RGBA").resize((160, 160))
        flat = Image.new("RGBA", (160, 160), (255, 255, 255, 255))
        flat.alpha_composite(src)
        edges = flat.convert("L").filter(ImageFilter.FIND_EDGES)
        px = list(edges.getdata())
        n = len(px) or 1
        frac = sum(1 for v in px if v > 40) / n
        mean = sum(px) / n
        return frac < 0.04 and mean < 9.0
    except Exception:
        return False


def _is_blank(info: Optional[dict]) -> bool:
    """Ảnh gần như trắng/đồng màu hoặc trong suốt hoàn toàn -> coi như không có logo."""
    if not info:
        return True
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(info["png"])).convert("RGBA")
        small = img.resize((32, 32))
        px = list(small.getdata())
        if not px:
            return True
        opaque = [p for p in px if p[3] > 20]
        if len(opaque) < len(px) * 0.02:
            return True
        # độ lệch màu tối đa giữa các pixel đục
        rs = [p[0] for p in opaque]; gs = [p[1] for p in opaque]; bs = [p[2] for p in opaque]
        spread = max(max(rs) - min(rs), max(gs) - min(gs), max(bs) - min(bs))
        return spread < 12
    except Exception:
        return False


# ----------------------------------------------------------------------------- ánh xạ ticker -> tên miền
def _load_json_map(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {normalize_ticker(k): _domain_from(v) or (v or None) for k, v in data.items() if k}
    except Exception:
        return {}


def _save_json_map(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _lookup_domain_online(ticker: str) -> Optional[str]:
    """Tra website chính thức qua vnstock (best effort, nuốt mọi lỗi + tiếng ồn stdout)."""
    if _offline():
        return None
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            from vnstock import Company  # type: ignore
            ov = Company(symbol=ticker, source="KBS", show_log=False).overview()
            row = ov.iloc[0] if hasattr(ov, "iloc") else ov
            website = row.get("website") if hasattr(row, "get") else None
        return _domain_from(website)
    except BaseException:
        return None


def resolve_domain(ticker: str, website: Optional[str] = None, domain: Optional[str] = None,
                   allow_network: bool = True) -> Optional[str]:
    """Xác định tên miền doanh nghiệp từ ticker (không hardcode cho một mã)."""
    if domain:
        return _domain_from(domain) or _domain_from(f"https://{domain}")
    if website:
        d = _domain_from(website)
        if d:
            return d
    t = normalize_ticker(ticker)
    if not t:
        return None
    for src in (_MINIMAL_STATIC, _load_json_map(DOMAIN_SEED_FILE), _load_json_map(DOMAIN_LEARNED_FILE)):
        d = src.get(t)
        if d:
            return d
    if allow_network and not _offline():
        d = _lookup_domain_online(t)
        if d:
            learned = _load_json_map(DOMAIN_LEARNED_FILE)
            learned[t] = d
            _save_json_map(DOMAIN_LEARNED_FILE, learned)
            return d
    return None


# ----------------------------------------------------------------------------- cache
def _manual_path(ticker: str) -> Optional[Path]:
    for folder in LOGO_DIRS:
        for ext in EXTS:
            p = folder / f"{ticker}.{ext}"
            try:
                if p.exists() and p.stat().st_size > 200:
                    return p
            except OSError:
                continue
    return None


def _cache_paths(ticker: str) -> tuple[Path, Path]:
    return CACHE_DIR / f"{ticker}.png", CACHE_DIR / f"{ticker}.json"


def _read_cache(ticker: str) -> Optional[dict]:
    png, meta_p = _cache_paths(ticker)
    try:
        if not png.exists() or png.stat().st_size < MIN_FILE_BYTES:
            return None
        raw = png.read_bytes()
    except OSError:
        return None
    info = normalize_image(raw)
    if not info or _is_blank(info) or _is_low_detail(info):
        return None
    meta = {}
    try:
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8")) or {}
    except Exception:
        meta = {}
    meta.setdefault("source", "cache")
    return {"png": raw, "meta": meta, "info": info}


def _cache_fresh(meta: dict) -> bool:
    ts = meta.get("fetched_at")
    if not ts:
        return False
    try:
        when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - when).total_seconds() / 86400
        return age_days <= CACHE_TTL_DAYS
    except Exception:
        return False


def _write_cache(ticker: str, info: dict, meta: dict) -> Optional[Path]:
    """Ghi cache + metadata. Không ghi nếu ảnh không hợp lệ."""
    if not info or not info.get("png"):
        return None
    png, meta_p = _cache_paths(ticker)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        raw = info["png"]
        meta = dict(meta)
        meta.update({"ticker": ticker, "width": info["width"], "height": info["height"],
                     "format": info.get("format", "PNG"),
                     "sha256": hashlib.sha256(raw).hexdigest(),
                     "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        tmp = png.with_suffix(".png.tmp")
        tmp.write_bytes(raw)
        tmp.replace(png)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return png
    except Exception:
        return None


# ----------------------------------------------------------------------------- nguồn trực tuyến
def _providers(domain: str, ticker: str) -> list[tuple[str, str]]:
    provs: list[tuple[str, str]] = []
    tok = _logodev_token()
    if tok:
        provs.append(("logo.dev", f"https://img.logo.dev/{domain}?token={tok}&format=png&size=256&fallback=404"))
    provs.append(("hunter", f"https://logos.hunter.io/{domain}"))
    return provs


def _fetch_provider(name: str, url: str) -> Optional[dict]:
    status, raw, _ct = _http_get(url)
    if status != 200:
        return None
    info = normalize_image(raw)
    if not _passes_quality(info) or _is_blank(info) or _is_low_detail(info):
        return None
    info["source"], info["url"] = name, url
    return info


_ICON_RE = re.compile(r"<link\b[^>]*>", re.I)
_OG_RE = re.compile(r"<meta\b[^>]*>", re.I)


def _attr(tag: str, name: str) -> Optional[str]:
    m = re.search(rf'{name}\s*=\s*["\']([^"\']+)["\']', tag, re.I)
    return m.group(1) if m else None


def _fetch_site_icon(domain: str) -> Optional[dict]:
    """Ảnh thương hiệu trên chính website doanh nghiệp (nguồn do doanh nghiệp sở hữu)."""
    status, raw, ctype = _http_get(f"https://{domain}/")
    if status != 200 or b"<" not in raw[:2048]:
        return None
    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        return None
    cands: list[tuple[int, str, str]] = []  # (ưu tiên, url, nhãn)
    for tag in _ICON_RE.findall(html):
        rel = (_attr(tag, "rel") or "").lower()
        href = _attr(tag, "href")
        if not href or "icon" not in rel:
            continue
        sizes = _attr(tag, "sizes") or ""
        px = 0
        m = re.match(r"(\d+)", sizes)
        if m:
            px = int(m.group(1))
        prio = 0 if "apple" in rel else (1 if "shortcut" in rel else 2)
        cands.append((prio * 1000 + (512 - min(px, 512)), href, rel or "icon"))
    for tag in _OG_RE.findall(html):
        prop = (_attr(tag, "property") or _attr(tag, "name") or "").lower()
        if prop != "og:image":
            continue
        content = _attr(tag, "content")
        if content and "logo" in content.lower():   # chỉ nhận og:image có gợi ý là logo
            cands.append((2500, content, "og:image(logo)"))
    cands.sort(key=lambda c: c[0])
    for _prio, href, label in cands[:4]:
        url = urljoin(f"https://{domain}/", href)
        status, raw, _ct = _http_get(url)
        if status != 200:
            continue
        info = normalize_image(raw)
        if _passes_quality(info, min_dim=48, min_side=12) and not _is_blank(info) and not _is_low_detail(info):
            info["source"], info["url"] = f"site:{label}", url
            return info
    return None


# ----------------------------------------------------------------------------- API chính
def get_logo(ticker: str, website: Optional[str] = None, domain: Optional[str] = None,
             allow_network: bool = True, refresh: bool = False) -> tuple[bytes, dict]:
    """Trả (bytes ảnh, thông tin nguồn). Không bao giờ ném lỗi; thiếu thì trả monogram."""
    t = normalize_ticker(ticker)
    if not _valid_ticker(t):
        return monogram_png(t or "?"), {"source": "monogram", "reason": "invalid_ticker"}

    manual = _manual_path(t)
    if manual:
        try:
            info = normalize_image(manual.read_bytes())
            if info:
                return info["png"], {"source": "manual", "path": str(manual),
                                     "width": info["width"], "height": info["height"]}
            if manual.suffix.lower() == ".svg":   # SVG chưa raster hoá được -> đọc thô
                return manual.read_bytes(), {"source": "manual", "path": str(manual)}
        except OSError:
            pass

    cached = _read_cache(t)
    cached_maxdim = max(cached["info"]["width"], cached["info"]["height"]) if cached else 0
    low_res = cached is not None and cached_maxdim < MIN_ONLINE_DIM

    if cached is not None and (not allow_network or _offline()):
        return cached["png"], cached["meta"]
    if cached is not None and _cache_fresh(cached["meta"]) and not refresh and not low_res:
        return cached["png"], cached["meta"]

    if allow_network and not _offline():
        dom = resolve_domain(t, website, domain, allow_network=True)
        if dom:
            for name, url in _providers(dom, t):
                info = _fetch_provider(name, url)
                if not info:
                    continue
                if cached is not None and not refresh and cached_maxdim > max(info["width"], info["height"]):
                    return cached["png"], cached["meta"]      # giữ bản cũ chất lượng hơn
                meta = {"source": name, "url": url, "domain": dom}
                _write_cache(t, info, meta)
                return info["png"], {**meta, "width": info["width"], "height": info["height"]}
            info = _fetch_site_icon(dom)
            if info and not (cached is not None and not refresh and cached_maxdim > max(info["width"], info["height"])):
                meta = {"source": info["source"], "url": info["url"], "domain": dom}
                _write_cache(t, info, meta)
                return info["png"], {**meta, "width": info["width"], "height": info["height"]}

    if cached is not None:   # tải thất bại nhưng vẫn còn cache hợp lệ -> dùng cache
        return cached["png"], cached["meta"]
    return monogram_png(t), {"source": "monogram", "reason": "no_logo_found"}


def get_logo_path(ticker: str, website: Optional[str] = None, domain: Optional[str] = None) -> Optional[Path]:
    """Đường dẫn file logo thật (override/cache), hoặc None nếu chỉ có monogram."""
    t = normalize_ticker(ticker)
    if not _valid_ticker(t):
        return None
    manual = _manual_path(t)
    if manual:
        return manual
    png, meta = get_logo(t, website, domain)
    if meta.get("source") != "monogram":
        p = CACHE_DIR / f"{t}.png"
        if p.exists():
            return p
    return None


def logo_bytes(ticker: str, website: Optional[str] = None, domain: Optional[str] = None) -> bytes:
    """Luôn trả về bytes ảnh (logo thật hoặc monogram) - dùng cho PDF."""
    try:
        png, _info = get_logo(ticker, website, domain)
        return png or monogram_png(normalize_ticker(ticker) or "?")
    except Exception:
        return monogram_png(normalize_ticker(ticker) or "?")


def logo_data_uri(ticker: str, website: Optional[str] = None, domain: Optional[str] = None) -> str:
    """Luôn trả về data URI (logo thật hoặc monogram SVG) - dùng cho dashboard."""
    t = normalize_ticker(ticker)
    try:
        png, info = get_logo(t, website, domain)
        if info.get("source") != "monogram" and png:
            return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    except Exception:
        pass
    color = monogram_color(t)
    text = (t or "?")[:4]
    fs = 40 if len(text) <= 2 else 30 if len(text) == 3 else 24
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
           f"<rect width='96' height='96' rx='20' fill='{color}'/>"
           f"<text x='48' y='48' text-anchor='middle' dominant-baseline='central' "
           f"font-family='Arial,Helvetica,sans-serif' font-weight='700' font-size='{fs}' fill='white'>{text}</text></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")


# ----------------------------------------------------------------------------- monogram
def monogram_color(ticker: str) -> str:
    t = normalize_ticker(ticker) or "?"
    h = int(hashlib.md5(t.encode()).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]


def monogram_png(ticker: str, size: int = 256) -> bytes:
    """Ảnh PNG monogram dùng cho PDF."""
    from PIL import Image, ImageDraw, ImageFont
    t = normalize_ticker(ticker) or "?"
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=monogram_color(t))
    text = t[:4]
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
