"""Chẩn đoán vì sao Investment Score bị N/A (không in khóa/mật khẩu).

Chạy trong thư mục dự án, bằng đúng môi trường Python của dự án:
    python check_scores.py FPT
    python check_scores.py FPT --price 56300     # không gọi DNSE, dùng giá bạn nhập
"""
import inspect
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src import csv_data  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
ticker = (args[0] if args else "FPT").upper().replace(".VN", "")
price = None
if "--price" in sys.argv:
    price = float(sys.argv[sys.argv.index("--price") + 1])

print("=== 1. File đang được dùng")
print("src/csv_data.py:", csv_data.__file__)
patched = "rebase_limit" in inspect.getsource(csv_data.reconcile_market_snapshot)
print("Bản vá rebase đã có trong file này:", "CÓ" if patched else "KHÔNG -> bạn đang chạy file cũ / sai thư mục dự án")
print("Giới hạn quy đổi:", os.environ.get("STOCKLENS_SNAPSHOT_REBASE_LIMIT", "0.10 (mặc định)"))

print("\n=== 2. Giá thị trường")
if price is None:
    from market_data import get_market_data
    df = get_market_data(ticker, str(date.today() - timedelta(days=45)), str(date.today()))
    price = float(df.iloc[-1]["Close"])
    print("Phiên cuối:", df.iloc[-1]["Date"], "| Close:", f"{price:,.0f}")
else:
    print("Giá nhập tay:", f"{price:,.0f}")

print("\n=== 3. Số liệu BCTC / snapshot P/E, P/B")
from src.vnstock_data import get_financial_data  # noqa: E402
raw = get_financial_data(ticker, period="year")
snap = raw.get("_csv_market_snapshot") or {}
sp = snap.get("implied_price")
print("Nguồn BCTC (STOCKLENS_FINANCIAL_SOURCE):", os.environ.get("STOCKLENS_FINANCIAL_SOURCE", "csv"))
if sp:
    print(f"Snapshot P/E, P/B trong CSV được ghi ở giá {sp:,.0f}; giá thị trường {price:,.0f}; lệch {abs(price - sp) / price:.1%}")
else:
    print("Không có snapshot P/E, P/B trong CSV cho mã này.")
info = csv_data.reconcile_market_snapshot(raw, price)
print("P/E:", info.get("trailingPE"), "| P/B:", info.get("priceToBook"))
for w in info.get("qualityWarnings", []):
    print(" - cảnh báo:", w)

print("\n=== 4. Điểm từng thành phần")
from src.fundamental_analysis import analyze_fundamental  # noqa: E402
from src.valuation import analyze_valuation  # noqa: E402
fund = analyze_fundamental(info)
val = analyze_valuation(info, ticker=ticker, current_price=price)
print("Tài chính (fundamental):", fund.get("score"))
print("Định giá (valuation)   :", val.get("score"))
print("\n=> Investment Score chỉ tính được khi CẢ 5 thành phần có điểm (tài chính, định giá, kỹ thuật, tin tức, rủi ro).")
if val.get("score") is None:
    print("   Định giá đang THIẾU điểm -> đây là lý do Investment Score = N/A (xem cảnh báo ở mục 3).")
if fund.get("score") is None:
    print("   Tài chính đang THIẾU điểm -> đây là lý do Investment Score = N/A.")