"""Voucher approval (maker-checker, Phase 5): vouchers that match an approval rule are held back from Tally
(status "optional") until someone in the rule's approving role approves them.

Rules: voucher type (or every type), "amount at or over ₹X" (0 = every voucher) and the approving role. Admins and
people in the approving role are never held back. Approve → the voucher is confirmed (stock applied) and pushed to
Tally like any new voucher. Reject → it goes back to the maker as a draft with the note; they can edit it and send
it again.
"""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import is_admin_user
from app.models.portal_core import ApprovalRequest, ApprovalRule, Module, SyncQueue, User, UserCompanyAccess
from app.models.tally_core import MstStockItem, TrnInventory, TrnVoucher
from app.services.notifications import create_notifications


async def vouchers_module_id(db: AsyncSession) -> Optional[int]:
    return (await db.execute(select(Module.module_id).where(Module.code == "vouchers"))).scalar()


async def rule_for(db: AsyncSession, user: User, voucher_type_id: int, amount: Decimal) -> Optional[ApprovalRule]:
    """The first active rule this voucher falls under, or None (including for admins and approvers)."""
    if is_admin_user(user):
        return None
    module_id = await vouchers_module_id(db)
    if module_id is None:
        return None
    rules = (await db.execute(select(ApprovalRule).where(
        ApprovalRule.company_id == user.company_id, ApprovalRule.module_id == module_id, ApprovalRule.is_active.is_(True),
        or_(ApprovalRule.voucher_type_id.is_(None), ApprovalRule.voucher_type_id == voucher_type_id))
        .order_by(ApprovalRule.condition_value))).scalars().all()
    for rule in rules:
        if rule.approver_role_id == user.role_id:
            continue
        limit = Decimal(str(rule.condition_value or 0))
        if (rule.condition_operator == ">" and amount > limit) or (rule.condition_operator != ">" and amount >= limit):
            return rule
    return None


async def approver_ids(db: AsyncSession, company_id: int, role_id: int) -> List[int]:
    """Active users in the approving role who can open this company."""
    rows = await db.execute(
        select(User.user_id).outerjoin(UserCompanyAccess, UserCompanyAccess.user_id == User.user_id)
        .where(User.role_id == role_id, User.is_active.is_(True),
               or_(User.company_id == company_id, UserCompanyAccess.company_id == company_id)))
    return list(dict.fromkeys(rows.scalars().all()))


def describe(voucher: TrnVoucher, type_name: str) -> str:
    return f"{type_name} {voucher.voucher_number} for ₹{Decimal(str(voucher.total_amount or 0)):,.2f}"


async def request_approval(db: AsyncSession, user: User, voucher: TrnVoucher, rule: ApprovalRule, type_name: str) -> ApprovalRequest:
    """Hold the voucher and tell the approvers (the caller commits)."""
    voucher.status = "optional"
    request = ApprovalRequest(rule_id=rule.rule_id, voucher_id=voucher.voucher_id, requested_by=user.user_id, status="Pending")
    db.add(request)
    recipients = [uid for uid in await approver_ids(db, user.company_id, rule.approver_role_id) if uid != user.user_id]
    if recipients:
        await create_notifications(
            db, company_id=user.company_id, user_ids=recipients, type="voucher_approval",
            title=f"Approve {describe(voucher, type_name)}", message=f"Entered by {user.username}. It goes to Tally once approved.",
            link=f"/vouchers/{voucher.voucher_id}", reference_id=str(voucher.voucher_id), reference_type="voucher",
            group_key="voucher_approval", group_title=lambda n: f"{n} vouchers waiting for approval", group_link="/vouchers?tab=approvals",
        )
    return request


def can_decide(user: User, rule: ApprovalRule, request: ApprovalRequest) -> bool:
    if request.requested_by == user.user_id and not is_admin_user(user):
        return False
    return is_admin_user(user) or user.role_id == rule.approver_role_id


async def apply_stock(db: AsyncSession, voucher_id: int) -> None:
    """Moving a voucher to confirmed applies its stock (as PATCH /vouchers/{id}/status does)."""
    entries = (await db.execute(select(TrnInventory).where(TrnInventory.voucher_id == voucher_id))).scalars().all()
    for inv in entries:
        item = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv.stock_item_id))).scalars().first()
        if item:
            qty = float(inv.quantity)
            item.closing_qty = float(item.closing_qty or 0) + (qty if inv.is_inward else -qty)


async def confirm_and_queue(db: AsyncSession, company_id: int, voucher: TrnVoucher) -> SyncQueue:
    """Confirm a held voucher and queue it for Tally as a new voucher (the caller commits, then pushes)."""
    await apply_stock(db, voucher.voucher_id)
    voucher.status = "confirmed"
    sync_item = SyncQueue(company_id=company_id, record_type="Voucher", record_id=voucher.voucher_id, action="Create")
    db.add(sync_item)
    return sync_item


async def tell_maker(db: AsyncSession, company_id: int, request: ApprovalRequest, voucher: TrnVoucher, type_name: str,
                     approved: bool, by: User, note: Optional[str]) -> None:
    await create_notifications(
        db, company_id=company_id, user_ids=[request.requested_by], type="voucher_decision",
        title=f"{describe(voucher, type_name)} {'approved' if approved else 'sent back'}",
        message=(f"Approved by {by.username}; it's on its way to Tally." if approved
                 else f"{by.username}: {note or 'No note.'} Edit it and send it again."),
        link=f"/vouchers/{voucher.voucher_id}", reference_id=str(voucher.voucher_id), reference_type="voucher",
    )
