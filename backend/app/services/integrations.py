"""Features that need another provider's API keys or a paid subscription, each behind a per-company on/off switch.

Free features (UPI links, wa.me messages, PDFs, reports, backups...) never appear here. A switch that's off hides
the feature and its API routes refuse it (see require_integration). A switch that's on still only works once the
real connection is built and its keys are set; until then the feature runs as a clearly labelled demo, or not at
all where a demo would be unsafe. Statuses: off, demo, unavailable, needs_setup, connected.
"""
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import Company, CompanyIntegration, User


def _email_keys_set(_company: Company) -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASS)


def _whatsapp_keys_set(_company: Company) -> bool:
    return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_TEMPLATE)


def _gsp_keys_set(company: Company) -> bool:
    from app.services.gsp import gsp_account_ready
    return gsp_account_ready() and bool(company.gstin)


def _einvoice_keys_set(company: Company) -> bool:
    from app.services.gsp import einvoice_ready
    return einvoice_ready(company)


def _eway_keys_set(company: Company) -> bool:
    from app.services.gsp import eway_ready
    return eway_ready(company)


def _gst_demo_mode(company: Company) -> bool:
    """e-Invoice and e-way bill share one mode per company: Demo (made-up numbers) or Live (through the GSP)."""
    return (company.einvoice_env or "mock") == "mock"


@dataclass(frozen=True)
class Integration:
    key: str
    label: str
    description: str
    provider: str
    cost: str
    # Plan phase that builds the real connection (docs/livekeeping-parity-plan.md)
    phase: str
    # The real connection is built
    live: bool = False
    # A labelled demo is safe to run while the real connection isn't built
    demo: bool = False
    # Whether the company's keys are set; only asked once the connection is live
    has_keys: Optional[Callable[[Company], bool]] = None
    # The company chose to keep using the labelled demo even though the real connection is built
    demo_mode: Optional[Callable[[Company], bool]] = None


INTEGRATIONS: Dict[str, Integration] = {i.key: i for i in [
    Integration(
        key="email",
        label="Email (Gmail)",
        description="Send payment reminders by email from the business Gmail account.",
        provider="Gmail (SMTP with an app password)",
        cost="Free, up to about 500 emails a day",
        phase="Phase 2", live=True, has_keys=_email_keys_set,
    ),
    Integration(
        key="whatsapp_api",
        label="WhatsApp messages (automatic)",
        description="Send payment reminders on WhatsApp automatically, with delivery receipts. The tap-to-send WhatsApp button doesn't need this.",
        provider="Meta WhatsApp Cloud API",
        cost="Meta's charge per message",
        phase="Phase 2", live=True, has_keys=_whatsapp_keys_set,
    ),
    Integration(
        key="einvoice",
        label="e-Invoice (IRN and QR code)",
        description="Register B2B sales invoices on the government's invoice portal and print the IRN and QR code.",
        provider="GST Suvidha Provider (MasterGST)",
        cost="GSP charge per e-invoice",
        phase="Phase 4", live=True, demo=True, has_keys=_einvoice_keys_set, demo_mode=_gst_demo_mode,
    ),
    Integration(
        key="eway_bill",
        label="e-Way bill",
        description="Generate e-way bills for goods movements from sales vouchers.",
        provider="GST Suvidha Provider (MasterGST)",
        cost="GSP charge per e-way bill",
        phase="Phase 4", live=True, demo=True, has_keys=_eway_keys_set, demo_mode=_gst_demo_mode,
    ),
    Integration(
        key="gst_portal",
        label="GSTR-2B fetch from the GST portal",
        description="Download GSTR-2B straight from the GST portal with an OTP, instead of uploading the JSON file.",
        provider="GST Suvidha Provider (GSP)",
        cost="GSP subscription",
        phase="Later", has_keys=_gsp_keys_set,
    ),
    Integration(
        key="gst_filing",
        label="GST return submission through a provider",
        description="Send a locked GSTR-1 period to the GST portal through a GSP. Marking a return filed with its ARN doesn't need this.",
        provider="GST Suvidha Provider (GSP)",
        cost="GSP subscription",
        phase="Later", demo=True,
    ),
    Integration(
        key="payment_gateway",
        label="Online payment links (Razorpay / Stripe)",
        description="Card and net-banking payment links that mark the bill paid automatically. UPI links and QR codes don't need this.",
        provider="Razorpay or Stripe",
        cost="Gateway fee on each payment",
        phase="Phase 2b",
    ),
]}


def get_integration(key: str) -> Integration:
    if key not in INTEGRATIONS:
        raise KeyError(key)
    return INTEGRATIONS[key]


async def enabled_keys(db: AsyncSession, company_id: int) -> Set[str]:
    rows = await db.execute(select(CompanyIntegration.key).where(
        CompanyIntegration.company_id == company_id, CompanyIntegration.enabled.is_(True)))
    return {key for key in rows.scalars().all() if key in INTEGRATIONS}


async def is_enabled(db: AsyncSession, company_id: int, key: str) -> bool:
    return key in await enabled_keys(db, company_id)


async def set_enabled(db: AsyncSession, company_id: int, key: str, enabled: bool, user_id: Optional[int]) -> CompanyIntegration:
    """Switch one integration on or off (the caller commits). Raises KeyError for an unknown key."""
    get_integration(key)
    row = (await db.execute(select(CompanyIntegration).where(
        CompanyIntegration.company_id == company_id, CompanyIntegration.key == key))).scalars().first()
    if row:
        row.enabled = enabled
        row.updated_by_user_id = user_id
    else:
        row = CompanyIntegration(company_id=company_id, key=key, enabled=enabled, updated_by_user_id=user_id)
        db.add(row)
    return row


def status_of(integration: Integration, enabled: bool, company: Optional[Company]) -> str:
    if not enabled:
        return "off"
    if not integration.live:
        return "demo" if integration.demo else "unavailable"
    if company is not None and integration.demo_mode and integration.demo_mode(company):
        return "demo"
    keys_set = bool(company is not None and integration.has_keys and integration.has_keys(company))
    return "connected" if keys_set else "needs_setup"


async def integration_statuses(db: AsyncSession, company_id: int) -> List[dict]:
    company = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    on = await enabled_keys(db, company_id)
    return [
        {
            "key": i.key, "label": i.label, "description": i.description, "provider": i.provider,
            "cost": i.cost, "phase": i.phase, "live": i.live, "enabled": i.key in on,
            "status": status_of(i, i.key in on, company),
        }
        for i in INTEGRATIONS.values()
    ]


def switched_off(key: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"{get_integration(key).label} is switched off. An admin can turn it on in Admin → Integrations.",
    )


def not_available_yet(key: str, hint: str = "") -> HTTPException:
    integration = get_integration(key)
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{integration.label} isn't connected yet (planned for {integration.phase}).{(' ' + hint) if hint else ''}",
    )


def require_integration(key: str):
    """Route dependency: refuse unless the integration is switched on for the user's company."""
    get_integration(key)

    async def dependency(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
        if not await is_enabled(db, user.company_id, key):
            raise switched_off(key)
        return user
    return dependency
