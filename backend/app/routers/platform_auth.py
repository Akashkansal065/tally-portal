"""
platform_auth.py – Authentication and session management router for Platform Operators.

Prefix: /platform/auth
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import webauthn
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)

from app.core.config import settings
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.rate_limiter import get_client_ip
from app.core.platform_dependencies import (
    PlatformAdminContext,
    current_admin,
    require_platform_permission,
)
from app.core.platform_security import (
    ABSOLUTE_SESSION_HOURS,
    DUMMY_BCRYPT_HASH,
    calculate_lockout_duration_minutes,
    check_login_rate_limits,
    clear_operator_cookies,
    create_platform_access_token,
    create_platform_mfa_token,
    decode_platform_access_token,
    generate_csrf_token,
    generate_refresh_token,
    get_cookie_name,
    hash_token,
    record_login_attempt,
    set_operator_cookies,
    utc_now,
    verify_csrf,
    verify_password,
    verify_platform_mfa_token,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminSession,
    PlatformAdminWebAuthnCredential,
)

router = APIRouter(
    prefix="/platform/auth",
    tags=["Platform Operator Auth"],
)
logger = get_logger("app.routers.platform_auth")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    passkey_required: bool
    mfa_token: Optional[str] = None
    admin_id: Optional[int] = None
    email: Optional[str] = None
    csrf_token: Optional[str] = None


class PasskeyLoginOptionsRequest(BaseModel):
    mfa_token: str


class PasskeyLoginVerifyRequest(BaseModel):
    mfa_token: str
    assertion_response: Dict[str, Any]
    challenge_token: str


class PasskeyRegisterVerifyRequest(BaseModel):
    attestation_response: Dict[str, Any]
    challenge_token: str
    nickname: str = Field("Primary Device", max_length=60)


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None  # fallback if cookie not accessible (e.g. testing)


class StepUpPasswordRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=14)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FOR CHALLENGE TOKENS
# ─────────────────────────────────────────────────────────────────────────────

def create_challenge_token(challenge_str: str, admin_id: int) -> str:
    """Signs WebAuthn challenge into a 5-minute single-use token."""
    now = utc_now()
    payload = {
        "iss": "mytally-platform",
        "sub": str(admin_id),
        "type": "webauthn_challenge",
        "challenge": challenge_str,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.get_platform_jwt_secret(), algorithm="HS256")


def verify_challenge_token(token: str, admin_id: int) -> str:
    """Verifies challenge token and extracts challenge string."""
    try:
        payload = jwt.decode(
            token,
            settings.get_platform_jwt_secret(),
            algorithms=["HS256"],
            issuer="mytally-platform",
        )
        if payload.get("type") != "webauthn_challenge" or int(payload.get("sub", 0)) != admin_id:
            raise HTTPException(status_code=400, detail="Challenge verification failed.")
        return payload["challenge"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="WebAuthn challenge expired. Please retry.")


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Operator login with email and password against platform_admins only.
    Enforces per-IP and per-email lockout/rate limits.
    """
    client_ip = get_client_ip(request)
    clean_email = body.email.strip().lower()

    # 1. Mandatory brute-force rate limit checks
    await check_login_rate_limits(db, client_ip, clean_email)

    # 2. Check platform_admins table ONLY (customer users table is never touched)
    res = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.email == clean_email)
    )
    admin = res.scalars().first()

    now = utc_now()

    # Unknown operator email
    if not admin:
        # Constant-time delay defense
        verify_password("dummy-password", DUMMY_BCRYPT_HASH)
        await record_login_attempt(db, client_ip, clean_email, succeeded=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Check lockout
    if admin.locked_until and admin.locked_until > now:
        verify_password("dummy-password", DUMMY_BCRYPT_HASH)
        await record_login_attempt(db, client_ip, clean_email, succeeded=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Check password
    if not verify_password(body.password, admin.password_hash):
        admin.failed_logins += 1
        if admin.failed_logins >= 5:
            duration = calculate_lockout_duration_minutes(admin.failed_logins)
            admin.locked_until = now + timedelta(minutes=duration)
            logger.warning(
                f"Operator account {admin.email} locked until {admin.locked_until} "
                f"after {admin.failed_logins} failed attempts."
            )
        await db.commit()
        await record_login_attempt(db, client_ip, clean_email, succeeded=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Status check
    if admin.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator account is {admin.status}.",
        )

    # Password correct: reset failed counters
    admin.failed_logins = 0
    admin.locked_until = None
    admin.last_login_at = now
    admin.last_login_ip = client_ip
    await db.commit()
    await record_login_attempt(db, client_ip, clean_email, succeeded=True)

    # 3. Handle Second Step (Passkey) requirement
    if settings.PLATFORM_PASSKEY_REQUIRED:
        # Check if operator has passkeys registered
        cred_res = await db.execute(
            select(PlatformAdminWebAuthnCredential.credential_pk).where(
                PlatformAdminWebAuthnCredential.admin_id == admin.admin_id
            )
        )
        has_credentials = cred_res.scalars().first() is not None

        # When passkeys are required, issue mfa_token for passkey verification
        mfa_token = create_platform_mfa_token(admin.admin_id)
        return LoginResponse(
            passkey_required=True,
            mfa_token=mfa_token,
            admin_id=admin.admin_id,
            email=admin.email,
        )

    # 4. Passkeys disabled: create session immediately
    family_id = str(uuid.uuid4())
    raw_refresh = generate_refresh_token()
    r_hash = hash_token(raw_refresh)
    csrf_token = generate_csrf_token()

    session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id=family_id,
        refresh_hash=r_hash,
        refresh_used=False,
        mfa_at=now,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", "")[:500],
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=ABSOLUTE_SESSION_HOURS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    access_token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=session.session_id,
        permission_version=admin.permission_version,
        amr=["pwd"],
    )

    set_operator_cookies(response, access_token, raw_refresh, csrf_token)

    return LoginResponse(
        passkey_required=False,
        admin_id=admin.admin_id,
        email=admin.email,
        csrf_token=csrf_token,
    )


# ─────────────────────────────────────────────────────────────────────────────
# WEBAUTHN / PASSKEY AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/passkey/login/options")
async def passkey_login_options(
    body: PasskeyLoginOptionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generates WebAuthn authentication options for passkey verification."""
    admin_id = verify_platform_mfa_token(body.mfa_token)

    # Load operator's registered credentials
    res = await db.execute(
        select(PlatformAdminWebAuthnCredential).where(
            PlatformAdminWebAuthnCredential.admin_id == admin_id
        )
    )
    credentials = res.scalars().all()
    if not credentials:
        raise HTTPException(
            status_code=400,
            detail="No passkeys registered for this operator. Please contact a super administrator.",
        )

    allow_descriptors = [
        PublicKeyCredentialDescriptor(id=c.credential_id)
        for c in credentials
    ]

    options = webauthn.generate_authentication_options(
        rp_id=settings.PLATFORM_WEBAUTHN_RP_ID,
        allow_credentials=allow_descriptors,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge_str = bytes_to_base64url(options.challenge)
    challenge_token = create_challenge_token(challenge_str, admin_id)

    return {
        "options": json.loads(webauthn.options_to_json(options)),
        "challenge_token": challenge_token,
    }


@router.post("/passkey/login/verify")
async def passkey_login_verify(
    request: Request,
    response: Response,
    body: PasskeyLoginVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verifies passkey assertion, creates operator session, and sets cookies."""
    admin_id = verify_platform_mfa_token(body.mfa_token)
    expected_challenge_str = verify_challenge_token(body.challenge_token, admin_id)

    raw_cred_id_str = body.assertion_response.get("id") or body.assertion_response.get("rawId")
    if not raw_cred_id_str:
        raise HTTPException(status_code=400, detail="Missing credential ID in assertion response.")

    raw_cred_id = base64url_to_bytes(raw_cred_id_str)

    # Find registered credential
    res = await db.execute(
        select(PlatformAdminWebAuthnCredential).where(
            PlatformAdminWebAuthnCredential.admin_id == admin_id,
            PlatformAdminWebAuthnCredential.credential_id == raw_cred_id,
        )
    )
    cred = res.scalars().first()
    if not cred:
        raise HTTPException(status_code=400, detail="Unrecognized passkey credential.")

    expected_origin = settings.PLATFORM_CONSOLE_ORIGIN

    try:
        verification = webauthn.verify_authentication_response(
            credential=body.assertion_response,
            expected_challenge=base64url_to_bytes(expected_challenge_str),
            expected_rp_id=settings.PLATFORM_WEBAUTHN_RP_ID,
            expected_origin=expected_origin,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
        )
    except Exception as e:
        logger.warning(f"Passkey verification failed for operator {admin_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Passkey verification failed: {str(e)}")

    # Update credential sign count & usage time
    cred.sign_count = verification.new_sign_count
    now = utc_now()
    cred.last_used_at = now

    # Load operator
    admin_res = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id)
    )
    admin = admin_res.scalars().first()
    if not admin or admin.status != "active":
        raise HTTPException(status_code=403, detail="Operator account unavailable.")

    # Create session
    family_id = str(uuid.uuid4())
    raw_refresh = generate_refresh_token()
    r_hash = hash_token(raw_refresh)
    csrf_token = generate_csrf_token()
    client_ip = get_client_ip(request)

    session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id=family_id,
        refresh_hash=r_hash,
        refresh_used=False,
        mfa_at=now,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", "")[:500],
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=ABSOLUTE_SESSION_HOURS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    access_token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=session.session_id,
        permission_version=admin.permission_version,
        amr=["pwd", "mfa"],
    )

    set_operator_cookies(response, access_token, raw_refresh, csrf_token)

    return {
        "status": "authenticated",
        "admin_id": admin.admin_id,
        "email": admin.email,
        "csrf_token": csrf_token,
    }


# ─────────────────────────────────────────────────────────────────────────────
# WEBAUTHN REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/passkey/register/options")
async def passkey_register_options(
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generates options for registering a new passkey credential."""
    # Fetch existing credentials to exclude
    res = await db.execute(
        select(PlatformAdminWebAuthnCredential).where(
            PlatformAdminWebAuthnCredential.admin_id == ctx.admin.admin_id
        )
    )
    existing = res.scalars().all()
    exclude_descriptors = [
        PublicKeyCredentialDescriptor(id=c.credential_id)
        for c in existing
    ]

    options = webauthn.generate_registration_options(
        rp_id=settings.PLATFORM_WEBAUTHN_RP_ID,
        rp_name=settings.PLATFORM_WEBAUTHN_RP_NAME,
        user_id=str(ctx.admin.admin_id).encode("utf-8"),
        user_name=ctx.admin.email,
        user_display_name=ctx.admin.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_descriptors,
    )

    challenge_str = bytes_to_base64url(options.challenge)
    challenge_token = create_challenge_token(challenge_str, ctx.admin.admin_id)

    return {
        "options": json.loads(webauthn.options_to_json(options)),
        "challenge_token": challenge_token,
    }


@router.post("/passkey/register/verify")
async def passkey_register_verify(
    body: PasskeyRegisterVerifyRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Verifies and registers a new passkey credential."""
    expected_challenge_str = verify_challenge_token(body.challenge_token, ctx.admin.admin_id)

    expected_origin = settings.PLATFORM_CONSOLE_ORIGIN

    try:
        verification = webauthn.verify_registration_response(
            credential=body.attestation_response,
            expected_challenge=base64url_to_bytes(expected_challenge_str),
            expected_rp_id=settings.PLATFORM_WEBAUTHN_RP_ID,
            expected_origin=expected_origin,
        )
    except Exception as e:
        logger.warning(f"Passkey registration failed for operator {ctx.admin.admin_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")

    cred_record = PlatformAdminWebAuthnCredential(
        admin_id=ctx.admin.admin_id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        aaguid=verification.aaguid,
        rp_id=settings.PLATFORM_WEBAUTHN_RP_ID,
        nickname=body.nickname,
        created_at=utc_now(),
        last_used_at=utc_now(),
    )
    db.add(cred_record)
    await db.commit()

    return {
        "status": "registered",
        "credential_id": bytes_to_base64url(verification.credential_id),
        "nickname": body.nickname,
    }


@router.get("/passkey/credentials")
async def list_passkey_credentials(
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lists registered passkeys for the current operator."""
    res = await db.execute(
        select(PlatformAdminWebAuthnCredential).where(
            PlatformAdminWebAuthnCredential.admin_id == ctx.admin.admin_id
        )
    )
    creds = res.scalars().all()
    return [
        {
            "credential_pk": c.credential_pk,
            "nickname": c.nickname,
            "rp_id": c.rp_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
        }
        for c in creds
    ]


@router.delete("/passkey/credentials/{credential_pk}")
async def delete_passkey_credential(
    credential_pk: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a passkey credential. The last one cannot be deleted while passkeys are required."""
    res = await db.execute(
        select(PlatformAdminWebAuthnCredential).where(
            PlatformAdminWebAuthnCredential.admin_id == ctx.admin.admin_id
        )
    )
    creds = res.scalars().all()
    target = next((c for c in creds if c.credential_pk == credential_pk), None)
    if not target:
        raise HTTPException(status_code=404, detail="Passkey credential not found.")

    if settings.PLATFORM_PASSKEY_REQUIRED and len(creds) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your only passkey while passkeys are required.",
        )

    await db.delete(target)
    await db.commit()
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN REFRESH & ROTATION WITH REUSE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotates refresh token. Detects token reuse to prevent token theft.
    """
    rt_cookie_name = get_cookie_name("pa_rt")
    raw_token = (body.refresh_token if body and body.refresh_token else None) or request.cookies.get(rt_cookie_name)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required.",
        )

    r_hash = hash_token(raw_token)
    res = await db.execute(
        select(PlatformAdminSession).where(PlatformAdminSession.refresh_hash == r_hash)
    )
    session = res.scalars().first()

    now = utc_now()

    if not session:
        clear_operator_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    # ── TOKEN REUSE DETECTION ──
    if session.refresh_used:
        # A token was used twice: token theft detected! Revoke the entire session family!
        logger.critical(
            f"SECURITY ALERT: Refresh token reuse detected for operator {session.admin_id}. "
            f"Revoking session family {session.family_id} immediately."
        )
        await db.execute(
            update(PlatformAdminSession)
            .where(PlatformAdminSession.family_id == session.family_id)
            .values(
                revoked_at=now,
                revoked_reason="refresh_reuse_detected",
            )
        )
        await db.commit()
        clear_operator_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security violation: refresh token reuse detected. Family revoked.",
        )

    if session.revoked_at or session.expires_at < now:
        clear_operator_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or was revoked.",
        )

    # Load operator
    admin_res = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.admin_id == session.admin_id)
    )
    admin = admin_res.scalars().first()
    if not admin or admin.status != "active":
        clear_operator_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator inactive.")

    # Mark current token as used
    session.refresh_used = True

    # Issue new token pair in same family
    new_raw_refresh = generate_refresh_token()
    new_r_hash = hash_token(new_raw_refresh)
    csrf_token = generate_csrf_token()
    client_ip = get_client_ip(request)

    new_session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id=session.family_id,
        refresh_hash=new_r_hash,
        refresh_used=False,
        mfa_at=session.mfa_at,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", "")[:500],
        created_at=session.created_at,
        last_seen_at=now,
        expires_at=session.expires_at,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    new_access_token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=new_session.session_id,
        permission_version=admin.permission_version,
        amr=["pwd", "mfa"] if session.mfa_at else ["pwd"],
    )

    set_operator_cookies(response, new_access_token, new_raw_refresh, csrf_token)

    return {
        "status": "refreshed",
        "access_token": new_access_token,  # returned for test harnesses
        "refresh_token": new_raw_refresh,
        "csrf_token": csrf_token,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP-UP AUTHENTICATION (Section 1.3)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/step-up")
async def step_up_auth(
    body: StepUpPasswordRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Fresh check for sensitive actions within 5 minutes.
    When passkeys are off (or fallback), checks password.
    """
    if not verify_password(body.password, ctx.admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password incorrect.",
        )

    now = utc_now()
    ctx.session.mfa_at = now
    await db.commit()

    return {
        "succeeded": True,
        "mfa_at": now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ME & SESSIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(
    request: Request,
    response: Response,
    ctx: PlatformAdminContext = Depends(current_admin),
):
    """Returns the authenticated operator profile, permissions, and visible pages."""
    allowed_pages = [
        perm.replace("page.", "")
        for perm in ctx.permissions
        if perm.startswith("page.")
    ]

    csrf_cookie = request.cookies.get("pa_csrf")
    if not csrf_cookie:
        csrf_token = generate_csrf_token()
    else:
        csrf_token = csrf_cookie

    response.set_cookie(
        key="pa_csrf",
        value=csrf_token,
        httponly=False,
        secure=settings.PLATFORM_COOKIE_SECURE,
        samesite="strict",
        path="/",
        max_age=ABSOLUTE_SESSION_HOURS * 3600,
    )

    return {
        "admin_id": ctx.admin.admin_id,
        "email": ctx.admin.email,
        "full_name": ctx.admin.full_name,
        "status": ctx.admin.status,
        "last_login_at": ctx.admin.last_login_at.isoformat() if ctx.admin.last_login_at else None,
        "permissions": sorted(list(ctx.permissions)),
        "max_rank": ctx.max_rank,
        "pages": sorted(allowed_pages),
        "passkey_required": settings.PLATFORM_PASSKEY_REQUIRED,
        "csrf_token": csrf_token,
    }


@router.get("/sessions")
async def list_my_sessions(
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lists active sessions for the current operator."""
    now = utc_now()
    res = await db.execute(
        select(PlatformAdminSession).where(
            PlatformAdminSession.admin_id == ctx.admin.admin_id,
            PlatformAdminSession.revoked_at == None,  # noqa: E711
            PlatformAdminSession.expires_at > now,
        )
    )
    sessions = res.scalars().all()
    return [
        {
            "session_id": s.session_id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
            "is_current": s.session_id == ctx.session.session_id,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revokes a specific session belonging to current operator."""
    res = await db.execute(
        select(PlatformAdminSession).where(
            PlatformAdminSession.session_id == session_id,
            PlatformAdminSession.admin_id == ctx.admin.admin_id,
        )
    )
    target = res.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Session not found.")

    target.revoked_at = utc_now()
    target.revoked_reason = "revoked_by_operator"
    await db.commit()
    return {"status": "revoked"}


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT & LOGOUT ALL
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Terminates the current session."""
    ctx.session.revoked_at = utc_now()
    ctx.session.revoked_reason = "operator_logout"
    await db.commit()
    clear_operator_cookies(response)
    return {"status": "logged_out"}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Terminates all sessions for current operator."""
    now = utc_now()
    await db.execute(
        update(PlatformAdminSession)
        .where(
            PlatformAdminSession.admin_id == ctx.admin.admin_id,
            PlatformAdminSession.revoked_at == None,  # noqa: E711
        )
        .values(
            revoked_at=now,
            revoked_reason="logout_all_sessions",
        )
    )
    await db.commit()
    clear_operator_cookies(response)
    return {"status": "all_sessions_logged_out"}
