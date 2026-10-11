"""StockLens - Luận điểm đầu tư, rủi ro cần lưu ý và quan điểm theo mô hình.

Tất cả nội dung được sinh từ chính kết quả phân tích của từng mã (tài chính, định giá, kỹ thuật,
tin tức) và được cá nhân hóa theo hồ sơ nhà đầu tư. Không bịa dữ kiện: chỉ nêu điều có số liệu/tin đi kèm.

Muốn bổ sung nhận định riêng cho một mã (dự án trọng điểm, quỹ đất, chu kỳ ngành...), tạo file
data/thesis_notes.json:
    {"DXG": {"thesis": ["đoạn văn 1", "đoạn văn 2"], "risks": ["đoạn văn rủi ro"]}}
Các đoạn này sẽ được chèn vào đầu mục tương ứng trong dashboard và PDF.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "thesis_notes.json"


# ----------------------------------------------------------------------------- tiện ích
def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _ratio(x):
    """Chuẩn hóa tỷ lệ về dạng số thập phân (0.27) dù nguồn trả 27.2 hay 0.272."""
    v = _f(x)
    if v is None:
        return None
    return v / 100 if abs(v) > 1.5 else v


def _pct(x, d=1, sign=False):
    v = _f(x)
    if v is None:
        return "N/A"
    return f"{v * 100:+.{d}f}%" if sign else f"{v * 100:.{d}f}%"


def _money(x):
    v = _f(x)
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"{v / 1e12:,.1f} nghìn tỷ đồng"
    if abs(v) >= 1e9:
        return f"{v / 1e9:,.0f} tỷ đồng"
    return f"{v:,.0f} đồng"


def _x(v, d=2):
    v = _f(v)
    return "N/A" if v is None else f"{v:,.{d}f}x"


def _history(financial_data):
    rows = []
    for r in (financial_data or {}).get("financialHistory", []) or []:
        if isinstance(r, dict) and r.get("period") is not None:
            rows.append(r)
    try:
        rows.sort(key=lambda r: str(r.get("period")))
    except Exception:
        pass
    rows = [dict(r) for r in rows]
    for k in ("roe", "roa"):  # chuẩn hóa theo cả cột
        vals = [abs(_f(r.get(k))) for r in rows if _f(r.get(k)) is not None]
        if vals and max(vals) > 1.5:
            for r in rows:
                if _f(r.get(k)) is not None:
                    r[k] = _f(r[k]) / 100
    return rows


def _growth(cur, prev):
    cur, prev = _f(cur), _f(prev)
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1


def _cagr(first, last, years):
    first, last = _f(first), _f(last)
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def _news(results, sentiment, limit=2):
    items = [i for i in ((results.get("news") or {}).get("items") or [])
             if isinstance(i, dict) and i.get("title") and (sentiment is None or i.get("sentiment") == sentiment)]

    def key(i):
        p = pd.to_datetime(i.get("published"), errors="coerce", utc=True)
        return 0 if pd.isna(p) else int(p.value)
    items.sort(key=key, reverse=True)
    out = []
    for i in items[:limit]:
        title = str(i["title"])
        src = str(i.get("source_name") or "")
        suffix = f" - {src}" if src and not title.endswith(src) else ""
        date = str(i.get("published") or "")[:10]
        out.append({"title": title + suffix, "date": date})
    return out


def _clean_title(t):
    return t.rsplit(" - ", 1)[0] if " - " in t else t


# ----------------------------------------------------------------------------- quan điểm / khuyến nghị
def recommendation(summary, results, profile, close=None):
    summary = summary or {}
    score = _f((summary.get("profile_scores") or {}).get(profile))
    if score is None:
        score = _f(summary.get("score"))
    if score is None:
        stance, tone = "Chưa đủ dữ liệu", "neutral"
    elif score >= 80:
        stance, tone = "Cơ hội cao", "positive"
    elif score >= 65:
        stance, tone = "Tích cực", "positive"
    elif score >= 50:
        stance, tone = "Trung lập", "neutral"
    else:
        stance, tone = "Thận trọng", "caution"

    comp = summary.get("component_scores") or {}
    fund, val, tech, news = (_f(comp.get(k)) for k in ("fundamental", "valuation", "technical", "news"))
    hint = "Chưa đủ dữ liệu để đưa ra hướng theo dõi."
    if score is not None:
        strong_base = (fund or 0) >= 70 and (val or 0) >= 60
        weak_timing = tech is not None and tech < 40
        if strong_base and weak_timing:
            hint = "Nền tảng và định giá hấp dẫn nhưng xu hướng giá chưa xác nhận: phù hợp đưa vào danh sách theo dõi, chờ tín hiệu kỹ thuật cải thiện."
        elif strong_base:
            hint = "Nền tảng, định giá và xu hướng giá khá đồng thuận: có thể xem xét theo hồ sơ rủi ro của bạn."
        elif score >= 65:
            hint = "Điểm tổng hợp tích cực nhưng không đồng đều giữa các nhóm: nên xem kỹ nhóm điểm thấp trước khi quyết định."
        elif score >= 50:
            hint = "Tín hiệu trái chiều: nên theo dõi thêm diễn biến kết quả kinh doanh, giá và tin tức."
        else:
            hint = "Nhiều tín hiệu chưa thuận lợi: ưu tiên quản trị rủi ro và chờ cải thiện trước khi cân nhắc."

    valuation = (results or {}).get("valuation") or {}
    peer = valuation.get("peer_valuation") or {}
    ref = _f(valuation.get("peer_fair_value"))
    if ref is None:
        ref = _f(peer.get("peer_fair_value", peer.get("fair_value")))
    price = _f(close) or _f(((results or {}).get("technical") or {}).get("close"))
    upside = None
    if ref and price:
        upside = ref / price - 1
    return {"stance": stance, "tone": tone, "score": score, "price": price, "ref_value": ref,
            "upside": upside, "hint": hint, "profile": profile}


# ----------------------------------------------------------------------------- khối luận điểm
def _p_business(ticker, company, fd, hist, profile):
    if not hist:
        return None
    last, prev = hist[-1], (hist[-2] if len(hist) >= 2 else {})
    bank = str(fd.get("financialBusinessType") or "").lower() == "bank"
    rev_label = "thu nhập hoạt động" if bank else "doanh thu thuần"
    per = last.get("period")
    gr, gp = _growth(last.get("revenue"), prev.get("revenue")), _growth(last.get("net_profit"), prev.get("net_profit"))
    roe, roa = _ratio(last.get("roe")), _ratio(last.get("roa"))
    name = company.get("name") or ticker
    parts = [f"Trong năm {per}, {name} ghi nhận {rev_label} {_money(last.get('revenue'))}"]
    if gr is not None:
        parts[0] += f" ({_pct(gr, 1, True)} so với năm trước)"
    parts[0] += f" và lợi nhuận sau thuế {_money(last.get('net_profit'))}"
    if gp is not None:
        parts[0] += f" ({_pct(gp, 1, True)})"
    parts[0] += "."
    if len(hist) >= 3:
        n = len(hist) - 1
        cr, cp = _cagr(hist[0].get("revenue"), last.get("revenue"), n), _cagr(hist[0].get("net_profit"), last.get("net_profit"), n)
        if cr is not None and cp is not None:
            parts.append(f"Từ {hist[0].get('period')} đến {per}, {rev_label} tăng trưởng kép {_pct(cr)} mỗi năm và lợi nhuận tăng trưởng kép {_pct(cp)} mỗi năm.")
    if roe is not None:
        s = f"ROE đạt {_pct(roe)}"
        if roa is not None:
            s += f" và ROA đạt {_pct(roa)}"
        parts.append(s + (", thuộc nhóm sinh lời cao." if roe >= 0.15 else ", ở mức trung bình." if roe >= 0.08 else ", ở mức thấp."))
    de = _f(fd.get("debtToEquity"))
    if not bank and de is not None:
        tail = {"Thận trọng": " Với nhà đầu tư thận trọng, đây là điểm cần đối chiếu với ngưỡng an toàn của ngành.",
                "Tăng trưởng": " Đòn bẩy này cho thấy dư địa tài trợ cho kế hoạch mở rộng."}.get(profile, "")
        parts.append(f"Nợ phải trả/vốn chủ sở hữu ở mức {_x(de)}." + (tail if de else ""))
    return " ".join(parts)


def _p_valuation(ticker, results, hist, profile):
    v = (results.get("valuation") or {})
    pe, pb = _f(v.get("pe")), _f(v.get("pb"))
    mpe, mpb = _f(v.get("historical_pe_median")), _f(v.get("historical_pb_median"))
    if pe is None and pb is None:
        return None
    parts = []
    if pe is not None and mpe:
        d = pe / mpe - 1
        parts.append(f"P/E hiện tại {_x(pe)} {'thấp hơn' if d < 0 else 'cao hơn'} trung vị lịch sử {_x(mpe)} khoảng {abs(d) * 100:.1f}%.")
    elif pe is not None:
        parts.append(f"P/E hiện tại là {_x(pe)}.")
    if pb is not None and mpb:
        d = pb / mpb - 1
        parts.append(f"P/B {_x(pb)} {'thấp hơn' if d < 0 else 'cao hơn'} trung vị lịch sử {_x(mpb)} khoảng {abs(d) * 100:.1f}%.")
    ref = _f(v.get("peer_fair_value"))
    up = _f(v.get("peer_upside_downside"))
    if up is not None and abs(up) > 3:
        up /= 100
    if ref and up is not None:
        parts.append(f"So với nhóm cùng ngành, giá trị hàm ý theo P/E, P/B của peers là {ref:,.0f} đồng ({_pct(up, 1, True)} so với giá hiện tại); đây là mức tham chiếu tương đối, không phải giá mục tiêu.")
    if profile == "Tăng trưởng" and pe and len(hist) >= 2:
        g = _growth(hist[-1].get("net_profit"), hist[-2].get("net_profit"))
        if g and g > 0.05:
            parts.append(f"Với lợi nhuận tăng {_pct(g)}, P/E trên tốc độ tăng trưởng (PEG) khoảng {pe / (g * 100):.2f}.")
    if profile == "Thận trọng" and pb:
        parts.append("Với phong cách thận trọng, nên so sánh mức P/B này với giá trị sổ sách và chất lượng tài sản để đánh giá biên an toàn.")
    return " ".join(parts)


def _p_catalysts(results):
    pos = _news(results, "Positive", 2)
    # Tiêu đề hỗn hợp không được dùng làm luận cứ tích cực.
    from .news_analysis import _classify_sentiment
    pos = [p for p in pos if _classify_sentiment(p['title']).get('reason') == 'positive_keywords']
    if pos:
        lines = "; ".join(f"“{_clean_title(p['title'])}” ({p['date']})" for p in pos)
        return f"Về thông tin gần đây, các tin tích cực nổi bật gồm {lines}. Đây là các yếu tố có thể hỗ trợ tâm lý thị trường nếu được xác nhận bằng kết quả kinh doanh."
    latest = _news(results, None, 1)
    if latest:
        return f"Tin mới nhất về doanh nghiệp: “{_clean_title(latest[0]['title'])}” ({latest[0]['date']}); chưa ghi nhận tin tích cực nổi bật trong tập tin đang phân tích."
    return None


def _p_technical(results):
    t = results.get("technical") or {}
    close, ma20, ma50, rsi = (_f(t.get(k)) for k in ("close", "ma20", "ma50", "rsi"))
    if close is None or ma20 is None or ma50 is None:
        return None
    if close > ma20 > ma50:
        trend = "Giá đang nằm trên MA20 và MA50, xu hướng ngắn - trung hạn thuận lợi."
    elif close < ma20 < ma50:
        trend = "Giá đang dưới MA20 và MA50, xu hướng ngắn - trung hạn còn yếu."
    else:
        trend = "Giá dao động quanh các đường trung bình động, xu hướng chưa rõ ràng."
    extra = ""
    if rsi is not None:
        extra = (f" RSI(14) ở {rsi:.1f}, thuộc vùng quá bán nên có thể xuất hiện nhịp hồi kỹ thuật." if rsi < 30
                 else f" RSI(14) ở {rsi:.1f}, thuộc vùng quá mua." if rsi > 70 else f" RSI(14) ở {rsi:.1f}, chưa ở vùng cực trị.")
    return trend + extra


# ----------------------------------------------------------------------------- khối rủi ro
def _drawdown(t):
    d = t.get("data")
    try:
        if isinstance(d, pd.DataFrame) and "Close" in d and len(d) > 20:
            c = pd.to_numeric(d["Close"], errors="coerce").dropna()
            return float((c / c.cummax() - 1).min())
    except Exception:
        pass
    return None


def _r_market(results):
    t = results.get("technical") or {}
    parts = []
    dd, vol = _drawdown(t), _f(t.get("volatility"))
    if dd is not None and dd < -0.15:
        parts.append(f"Giá đã giảm sâu nhất {abs(dd) * 100:.1f}% từ đỉnh trong kỳ phân tích")
    if vol is not None:
        v = vol / 100 if vol > 1.5 else vol
        parts.append(f"biến động 20 phiên quy năm khoảng {v * 100:.1f}%")
    if not parts:
        return None
    s = ", ".join(parts)[0].upper() + ", ".join(parts)[1:] + "; mức dao động này đòi hỏi kiểm soát quy mô vị thế và kỷ luật cắt lỗ."
    close, ma20, ma50 = (_f(t.get(k)) for k in ("close", "ma20", "ma50"))
    if close and ma20 and ma50 and close < ma20 < ma50:
        s += " Xu hướng kỹ thuật hiện chưa xác nhận đảo chiều."
    return s


def _r_news(results):
    neg = _news(results, "Negative", 2)
    if not neg:
        return None
    lines = "; ".join(f"“{_clean_title(n['title'])}” ({n['date']})" for n in neg)
    return f"Dòng tin gần đây có các yếu tố tiêu cực cần theo dõi: {lines}. Nếu các thông tin này kéo dài hoặc được xác nhận, tâm lý và dòng tiền có thể tiếp tục chịu áp lực."


def _r_valuation_fin(results, fd, hist):
    parts = []
    v = results.get("valuation") or {}
    pe, mpe_peer = _f(v.get("pe")), _f(v.get("peer_median_pe"))
    pb, mpb_peer = _f(v.get("pb")), _f(v.get("peer_median_pb"))
    if pe and mpe_peer and pe > mpe_peer * 1.2:
        parts.append(f"P/E {_x(pe)} cao hơn trung vị nhóm cùng ngành ({_x(mpe_peer)})")
    if pb and mpb_peer and pb > mpb_peer * 1.5:
        parts.append(f"P/B {_x(pb)} cao hơn trung vị nhóm cùng ngành ({_x(mpb_peer)})")
    out = ""
    if parts:
        out = "Định giá tương đối còn cao hơn nhóm cùng ngành: " + "; ".join(parts) + "."
    warns = v.get("peer_quality_warnings") or []
    if warns:
        out += " Bộ so sánh cùng ngành có hạn chế về chất lượng dữ liệu nên kết quả peers cần được đọc thận trọng."
    bank = str(fd.get("financialBusinessType") or "").lower() == "bank"
    de = _f(fd.get("debtToEquity"))
    if not bank and de is not None and de > 1.5:
        out += f" Đòn bẩy cao (nợ vay/vốn chủ sở hữu {_x(de)}) làm tăng độ nhạy với lãi suất."
    if len(hist) >= 2:
        g = _growth(hist[-1].get("net_profit"), hist[-2].get("net_profit"))
        if g is not None and g < 0:
            out += f" Lợi nhuận năm gần nhất giảm {abs(g) * 100:.1f}%."
    return out.strip() or None


def _r_model(summary):
    miss = (summary or {}).get("missing") or []
    base = "Investment Score là mô hình heuristic phục vụ học tập, chưa được backtest; dữ liệu bên thứ ba có thể chậm hoặc thiếu."
    if miss:
        base += " Hiện thiếu dữ liệu ở nhóm: " + ", ".join(map(str, miss)) + "."
    return base


# ----------------------------------------------------------------------------- hàm chính
def build_thesis(ticker, company, results, summary, financial_data, profile="Cân bằng", close=None):
    company, results, financial_data = company or {}, results or {}, financial_data or {}
    hist = _history(financial_data)

    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception:
            return None

    order = {
        "Thận trọng": [("fin", 0), ("val", 1), ("tech", 2), ("cat", 3)],
        "Cân bằng": [("fin", 0), ("val", 1), ("cat", 2), ("tech", 3)],
        "Tăng trưởng": [("fin", 0), ("cat", 1), ("val", 2), ("tech", 3)],
    }.get(profile, [("fin", 0), ("val", 1), ("cat", 2), ("tech", 3)])
    blocks = {
        "fin": safe(_p_business, ticker, company, financial_data, hist, profile),
        "val": safe(_p_valuation, ticker, results, hist, profile),
        "cat": safe(_p_catalysts, results),
        "tech": safe(_p_technical, results),
    }
    thesis = [blocks[k] for k, _ in order if blocks.get(k)]
    risks = [r for r in (safe(_r_market, results), safe(_r_news, results),
                         safe(_r_valuation_fin, results, financial_data, hist)) if r]
    limitations = safe(_r_model, summary) or ""

    # nhận định bổ sung do người dùng tự nhập cho từng mã
    try:
        notes = json.loads(NOTES_PATH.read_text(encoding="utf-8")).get(ticker.upper(), {}) if NOTES_PATH.exists() else {}
        thesis = list(notes.get("thesis", [])) + thesis
        risks = list(notes.get("risks", [])) + risks
    except Exception:
        pass

    rec = recommendation(summary, results, profile, close)
    comp = (summary or {}).get("component_scores") or {}
    names = {"fundamental": "Tài chính", "valuation": "Định giá", "technical": "Kỹ thuật", "news": "Tin tức", "risk": "Rủi ro/An toàn"}
    vals = {k: _f(v) for k, v in comp.items() if _f(v) is not None and k in names}
    conclusion = ""
    if vals and rec["score"] is not None:
        best, worst = max(vals, key=vals.get), min(vals, key=vals.get)
        conclusion = (f"Tóm lại, theo hồ sơ {profile.lower()}, {ticker} đạt {rec['score']:.1f}/100 ({rec['stance'].lower()}). "
                      f"Nhóm hỗ trợ mạnh nhất là {names[best].lower()} ({vals[best]:.0f}/100), nhóm kéo điểm thấp nhất là {names[worst].lower()} ({vals[worst]:.0f}/100). "
                      "Kết quả là công cụ tổng hợp dữ liệu, không phải khuyến nghị mua bán hay giá mục tiêu.")
    else:
        conclusion = "Chưa đủ dữ liệu để kết luận tổng hợp; StockLens không tự nội suy thành phần bị thiếu."
    return {"recommendation": rec, "thesis": thesis, "risks": risks,
            "limitations": limitations, "conclusion": conclusion}
