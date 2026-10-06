"""Sending messages to customers: email through Gmail SMTP and WhatsApp template messages through Meta's
WhatsApp Cloud API. Callers check the integration switches first (app/services/integrations.py); these functions
only need the keys in settings. Neither ever raises for a delivery problem: they return a SendResult."""
import asyncio
import hashlib
import hmac
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import List, Optional, Sequence, Tuple

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("app.services.messaging")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class SendResult:
    ok: bool
    provider_message_id: Optional[str] = None
    error: Optional[str] = None


def clean_email(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value if EMAIL_PATTERN.match(value) else None


def whatsapp_number(value: Optional[str]) -> Optional[str]:
    """Digits with the country code, as Meta wants them (no +). Indian 10-digit mobiles get 91; a leading 0 is
    dropped. Anything that doesn't look like a mobile number gives None."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    return None


# (filename, content, MIME type), e.g. ("Invoice_S-101.pdf", b"%PDF...", "application/pdf")
Attachment = Tuple[str, bytes, str]


def _send_email_blocking(to: str, subject: str, text: str, html: Optional[str], from_name: str,
                         attachments: Sequence[Attachment] = ()) -> SendResult:
    message = EmailMessage()
    message["From"] = formataddr((from_name, settings.SMTP_USER))
    message["To"] = to
    message["Subject"] = subject
    message_id = make_msgid(domain=(settings.SMTP_USER or "mytally").split("@")[-1])
    message["Message-ID"] = message_id
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    for filename, content, mime in attachments:
        maintype, _, subtype = mime.partition("/")
        message.add_attachment(content, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
            refused = smtp.send_message(message)
        if refused:
            return SendResult(False, error=f"Refused by Gmail: {', '.join(refused)}")
        return SendResult(True, provider_message_id=message_id.strip("<>"))
    except smtplib.SMTPAuthenticationError:
        return SendResult(False, error="Gmail rejected the login. SMTP_PASS must be an app password for SMTP_USER.")
    except (smtplib.SMTPException, OSError) as e:
        return SendResult(False, error=f"Email not sent: {type(e).__name__}: {str(e)[:200]}")


async def send_email(to: str, subject: str, text: str, html: Optional[str] = None, from_name: Optional[str] = None,
                     attachments: Sequence[Attachment] = ()) -> SendResult:
    if not (settings.SMTP_USER and settings.SMTP_PASS):
        return SendResult(False, error="Email isn't set up (SMTP_USER / SMTP_PASS).")
    return await asyncio.to_thread(_send_email_blocking, to, subject, text, html,
                                   from_name or settings.SMTP_FROM_NAME or "Accounts", attachments)


async def send_whatsapp_template(to: str, parameters: List[str]) -> SendResult:
    """Send the approved reminder template (WHATSAPP_TEMPLATE) with its body parameters in order."""
    if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_TEMPLATE):
        return SendResult(False, error="WhatsApp isn't set up (access token, phone number id, template).")
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_TEMPLATE,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANG},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parameters]}],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=body, headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"})
        data = response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as e:
        return SendResult(False, error=f"WhatsApp not reached: {type(e).__name__}")
    if response.is_error:
        error = (data.get("error") or {}) if isinstance(data, dict) else {}
        return SendResult(False, error=f"WhatsApp refused ({response.status_code}): {str(error.get('message') or data)[:300]}")
    messages = data.get("messages") or []
    return SendResult(True, provider_message_id=messages[0].get("id") if messages else None)


def whatsapp_signature_valid(body: bytes, signature_header: Optional[str]) -> bool:
    """Meta signs webhook calls with the app secret (X-Hub-Signature-256: sha256=<hex>)."""
    if not settings.WHATSAPP_APP_SECRET or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256="):])
