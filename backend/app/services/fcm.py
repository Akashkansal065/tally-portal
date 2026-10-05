"""Firebase Cloud Messaging (HTTP v1) for the installed Android app: lock-screen notifications.

Off unless FCM_SERVICE_ACCOUNT_JSON holds a Firebase service account: a path to the downloaded key file
(relative paths start at the backend folder), or the JSON itself.
The service account signs a short-lived Google OAuth token, which is cached until shortly before it expires.
"""
import json
import logging
import os
import time
from typing import Dict, List, Optional, Sequence, Tuple

import httpx
import jwt

from app.core.config import settings

logger = logging.getLogger("fcm")

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
ANDROID_CHANNEL_ID = "mytally_alerts"
# FCM error codes meaning the token will never work again. INVALID_ARGUMENT is left out: it can also mean
# a malformed message, which must not wipe every token.
GONE_ERRORS = {"UNREGISTERED", "SENDER_ID_MISMATCH"}

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_account: Optional[dict] = None
_access_token: Tuple[Optional[str], float] = (None, 0.0)


def service_account() -> Optional[dict]:
    """The configured service account, or None when FCM is off or misconfigured."""
    global _account
    raw = (settings.FCM_SERVICE_ACCOUNT_JSON or "").strip()
    if not raw:
        return None
    if _account is None:
        try:
            if not raw.startswith("{"):
                # A path: relative ones are taken from the backend folder (where .env lives), not the cwd
                path = raw if os.path.isabs(raw) else os.path.join(BACKEND_DIR, raw)
                with open(path, encoding="utf-8") as fh:
                    raw = fh.read()
            data = json.loads(raw)
            if not all(data.get(k) for k in ("project_id", "client_email", "private_key")):
                raise ValueError("needs project_id, client_email and private_key")
            _account = data
        except Exception as e:
            logger.warning(f"FCM_SERVICE_ACCOUNT_JSON is not a usable service account: {e}")
            return None
    return _account


def enabled() -> bool:
    return service_account() is not None


async def _oauth_token(client: httpx.AsyncClient, account: dict) -> str:
    global _access_token
    token, expires_at = _access_token
    if token and time.time() < expires_at - 60:
        return token
    now = int(time.time())
    token_uri = account.get("token_uri") or "https://oauth2.googleapis.com/token"
    assertion = jwt.encode(
        {"iss": account["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
        account["private_key"],
        algorithm="RS256",
    )
    res = await client.post(token_uri, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    })
    res.raise_for_status()
    body = res.json()
    _access_token = (body["access_token"], time.time() + int(body.get("expires_in", 3600)))
    return body["access_token"]


def message_for(token: str, payload: dict) -> dict:
    """Turn a web push payload (title, body, tag, data.url ...) into an FCM message for the Android app."""
    data = {k: str(v) for k, v in (payload.get("data") or {}).items() if v is not None}
    return {
        "message": {
            "token": token,
            "notification": {"title": payload.get("title", "MyTally"), "body": payload.get("body", "")},
            "data": data,
            "android": {
                "priority": "high",
                "notification": {
                    "channel_id": ANDROID_CHANNEL_ID,
                    "tag": payload.get("tag") or "mytally",
                    "default_sound": True,
                },
            },
        }
    }


def _is_gone(res: httpx.Response) -> bool:
    if res.status_code == 404:
        return True
    try:
        error = res.json().get("error", {})
    except ValueError:
        return False
    codes = {error.get("status")}
    for detail in error.get("details", []) or []:
        codes.add(detail.get("errorCode"))
    return bool(codes & GONE_ERRORS)


async def send(messages: Sequence[Tuple[str, dict]]) -> Tuple[int, List[str]]:
    """Send (token, payload) pairs. Returns how many were accepted and which tokens are gone for good."""
    account = service_account()
    if not account or not messages:
        return 0, []
    url = f"https://fcm.googleapis.com/v1/projects/{account['project_id']}/messages:send"
    delivered, gone = 0, []
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            access = await _oauth_token(client, account)
        except Exception as e:
            logger.warning(f"FCM sign-in failed: {e}")
            return 0, []
        headers: Dict[str, str] = {"Authorization": f"Bearer {access}"}
        for token, payload in messages:
            try:
                res = await client.post(url, json=message_for(token, payload), headers=headers)
            except Exception as e:
                logger.warning(f"FCM send failed: {e}")
                continue
            if res.is_success:
                delivered += 1
            elif _is_gone(res):
                gone.append(token)
            else:
                logger.warning(f"FCM rejected a message ({res.status_code}): {res.text[:200]}")
    return delivered, gone
