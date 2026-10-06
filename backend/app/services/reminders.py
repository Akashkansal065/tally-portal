"""Automatic payment reminders (Phase 2 of docs/livekeeping-parity-plan.md).

A reminder goes to one customer (a Tally debtor ledger) on the channels chosen: email through Gmail and WhatsApp
through Meta's Cloud API, each only while its integration switch is on and its keys are set. Amounts come from the
shared receivables service, so a reminder always says what Tally says now. Rules: nothing before 9 am or after
8 pm IST, at most one reminder per customer per channel per day, Gmail's daily limit respected, and a schedule
stops by itself once the customer has paid. REMINDERS_DRY_RUN logs instead of sending.
"""
import asyncio
import html
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.core.logging_config import get_logger
from app.models.portal_core import Company, CustomerProfile, ReminderLog, ReminderSchedule
from app.models.tally_core import MstLedger
from app.services import messaging
from app.services.integrations import integration_statuses
from app.services.receivables import PartyAgeing, receivables_ageing

logger = get_logger("app.services.reminders")

CHANNELS = ("email", "whatsapp")
CHANNEL_SWITCH = {"email": "email", "whatsapp": "whatsapp_api"}
CHANNEL_LABEL = {"email": "Email", "whatsapp": "WhatsApp"}
FREQUENCIES = ("once", "daily", "weekly", "monthly")
QUIET_START, QUIET_END = time(9, 0), time(20, 0)
DELIVERED = ("sent", "delivered", "read", "dry_run")
# Status order for WhatsApp receipts: a later receipt never moves a message backwards
STATUS_RANK = {"sent": 1, "delivered": 2, "read": 3, "failed": 4}

# The text of the WhatsApp template we ask Meta to approve (docs/livekeeping-parity-plan.md, Phase 2). Only used
# for previews: Meta sends the approved template, filled with whatsapp_parameters().
WHATSAPP_TEMPLATE_TEXT = (
    "Hello {1}, this is a reminder from {2}. Your outstanding balance is ₹{3}, of which ₹{4} is overdue. "
    "You can pay by UPI to {5}. Please ignore this if you have already paid. Thank you."
)


def inr(amount: float) -> str:
    """12,34,567.50 style (Indian grouping), without the ₹ sign; whole rupees drop the paise."""
    negative = amount < 0
    rupees, paise = divmod(round(abs(amount) * 100), 100)
    digits = str(int(rupees))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    text = digits + (f".{paise:02d}" if paise else "")
    return ("-" if negative else "") + text


# ── contacts ─────────────────────────────────────────────────────────────────

@dataclass
class Contact:
    email: Optional[str] = None
    email_source: Optional[str] = None  # 'mytally' (customer profile) or 'tally' (ledger)
    whatsapp: Optional[str] = None  # digits with country code
    whatsapp_source: Optional[str] = None

    def for_channel(self, channel: str) -> Optional[str]:
        return self.email if channel == "email" else self.whatsapp


async def contacts_for(db: AsyncSession, company_id: int, ledger_ids: Iterable[int]) -> Dict[int, Contact]:
    """Email: MyTally profile, then the Tally ledger. WhatsApp: profile WhatsApp number, ledger mobile, ledger
    phone, profile phone; the first that is a valid mobile number."""
    ids = list(set(ledger_ids))
    if not ids:
        return {}
    ledgers = {r.ledger_id: r for r in (await db.execute(
        select(MstLedger.ledger_id, MstLedger.email, MstLedger.mobile, MstLedger.phone)
        .where(MstLedger.company_id == company_id, MstLedger.ledger_id.in_(ids)))).all()}
    profiles = {r.ledger_id: r for r in (await db.execute(
        select(CustomerProfile.ledger_id, CustomerProfile.email, CustomerProfile.whatsapp_number, CustomerProfile.phone)
        .where(CustomerProfile.company_id == company_id, CustomerProfile.ledger_id.in_(ids)))).all()}
    result = {}
    for lid in ids:
        ledger, profile = ledgers.get(lid), profiles.get(lid)
        contact = Contact()
        for value, source in ((profile and profile.email, "mytally"), (ledger and ledger.email, "tally")):
            if messaging.clean_email(value):
                contact.email, contact.email_source = messaging.clean_email(value), source
                break
        for value, source in ((profile and profile.whatsapp_number, "mytally"), (ledger and ledger.mobile, "tally"),
                              (ledger and ledger.phone, "tally"), (profile and profile.phone, "mytally")):
            if messaging.whatsapp_number(value):
                contact.whatsapp, contact.whatsapp_source = messaging.whatsapp_number(value), source
                break
        result[lid] = contact
    return result


async def save_contact(db: AsyncSession, company_id: int, ledger_id: int, user_id: int,
                       email: Optional[str] = None, whatsapp: Optional[str] = None) -> None:
    """Store a customer's email / WhatsApp number on their MyTally profile (Tally is not changed). None leaves a
    field as it is; an empty string clears it. Raises ValueError for an invalid value (the caller commits)."""
    if email:
        if not messaging.clean_email(email):
            raise ValueError("That doesn't look like an email address.")
        email = messaging.clean_email(email)
    if whatsapp:
        if not messaging.whatsapp_number(whatsapp):
            raise ValueError("Enter a 10-digit mobile number (or one with 91 in front).")
        whatsapp = messaging.whatsapp_number(whatsapp)
    profile = (await db.execute(select(CustomerProfile).where(
        CustomerProfile.company_id == company_id, CustomerProfile.ledger_id == ledger_id))).scalars().first()
    if not profile:
        profile = CustomerProfile(company_id=company_id, ledger_id=ledger_id, created_by=user_id)
        db.add(profile)
    if email is not None:
        profile.email = email or None
    if whatsapp is not None:
        profile.whatsapp_number = whatsapp or None


# ── message content ──────────────────────────────────────────────────────────

def company_upi(company: Company) -> Optional[str]:
    features = company.features if isinstance(company.features, dict) else {}
    upi = (features.get("upi_id") or features.get("upi_vpa") or "").strip()
    if not upi and settings.DEFAULT_UPI_VPA and "*" not in settings.DEFAULT_UPI_VPA:
        upi = settings.DEFAULT_UPI_VPA
    return upi or None


@dataclass
class Draft:
    party: PartyAgeing
    company_name: str
    upi: Optional[str]
    email_subject: str = ""
    email_text: str = ""
    email_html: str = ""
    whatsapp_parameters: List[str] = field(default_factory=list)
    whatsapp_preview: str = ""


def build_draft(company: Company, party: PartyAgeing) -> Draft:
    name, outstanding, overdue = party.name, party.balance, party.overdue
    upi = company_upi(company)
    draft = Draft(party=party, company_name=company.name, upi=upi)
    open_bills = [b for b in party.bills if b.outstanding > 0.005]
    draft.email_subject = f"Payment reminder from {company.name}: ₹{inr(outstanding)} outstanding"
    lines = [
        f"Dear {name},",
        "",
        f"This is a reminder from {company.name}. Your outstanding balance is ₹{inr(outstanding)}"
        + (f", of which ₹{inr(overdue)} is overdue." if overdue > 0.005 else ", none of it overdue yet."),
        "",
    ]
    if open_bills:
        lines.append("Open bills:")
        for b in open_bills:
            due = b.due_date.strftime("%d %b %Y") if b.due_date else "-"
            late = f", {b.days_overdue} days overdue" if b.days_overdue > 0 else ""
            lines.append(f"  {b.voucher_number}  dated {b.bill_date.strftime('%d %b %Y') if b.bill_date else '-'}  "
                         f"due {due}  ₹{inr(b.outstanding)}{late}")
        lines.append("")
    if upi:
        lines += [f"You can pay by UPI to {upi}.", ""]
    lines += ["Please ignore this if you have already paid.", "", "Thank you,", company.name]
    draft.email_text = "\n".join(lines)

    e = html.escape
    rows = "".join(
        f"<tr><td style='padding:4px 8px'>{e(b.voucher_number)}</td>"
        f"<td style='padding:4px 8px'>{b.bill_date.strftime('%d %b %Y') if b.bill_date else '-'}</td>"
        f"<td style='padding:4px 8px'>{b.due_date.strftime('%d %b %Y') if b.due_date else '-'}</td>"
        f"<td style='padding:4px 8px;text-align:right'>₹{inr(b.outstanding)}</td>"
        f"<td style='padding:4px 8px;text-align:right'>{b.days_overdue if b.days_overdue > 0 else ''}</td></tr>"
        for b in open_bills
    )
    table = (
        "<table style='border-collapse:collapse;font-size:14px;margin:12px 0'>"
        "<tr style='background:#f3f4f6'><th style='padding:4px 8px;text-align:left'>Bill</th>"
        "<th style='padding:4px 8px;text-align:left'>Date</th><th style='padding:4px 8px;text-align:left'>Due</th>"
        "<th style='padding:4px 8px;text-align:right'>Amount due</th><th style='padding:4px 8px;text-align:right'>Days overdue</th></tr>"
        f"{rows}</table>"
    ) if open_bills else ""
    overdue_html = f", of which <strong>₹{inr(overdue)}</strong> is overdue" if overdue > 0.005 else ""
    draft.email_html = (
        "<div style='font-family:Arial,sans-serif;font-size:15px;color:#111;line-height:1.5'>"
        f"<p>Dear {e(name)},</p>"
        f"<p>This is a reminder from {e(company.name)}. Your outstanding balance is <strong>₹{inr(outstanding)}</strong>{overdue_html}.</p>"
        f"{table}"
        + (f"<p>You can pay by UPI to <strong>{e(upi)}</strong>.</p>" if upi else "")
        + f"<p>Please ignore this if you have already paid.</p><p>Thank you,<br>{e(company.name)}</p></div>"
    )

    draft.whatsapp_parameters = [name, company.name, inr(outstanding), inr(max(overdue, 0)), upi or ""]
    draft.whatsapp_preview = WHATSAPP_TEMPLATE_TEXT
    for i, value in enumerate(draft.whatsapp_parameters, start=1):
        draft.whatsapp_preview = draft.whatsapp_preview.replace("{" + str(i) + "}", value)
    return draft


# ── sending ──────────────────────────────────────────────────────────────────

async def channel_readiness(db: AsyncSession, company_id: int) -> Dict[str, Tuple[bool, str]]:
    """channel -> (can send now, reason if not)."""
    statuses = {s["key"]: s for s in await integration_statuses(db, company_id)}
    result = {}
    for channel, key in CHANNEL_SWITCH.items():
        status, label = statuses[key]["status"], statuses[key]["label"]
        if status == "connected":
            result[channel] = (True, "")
        elif status == "off":
            result[channel] = (False, f"{label} is switched off (Admin → Integrations).")
        else:
            result[channel] = (False, f"{label} keys aren't set on the server yet.")
    return result


def day_start(now: datetime) -> datetime:
    return datetime.combine(now.date(), time(0, 0))


async def emails_sent_today(db: AsyncSession, now: datetime) -> int:
    """Across every company: the Gmail account's daily limit is per account."""
    return (await db.execute(select(func.count(ReminderLog.id)).where(
        ReminderLog.channel == "email", ReminderLog.status == "sent", ReminderLog.created_at >= day_start(now)))).scalar() or 0


async def reminded_today(db: AsyncSession, company_id: int, ledger_id: int, channel: str, now: datetime) -> bool:
    return bool((await db.execute(select(func.count(ReminderLog.id)).where(
        ReminderLog.company_id == company_id, ReminderLog.ledger_id == ledger_id, ReminderLog.channel == channel,
        ReminderLog.status.in_(DELIVERED), ReminderLog.created_at >= day_start(now)))).scalar())


async def party_for(db: AsyncSession, company_id: int, ledger_id: int) -> Optional[PartyAgeing]:
    parties = await receivables_ageing(db, company_id, party_ledger_id=ledger_id)
    return parties[0] if parties else None


async def send_reminder(
    db: AsyncSession, company: Company, ledger_id: int, channels: Iterable[str], *,
    schedule_id: Optional[int] = None, user_id: Optional[int] = None, now: Optional[datetime] = None,
    party: Optional[PartyAgeing] = None,
) -> List[ReminderLog]:
    """Send (or skip, with the reason) one reminder per channel and log each attempt. The caller commits."""
    now = now or get_ist_now()
    party = party or await party_for(db, company.company_id, ledger_id)
    readiness = await channel_readiness(db, company.company_id)
    contact = (await contacts_for(db, company.company_id, [ledger_id])).get(ledger_id, Contact())
    draft = build_draft(company, party) if party else None
    logs = []
    for channel in dict.fromkeys(c for c in channels if c in CHANNELS):
        log = ReminderLog(company_id=company.company_id, ledger_id=ledger_id, schedule_id=schedule_id, channel=channel,
                          recipient=contact.for_channel(channel), created_at=now, sent_by_user_id=user_id,
                          outstanding=Decimal(str(round(party.balance, 2))) if party else None,
                          overdue=Decimal(str(round(party.overdue, 2))) if party else None)
        ready, why = readiness[channel]
        if not party or party.balance <= 0.005:
            log.status, log.detail = "skipped", "Nothing is owed."
        elif not ready:
            log.status, log.detail = "skipped", why
        elif not log.recipient:
            log.status, log.detail = "skipped", "No email address on file." if channel == "email" else "No mobile number on file."
        elif channel == "whatsapp" and not draft.upi:
            log.status, log.detail = "skipped", "Set the company's UPI ID first; the WhatsApp message includes it."
        elif await reminded_today(db, company.company_id, ledger_id, channel, now):
            log.status, log.detail = "skipped", f"Already reminded on {CHANNEL_LABEL[channel]} today."
        elif channel == "email" and await emails_sent_today(db, now) >= settings.EMAIL_DAILY_LIMIT:
            log.status, log.detail = "skipped", f"Gmail daily limit reached ({settings.EMAIL_DAILY_LIMIT} emails)."
        elif settings.REMINDERS_DRY_RUN:
            log.status, log.detail = "dry_run", "Dry run (REMINDERS_DRY_RUN): not sent."
        else:
            if channel == "email":
                result = await messaging.send_email(log.recipient, draft.email_subject, draft.email_text, draft.email_html,
                                                    from_name=settings.SMTP_FROM_NAME or company.name)
            else:
                result = await messaging.send_whatsapp_template(log.recipient, draft.whatsapp_parameters)
            log.status = "sent" if result.ok else "failed"
            log.provider_message_id, log.detail = result.provider_message_id, result.error
        db.add(log)
        logs.append(log)
    failed = [log for log in logs if log.status == "failed"]
    if failed:
        await notify_failure(db, company.company_id, party.name if party else f"Ledger {ledger_id}", failed[0].channel,
                             failed[0].detail, exclude_user_id=user_id)
    return logs


async def notify_failure(db: AsyncSession, company_id: int, customer: str, channel: str, detail: Optional[str],
                         exclude_user_id: Optional[int] = None) -> None:
    from app.services.notifications import notify_admins
    await notify_admins(
        db, company_id, "reminder_failed",
        title=f"{CHANNEL_LABEL.get(channel, channel)} reminder to {customer} failed",
        message=(detail or "The provider refused the message.")[:300],
        link="/outstanding", exclude_user_id=exclude_user_id,
        group_key="reminder_failed", group_title=lambda n: f"{n} payment reminders failed",
    )


# ── schedules ────────────────────────────────────────────────────────────────

def parse_time(value: str) -> time:
    try:
        hour, minute = (int(x) for x in value.split(":"))
        chosen = time(hour, minute)
    except (ValueError, AttributeError):
        raise ValueError("Time must look like 10:30.")
    if not (QUIET_START <= chosen <= QUIET_END):
        raise ValueError("Reminders go out between 09:00 and 20:00.")
    return chosen


def next_run(frequency: str, send_time: str, after: datetime, weekday: Optional[int] = None,
             month_day: Optional[int] = None, first: bool = False) -> Optional[datetime]:
    """The next send time strictly after `after` (or at/after it for the first run). 'once' runs one time."""
    at = parse_time(send_time)
    if frequency == "once" and not first:
        return None
    day = after.date()
    for _ in range(400):
        candidate = datetime.combine(day, at)
        fits = (
            frequency in ("once", "daily")
            or (frequency == "weekly" and day.weekday() == weekday)
            or (frequency == "monthly" and day.day == month_day)
        )
        if fits and (candidate >= after if first else candidate > after):
            return candidate
        day += timedelta(days=1)
    return None


def validate_schedule(frequency: str, send_time: str, channels: List[str], weekday: Optional[int], month_day: Optional[int]) -> None:
    if frequency not in FREQUENCIES:
        raise ValueError("Choose once, daily, weekly or monthly.")
    parse_time(send_time)
    if not channels or any(c not in CHANNELS for c in channels):
        raise ValueError("Choose email and/or WhatsApp.")
    if frequency == "weekly" and weekday not in range(7):
        raise ValueError("Choose a weekday.")
    if frequency == "monthly" and month_day not in range(1, 29):
        raise ValueError("Choose a day of the month from 1 to 28.")


async def upsert_schedule(db: AsyncSession, company_id: int, ledger_id: int, user_id: int, *, channels: List[str],
                          frequency: str, send_time: str, weekday: Optional[int], month_day: Optional[int],
                          only_when_overdue: bool, now: datetime) -> ReminderSchedule:
    """One active schedule per customer: change it if there is one, otherwise create it (the caller commits)."""
    schedule = (await db.execute(select(ReminderSchedule).where(
        ReminderSchedule.company_id == company_id, ReminderSchedule.ledger_id == ledger_id,
        ReminderSchedule.active.is_(True)))).scalars().first()
    if not schedule:
        schedule = ReminderSchedule(company_id=company_id, ledger_id=ledger_id, created_by_user_id=user_id)
        db.add(schedule)
    schedule.channels = list(dict.fromkeys(channels))
    schedule.frequency, schedule.send_time = frequency, send_time
    schedule.weekday = weekday if frequency == "weekly" else None
    schedule.month_day = month_day if frequency == "monthly" else None
    schedule.only_when_overdue, schedule.active, schedule.stop_reason = only_when_overdue, True, None
    schedule.next_run_at = next_run(frequency, send_time, now, schedule.weekday, schedule.month_day, first=True)
    return schedule


def in_sending_hours(now: datetime) -> bool:
    return QUIET_START <= now.time() <= QUIET_END


async def run_due(db: AsyncSession, now: Optional[datetime] = None, limit: int = 200) -> int:
    """Send every schedule that's due. Returns how many schedules ran (sent, skipped or stopped)."""
    now = now or get_ist_now()
    if not in_sending_hours(now):
        return 0
    due = (await db.execute(select(ReminderSchedule).where(
        ReminderSchedule.active.is_(True), ReminderSchedule.next_run_at.is_not(None), ReminderSchedule.next_run_at <= now)
        .order_by(ReminderSchedule.next_run_at).limit(limit))).scalars().all()
    companies: Dict[int, Company] = {}
    ran = 0
    for schedule in due:
        company = companies.get(schedule.company_id)
        if company is None:
            company = companies[schedule.company_id] = (await db.execute(
                select(Company).where(Company.company_id == schedule.company_id))).scalars().first()
        if company is None:
            schedule.active, schedule.stop_reason = False, "stopped"
            continue
        party = await party_for(db, company.company_id, schedule.ledger_id)
        if not party or party.balance <= 0.005:
            schedule.active, schedule.stop_reason, schedule.next_run_at = False, "paid", None
        elif not (schedule.only_when_overdue and party.overdue <= 0.005):
            channels = list(schedule.channels or [])
            if channels == ["email"] and await emails_sent_today(db, now) >= settings.EMAIL_DAILY_LIMIT:
                continue  # stays due; goes out tomorrow once the limit resets
            await send_reminder(db, company, schedule.ledger_id, channels, schedule_id=schedule.id, now=now, party=party)
        if schedule.active:
            schedule.last_run_at = now
            schedule.next_run_at = next_run(schedule.frequency, schedule.send_time, now, schedule.weekday, schedule.month_day)
            if schedule.next_run_at is None:
                schedule.active, schedule.stop_reason = False, "done"
        ran += 1
        await db.commit()
    return ran


async def reminder_worker(interval_seconds: int = 300, initial_delay_seconds: int = 60):
    """Background loop in the web process (single worker), like the attendance worker."""
    from app.core.database import AsyncSessionLocal
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                ran = await run_due(db)
                if ran:
                    logger.info(f"Payment reminders: ran {ran} schedule(s)")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Payment reminder run failed")
        await asyncio.sleep(interval_seconds)


# ── WhatsApp delivery receipts ───────────────────────────────────────────────

async def apply_whatsapp_statuses(db: AsyncSession, payload: dict) -> int:
    """Update the log from Meta's webhook payload (entry[].changes[].value.statuses[]). Returns rows changed."""
    updates = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            for item in (change.get("value") or {}).get("statuses") or []:
                if item.get("id") and item.get("status") in STATUS_RANK:
                    updates.append(item)
    changed = 0
    for item in updates:
        log = (await db.execute(select(ReminderLog).where(
            ReminderLog.channel == "whatsapp", ReminderLog.provider_message_id == item["id"]))).scalars().first()
        if not log or STATUS_RANK.get(item["status"], 0) <= STATUS_RANK.get(log.status, 0):
            continue
        log.status, log.updated_at = item["status"], get_ist_now()
        if item["status"] == "failed":
            errors = item.get("errors") or [{}]
            log.detail = str(errors[0].get("title") or errors[0].get("message") or "Not delivered")[:500]
            name = (await db.execute(select(MstLedger.name).where(MstLedger.ledger_id == log.ledger_id))).scalar()
            await notify_failure(db, log.company_id, name or f"Ledger {log.ledger_id}", "whatsapp", log.detail)
        changed += 1
    return changed


# ── emailing a document (invoice / statement PDF) ────────────────────────────

async def email_document(
    db: AsyncSession, company: Company, ledger_id: int, *, to: str, subject: str, message: str, filename: str,
    content: bytes, reference: str, user_id: Optional[int], now: Optional[datetime] = None,
) -> ReminderLog:
    """Email a PDF someone asked to send now (not a reminder, so no sending hours or once-a-day rule). Logged in
    the customer's reminder history and counted toward the Gmail daily limit. The caller commits."""
    now = now or get_ist_now()
    recipient = messaging.clean_email(to)
    log = ReminderLog(company_id=company.company_id, ledger_id=ledger_id, channel="email", recipient=recipient or to[:150],
                      created_at=now, sent_by_user_id=user_id)
    ready, why = (await channel_readiness(db, company.company_id))["email"]
    if not ready:
        log.status, log.detail = "skipped", why
    elif not recipient:
        log.status, log.detail = "skipped", "That doesn't look like an email address."
    elif await emails_sent_today(db, now) >= settings.EMAIL_DAILY_LIMIT:
        log.status, log.detail = "skipped", f"Gmail daily limit reached ({settings.EMAIL_DAILY_LIMIT} emails)."
    elif settings.REMINDERS_DRY_RUN:
        log.status, log.detail = "dry_run", f"{reference}: dry run (REMINDERS_DRY_RUN), not sent."
    else:
        result = await messaging.send_email(recipient, subject, message, from_name=settings.SMTP_FROM_NAME or company.name,
                                            attachments=[(filename, content, "application/pdf")])
        log.status = "sent" if result.ok else "failed"
        log.provider_message_id = result.provider_message_id
        log.detail = reference if result.ok else f"{reference}: {result.error}"
    log.detail = (log.detail or "")[:500]
    db.add(log)
    return log
