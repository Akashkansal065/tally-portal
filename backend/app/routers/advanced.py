from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.ledger import MstLedger
from app.models.voucher import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.advanced import (
    Employee, SalaryComponent, SalaryStructure, SalaryStructureComponent,
    PayrollPeriod, Payslip, PayslipComponent, PosPayment, EinvoiceMetadata
)
from app.schemas.advanced import (
    EmployeeCreate, EmployeeResponse,
    SalaryComponentCreate, SalaryComponentResponse,
    SalaryStructureCreate, SalaryStructureResponse,
    PayrollPeriodCreate, PayrollPeriodResponse,
    PayslipResponse, PosPaymentCreate, PosPaymentResponse,
    EinvoiceMetadataCreate, EinvoiceMetadataResponse
)

router = APIRouter(tags=["Advanced Modules"])

# --- Employees ---

@router.post("/payroll/employees", response_model=EmployeeResponse)
async def create_employee(
    req: EmployeeCreate,
    user: User = Depends(require_permission("payroll", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        jdate = datetime.strptime(req.date_of_joining, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Verify ledger exists
    ledg_query = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == req.payment_ledger_id, MstLedger.company_id == user.company_id)
    )
    if not ledg_query.scalars().first():
        raise HTTPException(status_code=400, detail="Payment ledger not found.")
        
    # Check duplicate code
    dup_query = await db.execute(
        select(Employee).where(
            Employee.employee_code == req.employee_code,
            Employee.company_id == user.company_id
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="Employee code already exists.")
        
    emp = Employee(
        company_id=user.company_id,
        linked_user_id=req.linked_user_id,
        employee_code=req.employee_code,
        name=req.name,
        designation=req.designation,
        department=req.department,
        date_of_joining=jdate,
        pan=req.pan,
        uan=req.uan,
        pf_number=req.pf_number,
        esi_number=req.esi_number,
        bank_account_no=req.bank_account_no,
        bank_ifsc=req.bank_ifsc,
        payment_ledger_id=req.payment_ledger_id,
        is_active=True
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp

@router.get("/payroll/employees", response_model=List[EmployeeResponse])
async def get_employees(
    user: User = Depends(require_permission("payroll", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Employee).where(Employee.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Salary Components ---

@router.post("/payroll/components", response_model=SalaryComponentResponse)
async def create_salary_component(
    req: SalaryComponentCreate,
    user: User = Depends(require_permission("payroll", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify ledger exists
    ledg_query = await db.execute(
        select(MstLedger).where(MstLedger.linked_ledger_id == req.linked_ledger_id, MstLedger.company_id == user.company_id) if hasattr(MstLedger, 'linked_ledger_id') else select(MstLedger).where(MstLedger.ledger_id == req.linked_ledger_id, MstLedger.company_id == user.company_id)
    )
    if not ledg_query.scalars().first():
        raise HTTPException(status_code=400, detail="Linked ledger not found.")
        
    comp = SalaryComponent(
        company_id=user.company_id,
        name=req.name,
        component_type=req.component_type,
        calculation_type=req.calculation_type,
        percent_of_basic=req.percent_of_basic,
        is_statutory=req.is_statutory,
        linked_ledger_id=req.linked_ledger_id
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp

@router.get("/payroll/components", response_model=List[SalaryComponentResponse])
async def get_salary_components(
    user: User = Depends(require_permission("payroll", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SalaryComponent).where(SalaryComponent.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Salary Structures ---

@router.post("/payroll/structures", response_model=SalaryStructureResponse)
async def create_salary_structure(
    req: SalaryStructureCreate,
    user: User = Depends(require_permission("payroll", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        fdate = datetime.strptime(req.effective_from, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Verify employee exists
    emp_query = await db.execute(
        select(Employee).where(
            Employee.employee_id == req.employee_id,
            Employee.company_id == user.company_id
        )
    )
    if not emp_query.scalars().first():
        raise HTTPException(status_code=400, detail="Employee not found.")
        
    struct = SalaryStructure(
        employee_id=req.employee_id,
        effective_from=fdate,
        ctc_annual=req.ctc_annual
    )
    db.add(struct)
    await db.flush() # Populate structure_id
    
    for c in req.components:
        # Verify component
        comp_query = await db.execute(
            select(SalaryComponent).where(
                SalaryComponent.component_id == c.component_id,
                SalaryComponent.company_id == user.company_id
            )
        )
        if not comp_query.scalars().first():
            raise HTTPException(status_code=400, detail=f"Salary component ID {c.component_id} not found.")
            
        sc = SalaryStructureComponent(
            structure_id=struct.structure_id,
            component_id=c.component_id,
            amount=c.amount
        )
        db.add(sc)
        
    await db.commit()
    
    final_query = await db.execute(
        select(SalaryStructure)
        .options(selectinload(SalaryStructure.components))
        .where(SalaryStructure.structure_id == struct.structure_id)
    )
    return final_query.scalars().first()

# --- Payroll Processing ---

@router.post("/payroll/periods", response_model=PayrollPeriodResponse)
async def create_payroll_period(
    req: PayrollPeriodCreate,
    user: User = Depends(require_permission("payroll", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Check duplicate period
    dup_query = await db.execute(
        select(PayrollPeriod).where(
            PayrollPeriod.company_id == user.company_id,
            PayrollPeriod.period_month == req.period_month,
            PayrollPeriod.period_year == req.period_year
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="Payroll period already exists.")
        
    period = PayrollPeriod(
        company_id=user.company_id,
        period_month=req.period_month,
        period_year=req.period_year,
        status="Draft"
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period

@router.post("/payroll/periods/{period_id}/process", response_model=List[PayslipResponse])
async def process_payroll(
    period_id: int,
    user: User = Depends(require_permission("payroll", "update")),
    db: AsyncSession = Depends(get_db)
):
    # Verify period
    period_query = await db.execute(
        select(PayrollPeriod).where(
            PayrollPeriod.period_id == period_id,
            PayrollPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found.")
    if period.status != "Draft":
        raise HTTPException(status_code=400, detail="Only draft periods can be processed.")
        
    # Get active employees
    employees_query = await db.execute(
        select(Employee).where(Employee.company_id == user.company_id, Employee.is_active == True)
    )
    employees = employees_query.scalars().all()
    
    payslips = []
    days_in_month = 30
    
    for emp in employees:
        # Get active structure
        struct_query = await db.execute(
            select(SalaryStructure)
            .options(selectinload(SalaryStructure.components))
            .where(SalaryStructure.employee_id == emp.employee_id)
            .order_by(SalaryStructure.effective_from.desc())
        )
        struct = struct_query.scalars().first()
        if not struct:
            continue
            
        gross_earnings = Decimal("0.00")
        total_deductions = Decimal("0.00")
        
        payslip = Payslip(
            period_id=period_id,
            employee_id=emp.employee_id,
            days_present=Decimal("30.0"),
            days_in_period=days_in_month,
            gross_earnings=Decimal("0.00"),
            total_deductions=Decimal("0.00"),
            net_pay=Decimal("0.00")
        )
        db.add(payslip)
        await db.flush()
        
        for sc in struct.components:
            comp_query = await db.execute(
                select(SalaryComponent).where(SalaryComponent.component_id == sc.component_id)
            )
            comp = comp_query.scalars().first()
            if not comp:
                continue
                
            amount = sc.amount
            if comp.component_type == "Earning":
                gross_earnings += amount
            else:
                total_deductions += amount
                
            pc = PayslipComponent(
                payslip_id=payslip.payslip_id,
                component_id=sc.component_id,
                amount=amount
            )
            db.add(pc)
            
        payslip.gross_earnings = gross_earnings
        payslip.total_deductions = total_deductions
        payslip.net_pay = gross_earnings - total_deductions
        payslips.append(payslip)
        
    await db.commit()
    
    final_query = await db.execute(
        select(Payslip)
        .options(selectinload(Payslip.components))
        .where(Payslip.period_id == period_id)
    )
    return final_query.scalars().all()

@router.post("/payroll/periods/{period_id}/approve")
async def approve_payroll(
    period_id: int,
    salary_expense_ledger_id: int,
    salaries_payable_ledger_id: int,
    user: User = Depends(require_permission("payroll", "update")),
    db: AsyncSession = Depends(get_db)
):
    period_query = await db.execute(
        select(PayrollPeriod).where(
            PayrollPeriod.period_id == period_id,
            PayrollPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found.")
    if period.status != "Draft":
        raise HTTPException(status_code=400, detail="Only draft periods can be approved.")
        
    # Get all payslips
    payslips_query = await db.execute(
        select(Payslip).where(Payslip.period_id == period_id)
    )
    payslips = payslips_query.scalars().all()
    if not payslips:
        raise HTTPException(status_code=400, detail="No payslips processed for this period.")
        
    total_net = sum(p.net_pay for p in payslips)
    total_deductions = sum(p.total_deductions for p in payslips)
    total_gross = sum(p.gross_earnings for p in payslips)
    
    # Fetch Journal Voucher Type
    vtype_query = await db.execute(
        select(MstVoucherType).where(
            MstVoucherType.company_id == user.company_id,
            MstVoucherType.name == "Journal"
        )
    )
    vtype = vtype_query.scalars().first()
    if not vtype:
        raise HTTPException(status_code=400, detail="Journal Voucher type not found.")
        
    vnum = f"{vtype.prefix or ''}{vtype.next_number}"
    vtype.next_number += 1
    
    voucher = TrnVoucher(
        company_id=user.company_id,
        voucher_type_id=vtype.voucher_type_id,
        voucher_number=vnum,
        voucher_date=date.today(),
        narration=f"Salaries accrual for period {period.period_month}/{period.period_year}",
        total_amount=total_gross,
        is_optional=False,
        created_by=user.user_id
    )
    db.add(voucher)
    await db.flush()
    
    # Debit Salary Expense
    e1 = TrnAccounting(
        voucher_id=voucher.voucher_id,
        ledger_id=salary_expense_ledger_id,
        debit_amount=total_gross,
        credit_amount=Decimal("0.00"),
        entry_narration="Gross salary expense"
    )
    db.add(e1)
    
    # Credit Salaries Payable
    e2 = TrnAccounting(
        voucher_id=voucher.voucher_id,
        ledger_id=salaries_payable_ledger_id,
        debit_amount=Decimal("0.00"),
        credit_amount=total_net,
        entry_narration="Net salary payable"
    )
    db.add(e2)
    
    # Credit Deductions
    if total_deductions > 0:
        e3 = TrnAccounting(
            voucher_id=voucher.voucher_id,
            ledger_id=salaries_payable_ledger_id,
            debit_amount=Decimal("0.00"),
            credit_amount=total_deductions,
            entry_narration="Salary deductions PF/ESI"
        )
        db.add(e3)
        
    period.status = "Processed"
    period.processed_at = datetime.now(timezone.utc)
    period.processed_by = user.user_id
    
    for p in payslips:
        p.voucher_id = voucher.voucher_id
        
    await db.commit()
    return {"detail": "Payroll approved. Journal entry posted.", "voucher_number": vnum}

# --- POS Billing ---

@router.post("/pos/payments", response_model=PosPaymentResponse)
async def create_pos_payment(
    req: PosPaymentCreate,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    v_query = await db.execute(
        select(TrnVoucher).where(TrnVoucher.voucher_id == req.voucher_id, TrnVoucher.company_id == user.company_id)
    )
    if not v_query.scalars().first():
        raise HTTPException(status_code=400, detail="Voucher not found.")
        
    pos = PosPayment(
        voucher_id=req.voucher_id,
        cash_amount=req.cash_amount,
        card_amount=req.card_amount,
        upi_amount=req.upi_amount,
        points_redeemed=req.points_redeemed
    )
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return pos

@router.get("/pos/payments/{voucher_id}", response_model=PosPaymentResponse)
async def get_pos_payment(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PosPayment).where(PosPayment.voucher_id == voucher_id)
    res = await db.execute(stmt)
    pos = res.scalars().first()
    if not pos:
        raise HTTPException(status_code=404, detail="POS Payment splits not found.")
    return pos

# --- E-Way & E-Invoicing ---

@router.post("/einvoice/metadata", response_model=EinvoiceMetadataResponse)
async def create_einvoice_metadata(
    req: EinvoiceMetadataCreate,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    v_query = await db.execute(
        select(TrnVoucher).where(TrnVoucher.voucher_id == req.voucher_id, TrnVoucher.company_id == user.company_id)
    )
    if not v_query.scalars().first():
        raise HTTPException(status_code=400, detail="Voucher not found.")
        
    ack_dt = datetime.strptime(req.ack_date, "%Y-%m-%d %H:%M:%S") if req.ack_date else None
    ew_dt = datetime.strptime(req.eway_bill_date, "%Y-%m-%d %H:%M:%S") if req.eway_bill_date else None
    
    meta = EinvoiceMetadata(
        voucher_id=req.voucher_id,
        irn=req.irn,
        ack_no=req.ack_no,
        ack_date=ack_dt,
        eway_bill_no=req.eway_bill_no,
        eway_bill_date=ew_dt,
        raw_response=req.raw_response
    )
    db.add(meta)
    await db.commit()
    await db.refresh(meta)
    return meta

@router.get("/einvoice/metadata/{voucher_id}", response_model=EinvoiceMetadataResponse)
async def get_einvoice_metadata(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(EinvoiceMetadata).where(EinvoiceMetadata.voucher_id == voucher_id)
    res = await db.execute(stmt)
    meta = res.scalars().first()
    if not meta:
        raise HTTPException(status_code=404, detail="E-Invoice metadata not found.")
    return meta
