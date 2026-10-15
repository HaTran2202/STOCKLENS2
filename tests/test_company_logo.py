"""Kiểm thử pipeline logo doanh nghiệp theo ticker (src/branding.py).

Không gọi mạng thật: mọi truy cập HTTP được thay bằng hàm giả qua monkeypatch.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

import src.branding as branding


def _png(w=128, h=128, bg=(255, 255, 255, 255), fg=(20, 90, 200, 255)):
    """Tạo PNG nhiều chi tiết (giống logo/wordmark) để vượt qua kiểm tra ảnh trắng/banner."""
    im = Image.new("RGBA", (w, h), bg)
    d = ImageDraw.Draw(im)
    step = max(6, w // 14)
    for i in range(2, max(3, w - 2), step):
        d.rectangle((i, h // 4, min(i + max(2, step // 3), w - 2), h * 3 // 4), fill=fg)
    d.rectangle((2, h // 2 - 3, max(3, w - 3), h // 2 + 3), fill=(230, 120, 20, 255))
    d.ellipse((w // 2 - 10, h // 2 - 10, w // 2 + 10, h // 2 + 10), fill=(15, 150, 120, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _solid(w, h, color):
    im = Image.new("RGBA", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _gradient(w=256, h=256):
    """Ảnh nền gradient mượt (giống banner thương hiệu) -> không phải logo."""
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (200 + x * 40 // w, 215 + y * 35 // h, 235)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """Cô lập cache/logos vào thư mục tạm và xoá cấu hình môi trường."""
    cache = tmp_path / "cache"
    monkeypatch.setattr(branding, "CACHE_DIR", cache)
    monkeypatch.setattr(branding, "DOMAIN_LEARNED_FILE", cache / "_domains.json")
    monkeypatch.setattr(branding, "LOGO_DIRS", [tmp_path / "logos"])
    for var in ("LOGODEV_TOKEN", "LOGO_DEV_TOKEN", "LOGO_DEV_KEY", "STOCKLENS_LOGO_OFFLINE"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


# --------------------------------------------------------------------------- chuẩn hoá + ánh xạ
def test_normalize_ticker():
    assert branding.normalize_ticker(" fpt ") == "FPT"
    assert branding.normalize_ticker("FPT.VN") == "FPT"
    assert branding.normalize_ticker("hpg-hose") == "HPG"
    assert branding.normalize_ticker("") == ""
    assert branding.normalize_ticker(None) == ""


def test_resolve_domain_offline_from_seed_and_website():
    assert branding.resolve_domain("FPT", allow_network=False) == "fpt.com"
    assert branding.resolve_domain("MWG", allow_network=False) == "mwg.vn"
    assert branding.resolve_domain("ZZZZ", allow_network=False) is None
    assert branding.resolve_domain("XXX", website="https://www.example.com/trang-chu",
                                   allow_network=False) == "example.com"
    assert branding.resolve_domain("YYY", domain="https://acme.vn/x", allow_network=False) == "acme.vn"


def test_resolve_domain_learns_and_caches_online(isolated, monkeypatch):
    monkeypatch.setattr(branding, "_lookup_domain_online", lambda t: "acme.com")
    assert branding.resolve_domain("ZZZZ", allow_network=True) == "acme.com"
    # Đã học vào file cache dùng lại được khi offline
    assert branding._load_json_map(branding.DOMAIN_LEARNED_FILE).get("ZZZZ") == "acme.com"
    assert branding.resolve_domain("ZZZZ", allow_network=False) == "acme.com"


# --------------------------------------------------------------------------- kiểm tra ảnh
def test_normalize_image_rejects_invalid_and_tiny():
    assert branding.normalize_image(b"day khong phai anh") is None
    assert branding.normalize_image(b"x" * 5000) is None
    assert branding.normalize_image(_solid(1, 1, (0, 0, 0, 255))) is None      # 1x1
    info = branding.normalize_image(_png(128, 128))
    assert info and info["width"] == 128 and info["height"] == 128
    assert info["png"].startswith(b"\x89PNG")


def test_quality_and_blank_filters():
    assert not branding._passes_quality(branding.normalize_image(_png(32, 32)))     # quá nhỏ
    assert branding._passes_quality(branding.normalize_image(_png(128, 128)))
    white = branding.normalize_image(_solid(128, 128, (255, 255, 255, 255)))
    assert branding._is_blank(white) is True                                        # ảnh trắng -> loại
    assert branding._is_blank(branding.normalize_image(_png(128, 128))) is False


# --------------------------------------------------------------------------- cache
def test_cache_roundtrip_and_metadata(isolated):
    info = branding.normalize_image(_png(180, 180))
    p = branding._write_cache("FPT", info, {"source": "hunter", "url": "https://logos.hunter.io/fpt.com"})
    assert p and p.exists()
    meta = branding._cache_paths("FPT")[1]
    assert meta.exists()
    got, ginfo = branding.get_logo("FPT", allow_network=False)
    assert got == info["png"]
    assert ginfo["source"] == "hunter"
    assert ginfo["width"] == 180


def test_get_logo_offline_unknown_ticker_returns_monogram(isolated):
    png, info = branding.get_logo("ZZZZ", allow_network=False)
    assert info["source"] == "monogram"
    assert png.startswith(b"\x89PNG")


def test_get_logo_invalid_ticker_is_safe(isolated):
    for bad in ("../../etc/passwd", "FPT/../..", "", "!!!", "TOOLONGTICKER123"):
        png, info = branding.get_logo(bad, allow_network=False)
        assert info["source"] == "monogram"
        assert png.startswith(b"\x89PNG")
    # Không tạo file ngoài thư mục cache
    outside = list((isolated).glob("**/*.png"))
    assert all(branding.CACHE_DIR in p.parents or p.parent == branding.CACHE_DIR for p in outside)


# --------------------------------------------------------------------------- nguồn trực tuyến
def test_provider_hunter_fetch_and_cache(isolated, monkeypatch):
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        if "logos.hunter.io" in url:
            return 200, _png(160, 160), "image/png"
        return 0, b"", ""

    monkeypatch.setattr(branding, "_http_get", fake_get)
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"] == "hunter"
    assert info["domain"] == "fpt.com"
    assert (branding.CACHE_DIR / "FPT.png").exists()
    # Lần sau offline vẫn dùng được cache đã xác minh
    png2, info2 = branding.get_logo("FPT", allow_network=False)
    assert info2["source"] == "hunter" and png2 == png


def test_provider_network_error_falls_back_to_monogram(isolated, monkeypatch):
    monkeypatch.setattr(branding, "_http_get", lambda url, timeout=None: (0, b"", ""))
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"] == "monogram"
    assert png.startswith(b"\x89PNG")


def test_invalid_image_from_provider_is_rejected(isolated, monkeypatch):
    # CDN trả 200 nhưng nội dung không phải ảnh -> phải bị loại, rơi về monogram
    monkeypatch.setattr(branding, "_http_get",
                        lambda url, timeout=None: (200, b"<html>not an image</html>", "text/html"))
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"] == "monogram"


def test_blank_logo_is_rejected(isolated, monkeypatch):
    monkeypatch.setattr(branding, "_http_get",
                        lambda url, timeout=None: (200, _solid(256, 256, (255, 255, 255, 255)), "image/png"))
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"] == "monogram"


def test_low_detail_banner_filter():
    assert branding._is_low_detail(branding.normalize_image(_gradient(256, 256))) is True
    assert branding._is_low_detail(branding.normalize_image(_png(128, 128))) is False


def test_banner_like_provider_image_is_rejected(isolated, monkeypatch):
    # CDN trả ảnh nền gradient mượt thay vì logo -> loại, rơi về monogram
    monkeypatch.setattr(branding, "_http_get",
                        lambda url, timeout=None: (200, _gradient(256, 256), "image/png"))
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"] == "monogram"


def test_logodev_preferred_when_token_present(isolated, monkeypatch):
    monkeypatch.setenv("LOGODEV_TOKEN", "pk_test_token")

    def fake_get(url, timeout=None):
        if "img.logo.dev" in url:
            return 200, _png(256, 256), "image/png"
        if "logos.hunter.io" in url:
            return 200, _png(128, 128), "image/png"
        return 0, b"", ""

    monkeypatch.setattr(branding, "_http_get", fake_get)
    png, info = branding.get_logo("HPG", allow_network=True, refresh=True)
    assert info["source"] == "logo.dev"
    assert "img.logo.dev" in info["url"]


def test_site_icon_fallback(isolated, monkeypatch):
    html = b'<html><head><link rel="apple-touch-icon" href="/icon.png"></head><body>x</body></html>'

    def fake_get(url, timeout=None):
        if "logos.hunter.io" in url:
            return 404, b"not found", "text/plain"
        if url.rstrip("/") == "https://fpt.com":
            return 200, html, "text/html"
        if url == "https://fpt.com/icon.png":
            return 200, _png(180, 180), "image/png"
        return 0, b"", ""

    monkeypatch.setattr(branding, "_http_get", fake_get)
    png, info = branding.get_logo("FPT", allow_network=True, refresh=True)
    assert info["source"].startswith("site:")


def test_existing_higher_resolution_cache_not_overwritten(isolated, monkeypatch):
    branding._write_cache("FPT", branding.normalize_image(_png(256, 256)), {"source": "hunter"})
    # Làm cho cache cũ (không còn "tươi") để buộc thử tải lại
    meta_p = branding._cache_paths("FPT")[1]
    meta_p.write_text('{"source":"hunter","fetched_at":"2000-01-01T00:00:00+00:00"}', encoding="utf-8")

    monkeypatch.setattr(branding, "_http_get",
                        lambda url, timeout=None: (200, _png(128, 128), "image/png") if "hunter" in url else (0, b"", ""))
    png, info = branding.get_logo("FPT", allow_network=True, refresh=False)
    im = Image.open(io.BytesIO(png))
    assert im.size == (256, 256)          # giữ bản phân giải cao hơn
    assert info["source"] == "hunter"


def test_logo_bytes_never_raises_offline(isolated, monkeypatch):
    monkeypatch.setenv("STOCKLENS_LOGO_OFFLINE", "1")
    out = branding.logo_bytes("ZZZZ")
    assert out.startswith(b"\x89PNG")
    uri = branding.logo_data_uri("ZZZZ")
    assert uri.startswith("data:image/")
