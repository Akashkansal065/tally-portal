"""Automatic payment reminders: channels, preview, send now, schedules, history, customer contacts, and Meta's
WhatsApp delivery receipts. The logic lives in app/services/reminders.py."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import require_permission
from app.models.portal_core import Company, ReminderLog, ReminderSchedule, User
from app.models.tally_core import MstLedger
from app.services import messaging
from app.services import reminders as svc
from app.services.receivables import BUCKETS, receivables_ageing

router = APIRouter(prefix="/reminders", tags=["Payment Reminders"])


# ── shapes ───────────────────────────────────────────────────────────────────

class SendNow(BaseModel):
    ledger_id: int
    channels: List[str]


class ScheduleIn(BaseModel):
    ledger_ids: Optional[List[int]] = None
    # Everyone owing money in this ageing bucket ("1-30 Days" ... "90+ Days"), or "overdue" for any overdue amount
    bucket: Optional[str] = None
    channels: List[str]
    frequency: str
    send_time: str = "10:00"
    weekday: Optional[int] = None
    month_day: Optional[int] = None
    only_when_overdue: bool = True


class ScheduleChange(BaseModel):
    active: Optional[bool] = None
    channels: Optional[List[str]] = None
    frequency: Optional[str] = None
    send_time: Optional[str] = None
    weekday: Optional[int] = None
    month_day: Optional[int] = None
    only_when_overdue: Optional[bool] = None


class ContactIn(BaseModel):
    email: Optional[str] = None
    whatsapp: Optional[str] = None


def log_out(log: ReminderLog, names: dict) -> dict:
    return {
        "id": log.id, "ledger_id": log.ledger_id, "customer": names.get(log.ledger_id), "schedule_id": log.schedule_id,
        "channel": log.channel, "recipient": log.recipient, "status": log.status, "detail": log.detail,
        "outstanding": float(log.outstanding) if log.outstanding is not None else None,
        "overdue": float(log.overdue) if log.overdue is not None else None,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "updated_at": log.updated_at.isoformat() if log.updated_at else None,
    }


def schedule_out(s: ReminderSchedule, names: dict) -> dict:
    return {
        "id": s.id, "ledger_id": s.ledger_id, "customer": names.get(s.ledger_id), "channels": s.channels,
        "frequency": s.frequency, "send_time": s.send_time, "weekday": s.weekday, "month_day": s.month_day,
        "only_when_overdue": s.only_when_overdue, "active": s.active, "stop_reason": s.stop_reason,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
    }


async def ledger_names(db: AsyncSession, company_id: int, ids) -> dict:
    ids = list(set(ids))
    if not ids:
        return {}
    rows = await db.execute(select(MstLedger.ledger_id, MstLedger.name).where(
        MstLedger.company_id == company_id, MstLedger.ledger_id.in_(ids)))
    return dict(rows.all())


async def own_ledger(db: AsyncSession, user: User, ledger_id: int) -> MstLedger:
    ledger = (await db.execute(select(MstLedger).where(
        MstLedger.ledger_id == ledger_id, MstLedger.company_id == user.company_id))).scalars().first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return ledger


async def own_company(db: AsyncSession, user: User) -> Company:
    return (await db.execute(select(Company).where(Company.company_id == user.company_id))).scalars().first()


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/channels")
async def channels(user: User = Depends(require_permission("payments", "read")), db: AsyncSession = Depends(get_db)):
    readiness = await svc.channel_readiness(db, user.company_id)
    now = get_ist_now()
    return {
        "channels": [{"channel": c, "label": svc.CHANNEL_LABEL[c], "ready": readiness[c][0], "reason": readiness[c][1]}
                     for c in svc.CHANNELS],
        "emails_sent_today": await svc.emails_sent_today(db, now),
        "email_daily_limit": settings.EMAIL_DAILY_LIMIT,
        "dry_run": settings.REMINDERS_DRY_RUN,
        "sending_hours": f"{svc.QUIET_START:%H:%M}–{svc.QUIET_END:%H:%M}",
    }


@router.get("/summary")
async def summary(user: User = Depends(require_permission("payments", "read")), db: AsyncSession = Depends(get_db)):
    now = get_ist_now()
    cid = user.company_id
    active = (await db.execute(select(func.count(ReminderSchedule.id)).where(
        ReminderSchedule.company_id == cid, ReminderSchedule.active.is_(True)))).scalar() or 0
    rows = (await db.execute(select(ReminderLog.status, func.count(ReminderLog.id)).where(
        ReminderLog.company_id == cid, ReminderLog.created_at >= svc.day_start(now)).group_by(ReminderLog.status))).all()
    today = dict(rows)
    return {
        "active_schedules": active,
        "sent_today": sum(today.get(s, 0) for s in ("sent", "delivered", "read")),
        "dry_run_today": today.get("dry_run", 0),
        "failed_today": today.get("failed", 0),
        "skipped_today": today.get("skipped", 0),
    }


@router.get("/preview/{ledger_id}")
async def preview(ledger_id: int, user: User = Depends(require_permission("payments", "read")), db: AsyncSession = Depends(get_db)):
    ledger = await own_ledger(db, user, ledger_id)
    company = await own_company(db, user)
    party = await svc.party_for(db, user.company_id, ledger_id)
    contact = (await svc.contacts_for(db, user.company_id, [ledger_id]))[ledger_id]
    readiness = await svc.channel_readiness(db, user.company_id)
    draft = svc.build_draft(company, party) if party else None
    return {
        "ledger_id": ledger_id, "customer": ledger.name,
        "outstanding": party.balance if party else 0.0, "overdue": party.overdue if party else 0.0,
        "contact": {"email": contact.email, "email_source": contact.email_source,
                    "whatsapp": contact.whatsapp, "whatsapp_source": contact.whatsapp_source},
        "upi": svc.company_upi(company),
        "channels": {c: {"ready": readiness[c][0], "reason": readiness[c][1]} for c in svc.CHANNELS},
        "email": {"subject": draft.email_subject, "text": draft.email_text} if draft else None,
        "whatsapp": {"template": settings.WHATSAPP_TEMPLATE, "text": draft.whatsapp_preview} if draft else None,
    }


@router.post("/send-now")
async def send_now(req: SendNow, user: User = Depends(require_permission("payments", "create")), db: AsyncSession = Depends(get_db)):
    await own_ledger(db, user, req.ledger_id)
    if not req.channels or any(c not in svc.CHANNELS for c in req.channels):
        raise HTTPException(status_code=422, detail="Choose email and/or WhatsApp.")
    now = get_ist_now()
    if not svc.in_sending_hours(now):
        raise HTTPException(status_code=409, detail="Reminders go out between 09:00 and 20:00.")
    company = await own_company(db, user)
    logs = await svc.send_reminder(db, company, req.ledger_id, req.channels, user_id=user.user_id, now=now)
    await db.commit()
    names = await ledger_names(db, user.company_id, [req.ledger_id])
    return [log_out(log, names) for log in logs]


@router.get("/schedules")
async def list_schedules(
    ledger_id: Optional[int] = None,
    include_stopped: bool = False,
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ReminderSchedule).where(ReminderSchedule.company_id == user.company_id)
    if ledger_id is not None:
        stmt = stmt.where(ReminderSchedule.ledger_id == ledger_id)
    if not include_stopped:
        stmt = stmt.where(ReminderSchedule.active.is_(True))
    rows = (await db.execute(stmt.order_by(ReminderSchedule.next_run_at))).scalars().all()
    names = await ledger_names(db, user.company_id, [r.ledger_id for r in rows])
    return [schedule_out(r, names) for r in rows]


@router.post("/schedules")
async def create_schedules(req: ScheduleIn, user: User = Depends(require_permission("payments", "create")), db: AsyncSession = Depends(get_db)):
    try:
        svc.validate_schedule(req.frequency, req.send_time, req.channels, req.weekday, req.month_day)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if req.ledger_ids:
        ledger_ids = list(dict.fromkeys(req.ledger_ids))
        found = await ledger_names(db, user.company_id, ledger_ids)
        if len(found) != len(ledger_ids):
            raise HTTPException(status_code=404, detail="Customer not found.")
    elif req.bucket:
        if req.bucket != "overdue" and req.bucket not in BUCKETS:
            raise HTTPException(status_code=422, detail="Unknown ageing bucket.")
        parties = await receivables_ageing(db, user.company_id)
        ledger_ids = [p.ledger_id for p in parties
                      if (p.overdue > 0.005 if req.bucket == "overdue" else p.buckets.get(req.bucket, 0) > 0.005)]
    else:
        raise HTTPException(status_code=422, detail="Choose customers or an ageing bucket.")
    now = get_ist_now()
    schedules = [
        await svc.upsert_schedule(db, user.company_id, lid, user.user_id, channels=req.channels, frequency=req.frequency,
                                  send_time=req.send_time, weekday=req.weekday, month_day=req.month_day,
                                  only_when_overdue=req.only_when_overdue, now=now)
        for lid in ledger_ids
    ]
    await db.commit()
    names = await ledger_names(db, user.company_id, ledger_ids)
    return [schedule_out(s, names) for s in schedules]


@router.put("/schedules/{schedule_id}")
async def change_schedule(schedule_id: int, req: ScheduleChange, user: User = Depends(require_permission("payments", "update")),
                          db: AsyncSession = Depends(get_db)):
    schedule = (await db.execute(select(ReminderSchedule).where(
        ReminderSchedule.id == schedule_id, ReminderSchedule.company_id == user.company_id))).scalars().first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    for name in ("channels", "frequency", "send_time", "weekday", "month_day", "only_when_overdue"):
        value = getattr(req, name)
        if value is not None:
            setattr(schedule, name, value)
    try:
        svc.validate_schedule(schedule.frequency, schedule.send_time, schedule.channels, schedule.weekday, schedule.month_day)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if req.active is not None:
        schedule.active = req.active
        schedule.stop_reason = None if req.active else "stopped"
    if schedule.active:
        schedule.next_run_at = svc.next_run(schedule.frequency, schedule.send_time, get_ist_now(),
                                            schedule.weekday, schedule.month_day, first=True)
    await db.commit()
    names = await ledger_names(db, user.company_id, [schedule.ledger_id])
    return schedule_out(schedule, names)


@router.delete("/schedules/{schedule_id}")
async def stop_schedule(schedule_id: int, user: User = Depends(require_permission("payments", "update")), db: AsyncSession = Depends(get_db)):
    schedule = (await db.execute(select(ReminderSchedule).where(
        ReminderSchedule.id == schedule_id, ReminderSchedule.company_id == user.company_id))).scalars().first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    schedule.active, schedule.stop_reason, schedule.next_run_at = False, "stopped", None
    await db.commit()
    return {"detail": "Reminders stopped."}


@router.get("/log")
async def reminder_log(
    ledger_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ReminderLog).where(ReminderLog.company_id == user.company_id)
    if ledger_id is not None:
        stmt = stmt.where(ReminderLog.ledger_id == ledger_id)
    rows = (await db.execute(stmt.order_by(ReminderLog.created_at.desc(), ReminderLog.id.desc()).limit(limit))).scalars().all()
    names = await ledger_names(db, user.company_id, [r.ledger_id for r in rows])
    return [log_out(r, names) for r in rows]


@router.put("/contact/{ledger_id}")
async def save_contact(ledger_id: int, req: ContactIn, user: User = Depends(require_permission("payments", "create")),
                       db: AsyncSession = Depends(get_db)):
    await own_ledger(db, user, ledger_id)
    try:
        await svc.save_contact(db, user.company_id, ledger_id, user.user_id, email=req.email, whatsapp=req.whatsapp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await db.commit()
    contact = (await svc.contacts_for(db, user.company_id, [ledger_id]))[ledger_id]
    return {"email": contact.email, "email_source": contact.email_source,
            "whatsapp": contact.whatsapp, "whatsapp_source": contact.whatsapp_source}


MAX_PDF_BYTES = 5 * 1024 * 1024


@router.post("/email-document")
async def email_document(
    ledger_id: int = Form(...),
    to: str = Form(...),
    subject: str = Form(..., max_length=200),
    message: str = Form("", max_length=5000),
    reference: str = Form("", max_length=100),
    file: UploadFile = File(...),
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Email an invoice or statement PDF made in the browser to a customer, through Gmail (the "email" switch)."""
    await own_ledger(db, user, ledger_id)
    content = await file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="The PDF is larger than 5 MB.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Only PDF files can be emailed.")
    filename = (file.filename or "document.pdf").replace("/", "_").replace("\\", "_")[:120]
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    company = await own_company(db, user)
    log = await svc.email_document(db, company, ledger_id, to=to, subject=subject, message=message, filename=filename,
                                   content=content, reference=reference or filename, user_id=user.user_id)
    await db.commit()
    names = await ledger_names(db, user.company_id, [ledger_id])
    return log_out(log, names)


# ── Meta webhook (no login: Meta calls it; checked by verify token / signature) ──

@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook_verify(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    if mode == "subscribe" and settings.WHATSAPP_VERIFY_TOKEN and token == settings.WHATSAPP_VERIFY_TOKEN and challenge:
        return challenge
    raise HTTPException(status_code=403, detail="Verification failed.")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    if not messaging.whatsapp_signature_valid(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Bad signature.")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Not JSON.")
    changed = await svc.apply_whatsapp_statuses(db, payload)
    await db.commit()
    return {"updated": changed}
