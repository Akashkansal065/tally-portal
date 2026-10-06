"""Talking to the GST Suvidha Provider (GSP) for e-invoices (IRN) and e-way bills.

Only MasterGST is built. Everything specific to it (paths, headers, response shapes) is in MasterGst below and
follows its published API conventions; check it against MasterGST's API reference PDF when the sandbox keys
arrive, since that PDF is only available after signing up. Callers use the provider-neutral methods and get
plain dicts back, or a GspError with a message fit to show.

Keys: the GSP account (GSP_EMAIL, GSP_CLIENT_ID, GSP_CLIENT_SECRET) is in the server settings; each company's
GSTIN and its e-invoice / e-way bill portal API username and password are on the company record.
"""
import json
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.portal_core import Company

logger = get_logger("app.services.gsp")


class GspError(Exception):
    """A refusal or failure from the GSP / government portal, with a message fit to show."""


def gsp_account_ready() -> bool:
    return bool(settings.GSP_EMAIL and settings.GSP_CLIENT_ID and settings.GSP_CLIENT_SECRET)


def einvoice_ready(company: Company) -> bool:
    return gsp_account_ready() and bool(company.gstin and company.einvoice_username and company.einvoice_password)


def eway_ready(company: Company) -> bool:
    return gsp_account_ready() and bool(company.gstin and company.eway_username and company.eway_password)


def _error_text(body: Any) -> str:
    """Pull the human message out of the provider's error shapes (status_desc may hold a JSON list of errors)."""
    if not isinstance(body, dict):
        return str(body)[:300]
    for key in ("status_desc", "error", "message", "ErrorDetails"):
        value = body.get(key)
        if not value:
            continue
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return value[:300]
        if isinstance(value, list):
            return "; ".join(str(v.get("ErrorMessage") or v.get("message") or v) for v in value if v)[:300]
        if isinstance(value, dict):
            return str(value.get("message") or value.get("ErrorMessage") or value)[:300]
    return "The GST portal refused the request."


class MasterGst:
    """MasterGST (https://mastergst.com). Paths and headers per its public API conventions."""

    EINVOICE_VERSION = "V1_03"
    EWAY_VERSION = "v1.03"

    def __init__(self) -> None:
        self.base = settings.GSP_BASE_URL.rstrip("/")
        # (kind, gstin) -> (token, expires at)
        self._tokens: Dict[Tuple[str, str], Tuple[str, float]] = {}

    def _headers(self, company: Company) -> Dict[str, str]:
        return {"ip_address": settings.GSP_IP_ADDRESS, "client_id": settings.GSP_CLIENT_ID or "",
                "client_secret": settings.GSP_CLIENT_SECRET or "", "gstin": company.gstin or ""}

    async def _call(self, method: str, path: str, headers: Dict[str, str], params: Optional[dict] = None,
                    body: Optional[dict] = None) -> dict:
        params = {"email": settings.GSP_EMAIL, **(params or {})}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.request(method, f"{self.base}{path}", params=params, headers=headers, json=body)
            data = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as e:
            raise GspError(f"Couldn't reach the GST provider ({type(e).__name__}). Try again in a minute.")
        status = str(data.get("status_cd", "")).lower() if isinstance(data, dict) else ""
        if response.is_error or status in ("0", "error") or not isinstance(data, dict) or data.get("data") in (None, ""):
            raise GspError(_error_text(data))
        result = data["data"]
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                pass
        return result if isinstance(result, dict) else {"value": result}

    # ── e-invoice ──

    async def _einvoice_token(self, company: Company, fresh: bool = False) -> str:
        key = ("einvoice", company.gstin)
        cached = self._tokens.get(key)
        if cached and not fresh and cached[1] > time.time():
            return cached[0]
        data = await self._call("GET", "/einvoice/authenticate",
                                {**self._headers(company), "username": company.einvoice_username,
                                 "password": company.einvoice_password})
        token = data.get("AuthToken")
        if not token:
            raise GspError("The e-invoice portal didn't accept the API username / password.")
        self._tokens[key] = (token, time.time() + 5 * 3600)  # tokens last 6 hours; renew a little early
        return token

    async def _einvoice(self, company: Company, kind: str, body: Optional[dict] = None, method: str = "POST",
                        params: Optional[dict] = None) -> dict:
        for attempt in (0, 1):
            token = await self._einvoice_token(company, fresh=attempt == 1)
            headers = {**self._headers(company), "username": company.einvoice_username, "auth-token": token}
            try:
                return await self._call(method, f"/einvoice/type/{kind}/version/{self.EINVOICE_VERSION}", headers,
                                        params=params, body=body)
            except GspError as e:
                if attempt == 0 and "token" in str(e).lower():
                    continue  # expired token: sign in again once
                raise
        raise GspError("The e-invoice portal session couldn't be renewed.")

    async def generate_irn(self, company: Company, payload: dict) -> dict:
        """→ Irn, AckNo, AckDt, SignedInvoice, SignedQRCode, (EwbNo, EwbDt, EwbValidTill when e-way details sent)."""
        return await self._einvoice(company, "GENERATE", payload)

    async def cancel_irn(self, company: Company, irn: str, reason: str, remark: str) -> dict:
        return await self._einvoice(company, "CANCEL", {"Irn": irn, "CnlRsn": reason, "CnlRem": remark[:100]})

    async def get_irn(self, company: Company, irn: str) -> dict:
        return await self._einvoice(company, "GETIRN", method="GET", params={"param1": irn})

    async def ewaybill_by_irn(self, company: Company, body: dict) -> dict:
        """→ EwbNo, EwbDt, EwbValidTill"""
        return await self._einvoice(company, "GENERATE_EWAYBILL", body)

    # ── e-way bill ──

    async def _eway_headers(self, company: Company, fresh: bool = False) -> Dict[str, str]:
        key = ("eway", company.gstin)
        cached = self._tokens.get(key)
        if not cached or fresh or cached[1] <= time.time():
            await self._call("GET", f"/ewaybillapi/{self.EWAY_VERSION}/authenticate", self._headers(company),
                             params={"username": company.eway_username, "password": company.eway_password})
            self._tokens[key] = ("session", time.time() + 5 * 3600)
        return self._headers(company)

    async def _eway(self, company: Company, action: str, body: dict) -> dict:
        for attempt in (0, 1):
            headers = await self._eway_headers(company, fresh=attempt == 1)
            try:
                return await self._call("POST", f"/ewaybillapi/{self.EWAY_VERSION}/ewayapi/{action}", headers, body=body)
            except GspError as e:
                if attempt == 0 and ("token" in str(e).lower() or "auth" in str(e).lower()):
                    continue
                raise
        raise GspError("The e-way bill session couldn't be renewed.")

    async def generate_ewaybill(self, company: Company, payload: dict) -> dict:
        """→ ewayBillNo, ewayBillDate, validUpto"""
        return await self._eway(company, "genewaybill", payload)

    async def cancel_ewaybill(self, company: Company, ewb_no: str, reason: str, remark: str) -> dict:
        return await self._eway(company, "canewb", {"ewbNo": int(ewb_no), "cancelRsnCode": int(reason), "cancelRmrk": remark[:50]})

    async def update_vehicle(self, company: Company, body: dict) -> dict:
        """→ vehUpdDate, validUpto"""
        return await self._eway(company, "vehewb", body)


_provider: Optional[MasterGst] = None


def provider() -> MasterGst:
    global _provider
    if settings.GSP_PROVIDER != "mastergst":
        raise GspError(f"GST provider '{settings.GSP_PROVIDER}' isn't supported yet (only mastergst).")
    if _provider is None:
        _provider = MasterGst()
    return _provider
