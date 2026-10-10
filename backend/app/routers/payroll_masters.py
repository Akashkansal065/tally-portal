"""
Payroll masters kept in step with Tally: attendance/production types, pay heads, employee groups and employees
(with their salary details). Employee categories are cost categories and work units are ordinary units, so
those two use the existing Cost Categories and Units screens.
"""
import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.cache import clear_company_cache
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import (
    MstAttendanceType, MstCostCategory, MstCostCentre, MstEmployeeSalaryRate, MstGroup, MstLedger, MstPayHead,
    TrnAccounting, TrnAttendance, TrnPayHead, TrnVoucher,
)
from app.services import payroll_masters as pm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payroll-masters", tags=["Payroll Masters"])

ATTENDANCE_KINDS = ("Attendance / Leave with Pay", "Leave without Pay", "Production", "User Defined Calendar Type")
PAY_HEAD_TYPES = ("Earnings for Employees", "Deductions from Employees", "Employees' Statutory Deductions", "Employer's Statutory Contributions",
                  "Employer's Other Charges", "Bonus", "Gratuity", "Loans and Advances", "Reimbursements to Employees")


class TallyOutcome(BaseModel):
    tally_guid: Optional[str] = None
    tally_master_id: Optional[int] = None
    # Outcome of the send made by a create or update; None on plain reads
    tally_synced: Optional[bool] = None
    tally_status: Optional[str] = None
    tally_message: Optional[str] = None


class AttendanceTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type_of_attendance: str = "Attendance / Leave with Pay"
    period: Optional[str] = "Days"
    unit_name: Optional[str] = None


class AttendanceTypeOut(AttendanceTypeIn, TallyOutcome):
    attendance_type_id: int


class PayHeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    pay_head_type: str = "Earnings for Employees"
    under_group_id: int
    payslip_name: Optional[str] = None
    calculation_type: Optional[str] = "As User Defined Value"


class PayHeadOut(TallyOutcome):
    pay_head_id: int
    name: str
    pay_head_type: str
    under_group_id: Optional[int] = None
    group_name: Optional[str] = None
    ledger_id: Optional[int] = None
    payslip_name: Optional[str] = None
    calculation_type: Optional[str] = None
    is_deduction: bool = False
    # False for pay heads whose calculation Tally holds and the app cannot edit (on attendance, computed, ...)
    calculation_editable: bool = True


class SalaryRate(BaseModel):
    effective_from: date
    pay_head_name: str
    rate: Optional[Decimal] = None


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category_id: int
    parent_id: Optional[int] = None
    is_employee_group: bool = False
    employee_number: Optional[str] = None
    date_of_join: Optional[date] = None
    designation: Optional[str] = None
    gender: Optional[str] = None
    salary_rates: List[SalaryRate] = []


class EmployeeOut(TallyOutcome):
    cost_centre_id: int
    name: str
    category_id: int
    category_name: Optional[str] = None
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    is_employee_group: bool = False
    employee_number: Optional[str] = None
    date_of_join: Optional[date] = None
    designation: Optional[str] = None
    gender: Optional[str] = None
    salary_rates: List[SalaryRate] = []


def _company_vouchers(company_id: int):
    """The Trn* payroll lines carry no company of their own; they are reached through their voucher."""
    return select(TrnVoucher.voucher_id).where(TrnVoucher.company_id == company_id)


def _outcome(result: Optional[dict]) -> dict:
    if result is None:
        return {}
    return {"tally_synced": result["status"] == "SUCCESS", "tally_status": result["status"],
            "tally_message": result["message"] if result["status"] != "SUCCESS" else None}


async def _name_taken(db, model, id_attr, company_id: int, name: str, own_id: Optional[int] = None, extra=None) -> bool:
    stmt = select(getattr(model, id_attr)).where(model.company_id == company_id, func.lower(model.name) == name.strip().lower())
    if own_id:
        stmt = stmt.where(getattr(model, id_attr) != own_id)
    if extra is not None:
        stmt = stmt.where(extra)
    return (await db.execute(stmt)).first() is not None


async def _save(db: AsyncSession, user: User, record_type: str, row, id_attr: str, action: str, tally_name: Optional[str] = None) -> dict:
    """
    Sends a created or changed master to Tally before it is committed. Refused by Tally: nothing is kept and
    the caller gets Tally's reason. Tally away: the change is kept and queued.
    """
    await db.flush()
    record_id, name, company_id = getattr(row, id_attr), row.name, user.company_id
    fresh = await pm.load_row(db, record_type, record_id)
    guid = await pm.tally_identity(db, record_type, fresh)
    result = await pm.send_master(db, company_id, record_type, record_id, action, name, await pm.build_body(db, record_type, fresh), guid, tally_name)
    if result["status"] == "REJECTED":
        await db.rollback()
        await pm.record_master_push(db, company_id, record_type, record_id, name, action, result)
        raise HTTPException(status_code=400, detail=f"Tally did not accept this: {result['message']}")
    if result["status"] == "SUCCESS":
        await pm.store_identity(db, record_type, fresh, result)
    else:
        await pm.queue_for_later(db, company_id, record_type, record_id, action, guid, tally_name or name)
    await db.commit()
    await pm.record_master_push(db, company_id, record_type, record_id, name, action, result)
    clear_company_cache(company_id)
    return result


async def _remove(db: AsyncSession, user: User, record_type: str, row, id_attr: str, also_delete=()) -> dict:
    """Deletes in Tally first. Refused: the record stays here too. Tally away: deleted here, and the delete is queued."""
    record_id, name, company_id = getattr(row, id_attr), row.name, user.company_id
    guid = await pm.tally_identity(db, record_type, row)
    result = await pm.send_master(db, company_id, record_type, record_id, "Delete", name, "", guid, name)
    if result["status"] == "REJECTED":
        await db.rollback()
        await pm.record_master_push(db, company_id, record_type, record_id, name, "Delete", result)
        raise HTTPException(status_code=400, detail=f"Tally did not allow the delete: {result['message']}")
    if result["status"] not in ("SUCCESS", "ALREADY_ABSENT"):
        await pm.queue_for_later(db, company_id, record_type, record_id, "Delete", guid, name)
    for extra in also_delete:
        await db.delete(extra)
    await db.delete(row)
    await db.commit()
    await pm.record_master_push(db, company_id, record_type, record_id, name, "Delete", result)
    clear_company_cache(company_id)
    return result


# ---------------------------------------------------------------------------------------------------
# Attendance / production types
# ---------------------------------------------------------------------------------------------------

def _attendance_out(row: MstAttendanceType, result: Optional[dict] = None) -> AttendanceTypeOut:
    return AttendanceTypeOut(attendance_type_id=row.attendance_type_id, name=row.name, type_of_attendance=row.type_of_attendance or ATTENDANCE_KINDS[0],
                             period=row.period, unit_name=row.unit_name, tally_guid=row.tally_guid, tally_master_id=row.tally_master_id, **_outcome(result))


def _check_attendance(req: AttendanceTypeIn) -> None:
    if req.type_of_attendance not in ATTENDANCE_KINDS:
        raise HTTPException(status_code=400, detail=f"Type must be one of: {', '.join(ATTENDANCE_KINDS)}")
    if req.type_of_attendance == "Production" and not (req.unit_name or "").strip():
        raise HTTPException(status_code=400, detail="A production type needs the unit it is measured in.")


@router.get("/attendance-types", response_model=List[AttendanceTypeOut])
async def list_attendance_types(user: User = Depends(require_permission("payroll", "read")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(MstAttendanceType).where(MstAttendanceType.company_id == user.company_id).order_by(MstAttendanceType.name))).scalars().all()
    return [_attendance_out(r) for r in rows]


@router.post("/attendance-types", response_model=AttendanceTypeOut, status_code=201)
async def create_attendance_type(req: AttendanceTypeIn, user: User = Depends(require_permission("payroll", "create")), db: AsyncSession = Depends(get_db)):
    _check_attendance(req)
    if await _name_taken(db, MstAttendanceType, "attendance_type_id", user.company_id, req.name):
        raise HTTPException(status_code=400, detail="An attendance type with this name already exists.")
    production = req.type_of_attendance == "Production"
    row = MstAttendanceType(company_id=user.company_id, name=req.name.strip(), type_of_attendance=req.type_of_attendance,
                            period=None if production else (req.period or "Days"), unit_name=req.unit_name.strip() if production else None)
    db.add(row)
    result = await _save(db, user, "AttendanceType", row, "attendance_type_id", "Create")
    return _attendance_out(await pm.load_row(db, "AttendanceType", row.attendance_type_id), result)


@router.put("/attendance-types/{type_id}", response_model=AttendanceTypeOut)
async def update_attendance_type(type_id: int, req: AttendanceTypeIn, user: User = Depends(require_permission("payroll", "update")), db: AsyncSession = Depends(get_db)):
    _check_attendance(req)
    row = (await db.execute(select(MstAttendanceType).where(MstAttendanceType.attendance_type_id == type_id, MstAttendanceType.company_id == user.company_id))).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Attendance type not found.")
    if await _name_taken(db, MstAttendanceType, "attendance_type_id", user.company_id, req.name, type_id):
        raise HTTPException(status_code=400, detail="An attendance type with this name already exists.")
    old_name, production = row.name, req.type_of_attendance == "Production"
    row.name, row.type_of_attendance = req.name.strip(), req.type_of_attendance
    row.period, row.unit_name = (None, req.unit_name.strip()) if production else (req.period or "Days", None)
    if old_name != row.name:
        # Vouchers name the attendance type, so they follow the rename
        await db.execute(update(TrnAttendance).where(TrnAttendance.attendancetype_name == old_name, TrnAttendance.voucher_id.in_(_company_vouchers(user.company_id)))
                         .values(attendancetype_name=row.name))
    result = await _save(db, user, "AttendanceType", row, "attendance_type_id", "Alter", old_name)
    return _attendance_out(await pm.load_row(db, "AttendanceType", type_id), result)


@router.delete("/attendance-types/{type_id}")
async def delete_attendance_type(type_id: int, user: User = Depends(require_permission("payroll", "delete")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(MstAttendanceType).where(MstAttendanceType.attendance_type_id == type_id, MstAttendanceType.company_id == user.company_id))).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Attendance type not found.")
    if (await db.execute(select(TrnAttendance.attendancetype_name).where(TrnAttendance.attendancetype_name == row.name, TrnAttendance.voucher_id.in_(_company_vouchers(user.company_id))).limit(1))).first():
        raise HTTPException(status_code=400, detail="This attendance type is used in attendance vouchers and cannot be deleted.")
    result = await _remove(db, user, "AttendanceType", row, "attendance_type_id")
    return {"message": "Attendance type deleted.", **_outcome(result)}


# ---------------------------------------------------------------------------------------------------
# Pay heads (each one is a ledger)
# ---------------------------------------------------------------------------------------------------

async def _pay_head_out(db: AsyncSession, row: MstPayHead, result: Optional[dict] = None) -> PayHeadOut:
    ledger = (await db.execute(select(MstLedger).where(MstLedger.ledger_id == row.ledger_id))).scalars().first() if row.ledger_id else None
    group_id = row.under_group_id or (ledger.group_id if ledger else None)
    group = (await db.execute(select(MstGroup.name).where(MstGroup.group_id == group_id))).scalars().first() if group_id else None
    calculation = row.calculation_type
    return PayHeadOut(pay_head_id=row.pay_head_id, name=row.name, pay_head_type=row.pay_head_type, under_group_id=group_id, group_name=group,
                      ledger_id=row.ledger_id, payslip_name=row.payslip_name or row.name, calculation_type=calculation,
                      is_deduction="deduction" in (row.pay_head_type or "").lower(), calculation_editable=calculation in pm.SIMPLE_CALCULATIONS,
                      tally_guid=ledger.tally_guid if ledger else None, tally_master_id=ledger.tally_master_id if ledger else None, **_outcome(result))


async def _check_pay_head(db: AsyncSession, user: User, req: PayHeadIn, existing: Optional[MstPayHead] = None) -> None:
    # Tally writes some of these with different capitals ("Deductions From Employees")
    known = {t.lower(): t for t in PAY_HEAD_TYPES}
    if req.pay_head_type.lower() not in known:
        raise HTTPException(status_code=400, detail=f"Pay head type must be one of: {', '.join(PAY_HEAD_TYPES)}")
    req.pay_head_type = known[req.pay_head_type.lower()]
    # An existing pay head keeps the calculation Tally holds for it unless it is one of the two the app can set
    locked = existing is not None and existing.calculation_type not in pm.SIMPLE_CALCULATIONS
    if not locked and (req.calculation_type or "As User Defined Value") not in pm.SIMPLE_CALCULATIONS:
        raise HTTPException(status_code=400, detail="Only 'As User Defined Value' and 'Flat Rate' pay heads can be set up here; set up calculated ones in Tally.")
    if not (await db.execute(select(MstGroup.group_id).where(MstGroup.group_id == req.under_group_id, MstGroup.company_id == user.company_id))).first():
        raise HTTPException(status_code=400, detail="Account group not found.")


async def _link_pay_head_ledger(db: AsyncSession, row: MstPayHead) -> Optional[MstLedger]:
    """The ledger behind a pay head; pay heads read from Tally are tied to theirs by name the first time."""
    if row.ledger_id:
        return (await db.execute(select(MstLedger).where(MstLedger.ledger_id == row.ledger_id))).scalars().first()
    ledger = (await db.execute(select(MstLedger).where(MstLedger.company_id == row.company_id, func.lower(MstLedger.name) == row.name.lower()))).scalars().first()
    if ledger:
        row.ledger_id = ledger.ledger_id
        row.under_group_id = row.under_group_id or ledger.group_id
    return ledger


@router.get("/pay-heads", response_model=List[PayHeadOut])
async def list_pay_heads(user: User = Depends(require_permission("payroll", "read")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(MstPayHead).where(MstPayHead.company_id == user.company_id).order_by(MstPayHead.name))).scalars().all()
    for row in rows:
        await _link_pay_head_ledger(db, row)
    out = [await _pay_head_out(db, r) for r in rows]
    await db.commit()
    return out


@router.post("/pay-heads", response_model=PayHeadOut, status_code=201)
async def create_pay_head(req: PayHeadIn, user: User = Depends(require_permission("payroll", "create")), db: AsyncSession = Depends(get_db)):
    await _check_pay_head(db, user, req)
    if await _name_taken(db, MstLedger, "ledger_id", user.company_id, req.name) or await _name_taken(db, MstPayHead, "pay_head_id", user.company_id, req.name):
        raise HTTPException(status_code=400, detail="A ledger or pay head with this name already exists.")
    ledger = MstLedger(company_id=user.company_id, name=req.name.strip(), group_id=req.under_group_id)
    db.add(ledger)
    await db.flush()
    row = MstPayHead(company_id=user.company_id, name=req.name.strip(), pay_head_type=req.pay_head_type, under_group_id=req.under_group_id,
                     ledger_id=ledger.ledger_id, payslip_name=(req.payslip_name or req.name).strip(), calculation_type=req.calculation_type or "As User Defined Value")
    db.add(row)
    result = await _save(db, user, "PayHead", row, "pay_head_id", "Create")
    return await _pay_head_out(db, await pm.load_row(db, "PayHead", row.pay_head_id), result)


@router.put("/pay-heads/{pay_head_id}", response_model=PayHeadOut)
async def update_pay_head(pay_head_id: int, req: PayHeadIn, user: User = Depends(require_permission("payroll", "update")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(MstPayHead).where(MstPayHead.pay_head_id == pay_head_id, MstPayHead.company_id == user.company_id))).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Pay head not found.")
    await _check_pay_head(db, user, req, row)
    ledger = await _link_pay_head_ledger(db, row)
    if await _name_taken(db, MstLedger, "ledger_id", user.company_id, req.name, ledger.ledger_id if ledger else None) \
            or await _name_taken(db, MstPayHead, "pay_head_id", user.company_id, req.name, pay_head_id):
        raise HTTPException(status_code=400, detail="A ledger or pay head with this name already exists.")
    old_name = row.name
    row.name, row.pay_head_type, row.under_group_id = req.name.strip(), req.pay_head_type, req.under_group_id
    row.payslip_name = (req.payslip_name or req.name).strip()
    if row.calculation_type in pm.SIMPLE_CALCULATIONS:
        row.calculation_type = req.calculation_type or row.calculation_type
    if ledger:
        ledger.name, ledger.group_id = row.name, req.under_group_id
    if old_name != row.name:
        await db.execute(update(TrnPayHead).where(TrnPayHead.payhead_name == old_name, TrnPayHead.voucher_id.in_(_company_vouchers(user.company_id))).values(payhead_name=row.name))
        await db.execute(update(MstEmployeeSalaryRate).where(MstEmployeeSalaryRate.company_id == user.company_id, MstEmployeeSalaryRate.pay_head_name == old_name)
                         .values(pay_head_name=row.name))
    result = await _save(db, user, "PayHead", row, "pay_head_id", "Alter", old_name)
    return await _pay_head_out(db, await pm.load_row(db, "PayHead", pay_head_id), result)


@router.delete("/pay-heads/{pay_head_id}")
async def delete_pay_head(pay_head_id: int, user: User = Depends(require_permission("payroll", "delete")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(MstPayHead).where(MstPayHead.pay_head_id == pay_head_id, MstPayHead.company_id == user.company_id))).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Pay head not found.")
    ledger = await _link_pay_head_ledger(db, row)
    if ledger and (await db.execute(select(TrnAccounting.ledger_id).where(TrnAccounting.ledger_id == ledger.ledger_id).limit(1))).first():
        raise HTTPException(status_code=400, detail="This pay head has been used in vouchers and cannot be deleted.")
    if (await db.execute(select(MstEmployeeSalaryRate.rate_id).where(MstEmployeeSalaryRate.company_id == user.company_id, MstEmployeeSalaryRate.pay_head_name == row.name).limit(1))).first():
        raise HTTPException(status_code=400, detail="This pay head is part of an employee's salary details; remove it there first.")
    result = await _remove(db, user, "PayHead", row, "pay_head_id", also_delete=[ledger] if ledger else [])
    return {"message": "Pay head deleted.", **_outcome(result)}


# ---------------------------------------------------------------------------------------------------
# Employee groups and employees (payroll cost centres)
# ---------------------------------------------------------------------------------------------------

async def _employee_out(db: AsyncSession, row: MstCostCentre, result: Optional[dict] = None) -> EmployeeOut:
    category = (await db.execute(select(MstCostCategory.name).where(MstCostCategory.category_id == row.category_id))).scalars().first()
    parent = (await db.execute(select(MstCostCentre.name).where(MstCostCentre.cost_centre_id == row.parent_id))).scalars().first() if row.parent_id else None
    return EmployeeOut(cost_centre_id=row.cost_centre_id, name=row.name, category_id=row.category_id, category_name=category, parent_id=row.parent_id, parent_name=parent,
                       is_employee_group=bool(row.is_employee_group), employee_number=row.employee_number, date_of_join=row.date_of_join,
                       designation=row.designation, gender=row.gender,
                       salary_rates=[SalaryRate(effective_from=r.effective_from, pay_head_name=r.pay_head_name, rate=r.rate) for r in row.salary_rates],
                       tally_guid=row.tally_guid, tally_master_id=row.tally_master_id, **_outcome(result))


async def _check_employee(db: AsyncSession, user: User, req: EmployeeIn, own_id: Optional[int] = None) -> None:
    if not (await db.execute(select(MstCostCategory.category_id).where(MstCostCategory.category_id == req.category_id, MstCostCategory.company_id == user.company_id))).first():
        raise HTTPException(status_code=400, detail="Employee category not found.")
    if req.parent_id:
        parent = (await db.execute(select(MstCostCentre).where(MstCostCentre.cost_centre_id == req.parent_id, MstCostCentre.company_id == user.company_id))).scalars().first()
        if not parent or not parent.is_employee_group or parent.cost_centre_id == own_id:
            raise HTTPException(status_code=400, detail="The group must be an existing employee group.")
    if await _name_taken(db, MstCostCentre, "cost_centre_id", user.company_id, req.name, own_id):
        raise HTTPException(status_code=400, detail="An employee, group or cost centre with this name already exists.")
    if req.is_employee_group:
        return
    known = {n.lower() for n in (await db.execute(select(MstPayHead.name).where(MstPayHead.company_id == user.company_id))).scalars().all()}
    unknown = sorted({r.pay_head_name for r in req.salary_rates if r.pay_head_name.lower() not in known})
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown pay head: {', '.join(unknown)}")


def _apply_employee(row: MstCostCentre, req: EmployeeIn, company_id: int) -> None:
    row.name, row.category_id, row.parent_id = req.name.strip(), req.category_id, req.parent_id
    row.for_payroll, row.is_employee_group = True, req.is_employee_group
    group = req.is_employee_group
    row.employee_number = None if group else (req.employee_number or None)
    row.date_of_join = None if group else req.date_of_join
    row.designation = None if group else (req.designation or None)
    row.gender = None if group else (req.gender or None)
    row.salary_rates = [] if group else [
        MstEmployeeSalaryRate(company_id=company_id, effective_from=r.effective_from, pay_head_name=r.pay_head_name, rate=r.rate, position=i)
        for i, r in enumerate(req.salary_rates)]


@router.get("/employees", response_model=List[EmployeeOut])
async def list_employees(user: User = Depends(require_permission("payroll", "read")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(MstCostCentre).options(selectinload(MstCostCentre.salary_rates))
                             .where(MstCostCentre.company_id == user.company_id, MstCostCentre.for_payroll == True)  # noqa: E712
                             .order_by(MstCostCentre.is_employee_group.desc(), MstCostCentre.name))).scalars().all()
    return [await _employee_out(db, r) for r in rows]


@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(req: EmployeeIn, user: User = Depends(require_permission("payroll", "create")), db: AsyncSession = Depends(get_db)):
    await _check_employee(db, user, req)
    row = MstCostCentre(company_id=user.company_id, name=req.name.strip(), category_id=req.category_id, is_active=True)
    _apply_employee(row, req, user.company_id)
    db.add(row)
    result = await _save(db, user, "Employee", row, "cost_centre_id", "Create")
    return await _employee_out(db, await pm.load_row(db, "Employee", row.cost_centre_id), result)


@router.put("/employees/{cost_centre_id}", response_model=EmployeeOut)
async def update_employee(cost_centre_id: int, req: EmployeeIn, user: User = Depends(require_permission("payroll", "update")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(MstCostCentre).options(selectinload(MstCostCentre.salary_rates)).where(
        MstCostCentre.cost_centre_id == cost_centre_id, MstCostCentre.company_id == user.company_id, MstCostCentre.for_payroll == True))).scalars().first()  # noqa: E712
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if bool(row.is_employee_group) != req.is_employee_group:
        raise HTTPException(status_code=400, detail="An employee cannot be turned into a group or back.")
    await _check_employee(db, user, req, cost_centre_id)
    old_name = row.name
    _apply_employee(row, req, user.company_id)
    if old_name != row.name:
        for model in (TrnAttendance, TrnPayHead):
            await db.execute(update(model).where(model.employee_name == old_name, model.voucher_id.in_(_company_vouchers(user.company_id))).values(employee_name=row.name))
    result = await _save(db, user, "Employee", row, "cost_centre_id", "Alter", old_name)
    return await _employee_out(db, await pm.load_row(db, "Employee", cost_centre_id), result)


@router.delete("/employees/{cost_centre_id}")
async def delete_employee(cost_centre_id: int, user: User = Depends(require_permission("payroll", "delete")), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(MstCostCentre).where(
        MstCostCentre.cost_centre_id == cost_centre_id, MstCostCentre.company_id == user.company_id, MstCostCentre.for_payroll == True))).scalars().first()  # noqa: E712
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")
    if (await db.execute(select(MstCostCentre.cost_centre_id).where(MstCostCentre.parent_id == cost_centre_id).limit(1))).first():
        raise HTTPException(status_code=400, detail="This group still has employees or groups under it.")
    for model in (TrnAttendance, TrnPayHead):
        if (await db.execute(select(model.employee_name).where(model.employee_name == row.name, model.voucher_id.in_(_company_vouchers(user.company_id))).limit(1))).first():
            raise HTTPException(status_code=400, detail="This employee appears in attendance or payroll vouchers and cannot be deleted.")
    result = await _remove(db, user, "Employee", row, "cost_centre_id")
    return {"message": "Deleted.", **_outcome(result)}
