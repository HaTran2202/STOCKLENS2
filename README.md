> **Bản V4 – Editorial PDF:** Thiết kế bìa, mục lục, bảng biểu và phân cấp nội dung mới. Xem `HUONG_DAN_V4_EDITORIAL.md`. Luồng phân tích bên dưới kế thừa bản V3; chỉ nâng cấp bộ sinh PDF.

﻿# StockLens

StockLens là ứng dụng học tập và nghiên cứu cổ phiếu Việt Nam. Ứng dụng lấy dữ liệu thị trường và báo cáo tài chính, phân tích kỹ thuật, tài chính, định giá, tin tức và rủi ro; sau đó hiển thị dashboard và có thể tạo báo cáo PDF.

> StockLens phục vụ học tập, không phải khuyến nghị mua/bán hoặc tư vấn đầu tư cá nhân. Investment Score là mô hình heuristic, chưa được kiểm định như chiến lược giao dịch. Dữ liệu có thể thiếu, trễ hoặc thay đổi.

## 1. Yêu cầu máy tính

- Windows 10/11 64-bit.
- Python 3.12 64-bit được khuyến nghị (Python 3.10 trở lên).
- Internet để cài thư viện và lấy dữ liệu.
- Trình duyệt hiện đại như Edge hoặc Chrome.
- Nên có ít nhất 2 GB dung lượng trống.

StockLens hiện được hướng dẫn chạy trên Windows. Không cần cài Anaconda.

## 2. Nội dung thư mục dự án

- **app.py**: giao diện Streamlit và điều phối quy trình phân tích.
- **market_data.py**: lấy giá và khối lượng; ưu tiên DNSE, chỉ dùng vnstock làm dự phòng khi lỗi kết nối.
- **src/**: các mô-đun phân tích kỹ thuật, tài chính, định giá, tin tức, chấm điểm, luận điểm, logo và tạo PDF.
- **assets/**: logo và tài nguyên giao diện.
- **.streamlit/config.toml**: màu sắc và giao diện mặc định.
- **requirements.txt**: danh sách thư viện Python.
- **RUN_STOCKLENS.bat**: chạy ứng dụng trên Windows.

Giữ nguyên cấu trúc thư mục khi giải nén. Không tách app.py khỏi src/ hoặc assets/.

## 3. Nhận và giải nén dự án an toàn

Khi gửi dự án cho người khác, tạo ZIP từ thư mục dự án nhưng **không đưa dữ liệu riêng tư hoặc tệp sinh ra trên máy bạn** vào ZIP.

Loại khỏi ZIP:

- **.env**: có thể chứa thông tin DNSE và mật khẩu SMTP.
- **.venv/**: môi trường Python riêng của máy bạn, không dùng chung được.
- **.git/**: lịch sử phiên bản.
- **data/watchlist.json**: có thể chứa email người nhận báo cáo.
- **charts/**, **reports/**, **tmp/**, **__pycache__/** và các tệp **.pyc**.
- **.streamlit/secrets.toml** nếu có.

Giữ lại mã nguồn, requirements.txt, RUN_STOCKLENS.bat, .streamlit/config.toml, src/ và assets/. Người nhận tự tạo môi trường và cấu hình API theo hướng dẫn dưới đây.

**Không gửi mật khẩu/API key qua nhóm chat hoặc để trong README.** Nếu lỡ gửi tệp .env, hãy thu hồi hoặc tạo lại các khóa/mật khẩu đó.

## 4. Cài Python

1. Tải Python 3.12 bản Windows 64-bit từ [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. Mở trình cài đặt và đánh dấu **Add python.exe to PATH**.
3. Hoàn tất cài đặt, mở PowerShell mới rồi kiểm tra:

        py -3.12 --version

Kết quả cần có dạng Python 3.12.x. Nếu lệnh py không có, thử:

        python --version

Nếu máy không nhận py hoặc python, cài lại Python và bật Add python.exe to PATH.

## 5. Tạo môi trường và cài thư viện

Mở thư mục đã giải nén. Trong File Explorer, mở thư mục chứa app.py, bấm thanh địa chỉ, gõ powershell rồi nhấn Enter. Kiểm tra:

        dir app.py

Nếu không tìm thấy app.py, bạn đang ở sai thư mục. Chuyển vào thư mục dự án bằng lệnh cd, ví dụ:

        cd "C:\StockLens"

Tạo môi trường Python riêng trong thư mục dự án, rồi cài các gói:

        py -3.12 -m venv .venv
        .\.venv\Scripts\python.exe -m pip install --upgrade pip
        .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Lần cài đầu cần Internet và có thể mất vài phút. requirements.txt cài Streamlit, pandas, NumPy, Matplotlib, Plotly, requests, python-dotenv, feedparser, ReportLab, vnstock, svglib và Pillow.

Không bắt buộc kích hoạt môi trường bằng Activate.ps1; các lệnh trên gọi trực tiếp Python trong .venv và không cần thay đổi PowerShell Execution Policy.

Nếu py -3.12 không dùng được nhưng python --version cho biết Python 3.10 trở lên, thay py -3.12 ở lệnh đầu bằng python. Sau khi tạo môi trường, tiếp tục dùng .venv\Scripts\python.exe.

## 6. Cấu hình DNSE để lấy dữ liệu giá

StockLens cần API key và API secret DNSE hợp lệ để truy vấn giá. Nếu chưa cấu hình, ứng dụng báo thiếu DNSE_API_KEY hoặc DNSE_API_SECRET. Nguồn vnstock chỉ dự phòng khi DNSE gặp lỗi kết nối; không thay thế khóa DNSE bị thiếu hoặc sai.

Tạo tệp .env ngay cạnh app.py:

1. Mở Notepad.
2. Nhập nội dung mẫu dưới đây và thay phần giữ chỗ bằng khóa của chính bạn:

        DNSE_API_KEY=thay_bang_api_key_cua_ban
        DNSE_API_SECRET=thay_bang_api_secret_cua_ban

3. Chọn File > Save As.
4. Đặt tên là .env (không phải .env.txt). Chọn All files nếu Notepad hỏi loại tệp.
5. Lưu với mã hóa UTF-8.

Tệp .env được Git bỏ qua. Không gửi tệp này cho nhóm và không chia sẻ ảnh có chứa giá trị khóa. Không cần dấu ngoặc kép cho các giá trị mẫu đơn giản ở trên.

Các thiết lập tùy chọn như DNSE_API_BASE_URL, DNSE_API_VERSION, DNSE_RESOLUTION, DNSE_CONNECT_TIMEOUT và DNSE_READ_TIMEOUT đã có mặc định trong mã; chỉ thay đổi nếu biết rõ lý do.

## 7. Cấu hình gửi PDF qua email (tùy chọn)

Không cần SMTP để dùng dashboard hoặc tải PDF thủ công. Chỉ cấu hình nếu muốn StockLens gửi PDF qua email sau khi phân tích thành công một mã đã đăng ký trong Danh mục.

Thêm các dòng sau vào .env, thay bằng thông tin SMTP của tài khoản gửi:

        STOCKLENS_SMTP_HOST=smtp.example.com
        STOCKLENS_SMTP_PORT=587
        STOCKLENS_SMTP_USERNAME=sender@example.com
        STOCKLENS_SMTP_PASSWORD=mat_khau_ung_dung
        STOCKLENS_SMTP_FROM=sender@example.com
        STOCKLENS_SMTP_STARTTLS=true

SMTP SSL thường dùng cổng 465; khi đó đặt STOCKLENS_SMTP_SSL=true. Dùng mật khẩu ứng dụng do nhà cung cấp email cấp nếu dịch vụ yêu cầu. Không dùng hoặc chia sẻ mật khẩu email cá nhân.

Danh sách mã và địa chỉ người nhận lưu trên máy chạy ứng dụng tại data/watchlist.json. Không đưa tệp này vào ZIP gửi cho người khác. StockLens gửi khi người dùng tự phân tích mã có trong danh mục; ứng dụng hiện không tự lên lịch quét toàn danh mục.

## 8. Chạy StockLens

Sau khi cài gói và cấu hình DNSE:

- Cách đơn giản: nhấp đúp RUN_STOCKLENS.bat.
- Hoặc chạy PowerShell tại thư mục chứa app.py:

        .\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

Mở địa chỉ sau trên máy đang chạy ứng dụng:

        http://localhost:8501

Nếu cổng 8501 đã được dùng, đổi 8501 trong lệnh trên thành 8502, rồi mở http://localhost:8502.

Giữ cửa sổ chạy ứng dụng mở khi sử dụng. Để dừng, chuyển tới cửa sổ đó và nhấn Ctrl+C. Khi ứng dụng dừng, trang localhost không còn hoạt động.

Mặc định, ứng dụng chỉ nên dùng trên chính máy tính. Không đổi địa chỉ thành 0.0.0.0, không tạo đường hầm công khai và không mở cổng trên router nếu chưa cấu hình xác thực và hiểu ai có thể truy cập dữ liệu.

## 9. Dùng ứng dụng

1. Nhập mã cổ phiếu Việt Nam, ví dụ FPT, HPG, MWG, VNM hoặc ACB.
2. Chọn ngày bắt đầu, ngày kết thúc và phong cách đầu tư.
3. Nhấn Phân tích cổ phiếu.
4. Dùng các mục Tổng quan, Kỹ thuật, Tài chính, Định giá, Tin tức và Báo cáo.
5. Trong trang Báo cáo, tạo/tải PDF. Nếu đổi mã hoặc tùy chọn, tạo lại PDF để cập nhật nội dung.

Dữ liệu lấy từ DNSE/vnstock, báo cáo tài chính từ vnstock/KBS, tin tức từ Google News RSS. Một số mã hoặc thời kỳ có thể không có đủ dữ liệu.

## 10. Lỗi thường gặp

### Python hoặc lệnh py không được nhận dạng

Cài Python 3.12 64-bit, đánh dấu Add python.exe to PATH, sau đó đóng và mở lại PowerShell.

### ModuleNotFoundError hoặc thiếu thư viện

Đảm bảo đã cài gói vào .venv bằng đúng lệnh:

        .\.venv\Scripts\python.exe -m pip install -r requirements.txt

### Cài đặt gói bị lỗi hoặc tải lâu

Kiểm tra Internet rồi thử lại. Dự án cài vnstock==4.0.8 cùng các thư viện từ các nguồn khai báo trong requirements.txt. Mạng cơ quan/trường học có thể chặn một số package index.

### DNSE báo thiếu khóa, HTTP 401 hoặc 403

Kiểm tra tên biến, giá trị API key/API secret, hạn sử dụng và quyền của khóa trong .env. Sau khi sửa .env, dừng rồi chạy lại Streamlit.

### DNSE trả HTTP 429

Đây là giới hạn tần suất truy vấn. Chờ một lúc rồi thử lại.

### Cổng 8501 đang được sử dụng

Dùng cổng 8502 trong lệnh chạy và truy cập http://localhost:8502. Không cần tắt ứng dụng khác nếu không biết tiến trình đó là gì.

### Giao diện báo Failed to fetch dynamically imported module

Tải lại toàn bộ trang bằng Ctrl+Shift+R. Nếu vẫn lỗi, đóng tab và mở lại ứng dụng. Lỗi có thể do trình duyệt giữ tệp giao diện cũ trong cache.

## 11. PDF và biểu đồ

PDF được tạo từ dữ liệu phân tích đang hiển thị. Biểu đồ và tệp tạm có thể được tạo trong charts/, reports/ hoặc tmp/ khi chạy. Có thể xóa tệp sinh ra sau khi đã lưu báo cáo cần giữ; không xóa mã nguồn hoặc assets/.

Các thư viện ReportLab, Matplotlib, svglib và Pillow đã có trong requirements.txt.

## 12. Dữ liệu và quyền riêng tư

- .env: khóa DNSE và cấu hình SMTP; giữ riêng trên từng máy.
- data/watchlist.json: mã cổ phiếu và email người nhận; chỉ dùng cục bộ.
- assets/logos/: logo có thể chia sẻ cùng dự án.
- charts/, reports/, tmp/: tệp tạo trong lúc chạy.
- .venv/: thư viện Python riêng cho máy hiện tại; mỗi người nhận tự tạo lại.

Ứng dụng gọi các nhà cung cấp bên ngoài để tải giá, báo cáo tài chính và tin tức. Không nhập dữ liệu cá nhân hoặc bí mật trừ khi bạn hiểu mục đích và nơi dữ liệu được gửi.

## 13. Giới hạn phân tích

- Investment Score và quan điểm StockLens là kết quả mô hình heuristic, không phải lời khuyên mua/bán.
- Giá trị peer là tham chiếu tương đối, không phải giá mục tiêu chính thức hay định giá DCF.
- Chất lượng kết quả phụ thuộc nguồn, thời điểm và mức độ đầy đủ của dữ liệu.
- Dữ liệu hoặc ngành đặc thù có thể cần người dùng kiểm tra thêm trước khi sử dụng.


## STOCKLENS2 sửa dữ liệu (bản CSV)

- **BCTC mặc định:** CSV đã kèm theo dưới `data/financials-market_2020-2026/`.
- **Giá giao dịch:** DNSE, yêu cầu khóa API trong `.env` (không commit).
- **Tin tức:** Google News RSS; điểm cảm xúc chỉ theo tiêu đề, có sai số.
- **KBS:** Chỉ cần nếu bật `STOCKLENS_FINANCIAL_SOURCE=vnstock` hoặc chủ động cấu hình `auto` cho mã thiếu CSV.
- **Lưu ý:** CSV đang dừng ở báo cáo năm 2025; nếu cần kỳ 2026, hãy cập nhật dữ liệu có thể kiểm chứng.
- **CSV license:** Kiểm tra điều khoản sử dụng của bên cung cấp trước khi tái phân phối trên GitHub công khai.

Xem `HUONG_DAN_SUA_TOAN_BO.md` để cài đặt và chạy kiểm thử.
