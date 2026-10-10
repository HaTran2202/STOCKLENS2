"""Persistent local mapping of stock tickers to report recipients."""
from __future__ import annotations
import json
import re
from pathlib import Path
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "watchlist.json"

def list_watchlist() -> list[dict[str, str]]:
    if not DATA_FILE.exists():
        return []
    try:
        rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Không đọc được danh mục: {exc}") from exc
    return rows if isinstance(rows, list) else []

def get_recipient(ticker: str) -> str | None:
    key = str(ticker or "").strip().upper().split(".")[0]
    return next((r.get("email") for r in list_watchlist() if r.get("ticker") == key), None)

def save_entry(ticker: str, email: str) -> None:
    key = re.sub(r"[^A-Z0-9]", "", str(ticker or "").strip().upper().split(".")[0])
    address = str(email or "").strip()
    if not key:
        raise ValueError("Vui lòng nhập mã cổ phiếu.")
    if len(key) > 12:
        raise ValueError("Mã cổ phiếu không hợp lệ.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
        raise ValueError("Địa chỉ email không hợp lệ.")
    rows = [r for r in list_watchlist() if r.get("ticker") != key]
    rows.append({"ticker": key, "email": address})
    rows.sort(key=lambda r: r["ticker"])
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

def remove_entry(ticker: str) -> None:
    key = str(ticker or "").strip().upper().split(".")[0]
    rows = [r for r in list_watchlist() if r.get("ticker") != key]
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
