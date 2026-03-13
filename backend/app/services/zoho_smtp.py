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


def send_onboarding_email(
    *,
    to_email: str,
    employee_name: str,
    password: str,
    role: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    manager: Optional[str] = None,
    lead: Optional[str] = None,
):
    """Send onboarding email with credentials and employee details."""
    subject = "Welcome to JoyBps - Your JoyHR Access"

    details_lines = [
        f"Name: {employee_name}",
        f"Email: {to_email}",
    ]

    if role:
        details_lines.append(f"Role: {role}")
    if department:
        details_lines.append(f"Department: {department}")
    if designation:
        details_lines.append(f"Designation: {designation}")
    if manager:
        details_lines.append(f"Manager: {manager}")
    if lead:
        details_lines.append(f"Lead: {lead}")

    details_block = "\n".join(details_lines)

    body = (
        f"Hello {employee_name},\n\n"
        "Welcome to JoyBps. Your JoyHR account has been created.\n\n"
        "Login URL: https://hr.joyrts.com/\n"
        f"Username: {to_email}\n"
        f"Temporary Password: {password}\n\n"
        "Employee Details:\n"
        f"{details_block}\n\n"
        "Please change your password after your first login. If you need any help,"
        " please contact HR.\n\n"
        "Regards,\n"
        "JoyBps"
    )

    send_email_smtp(to_email=to_email, subject=subject, body=body)
