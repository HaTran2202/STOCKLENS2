"""Send generated StockLens PDFs using SMTP settings from the environment."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def send_report_email(recipient: str, ticker: str, company_name: str, pdf_bytes: bytes, filename: str) -> None:
    host = os.getenv("STOCKLENS_SMTP_HOST", "").strip()
    port = int(os.getenv("STOCKLENS_SMTP_PORT", "587"))
    username = os.getenv("STOCKLENS_SMTP_USERNAME", "").strip()
    password = os.getenv("STOCKLENS_SMTP_PASSWORD", "")
    sender = os.getenv("STOCKLENS_SMTP_FROM", "").strip() or username
    use_ssl = os.getenv("STOCKLENS_SMTP_SSL", "").strip().lower() in {"1", "true", "yes"} or port == 465
    use_tls = os.getenv("STOCKLENS_SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes"}

    if not host or not sender:
        raise RuntimeError("Ch\u01b0a c\u1ea5u h\u00ecnh email g\u1eedi. H\u00e3y \u0111\u1eb7t STOCKLENS_SMTP_HOST v\u00e0 STOCKLENS_SMTP_FROM (ho\u1eb7c STOCKLENS_SMTP_USERNAME) trong .env.")
    parsed_recipient = parseaddr(recipient)[1]
    if not parsed_recipient or "@" not in parsed_recipient:
        raise ValueError("\u0110\u1ecba ch\u1ec9 email nh\u1eadn kh\u00f4ng h\u1ee3p l\u1ec7.")
    if username and not password:
        raise RuntimeError("Thi\u1ebfu STOCKLENS_SMTP_PASSWORD trong .env.")

    message = EmailMessage()
    message["Subject"] = f"StockLens | B\u00e1o c\u00e1o ph\u00e2n t\u00edch {ticker}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Xin ch\u00e0o,\n\n\u0110\u00ednh k\u00e8m l\u00e0 b\u00e1o c\u00e1o ph\u00e2n t\u00edch {ticker} ({company_name}) v\u1eeba \u0111\u01b0\u1ee3c t\u1ea1o tr\u00ean StockLens.\n\n"
        "B\u00e1o c\u00e1o ph\u1ee5c v\u1ee5 m\u1ee5c \u0111\u00edch h\u1ecdc t\u1eadp v\u00e0 nghi\u00ean c\u1ee9u, kh\u00f4ng ph\u1ea3i khuy\u1ebfn ngh\u1ecb mua/b\u00e1n hay t\u01b0 v\u1ea5n \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n.\n"
    )
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=25, context=context) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=context)
                server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)
