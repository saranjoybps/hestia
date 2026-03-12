import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional
from app.config import get_settings


def send_email_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    cc_emails: Optional[Iterable[str]] = None
) -> None:
    """Send an email using Zoho SMTP."""
    settings = get_settings()
    smtp_host = settings.zoho_smtp_host or os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.in")
    smtp_port = settings.zoho_smtp_port or int(os.getenv("ZOHO_SMTP_PORT", "587"))
    smtp_user = settings.zoho_email or os.getenv("ZOHO_EMAIL")
    smtp_pass = settings.zoho_password or os.getenv("ZOHO_PASSWORD")

    if not smtp_user or not smtp_pass:
        raise ValueError("Missing ZOHO_EMAIL or ZOHO_PASSWORD for SMTP")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
