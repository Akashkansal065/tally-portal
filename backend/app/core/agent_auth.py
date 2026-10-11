"""How the Desktop Sync Agent proves who it is.

The agent signs in as a PC (a device of one account), not as a person. A person proves who they are once, at
sign-up or sign-in; the PC is then given a device token that can call the sync and agent endpoints for the
companies linked to it, and nothing else.
"""
import hashlib
import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import (
    Account, AgentCompanyLink, AgentDevice, Company, Module, User, UserPermissionOverride,
)

DEVICE_TOKEN_PREFIX = "mta_"
# The permission that lets a person sign in to the agent, link companies and manage synced PCs. Held as an
# explicit grant: being an admin is not enough.
SYNC_AGENT_MODULE = "sync_agent"
# What a device token may call. Everything else answers 403, so a token lifted from a PC cannot browse the app.
DEVICE_PATH_SUFFIXES = (
    "/sync/outbound-queue", "/sync/acknowledge", "/sync/voucher-identities", "/sync/last-alter-id",
    "/sync/inbound", "/sync/state",
)
DEVICE_LAST_SEEN_INTERVAL_SECONDS = 60
_device_last_seen_written: Dict[int, float] = {}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_token() -> Tuple[str, str]:
    """A fresh device token and the hash to store. The token itself is shown to the agent once and never kept."""
    token = DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(40)
    return token, hash_token(token)


def is_device_token(token: Optional[str]) -> bool:
    return bool(token) and token.startswith(DEVICE_TOKEN_PREFIX)


def device_may_call(path: str) -> bool:
    return "/agent/" in path or path.endswith(DEVICE_PATH_SUFFIXES)


def agent_device(request: Request) -> Optional[AgentDevice]:
    """The device this request is signed in as, or None when a person is."""
    return getattr(request.state, "agent_device", None)


def _unauthorized(reason: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer", "X-Auth-Reason": reason})


async def authenticate_device(request: Request, token: str, db: AsyncSession) -> User:
    """Check a device token and return the person the device acts for (whoever signed the PC in). The device is
    left on request.state for the handlers that need it."""
    if not device_may_call(request.url.path):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="A sync agent's sign-in can only be used for syncing.")
    device = (await db.execute(
        select(AgentDevice).where(AgentDevice.token_hash == hash_token(token)))).scalars().first()
    if device is None:
        raise _unauthorized("invalid", "This PC is not signed in. Sign in to the sync agent again.")
    if device.revoked_at is not None:
        raise _unauthorized("admin_revoke", "This PC was signed out by an administrator.")
    account = (await db.execute(select(Account).where(Account.account_id == device.account_id))).scalars().first()
    if account is None or account.status != "active":
        raise _unauthorized("deactivated", "This account is closed.")
    user = None
    if device.registered_by_user_id is not None:
        user = (await db.execute(
            select(User).options(selectinload(User.role))
            .where(User.user_id == device.registered_by_user_id, User.is_active == True)  # noqa: E712
        )).scalars().first()
    if user is None or user.account_id != device.account_id:
        raise _unauthorized("deactivated", "The person who signed this PC in is no longer active. Sign in again.")

    now = time.time()
    if now - _device_last_seen_written.get(device.device_id, 0) >= DEVICE_LAST_SEEN_INTERVAL_SECONDS:
        _device_last_seen_written[device.device_id] = now
        try:  # in its own short transaction: activity tracking never commits or fails the request's work
            async with AsyncSession(db.bind, expire_on_commit=False) as touch_db:
                await touch_db.execute(update(AgentDevice).where(AgentDevice.device_id == device.device_id)
                                       .values(last_seen_at=get_ist_now()))
                await touch_db.commit()
        except Exception:
            pass
    request.state.agent_device = device
    return user


COPY_MISMATCH = "company_copy_mismatch"


def different_copy(company: Company, fingerprint: Optional[str]) -> bool:
    """Whether the company open in Tally is another copy of the books than the one this company was linked
    from. A copied or restored company keeps its GUID; its Tally company number or books-from date gives it
    away. Nothing to compare (an older agent, or a company linked before fingerprints) is not a difference."""
    return bool(fingerprint and company.tally_fingerprint and fingerprint.strip() != company.tally_fingerprint.strip())


def copy_mismatch_error(company: Company) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, headers={"X-Sync-Reason": COPY_MISMATCH},
        detail=f"The '{company.name}' open in Tally is a different copy of the books from the one that is synced "
               "(its Tally company number or books-from date differs). Sync is stopped so two sets of books are not "
               "mixed. If the company was moved or restored on purpose, unlink it in the agent's Companies window "
               "and link it again.")


async def device_company(db: AsyncSession, device: AgentDevice, tally_guid: str, fingerprint: Optional[str] = None) -> Company:
    """The company of the device's account linked to this Tally GUID, which this device is the one syncing.
    With a fingerprint, a different copy of the books under the same GUID is refused."""
    companies = (await db.execute(
        select(Company).where(Company.account_id == device.account_id, Company.tally_guid == tally_guid)
    )).scalars().all()
    if not companies:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, headers={"X-Sync-Reason": "company_not_linked"},
                            detail="This Tally company is not linked yet. Link it in the sync agent's Companies screen.")
    if len(companies) > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, headers={"X-Sync-Reason": "company_ambiguous"},
                            detail=f"More than one company is linked to Tally company GUID {tally_guid}.")
    company = companies[0]
    linked = (await db.execute(select(AgentCompanyLink.link_id).where(
        AgentCompanyLink.device_id == device.device_id, AgentCompanyLink.company_id == company.company_id,
        AgentCompanyLink.is_active == True))).scalars().first()  # noqa: E712
    if linked is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, headers={"X-Sync-Reason": "company_not_linked_to_device"},
                            detail=f"'{company.name}' is not synced from this PC.")
    if different_copy(company, fingerprint):
        raise copy_mismatch_error(company)
    return company


# ─── "Manage sync agent" ─────────────────────────────────────────────────────

async def sync_agent_module(db: AsyncSession) -> Module:
    module = (await db.execute(select(Module).where(Module.code == SYNC_AGENT_MODULE))).scalars().first()
    if module is None:
        module = Module(code=SYNC_AGENT_MODULE, name="Manage sync agent",
                        description="Sign in to the Desktop Sync Agent, link companies and manage synced PCs", is_system=True)
        db.add(module)
        await db.flush()
    return module


def _holds_sync_agent(module_id: int):
    return (
        UserPermissionOverride.module_id == module_id,
        UserPermissionOverride.can_read == True,  # noqa: E712
        or_(UserPermissionOverride.expires_at.is_(None), UserPermissionOverride.expires_at > get_ist_now()),
    )


async def can_manage_sync_agent(db: AsyncSession, user_id: int) -> bool:
    module = (await db.execute(select(Module).where(Module.code == SYNC_AGENT_MODULE))).scalars().first()
    if module is None:
        return False
    return (await db.execute(select(UserPermissionOverride.override_id).where(
        UserPermissionOverride.user_id == user_id, *_holds_sync_agent(module.module_id)))).scalars().first() is not None


async def needs_tally_setup(db: AsyncSession, user: User) -> bool:
    """Whether this person has to connect a Tally PC before using the app: their business was created in the
    app and still has neither a Tally company nor a PC signed in to the sync agent. Asked only of people who
    can do something about it (they hold "Manage sync agent"); nobody else is ever held up."""
    if user.account_id is None:
        return False
    awaiting = (await db.execute(select(Company.company_id).where(
        Company.account_id == user.account_id, Company.awaiting_tally == True).limit(1))).scalars().first()  # noqa: E712
    if awaiting is None:
        return False
    connected = (await db.execute(select(AgentDevice.device_id).where(
        AgentDevice.account_id == user.account_id, AgentDevice.revoked_at.is_(None)).limit(1))).scalars().first()
    if connected is not None:
        return False
    return await can_manage_sync_agent(db, user.user_id)


async def sync_agent_holders(db: AsyncSession, account_id: int) -> list:
    """Active users of the account who may use the sync agent."""
    module = (await db.execute(select(Module).where(Module.code == SYNC_AGENT_MODULE))).scalars().first()
    if module is None:
        return []
    return list((await db.execute(
        select(User.user_id).join(UserPermissionOverride, UserPermissionOverride.user_id == User.user_id)
        .where(User.account_id == account_id, User.is_active == True, *_holds_sync_agent(module.module_id))  # noqa: E712
    )).scalars().all())


async def grant_sync_agent(db: AsyncSession, user_id: int, granted_by: int, reason: str) -> None:
    """Give a user "Manage sync agent". Does nothing when they hold it already."""
    module = await sync_agent_module(db)
    existing = (await db.execute(select(UserPermissionOverride).where(
        UserPermissionOverride.user_id == user_id, UserPermissionOverride.module_id == module.module_id))).scalars().first()
    if existing is None:
        db.add(UserPermissionOverride(user_id=user_id, module_id=module.module_id, can_create=True, can_read=True,
                                      can_update=True, can_delete=True, reason=reason, granted_by=granted_by))
    else:
        existing.can_create = existing.can_read = existing.can_update = existing.can_delete = True
        existing.expires_at = None
    await db.flush()


async def revoke_sync_agent(db: AsyncSession, user_id: int) -> None:
    module = await sync_agent_module(db)
    for row in (await db.execute(select(UserPermissionOverride).where(
            UserPermissionOverride.user_id == user_id, UserPermissionOverride.module_id == module.module_id))).scalars():
        await db.delete(row)
    await db.flush()
