"""Voucher approval (maker-checker): rules, the queue, approve / reject, and sending a rejected voucher again.
The rules and holding logic are in app/services/approvals.py."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import clear_company_cache
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import get_current_user, is_admin_user, require_permission
from app.models.portal_core import ApprovalRequest, ApprovalRule, AuditLog, Role, User
from app.models.tally_core import MstLedger, MstVoucherType, TrnVoucher
from app.routers.admin import require_admin
from app.services import approvals as svc

router = APIRouter(prefix="/approvals", tags=["Voucher approval"])


class RuleIn(BaseModel):
    voucher_type_id: Optional[int] = None  # None: every voucher type
    min_amount: Decimal = Field(Decimal("0"), ge=0)  # 0: every voucher
    approver_role_id: int


class RuleChange(BaseModel):
    voucher_type_id: Optional[int] = None
    all_types: bool = False  # set to clear voucher_type_id
    min_amount: Optional[Decimal] = Field(None, ge=0)
    approver_role_id: Optional[int] = None
    is_active: Optional[bool] = None


class Decision(BaseModel):
    note: str = Field("", max_length=500)


async def _rule_out(db: AsyncSession, rule: ApprovalRule) -> dict:
    vtype = (await db.execute(select(MstVoucherType.name).where(MstVoucherType.voucher_type_id == rule.voucher_type_id))).scalar() if rule.voucher_type_id else None
    role = (await db.execute(select(Role.name).where(Role.role_id == rule.approver_role_id))).scalar()
    return {"rule_id": rule.rule_id, "voucher_type_id": rule.voucher_type_id, "voucher_type": vtype or "All voucher types",
            "min_amount": float(rule.condition_value or 0), "approver_role_id": rule.approver_role_id, "approver_role": role,
            "is_active": bool(rule.is_active)}


async def _check_refs(db: AsyncSession, company_id: int, voucher_type_id: Optional[int], role_id: Optional[int]) -> None:
    if voucher_type_id is not None:
        found = (await db.execute(select(MstVoucherType.voucher_type_id).where(
            MstVoucherType.voucher_type_id == voucher_type_id, MstVoucherType.company_id == company_id))).scalar()
        if not found:
            raise HTTPException(status_code=404, detail="Voucher type not found.")
    if role_id is not None and not (await db.execute(select(Role.role_id).where(Role.role_id == role_id))).scalar():
        raise HTTPException(status_code=404, detail="Role not found.")


@router.get("/rules")
async def list_rules(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rules = (await db.execute(select(ApprovalRule).where(ApprovalRule.company_id == user.company_id, ApprovalRule.is_active.is_(True))
                              .order_by(ApprovalRule.rule_id))).scalars().all()
    return [await _rule_out(db, r) for r in rules]


@router.post("/rules")
async def create_rule(req: RuleIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    await _check_refs(db, user.company_id, req.voucher_type_id, req.approver_role_id)
    module_id = await svc.vouchers_module_id(db)
    if module_id is None:
        raise HTTPException(status_code=409, detail="The vouchers module isn't set up.")
    rule = ApprovalRule(company_id=user.company_id, module_id=module_id, voucher_type_id=req.voucher_type_id,
                        condition_field="total_amount", condition_operator=">=", condition_value=req.min_amount,
                        approver_role_id=req.approver_role_id, is_active=True)
    db.add(rule)
    await db.flush()
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="CREATE", entity_type="ApprovalRule", entity_id=rule.rule_id))
    await db.commit()
    return await _rule_out(db, rule)


@router.put("/rules/{rule_id}")
async def change_rule(rule_id: int, req: RuleChange, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rule = (await db.execute(select(ApprovalRule).where(ApprovalRule.rule_id == rule_id, ApprovalRule.company_id == user.company_id))).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    await _check_refs(db, user.company_id, req.voucher_type_id, req.approver_role_id)
    if req.all_types:
        rule.voucher_type_id = None
    elif req.voucher_type_id is not None:
        rule.voucher_type_id = req.voucher_type_id
    if req.min_amount is not None:
        rule.condition_value, rule.condition_operator = req.min_amount, ">="
    if req.approver_role_id is not None:
        rule.approver_role_id = req.approver_role_id
    if req.is_active is not None:
        rule.is_active = req.is_active
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="UPDATE", entity_type="ApprovalRule", entity_id=rule.rule_id))
    await db.commit()
    return await _rule_out(db, rule)


@router.delete("/rules/{rule_id}")
async def remove_rule(rule_id: int, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Switches the rule off (requests already made keep their history). Vouchers held by it stay in the queue."""
    rule = (await db.execute(select(ApprovalRule).where(ApprovalRule.rule_id == rule_id, ApprovalRule.company_id == user.company_id))).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    rule.is_active = False
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="DELETE", entity_type="ApprovalRule", entity_id=rule.rule_id))
    await db.commit()
    return {"detail": "Rule removed."}


async def _latest_requests(db: AsyncSession, company_id: int):
    """The latest request per voucher (a resubmitted voucher has several), with its rule and voucher."""
    latest = (select(func.max(ApprovalRequest.request_id)).join(TrnVoucher, TrnVoucher.voucher_id == ApprovalRequest.voucher_id)
              .where(TrnVoucher.company_id == company_id).group_by(ApprovalRequest.voucher_id))
    rows = await db.execute(
        select(ApprovalRequest, ApprovalRule, TrnVoucher, MstVoucherType.name, MstLedger.name)
        .join(ApprovalRule, ApprovalRule.rule_id == ApprovalRequest.rule_id)
        .join(TrnVoucher, TrnVoucher.voucher_id == ApprovalRequest.voucher_id)
        .outerjoin(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .outerjoin(MstLedger, MstLedger.ledger_id == TrnVoucher.party_ledger_id)
        .where(ApprovalRequest.request_id.in_(latest))
        .order_by(ApprovalRequest.requested_at.desc(), ApprovalRequest.request_id.desc()))
    return rows.all()


async def _names(db: AsyncSession, ids) -> dict:
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return dict((await db.execute(select(User.user_id, User.username).where(User.user_id.in_(ids)))).all())


def _request_out(req: ApprovalRequest, rule: ApprovalRule, v: TrnVoucher, type_name: Optional[str], party: Optional[str], names: dict, user: User) -> dict:
    return {
        "request_id": req.request_id, "status": req.status, "voucher_id": v.voucher_id, "voucher_number": v.voucher_number,
        "voucher_type": type_name, "voucher_date": v.voucher_date.isoformat() if v.voucher_date else None, "party": party,
        "amount": float(v.total_amount or 0), "requested_by": names.get(req.requested_by), "requested_by_id": req.requested_by,
        "requested_at": req.requested_at.isoformat() if req.requested_at else None,
        "acted_by": names.get(req.acted_by), "acted_at": req.acted_at.isoformat() if req.acted_at else None,
        "note": req.comments, "can_decide": req.status == "Pending" and svc.can_decide(user, rule, req),
    }


@router.get("/requests")
async def list_requests(
    scope: str = Query("to_me", pattern="^(to_me|mine|all)$"),
    status: str = Query("Pending", pattern="^(Pending|Approved|Rejected|all)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """to_me: what this user can approve; mine: what this user sent; all: everything (admins)."""
    rows = await _latest_requests(db, user.company_id)
    names = await _names(db, [r[0].requested_by for r in rows] + [r[0].acted_by for r in rows])
    out = []
    for req, rule, v, type_name, party in rows:
        if status != "all" and req.status != status:
            continue
        if scope == "mine" and req.requested_by != user.user_id:
            continue
        if scope == "to_me" and not svc.can_decide(user, rule, req):
            continue
        if scope == "all" and not is_admin_user(user):
            continue
        out.append(_request_out(req, rule, v, type_name, party, names, user))
    return out


@router.get("/summary")
async def summary(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await _latest_requests(db, user.company_id)
    return {
        "waiting_for_me": sum(1 for req, rule, *_ in rows if req.status == "Pending" and svc.can_decide(user, rule, req)),
        "mine_pending": sum(1 for req, *_ in rows if req.status == "Pending" and req.requested_by == user.user_id),
        "mine_rejected": sum(1 for req, *_ in rows if req.status == "Rejected" and req.requested_by == user.user_id),
    }


@router.get("/vouchers/{voucher_id}")
async def voucher_approval(voucher_id: int, user: User = Depends(require_permission("vouchers", "read")), db: AsyncSession = Depends(get_db)):
    """The voucher's latest approval request, if it has one (for the voucher page banner)."""
    for req, rule, v, type_name, party in await _latest_requests(db, user.company_id):
        if v.voucher_id == voucher_id:
            names = await _names(db, [req.requested_by, req.acted_by])
            out = _request_out(req, rule, v, type_name, party, names, user)
            out["approver_role"] = (await db.execute(select(Role.name).where(Role.role_id == rule.approver_role_id))).scalar()
            out["can_resubmit"] = req.status == "Rejected" and (req.requested_by == user.user_id or is_admin_user(user))
            return out
    return None


async def _pending(db: AsyncSession, user: User, request_id: int):
    row = (await db.execute(
        select(ApprovalRequest, ApprovalRule, TrnVoucher, MstVoucherType.name)
        .join(ApprovalRule, ApprovalRule.rule_id == ApprovalRequest.rule_id)
        .join(TrnVoucher, TrnVoucher.voucher_id == ApprovalRequest.voucher_id)
        .outerjoin(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(ApprovalRequest.request_id == request_id, TrnVoucher.company_id == user.company_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found.")
    req, rule, voucher, type_name = row
    if req.status != "Pending":
        raise HTTPException(status_code=409, detail=f"Already {req.status.lower()}.")
    if not svc.can_decide(user, rule, req):
        raise HTTPException(status_code=403, detail="Only the approving role (or an admin) can decide, and not on their own voucher.")
    return req, rule, voucher, type_name or "Voucher"


@router.post("/requests/{request_id}/approve")
async def approve(request_id: int, body: Decision, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    req, rule, voucher, type_name = await _pending(db, user, request_id)
    req.status, req.acted_by, req.acted_at, req.comments = "Approved", user.user_id, get_ist_now(), body.note.strip() or None
    sync_item = await svc.confirm_and_queue(db, user.company_id, voucher)
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="APPROVE", entity_type="Voucher", entity_id=voucher.voucher_id))
    await svc.tell_maker(db, user.company_id, req, voucher, type_name, True, user, body.note)
    await db.commit()
    await db.refresh(sync_item)
    from app.routers.sync import try_push_voucher_realtime
    await try_push_voucher_realtime(voucher.voucher_id, sync_item.sync_id, "Create", db)
    clear_company_cache(user.company_id)
    return {"detail": "Approved and sent to Tally.", "status": "Approved"}


@router.post("/requests/{request_id}/reject")
async def reject(request_id: int, body: Decision, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not body.note.strip():
        raise HTTPException(status_code=422, detail="Say what needs changing.")
    req, rule, voucher, type_name = await _pending(db, user, request_id)
    req.status, req.acted_by, req.acted_at, req.comments = "Rejected", user.user_id, get_ist_now(), body.note.strip()
    voucher.status = "draft"
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="REJECT", entity_type="Voucher", entity_id=voucher.voucher_id))
    await svc.tell_maker(db, user.company_id, req, voucher, type_name, False, user, body.note.strip())
    await db.commit()
    clear_company_cache(user.company_id)
    return {"detail": "Sent back to the maker.", "status": "Rejected"}


@router.post("/vouchers/{voucher_id}/resubmit")
async def resubmit(voucher_id: int, user: User = Depends(require_permission("vouchers", "update")), db: AsyncSession = Depends(get_db)):
    """After editing a rejected voucher: check the rules again. Held again → a new request; otherwise it's confirmed
    and sent to Tally."""
    voucher = (await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))).scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found.")
    last = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.voucher_id == voucher_id)
                             .order_by(ApprovalRequest.request_id.desc()))).scalars().first()
    if not last or last.status != "Rejected" or voucher.status != "draft":
        raise HTTPException(status_code=409, detail="Only a voucher that was sent back can be sent again.")
    if last.requested_by != user.user_id and not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Only the person who entered it can send it again.")
    type_name = (await db.execute(select(MstVoucherType.name).where(MstVoucherType.voucher_type_id == voucher.voucher_type_id))).scalar() or "Voucher"
    rule = await svc.rule_for(db, user, voucher.voucher_type_id, Decimal(str(voucher.total_amount or 0)))
    if rule:
        await svc.request_approval(db, user, voucher, rule, type_name)
        await db.commit()
        return {"detail": "Sent for approval again.", "status": "Pending"}
    sync_item = await svc.confirm_and_queue(db, user.company_id, voucher)
    await db.commit()
    await db.refresh(sync_item)
    from app.routers.sync import try_push_voucher_realtime
    await try_push_voucher_realtime(voucher.voucher_id, sync_item.sync_id, "Create", db)
    clear_company_cache(user.company_id)
    return {"detail": "No approval needed now; sent to Tally.", "status": "Approved"}
