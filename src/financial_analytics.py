"""Contextual analytics for annual financial statements.

Benchmark medians are accepted as inputs because this app does not currently
have a grounded ROE/ROA/margin/debt benchmark dataset.
"""
from __future__ import annotations

import math
import re
from typing import Any


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _divide(a: Any, b: Any) -> float | None:
    a, b = _number(a), _number(b)
    return a / b if a is not None and b not in (None, 0) else None


def _year(row: dict) -> int | None:
    period = str(row.get("period") or "")
    # DuPont in this report is fiscal-year based; do not mix quarterly rows.
    if re.search(r"q[1-4]", period, flags=re.IGNORECASE):
        return None
    match = re.search(r"\d{4}", period)
    return int(match.group()) if match else None


def _dupont(info: dict) -> dict:
    rows = [r for r in (info.get("financialHistory") or [])
            if isinstance(r, dict) and _year(r) is not None]
    rows.sort(key=_year)
    if not rows:
        return {"available": False, "current": None, "previous": None,
                "factor_yoy_change": {}, "primary_driver": None, "commentary": None}

    latest, year = rows[-1], _year(rows[-1])
    prior = next((r for r in reversed(rows[:-1]) if _year(r) == year - 1), None)

    def factors(row: dict, preceding: dict | None) -> dict:
        assets, equity = _number(row.get("total_assets")), _number(row.get("equity"))
        old_assets = _number(preceding.get("total_assets")) if preceding else None
        old_equity = _number(preceding.get("equity")) if preceding else None
        avg_assets = (assets + old_assets) / 2 if assets is not None and old_assets is not None else None
        avg_equity = (equity + old_equity) / 2 if equity is not None and old_equity is not None else None
        margin = _divide(row.get("net_profit"), row.get("revenue"))
        turnover = _divide(row.get("revenue"), avg_assets)
        multiplier = _divide(avg_assets, avg_equity)
        roe = margin * turnover * multiplier if None not in (margin, turnover, multiplier) else None
        return {"period": str(_year(row)), "net_margin": margin,
                "asset_turnover": turnover, "equity_multiplier": multiplier, "roe": roe}

    current = factors(latest, prior)
    prior_prior = next((r for r in reversed(rows[:-1])
                        if prior and _year(r) == year - 2), None)
    previous = factors(prior, prior_prior) if prior else None
    changes = {}
    if previous:
        for key in ("net_margin", "asset_turnover", "equity_multiplier"):
            now, before = current[key], previous[key]
            changes[key] = now / before - 1 if now is not None and before not in (None, 0) else None
    drivers = [(key, value) for key, value in changes.items() if value is not None]
    driver = max(drivers, key=lambda pair: abs(pair[1]))[0] if drivers else None
    names = {"net_margin": "biên lợi nhuận ròng", "asset_turnover": "vòng quay tài sản",
             "equity_multiplier": "đòn bẩy tài chính"}
    commentary = None
    if current["roe"] is not None:
        if previous and previous["roe"] is not None:
            delta = current["roe"] - previous["roe"]
            if driver:
                others = [f"{names[k]} ({v:+.1%})" for k, v in changes.items()
                          if k != driver and v is not None]
                secondary = ", ".join(others) if others else "các yếu tố thứ yếu"
                commentary = (f"ROE năm {year} đạt {current['roe']:.2%} ({delta:+.2%} YoY). "
                              f"Động lực chính đến từ {names[driver]} ({changes[driver]:+.1%}), "
                              f"trong khi {secondary}.")
            else:
                commentary = (f"ROE năm {year} đạt {current['roe']:.2%} ({delta:+.2%} YoY); "
                              "chưa đủ dữ liệu xác định động lực.")
        else:
            commentary = (f"ROE năm {year} đạt {current['roe']:.2%}; chưa đủ dữ liệu năm trước "
                          "để phân tích động lực.")
    return {"available": current["roe"] is not None, "current": current,
            "previous": previous, "factor_yoy_change": changes,
            "primary_driver": driver, "commentary": commentary}


def _earnings_quality(info: dict) -> dict:
    profit = _number(info.get("netIncomeToCommon"))
    ocf = _number(info.get("operatingCashFlow"))
    ratio = _divide(ocf, profit)
    level, commentary = "missing", None
    if ocf is not None and profit is not None and ocf <= 0 < profit:
        level = "high"
        commentary = (f"RỦI RO DÒNG TIỀN: LNST đạt {profit / 1e9:.2f} tỷ nhưng OCF âm "
                      f"({ocf / 1e9:.2f} tỷ). Doanh nghiệp có dấu hiệu bị chiếm dụng vốn nặng "
                      "hoặc tồn kho/phải thu tăng cao.")
    elif ratio is not None and ratio < 0.8:
        level = "warning"
        commentary = (f"CẢNH BÁO CHẤT LƯỢNG LỢI NHUẬN: Dòng tiền HĐKD chỉ đệm được "
                      f"{ratio:.1%} LNST. Cần kiểm tra kỹ khoản Phải thu và Hàng tồn kho.")
    elif ratio is not None:
        level = "good"
        commentary = (f"CHẤT LƯỢNG LỢI NHUẬN TỐT: Dòng tiền thực thu đệm vững chắc cho LNST "
                      f"(OCF/LNST = {ratio:.1%}), đảm bảo sức khỏe tài chính lành mạnh.")
    return {"available": ratio is not None, "ocf": ocf, "net_income": profit,
            "ocf_ratio": ratio, "level": level, "commentary": commentary}


def _benchmark(info: dict) -> dict:
    current = {"ROE": _number(info.get("returnOnEquity")),
               "ROA": _number(info.get("returnOnAssets")),
               "Net_Margin": _number(info.get("profitMargins")),
               "Debt_to_Equity": _number(info.get("debtToEquity"))}
    source = info.get("financialBenchmarks") or {}
    industry_source = source.get("industry_median") or {}
    market_source = source.get("market_median") or {}
    industry = {key: _number(industry_source.get(key)) for key in current}
    market = {key: _number(market_source.get(key)) for key in current}
    tags = {}
    for key, value in current.items():
        median = industry.get(key)
        if value is None or median is None:
            tags[key] = None
        elif key == "Debt_to_Equity":
            tags[key] = ("Vượt trội (Top-tier)" if value < 0.8 * median else
                         "Ngang trung bình ngành" if value <= 1.2 * median else "Thấp hơn ngành")
        else:
            tags[key] = ("Vượt trội (Top-tier)" if value > 1.2 * median else
                         "Ngang trung bình ngành" if value >= 0.8 * median else "Thấp hơn ngành")
    return {"current_stock": current, "industry_median": industry,
            "market_median": market, "industry_level": source.get("industry_level"),
            "industry_tag": tags,
            "available": any(value is not None for value in industry.values())}


def analyze_financial_analytics(info: dict) -> dict:
    """Return JSON-serializable DuPont, OCF quality, and benchmark results."""
    info = info if isinstance(info, dict) else {}
    return {"dupont": _dupont(info), "earnings_quality": _earnings_quality(info),
            "benchmarking": _benchmark(info)}
