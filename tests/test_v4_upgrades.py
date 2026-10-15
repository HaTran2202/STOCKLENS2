"""Regression tests for the equity-research upgrade layer.

Covers: peer scenario math (deterministic, no probabilities), data-quality
gating of peer fair value/scenarios, news intelligence enrichment, warning
translation, and technical language that must not promise an oversold rebound.
"""
import math
import pytest

from src.csv_peer import _percentile, _peer_scenarios
from src.news_analysis import enrich_news_items, news_intelligence_summary, _news_category


# --------------------------------------------------------------------- scenarios
def test_percentile_edges_and_interpolation():
    assert _percentile([], 0.5) is None
    assert _percentile([0, -1], 0.5) is None  # non-positive ignored
    assert _percentile([5], 0.5) == 5
    assert _percentile([10, 20, 30, 40], 0.5) == pytest.approx(25)
    assert _percentile([10, 20, 30, 40], 0.25) == pytest.approx(17.5)
    assert _percentile([10, 20, 30, 40], 0.75) == pytest.approx(32.5)


def test_peer_scenarios_are_deterministic_and_probability_free():
    peers = [{"symbol": "A", "pe": 10, "pb": 1}, {"symbol": "B", "pe": 20, "pb": 2},
             {"symbol": "C", "pe": 30, "pb": 3}, {"symbol": "D", "pe": 40, "pb": 4}]
    s = _peer_scenarios(peers, eps=1000, bvps=5000, price=15000)
    assert s["available"] is True
    assert s["no_probability"] is True
    assert "xác suất" in s["assumption"]
    # base = mean(1000*25, 5000*2.5) = mean(25000, 12500)
    assert s["base"]["price"] == pytest.approx(18750)
    assert s["bear"]["price"] < s["base"]["price"] < s["bull"]["price"]
    assert s["bear"]["pe_multiple"] == pytest.approx(17.5)
    assert s["bull"]["pb_multiple"] == pytest.approx(3.25)
    # No probability-weight field anywhere. `no_probability` is the only key that
    # even mentions probability, and it is the flag asserting its absence.
    assert "no_probability" in s
    assert not any(key.startswith("prob") for key in s if key != "no_probability")
    assert not any("prob" in key for band in (s["bear"], s["base"], s["bull"]) for key in band)


def test_peer_scenarios_need_usable_inputs():
    no_multiple = _peer_scenarios([{"pe": None, "pb": None}], 1000, 5000, 15000)
    assert no_multiple["available"] is False and no_multiple["reason"]
    # Only BVPS available (loss-making) still allows a P/B-based band.
    pb_only = _peer_scenarios([{"pe": 10, "pb": 2}], eps=-5, bvps=5000, price=15000)
    assert pb_only["available"] is True
    assert pb_only["base"]["price"] == pytest.approx(10000)


# --------------------------------------------------------------------- data gating
def test_peer_fair_value_and_scenarios_blocked_without_provenance():
    from src.csv_data import get_csv_financial_data, reconcile_market_snapshot
    from src.csv_peer import analyze_csv_peers
    # MBB ratios are fallback-derived -> both fair value and scenarios must be off.
    bank = analyze_csv_peers("MBB", 25000, reconcile_market_snapshot(get_csv_financial_data("MBB"), 25000))
    assert bank["peer_fair_value"] is None
    assert bank["scenarios"]["available"] is False
    assert bank["scenarios"]["reason"]
    assert any("suy diễn" in w or "chất lượng" in w for w in bank["peer_quality_warnings"])


# --------------------------------------------------------------------- news intelligence
def test_news_dedup_category_and_opinion_split():
    items = [
        {"title": "FPT báo lãi ròng tăng 19% quý 3", "published": "2026-10-15", "source_name": "A", "sentiment": "Positive"},
        {"title": "FPT báo lãi ròng tăng 19% quý 3", "published": "2026-10-14", "source_name": "B", "sentiment": "Positive"},
        {"title": "Cổ phiếu FPT giảm 3 phiên liên tiếp", "published": "2026-10-13", "source_name": "C", "sentiment": "Negative"},
        {"title": "Định giá FPT đã đủ hấp dẫn?", "published": "2026-10-13", "source_name": "D", "sentiment": "Neutral"},
    ]
    enriched = enrich_news_items(items)
    assert len(enriched) == 3  # duplicate titles merged
    merged = [i for i in enriched if i["duplicate_count"] > 1]
    assert len(merged) == 1 and set(merged[0]["merged_sources"]) == {"A", "B"}
    price_only = [i for i in enriched if i["is_price_only"]]
    assert price_only and price_only[0]["category"] == "Giá & dòng tiền"
    opinion = [i for i in enriched if i["is_opinion"]]
    assert opinion and opinion[0]["evidence_type"] == "Ý kiến/nhận định"
    summary = news_intelligence_summary(enriched)
    assert summary["duplicates_merged"] == 1
    assert summary["opinion"] >= 1


def test_news_category_never_invents_unknown():
    assert _news_category("Tiêu đề không dấu hiệu gì đặc biệt") == "Khác"


# --------------------------------------------------------------------- warning translation
def test_warning_translation_keeps_vietnamese_and_maps_english():
    from src.report import _vi_warning
    vi = "P/E/P/B snapshot đã khớp giá hàm ý; snapshot không có ngày công bố."
    assert _vi_warning(vi) == vi  # already Vietnamese -> untouched
    en = "Current Stock Metrics snapshot has no period_date; use snapshot multiples only when..."
    out = _vi_warning(en)
    assert "ngày" in out and "period_date" not in out


# --------------------------------------------------------------------- technical language
def test_oversold_wording_does_not_promise_rebound():
    import pandas as pd
    import tempfile
    from src.technical_analysis import analyze_technical
    n = 120
    # Sustained decline -> deeply oversold RSI.
    close = [100000 * (0.994 ** i) for i in range(n)]
    frame = pd.DataFrame({"Date": pd.bdate_range("2026-01-01", periods=n), "Open": close,
                          "High": [c * 1.004 for c in close], "Low": [c * 0.996 for c in close],
                          "Close": close, "Volume": [400000] * n})
    with tempfile.TemporaryDirectory() as d:
        t = analyze_technical(frame, chart_dir=d)
    assert t["data_available"]
    text = (t.get("action_scenario") or "") + (t.get("commentary") or "") + str(t.get("rsi_state"))
    assert "nhịp hồi kỹ thuật" not in text
    if t["rsi"] < 30:
        assert "không đồng nghĩa" in text


# --------------------------------------------------------------------- PDF structure
def test_pdf_includes_exec_summary_and_method_definitions():
    pytest.importorskip("reportlab")
    from src.csv_data import csv_ready, get_csv_financial_data, reconcile_market_snapshot
    from src.fundamental_analysis import analyze_fundamental
    from src.valuation import analyze_valuation
    from src.scoring import score_all
    from src.report import generate_pdf
    import pandas as pd
    if not csv_ready():
        pytest.skip("Five annual CSV exports are required")
    info = reconcile_market_snapshot(get_csv_financial_data("FPT"), 57900)
    prices = [78000 - i * 120 for i in range(120)]
    frame = pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=120, freq="B"),
                          "Close": prices, "MA20": prices, "MA50": prices, "Volume": [500000] * 120})
    results = {"technical": {"data_available": True, "data": frame, "close": 57900, "ma20": 63000,
                             "ma50": 64000, "rsi": 25, "volume_ratio": 1.2, "macd": -500, "score": 20,
                             "signals": {"MA": {"signal": "Negative", "score": 0}},
                             "commentary": "Kiểm thử."},
               "fundamental": analyze_fundamental(info),
               "valuation": analyze_valuation(info, "FPT", 57900),
               "news": {"score": 50, "data_available": True, "classification": "Trung tính", "items": [],
                        "intelligence": {}, "commentary": "Chưa đủ tin tức."},
               "risk": {"score": 50, "data_available": True,
                        "metrics": {"volatility_20_annualized": 0.22, "max_drawdown_period": -0.4},
                        "component_scores": {"volatility": 60, "max_drawdown": 70}}}
    summary = score_all(results)
    company = {"name": "FPT", "exchange": "HOSE", "sector": "Công nghệ thông tin",
               "report_period": "2025", "last_date": "2026-10-09"}
    pdf = generate_pdf("FPT", "2024-01-01 → 2026-10-09", results, summary,
                       ["technical", "fundamental", "valuation", "news", "score", "method"],
                       "Cân bằng", company, info)
    assert pdf.startswith(b"%PDF")
    fitz = pytest.importorskip("fitz")
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    assert "Tóm tắt điều hành" in text
    assert "Định nghĩa chỉ tiêu quan trọng" in text
    assert "Xử lý thiếu dữ liệu & xung đột nguồn" in text
    assert "Risk/An toàn đo lường gì" in text
    # Exec summary must precede the business overview section.
    assert text.find("Tóm tắt điều hành") < text.find("Tổng quan doanh nghiệp")
    assert "Vốn lưu động & thanh khoản ngắn hạn" in text


# --------------------------------------------------------------------- working capital
def test_working_capital_is_grounded_in_raw_balance_sheet():
    from src.report import _working_capital
    from src.csv_data import csv_ready, get_csv_financial_data
    if not csv_ready():
        pytest.skip("Five annual CSV exports are required")
    fd = get_csv_financial_data("FPT")
    wc = _working_capital(fd)
    assert wc["available"] is True
    latest = wc["latest"]
    # Independently verify NWC / current ratio against the raw source row.
    bs = fd["_raw"]["balance_sheet"]
    row_ca = float(bs[bs["item_id"] == "current_assets"].iloc[0][latest["year"]])
    row_cl = float(bs[bs["item_id"] == "current_liabilities"].iloc[0][latest["year"]])
    assert latest["nwc"] == pytest.approx(row_ca - row_cl)
    assert latest["current_ratio"] == pytest.approx(row_ca / row_cl)
    assert wc["nwc_change"] is not None


def test_working_capital_absent_without_raw_data():
    from src.report import _working_capital
    assert _working_capital({}) == {"available": False}
    assert _working_capital({"_raw": {}}) == {"available": False}


# --------------------------------------------------------------------- confirmation / invalidation
def test_technical_states_confirmation_and_invalidation_levels():
    import pandas as pd
    import tempfile
    from src.technical_analysis import analyze_technical
    up = [70000 + i * 1000 for i in range(60)]
    down = [129000 - i * 1000 for i in range(1, 51)]
    rebound = [79000 + i * 1000 for i in range(1, 11)]
    close = up + down + rebound
    frame = pd.DataFrame({"Date": pd.bdate_range("2026-01-01", periods=len(close)), "Open": close,
                          "High": [c * 1.006 for c in close], "Low": [c * 0.994 for c in close],
                          "Close": close, "Volume": [400000] * len(close)})
    with tempfile.TemporaryDirectory() as d:
        t = analyze_technical(frame, chart_dir=d)
    assert t["data_available"]
    assert t["support_level"] is not None and t["resistance_level"] is not None
    text = t["action_scenario"]
    assert "XÁC NHẬN" in text and "VÔ HIỆU" in text
    assert f"{t['resistance_level']:,.0f}" in text
    assert f"{t['support_level']:,.0f}" in text
