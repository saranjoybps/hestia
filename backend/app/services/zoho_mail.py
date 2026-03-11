import os
import requests
from dotenv import load_dotenv

load_dotenv()

ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN", "sample_access_token")
ZOHO_ACCOUNT_ID = os.getenv("ZOHO_ACCOUNT_ID", "123456789")
ZOHO_FROM_EMAIL = os.getenv("ZOHO_FROM_EMAIL", "test@example.com")

def send_email(to_email: str, subject: str, html_content: str, cc_emails: list[str] | None = None):

    url = f"https://mail.zoho.com/api/accounts/{ZOHO_ACCOUNT_ID}/messages"

    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}"
    }

    data = {
        "fromAddress": ZOHO_FROM_EMAIL,
        "toAddress": to_email,
        "subject": subject,
        "content": html_content
    }

    # Add CC if provided
    if cc_emails:
        data["ccAddress"] = ",".join(cc_emails)

    response = requests.post(url, headers=headers, data=data)

    return response.json()