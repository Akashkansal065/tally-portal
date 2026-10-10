"""Running an account's people and PCs from the app: invitations, who may use the sync agent, and the PCs
that are signed in to it. Everything here stays inside the caller's own account."""
import logging
import secrets
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.agent_auth import (
    can_manage_sync_agent, grant_sync_agent, hash_token, now_utc, revoke_sync_agent, sync_agent_holders,
)
from app.core.account_roles import role_in_account
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import ADMIN_ROLE_NAMES
from app.core.rate_limiter import limiter
from app.core.security import get_password_hash
from app.models.portal_core import (
    Account, AgentCompanyLink, AgentDevice, Company, Role, User, UserCompanyAccess, UserInvite,
)
from app.routers.admin import require_admin
from app.services import messaging

logger = logging.getLogger("app.routers.team")
router = APIRouter(prefix="/admin", tags=["Account team"])
public_router = APIRouter(prefix="/auth/invites", tags=["Invitations"])

INVITE_TTL_DAYS = 7


class InviteCreate(BaseModel):
    email: str = Field(max_length=120)
    role_id: int
    company_ids: List[int] = Field(min_length=1)
    phone: Optional[str] = Field(default=None, max_length=20)


class InviteAccept(BaseModel):
    token: str
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class SyncAgentAccess(BaseModel):
    allowed: bool


async def _account(db: AsyncSession, admin: User) -> Account:
    if admin.account_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This server's data has not been moved into an account yet.")
    return (await db.execute(select(Account).where(Account.account_id == admin.account_id))).scalars().first()


async def _require_sync_agent(db: AsyncSession, admin: User) -> None:
    if not await can_manage_sync_agent(db, admin.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only an admin with the 'Manage sync agent' permission can do this.")


async def _check_user_limit(db: AsyncSession, account: Account) -> None:
    if account.max_users is None:
        return
    users = (await db.execute(select(func.count()).select_from(User).where(
        User.account_id == account.account_id, User.is_active == True))).scalar() or 0  # noqa: E712
    if users >= account.max_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This account's plan allows {account.max_users} user(s).")


# ─── Invitations ─────────────────────────────────────────────────────────────

def _invite_dict(invite: UserInvite) -> dict:
    return {
        "invite_id": invite.invite_id, "email": invite.email, "phone": invite.phone, "role_id": invite.role_id,
        "company_ids": invite.company_ids or [], "expires_at": invite.expires_at.isoformat(),
        "status": "accepted" if invite.accepted_at else "open" if invite.is_open and invite.expires_at > now_utc() else "closed",
    }


@router.post("/invites")
async def create_invite(payload: InviteCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Invite someone into the admin's account. A new invitation for the same email replaces the open one."""
    account = await _account(db, admin)
    email = messaging.clean_email(payload.email)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address.")
    email = email.lower()
    if (await db.execute(select(User.user_id).where(func.lower(User.email) == email))).scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")
    if (await db.execute(select(Role.role_id).where(
            Role.role_id == payload.role_id, role_in_account(account.account_id)))).scalars().first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found.")
    own = set((await db.execute(select(Company.company_id).where(
        Company.account_id == account.account_id, Company.company_id.in_(payload.company_ids)))).scalars().all())
    if own != set(payload.company_ids):
        # Another account's company and a company that does not exist get the same answer
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    await _check_user_limit(db, account)

    for earlier in (await db.execute(select(UserInvite).where(
            UserInvite.account_id == account.account_id, UserInvite.email == email, UserInvite.is_open == True))).scalars():  # noqa: E712
        earlier.is_open = None
    await db.flush()
    token = secrets.token_urlsafe(32)
    invite = UserInvite(account_id=account.account_id, email=email, phone=payload.phone, role_id=payload.role_id,
                        company_ids=sorted(own), token_hash=hash_token(token), is_open=True,
                        expires_at=now_utc() + timedelta(days=INVITE_TTL_DAYS), invited_by_user_id=admin.user_id)
    db.add(invite)
    await db.commit()

    base = (settings.APP_PUBLIC_URL or "").rstrip("/")
    how = f"Open {base}/accept-invite?token={token}" if base else f"Open the app, choose 'Accept invite' and enter this code:\n\n{token}"
    sent = await messaging.send_email(
        email, f"You are invited to {account.name} on MyTally",
        f"{admin.username} invited you to join {account.name}.\n\n{how}\n\nThe invitation expires in {INVITE_TTL_DAYS} days.")
    # The token is shown to the admin once, so the invitation can be passed on when email is not set up
    return {**_invite_dict(invite), "invite_token": token, "email_sent": sent.ok}


@router.get("/invites")
async def list_invites(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    account = await _account(db, admin)
    rows = (await db.execute(select(UserInvite).where(UserInvite.account_id == account.account_id)
                             .order_by(UserInvite.invite_id.desc()).limit(200))).scalars().all()
    return [_invite_dict(invite) for invite in rows]


@router.delete("/invites/{invite_id}")
async def cancel_invite(invite_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    account = await _account(db, admin)
    invite = (await db.execute(select(UserInvite).where(
        UserInvite.invite_id == invite_id, UserInvite.account_id == account.account_id))).scalars().first()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")
    invite.is_open = None
    await db.commit()
    return {"cancelled": True}


async def _open_invite(db: AsyncSession, token: str) -> UserInvite:
    invite = (await db.execute(select(UserInvite).where(UserInvite.token_hash == hash_token(token or "")).with_for_update())).scalars().first()
    if invite is None or not invite.is_open or invite.accepted_at is not None or invite.expires_at < now_utc():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="This invitation is not valid any more. Ask your admin for a new one.")
    return invite


@public_router.get("/{token}")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def view_invite(request: Request, response: Response, token: str, db: AsyncSession = Depends(get_db)):
    """What an invitation is for, shown before the person chooses a password."""
    invite = await _open_invite(db, token)
    account = (await db.execute(select(Account).where(Account.account_id == invite.account_id))).scalars().first()
    return {"email": invite.email, "account_name": account.name}


@public_router.post("/accept")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def accept_invite(request: Request, response: Response, payload: InviteAccept, db: AsyncSession = Depends(get_db)):
    """Become a user of the inviting account, with the role and companies the invitation carries."""
    invite = await _open_invite(db, payload.token)
    if (await db.execute(select(User.user_id).where(func.lower(User.email) == invite.email))).scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists. Sign in.")
    companies = (await db.execute(select(Company.company_id).where(
        Company.account_id == invite.account_id, Company.company_id.in_(invite.company_ids or []), Company.is_active == True  # noqa: E712
    ).order_by(Company.company_id))).scalars().all()
    if not companies:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="The companies this invitation was for are gone. Ask your admin for a new one.")
    # The limit is checked again here: other people may have joined since the invitation was sent
    await _check_user_limit(db, (await db.execute(select(Account).where(Account.account_id == invite.account_id))).scalars().first())
    role = (await db.execute(select(Role).where(Role.role_id == invite.role_id))).scalars().first()
    is_admin = bool(role and role.name.lower() in ADMIN_ROLE_NAMES)
    user = User(account_id=invite.account_id, company_id=companies[0], username=payload.username.strip(), email=invite.email,
                phone=invite.phone, password_hash=get_password_hash(payload.password), role_id=invite.role_id, is_active=True,
                email_verified_at=now_utc(), ledger_scope="full" if is_admin else "none", stock_scope="full" if is_admin else "none")
    db.add(user)
    await db.flush()
    for company_id in companies:
        db.add(UserCompanyAccess(user_id=user.user_id, company_id=company_id))
    invite.accepted_at = now_utc()
    invite.is_open = None
    await db.commit()
    return {"detail": "Your account is ready. Sign in with your email and password.", "email": user.email}


# ─── Who may use the sync agent ──────────────────────────────────────────────

@router.get("/sync-agent-access")
async def sync_agent_access(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """The account's admins and whether each may use the sync agent."""
    account = await _account(db, admin)
    holders = set(await sync_agent_holders(db, account.account_id))
    admins = (await db.execute(
        select(User.user_id, User.username, User.email).join(Role, Role.role_id == User.role_id)
        .where(User.account_id == account.account_id, User.is_active == True, func.lower(Role.name).in_(ADMIN_ROLE_NAMES))  # noqa: E712
        .order_by(User.username))).all()
    return [{"user_id": user_id, "username": username, "email": email, "allowed": user_id in holders}
            for user_id, username, email in admins]


@router.put("/users/{user_id}/sync-agent")
async def set_sync_agent_access(user_id: int, payload: SyncAgentAccess, db: AsyncSession = Depends(get_db),
                                admin: User = Depends(require_admin)):
    """Give or take away "Manage sync agent". Only an admin who holds it can, only for admins of the same
    account, and the account always keeps at least one holder."""
    account = await _account(db, admin)
    await _require_sync_agent(db, admin)
    target = (await db.execute(
        select(User).join(Role, Role.role_id == User.role_id)
        .where(User.user_id == user_id, User.account_id == account.account_id, func.lower(Role.name).in_(ADMIN_ROLE_NAMES))
    )).scalars().first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found.")
    if payload.allowed:
        await grant_sync_agent(db, target.user_id, admin.user_id, f"Granted by {admin.email}")
    else:
        holders = set(await sync_agent_holders(db, account.account_id))
        if holders <= {target.user_id}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="At least one admin must be able to use the sync agent.")
        await revoke_sync_agent(db, target.user_id)
    await db.commit()
    return {"user_id": target.user_id, "allowed": payload.allowed}


# ─── Synced PCs ──────────────────────────────────────────────────────────────

@router.get("/agent-devices")
async def list_agent_devices(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    account = await _account(db, admin)
    devices = (await db.execute(select(AgentDevice).where(AgentDevice.account_id == account.account_id)
                                .order_by(AgentDevice.device_id))).scalars().all()
    linked = {}
    for device_id, company_id, name in (await db.execute(
            select(AgentCompanyLink.device_id, Company.company_id, Company.name)
            .join(Company, Company.company_id == AgentCompanyLink.company_id)
            .where(Company.account_id == account.account_id, AgentCompanyLink.is_active == True).order_by(Company.name))).all():  # noqa: E712
        linked.setdefault(device_id, []).append({"company_id": company_id, "name": name})
    return [
        {"device_id": d.device_id, "name": d.name, "signed_in": d.revoked_at is None,
         "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
         "revoked_at": d.revoked_at.isoformat() if d.revoked_at else None, "companies": linked.get(d.device_id, [])}
        for d in devices
    ]


@router.post("/agent-devices/{device_id}/revoke")
async def revoke_agent_device(device_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    """Sign a PC out of the sync agent. Its token stops working at once and its companies are free to be linked
    from another PC. Doing it again changes nothing."""
    account = await _account(db, admin)
    await _require_sync_agent(db, admin)
    device = (await db.execute(select(AgentDevice).where(
        AgentDevice.device_id == device_id, AgentDevice.account_id == account.account_id))).scalars().first()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PC not found.")
    if device.revoked_at is None:
        device.revoked_at = now_utc()   # the token hash is kept, so the PC is told it was signed out, not that it is unknown
    for link in (await db.execute(select(AgentCompanyLink).where(
            AgentCompanyLink.device_id == device.device_id, AgentCompanyLink.is_active == True))).scalars():  # noqa: E712
        link.is_active = None
        link.unlinked_at = now_utc()
    await db.commit()
    return {"device_id": device.device_id, "revoked": True}
