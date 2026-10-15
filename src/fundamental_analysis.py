"""
StockLens - Fundamental Analysis

Nguồn đầu vào:
    src/vnstock_data.py -> vnstock / KBS

Thiết kế:
    - Doanh nghiệp thông thường: giữ nguyên bộ 6 chỉ tiêu cũ để không làm thay đổi
      cách chấm FPT/HPG/MWG...
    - Ngân hàng: dùng bộ chỉ tiêu riêng phù hợp hơn với mô hình ngân hàng; không
      ép Debt/Equity, Current Ratio hay Net Margin vào cùng thang điểm doanh nghiệp.

Các ngưỡng là heuristic của StockLens, phục vụ học tập và nghiên cứu.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from src.financial_analytics import analyze_financial_analytics


# =========================================================
# 1. BASIC HELPERS
# =========================================================

def _num(value) -> float | None:
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _pct_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _ratio_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}x"


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def _detect_business_type(info: dict) -> str:
    explicit = _normalize_text(info.get("financialBusinessType"))
    if explicit == "bank":
        return "bank"
    if explicit == "corporate":
        return "corporate"

    blob = _normalize_text(
        " ".join(
            str(info.get(k) or "")
            for k in ("sector", "industry", "name", "business_model")
        )
    )

    bank_markers = (
        "ngan hang",
        "commercial bank",
        "banking",
        "bank ",
    )
    if any(marker in blob for marker in bank_markers):
        return "bank"

    return "corporate"


def _period_key(value: Any) -> tuple[int, int]:
    text = str(value or "")
    q = re.search(r"(\d{4}).*?q([1-4])", text, flags=re.I)
    if q:
        return int(q.group(1)), int(q.group(2))
    y = re.search(r"(\d{4})", text)
    if y:
        return int(y.group(1)), 5
    return -1, -1


def _history_rows(info: dict) -> list[dict]:
    history = info.get("financialHistory", []) or []
    rows = [row for row in history if isinstance(row, dict)]
    return sorted(rows, key=lambda row: _period_key(row.get("period")), reverse=True)


def _history_growth(info: dict, field: str) -> float | None:
    values: list[float] = []
    for row in _history_rows(info):
        value = _num(row.get(field))
        if value is not None:
            values.append(value)
        if len(values) >= 2:
            break

    if len(values) < 2 or values[1] == 0:
        return None
    return values[0] / values[1] - 1


def _safe_divide(a, b) -> float | None:
    a = _num(a)
    b = _num(b)
    if a is None or b in (None, 0):
        return None
    return a / b


# =========================================================
# 2. SCORING HELPERS
# =========================================================

def _score_higher(value: float | None, strong: float, acceptable: float) -> int | None:
    if value is None:
        return None
    if value >= strong:
        return 100
    if value >= acceptable:
        return 60
    return 20


def _score_lower(value: float | None, strong: float, acceptable: float) -> int | None:
    if value is None:
        return None
    if value <= strong:
        return 100
    if value <= acceptable:
        return 60
    return 20


def _score_current_ratio(value: float | None) -> int | None:
    if value is None or value < 0:
        return None
    if value >= 1.5:
        return 100
    if value >= 1.0:
        return 60
    return 20


def _classification(score: float | None) -> str:
    if score is None:
        return "Không đủ dữ liệu"
    if score >= 80:
        return "Nền tảng cơ bản mạnh"
    if score >= 65:
        return "Nền tảng cơ bản tích cực"
    if score >= 50:
        return "Nền tảng cơ bản trung lập"
    return "Nền tảng cơ bản cần thận trọng"


def _weighted_score(component_scores: dict[str, float], weights: dict[str, float]):
    weighted_points = 0.0
    available_weight = 0.0

    for key, score_value in component_scores.items():
        weight = weights.get(key, 0.0)
        weighted_points += score_value * weight
        available_weight += weight

    score = round(weighted_points / available_weight, 2) if available_weight > 0 else None
    return score, available_weight


# =========================================================
# 3. CORPORATE ANALYSIS - GIỮ LOGIC CŨ
# =========================================================

def _analyze_corporate(info: dict, metrics: dict[str, float | None]) -> dict[str, Any]:
    component_weights = {
        "roe": 0.20,
        "roa": 0.15,
        "profit_margin": 0.20,
        "revenue_growth": 0.15,
        "debt_to_equity": 0.15,
        "current_ratio": 0.15,
    }

    component_scores: dict[str, int] = {}
    positives: list[str] = []
    risks: list[str] = []
    observations: list[str] = []

    roe = metrics["roe"]
    s = _score_higher(roe, 0.15, 0.08)
    if s is not None:
        component_scores["roe"] = s
        if s == 100:
            positives.append(f"ROE {_pct_text(roe)} cho thấy khả năng sinh lời trên vốn chủ sở hữu tốt.")
        elif s == 60:
            observations.append(f"ROE {_pct_text(roe)} ở mức chấp nhận được.")
        else:
            risks.append(f"ROE {_pct_text(roe)} tương đối thấp.")

    roa = metrics["roa"]
    s = _score_higher(roa, 0.07, 0.03)
    if s is not None:
        component_scores["roa"] = s
        if s == 100:
            positives.append(f"ROA {_pct_text(roa)} phản ánh hiệu quả sử dụng tài sản tốt.")
        elif s == 60:
            observations.append(f"ROA {_pct_text(roa)} ở mức trung bình.")
        else:
            risks.append(f"ROA {_pct_text(roa)} còn thấp.")

    margin = metrics["profit_margin"]
    s = _score_higher(margin, 0.12, 0.05)
    if s is not None:
        component_scores["profit_margin"] = s
        if s == 100:
            positives.append(f"Biên lợi nhuận ròng {_pct_text(margin)} ở mức tốt.")
        elif s == 60:
            observations.append(f"Biên lợi nhuận ròng {_pct_text(margin)} ở mức chấp nhận được.")
        else:
            risks.append(f"Biên lợi nhuận ròng {_pct_text(margin)} còn thấp.")

    growth = metrics["revenue_growth"]
    s = _score_higher(growth, 0.10, 0.00)
    if s is not None:
        component_scores["revenue_growth"] = s
        if s == 100:
            positives.append(f"Doanh thu tăng {_pct_text(growth)} so với kỳ trước.")
        elif s == 60:
            observations.append(f"Tăng trưởng doanh thu {_pct_text(growth)} ở mức dương nhưng chưa cao.")
        else:
            risks.append(f"Doanh thu giảm {_pct_text(abs(growth))} so với kỳ trước.")

    de = metrics["debt_to_equity"]
    s = _score_lower(de, 0.80, 1.50) if de is not None and de >= 0 else None
    if s is not None:
        component_scores["debt_to_equity"] = s
        if s == 100:
            positives.append(f"Debt/Equity {_ratio_text(de)} cho thấy đòn bẩy ở mức tương đối an toàn theo tiêu chí StockLens.")
        elif s == 60:
            observations.append(f"Debt/Equity {_ratio_text(de)} ở mức cần theo dõi.")
        else:
            risks.append(f"Debt/Equity {_ratio_text(de)} khá cao.")

    cr = metrics["current_ratio"]
    s = _score_current_ratio(cr)
    if s is not None:
        component_scores["current_ratio"] = s
        if s == 100:
            positives.append(f"Current Ratio {_ratio_text(cr)} cho thấy khả năng thanh toán ngắn hạn tốt.")
        elif s == 60:
            observations.append(f"Current Ratio {_ratio_text(cr)} ở mức chấp nhận được.")
        else:
            risks.append(f"Current Ratio {_ratio_text(cr)} dưới 1, cần lưu ý thanh khoản ngắn hạn.")

    score, available_weight = _weighted_score(component_scores, component_weights)

    return {
        "component_weights": component_weights,
        "component_scores": component_scores,
        "positives": positives,
        "risks": risks,
        "observations": observations,
        "score": score,
        "available_weight": available_weight,
        "total_components": len(component_weights),
        "method_note": (
            "Doanh nghiệp thông thường: ROE 20%, ROA 15%, biên lợi nhuận ròng 20%, "
            "tăng trưởng doanh thu 15%, Nợ phải trả/VCSH 15% và Current Ratio 15%. "
            "Chỉ tiêu thiếu dữ liệu được loại khỏi mẫu số thay vì chấm 0."
        ),
    }


# =========================================================
# 4. BANK ANALYSIS - BỘ CHỈ TIÊU RIÊNG
# =========================================================

def _analyze_bank(info: dict, metrics: dict[str, float | None]) -> dict[str, Any]:
    """Bank-specific heuristic. Every ratio is directly read from CSV/provider.

    NIM, CAR, CASA, NPL and LDR are NOT inferred from non-bank accounts.
    LLR is unavailable in this export; do not assign it a score.
    """
    weights = {'roe': .15, 'roa': .10, 'net_interest_margin': .15,
               'npl_ratio': .20, 'car': .15, 'casa_ratio': .10,
               'ldr': .10, 'loans_growth': .05}
    scores={}; positives=[]; risks=[]; observations=[]
    values = {
        'roe': metrics.get('roe'), 'roa': metrics.get('roa'),
        'net_interest_margin': metrics.get('net_interest_margin'),
        'npl_ratio': metrics.get('npl_ratio'), 'car': metrics.get('car'),
        'casa_ratio': metrics.get('casa_ratio'), 'ldr': metrics.get('ldr'),
        'loans_growth': metrics.get('loans_growth'),
    }
    configs={
        'roe': ('higher',.16,.10), 'roa':('higher',.015,.008),
        'net_interest_margin':('higher',.04,.025),
        'npl_ratio':('lower',.015,.03), 'car':('higher',.11,.085),
        'casa_ratio':('higher',.35,.20),'loans_growth':('higher',.14,.06),
    }
    for key,(direction,strong,acceptable) in configs.items():
        v=values.get(key)
        score=(_score_higher(v,strong,acceptable) if direction=='higher'
               else _score_lower(v,strong,acceptable))
        if score is not None: scores[key]=score
    ldr=values['ldr']
    if ldr is not None and ldr>=0:
        scores['ldr']=100 if .70<=ldr<=.95 else 60 if .60<=ldr<=1.10 else 20
    score, available_weight=_weighted_score(scores,weights)
    for key, value in values.items():
        if value is None: observations.append(f'Không có dữ liệu {key}; không tự tính hoặc gán 0.')
    if info.get('llrRatio') is None:
        observations.append('LLR không có trong 5 CSV, không suy đoán từ NPL hoặc CAR.')
    observations.append('Ngưỡng chấm là heuristic phục vụ nghiên cứu, không đồng nhất với chuẩn giám sát NHNN; CAR/LDR có nhiều cách xác định.')
    return {
        'component_weights':weights, 'component_scores':scores,
        'positives':positives,'risks':risks,'observations':observations,
        'score':score,'available_weight':available_weight,
        'total_components':len(weights),
        'method_note':('Ngân hàng: ROE 15%, ROA 10%, NIM 15%, NPL 20%, CAR 15%, '
                       'CASA 10%, LDR 10%, tăng trưởng tín dụng 5%; LLR hiển thị N/A nếu thiếu. '
                       'Không dùng D/E, current ratio hoặc biên lãi gộp của doanh nghiệp thường.')
    }


# =========================================================
# 5. PUBLIC API
# =========================================================

def analyze_fundamental(info: dict) -> dict[str, Any]:
    info = info or {}
    business_type = _detect_business_type(info)

    history = _history_rows(info)

    total_assets = _num(info.get("totalAssets"))
    total_equity = _num(info.get("totalEquity"))

    metrics = {
        "roe": _num(info.get("returnOnEquity")),
        "roa": _num(info.get("returnOnAssets")),
        "profit_margin": _num(info.get("profitMargins")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "current_ratio": _num(info.get("currentRatio")),
        "total_revenue": _num(info.get("totalRevenue")),
        "net_income": _num(info.get("netIncomeToCommon")),
        "gross_profit": _num(info.get("grossProfit")),
        "operating_cash_flow": _num(info.get("operatingCashFlow")),
        "total_assets": total_assets,
        "total_equity": total_equity,
        # Bank-oriented metrics derived only from actual historical values.
        "net_income_growth": _history_growth(info, "net_profit"),
        "asset_growth": _history_growth(info, "total_assets"),
        "equity_growth": _history_growth(info, "equity"),
        "operating_income_growth": _history_growth(info, "revenue"),
        "equity_to_assets": _safe_divide(total_equity, total_assets),
        "net_interest_margin": _num(info.get("netInterestMargin")),
        "npl_ratio": _num(info.get("nplRatio")),
        "car": _num(info.get("capitalAdequacyRatio")),
        "casa_ratio": _num(info.get("casaRatio")),
        "ldr": _num(info.get("loanToDepositRatio")),
        "loans_growth": _num(info.get("loansGrowth")),
        "llr_ratio": _num(info.get("llrRatio")),
    }

    if business_type == "bank":
        result = _analyze_bank(info, metrics)
    else:
        result = _analyze_corporate(info, metrics)

    score = result["score"]
    component_scores = result["component_scores"]
    component_weights = result["component_weights"]
    available_weight = result["available_weight"]
    total_components = result["total_components"]
    coverage = len(component_scores)
    coverage_ratio = coverage / total_components if total_components else 0
    quality_warnings = list(info.get('qualityWarnings') or [])
    essential_ok = bool(info.get('criticalDataReady', True))
    if business_type != 'bank':
        essential_ok = essential_ok and all(_num(info.get(k)) is not None for k in
            ('totalRevenue', 'netIncomeToCommon', 'totalAssets', 'totalEquity'))
    if available_weight < .80 or not essential_ok:
        quality_warnings.append('Thiếu dữ liệu trọng yếu hoặc độ bao phủ dưới 80%; không xếp hạng tài chính.')
        score = None
    classification = _classification(score)

    if score is None:
        commentary = "Không đủ dữ liệu tài chính để tính Fundamental Score."
    elif business_type == "bank":
        commentary = (
            f"Fundamental Score ngân hàng đạt {score:.2f}/100, xếp loại '{classification}'. "
            f"Điểm được tính từ {coverage}/{total_components} chỉ tiêu ngân hàng có dữ liệu. "
            "Debt/Equity, Current Ratio và biên lợi nhuận doanh nghiệp không bị ép vào mô hình ngân hàng."
        )
    else:
        commentary = (
            f"Fundamental Score đạt {score:.2f}/100, xếp loại '{classification}'. "
            f"Điểm được tính từ {coverage}/{total_components} chỉ tiêu tài chính có dữ liệu. "
            "Chỉ tiêu thiếu dữ liệu không bị quy thành 0."
        )

    return {
        "data_available": score is not None,
        "score": score,
        "classification": classification,
        "metrics": metrics,
        "component_scores": component_scores,
        "component_weights": component_weights,
        "positives": result["positives"],
        "observations": result["observations"],
        "risks": result["risks"],
        "commentary": commentary,
        "coverage": coverage,
        "total_components": total_components,
        "coverage_ratio": round(coverage_ratio, 4),
        "coverage_weight": round(available_weight * 100, 2),
        "business_type": business_type,
        "is_bank": business_type == "bank",
        "not_applicable_metrics": (
            ["profit_margin", "debt_to_equity", "current_ratio"]
            if business_type == "bank"
            else []
        ),
        "ticker": info.get("ticker"),
        "company_name": info.get("name"),
        "sector": info.get("sector"),
        "report_period": info.get("reportPeriod"),
        "financial_history": history,
        "source": info.get('source') or 'vnstock/KBS',
        "quality_warnings": quality_warnings,
        "confidence": 'Đủ điều kiện' if score is not None else 'Chưa đủ dữ liệu', 
        "method_note": result["method_note"],
        "financial_analytics": analyze_financial_analytics(info),
    }
if __name__ == "__main__":
    import json
    from src.vnstock_data import get_financial_data

    symbol = "FPT"
    print(f"--- ĐANG KIỂM TRA OUTPUT CHO MÃ {symbol} ---")

    info = get_financial_data(ticker=symbol, period="year")

    if not isinstance(info, dict):
        raise TypeError(
            f"get_financial_data phải trả về dict, "
            f"nhưng nhận được {type(info).__name__}: {info!r}"
        )

    result = analyze_fundamental(info)

    print(json.dumps(result, indent=4, ensure_ascii=False))