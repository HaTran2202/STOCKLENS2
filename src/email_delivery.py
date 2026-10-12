"""Gửi báo cáo PDF của StockLens qua SMTP.

Chỉ cần 2 biến trong file .env nếu dùng Gmail / Outlook / Yahoo (host và cổng được tự nhận từ địa chỉ email):
    STOCKLENS_SMTP_USERNAME=ten@gmail.com
    STOCKLENS_SMTP_PASSWORD=mat-khau-ung-dung        # Gmail: dùng "Mật khẩu ứng dụng" 16 ký tự, KHÔNG dùng mật khẩu đăng nhập
Tuỳ chọn:
    STOCKLENS_SMTP_HOST, STOCKLENS_SMTP_PORT (587 = STARTTLS, 465 = SSL), STOCKLENS_SMTP_FROM,
    STOCKLENS_SMTP_STARTTLS=true|false, STOCKLENS_SMTP_SSL=true|false

File .env được đọc lại mỗi lần gửi nên không cần khởi động lại Streamlit sau khi sửa.
"""
from __future__ import annotations

import os
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]

# máy chủ gửi thư mặc định theo tên miền của địa chỉ gửi
PROVIDERS = {
    "gmail.com": ("smtp.gmail.com", 587),
    "googlemail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp.office365.com", 587),
    "hotmail.com": ("smtp.office365.com", 587),
    "live.com": ("smtp.office365.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 587),
}


class EmailError(RuntimeError):
    """Lỗi gửi email, thông báo bằng tiếng Việt và nêu cách khắc phục."""


def _truthy(value, default=False):
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def smtp_config() -> dict:
    """Đọc cấu hình SMTP từ .env (đọc lại mỗi lần gọi)."""
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env", override=True)
    username = os.getenv("STOCKLENS_SMTP_USERNAME", "").strip()
    password = os.getenv("STOCKLENS_SMTP_PASSWORD", "").replace(" ", "").strip()
    sender = os.getenv("STOCKLENS_SMTP_FROM", "").strip() or username
    host = os.getenv("STOCKLENS_SMTP_HOST", "").strip()
    port_text = os.getenv("STOCKLENS_SMTP_PORT", "").strip()
    domain = (parseaddr(sender or username)[1].split("@")[-1] or "").lower()
    guessed = PROVIDERS.get(domain)
    if not host and guessed:
        host = guessed[0]
    port = int(port_text) if port_text.isdigit() else (guessed[1] if guessed and not port_text else 587)
    use_ssl = _truthy(os.getenv("STOCKLENS_SMTP_SSL"), default=False) or port == 465
    use_tls = _truthy(os.getenv("STOCKLENS_SMTP_STARTTLS"), default=True) and not use_ssl
    return {"host": host, "port": port, "username": username, "password": password, "sender": sender,
            "ssl": use_ssl, "starttls": use_tls}


def smtp_status() -> dict:
    """Trạng thái cấu hình (không bao giờ trả mật khẩu)."""
    cfg = smtp_config()
    missing = []
    if not cfg["sender"]:
        missing.append("STOCKLENS_SMTP_USERNAME (hoặc STOCKLENS_SMTP_FROM)")
    if not cfg["host"]:
        missing.append("STOCKLENS_SMTP_HOST (không tự nhận được từ địa chỉ email)")
    if cfg["username"] and not cfg["password"]:
        missing.append("STOCKLENS_SMTP_PASSWORD")
    return {"configured": not missing, "missing": missing, "host": cfg["host"], "port": cfg["port"],
            "sender": cfg["sender"], "env_file": str(ROOT / ".env"), "env_exists": (ROOT / ".env").exists()}


def _validate(recipient: str) -> str:
    address = parseaddr(recipient or "")[1]
    if not address or "@" not in address or "." not in address.split("@")[-1]:
        raise EmailError("Địa chỉ email nhận không hợp lệ.")
    return address


def _deliver(message: EmailMessage, cfg: dict) -> None:
    status = smtp_status()
    if not status["configured"]:
        where = "" if status["env_exists"] else f" (chưa có file {status['env_file']})"
        raise EmailError("Chưa cấu hình email gửi" + where + ". Thiếu: " + "; ".join(status["missing"]) +
                         ". Xem file .env.example để thêm các dòng cần thiết vào .env.")
    context = ssl.create_default_context()
    try:
        if cfg["ssl"]:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=25, context=context)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=25)
        with server:
            server.ehlo()
            if cfg["starttls"]:
                server.starttls(context=context)
                server.ehlo()
            if cfg["username"]:
                server.login(cfg["username"], cfg["password"])
            refused = server.send_message(message)
            if refused:
                raise EmailError(f"Máy chủ từ chối người nhận: {refused}")
    except smtplib.SMTPAuthenticationError as exc:
        hint = (" Gmail yêu cầu bật Xác minh 2 bước rồi tạo 'Mật khẩu ứng dụng' (App Password) tại myaccount.google.com/apppasswords, "
                "dán 16 ký tự đó vào STOCKLENS_SMTP_PASSWORD; mật khẩu đăng nhập thường sẽ bị từ chối."
                if "gmail" in cfg["host"] else " Kiểm tra lại tên đăng nhập và mật khẩu (hoặc mật khẩu ứng dụng).")
        raise EmailError(f"Máy chủ {cfg['host']} từ chối đăng nhập (mã {exc.smtp_code}).{hint}") from exc
    except (smtplib.SMTPConnectError, socket.gaierror, socket.timeout, ConnectionError, TimeoutError) as exc:
        raise EmailError(f"Không kết nối được tới {cfg['host']}:{cfg['port']} ({exc}). Kiểm tra mạng/tường lửa hoặc thử cổng 465 với STOCKLENS_SMTP_SSL=true.") from exc
    except ssl.SSLError as exc:
        raise EmailError(f"Lỗi SSL/TLS khi nối {cfg['host']}:{cfg['port']} ({exc}). Cổng 587 dùng STARTTLS; cổng 465 cần STOCKLENS_SMTP_SSL=true.") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailError(f"Địa chỉ nhận bị từ chối: {exc}") from exc
    except smtplib.SMTPException as exc:
        raise EmailError(f"Lỗi SMTP: {exc}") from exc


def send_report_email(recipient: str, ticker: str, company_name: str, pdf_bytes: bytes, filename: str) -> None:
    """Gửi PDF báo cáo. Ném EmailError (thông báo tiếng Việt) nếu thất bại."""
    address = _validate(recipient)
    if not pdf_bytes:
        raise EmailError("Chưa có PDF để gửi (PDF chưa tạo thành công).")
    cfg = smtp_config()
    message = EmailMessage()
    message["Subject"] = f"StockLens | Báo cáo phân tích {ticker}"
    message["From"] = cfg["sender"]
    message["To"] = address
    message.set_content(
        f"Xin chào,\n\nĐính kèm là báo cáo phân tích {ticker} ({company_name}) vừa được tạo trên StockLens.\n\n"
        "Báo cáo phục vụ mục đích học tập và nghiên cứu, không phải khuyến nghị mua/bán hay tư vấn đầu tư cá nhân.\n"
    )
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    _deliver(message, cfg)


def send_test_email(recipient: str) -> None:
    """Gửi thư thử (không đính kèm) để kiểm tra cấu hình SMTP."""
    address = _validate(recipient)
    cfg = smtp_config()
    message = EmailMessage()
    message["Subject"] = "StockLens | Thư thử cấu hình email"
    message["From"] = cfg["sender"]
    message["To"] = address
    message.set_content("Cấu hình gửi email của StockLens hoạt động. Báo cáo PDF sẽ được gửi tới địa chỉ này khi bạn bật gửi.\n")
    _deliver(message, cfg)
