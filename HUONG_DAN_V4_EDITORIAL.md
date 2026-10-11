
## Chạy trên macOS / VS Code

1. Giải nén thư mục `STOCKLENS2_EDITORIAL` và mở **chính thư mục chứa `app.py`** trong VS Code.
2. Mở Terminal, chạy lần lượt:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

3. Tạo file `.env` cạnh `app.py`, chỉ điền khóa DNSE mới hợp lệ. `.env.example` là file mẫu phải để trống khóa. Thư mục `data/financials-market_2020-2026` đã có 5 CSV trong ZIP.

```env
DNSE_API_KEY=your_new_key
DNSE_API_SECRET=your_new_secret
STOCKLENS_FINANCIAL_SOURCE=csv
```

4. Chạy:

```bash
python -m streamlit run app.py
```

5. Mở đúng địa chỉ `Local URL` Streamlit in ra. Phân tích FPT → GVR → MBB và tải PDF từng mã. Trên PDF hãy kiểm tra tên mã, nội dung biểu đồ, số liệu đúng mã; thử thay đổi kỳ và hồ sơ nhà đầu tư.

