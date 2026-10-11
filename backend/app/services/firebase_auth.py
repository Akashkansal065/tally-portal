"""Sign-in with a mobile number, confirmed by Firebase Authentication.

The app sends the OTP and confirms it with Firebase itself, then hands the server the ID token Firebase gave it.
This module checks that token: signed by Google for our Firebase project, not expired, from a phone sign-in,
and recent. Nothing here sends an SMS and no Firebase secret is needed, only the project id.

Off unless PHONE_SIGNIN_ENABLED is on and the Firebase project is known (FIREBASE_PROJECT_ID, or the project
of FCM_SERVICE_ACCOUNT_JSON).
"""
import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import httpx
import jwt
from cryptography import x509

from app.core.config import settings
from app.services import fcm

logger = logging.getLogger("firebase_auth")

# The certificates Firebase signs ID tokens with. Google rotates them; the answer says how long it may be kept.
CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
E164 = re.compile(r"^\+[1-9]\d{7,14}$")

_certs: Tuple[Dict[str, str], float] = ({}, 0.0)


class PhoneSignInOff(Exception):
    """Mobile number sign-in is not set up on this server."""


class PhoneTokenError(Exception):
    """The token is not proof of a confirmed mobile number. The message can be shown to the person."""


@dataclass
class VerifiedPhone:
    phone: str   # E.164, as Firebase confirmed it
    uid: str     # the Firebase user id


def e164(raw: Optional[str]) -> Optional[str]:
    """A typed mobile number in the form Firebase confirms numbers in (+919900000001), or None when it is not
    one. Ten digits with no country code are taken as Indian."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if (raw or "").strip().startswith("+"):
        number = "+" + digits
    elif len(digits) == 10:
        number = "+91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        number = "+91" + digits[1:]
    else:
        return None
    return number if E164.match(number) else None


def project_id() -> Optional[str]:
    if not settings.PHONE_SIGNIN_ENABLED:
        return None
    configured = (settings.FIREBASE_PROJECT_ID or "").strip()
    if configured:
        return configured
    account = fcm.service_account()
    return account["project_id"] if account else None


def enabled() -> bool:
    return project_id() is not None


async def _signing_certs(refresh: bool = False) -> Dict[str, str]:
    global _certs
    certs, expires_at = _certs
    if certs and not refresh and time.time() < expires_at:
        return certs
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(CERTS_URL)
        res.raise_for_status()
    max_age = re.search(r"max-age=(\d+)", res.headers.get("cache-control", ""))
    _certs = (res.json(), time.time() + (int(max_age.group(1)) if max_age else 3600))
    return _certs[0]


async def verify_phone_token(id_token: str) -> VerifiedPhone:
    """The mobile number a Firebase ID token proves, or PhoneTokenError."""
    project = project_id()
    if project is None:
        raise PhoneSignInOff()
    expired = PhoneTokenError("That code has expired. Ask for a new one.")
    invalid = PhoneTokenError("The mobile number could not be confirmed. Ask for a new code.")
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError:
        raise invalid
    kid = header.get("kid")
    if header.get("alg") != "RS256" or not kid:
        raise invalid
    try:
        certs = await _signing_certs()
        if kid not in certs:
            certs = await _signing_certs(refresh=True)   # Google has rotated its keys since we last looked
    except Exception as e:
        logger.error(f"Firebase's signing certificates could not be fetched: {e}")
        raise PhoneTokenError("Sign-in is unavailable for a moment. Try again.")
    if kid not in certs:
        raise invalid
    try:
        key = x509.load_pem_x509_certificate(certs[kid].encode()).public_key()
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=project,
                            issuer=f"https://securetoken.google.com/{project}",
                            options={"require": ["exp", "iat", "aud", "iss", "sub"]})
    except jwt.ExpiredSignatureError:
        raise expired
    except Exception:
        raise invalid

    uid = str(claims.get("sub") or "")
    phone = str(claims.get("phone_number") or "")
    # Only a phone sign-in counts: a token from another provider of the same project proves no number
    if not uid or (claims.get("firebase") or {}).get("sign_in_provider") != "phone" or not E164.match(phone):
        raise invalid
    try:
        confirmed_at = int(claims.get("auth_time") or 0)
    except (TypeError, ValueError):
        raise invalid
    if time.time() - confirmed_at > settings.PHONE_OTP_MAX_AGE_MINUTES * 60:
        raise expired
    return VerifiedPhone(phone=phone, uid=uid)
