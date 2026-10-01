"""
Bank Statement Reconciliation Router for MyTally.
Handles CSV statement parsing, automated 3-way matching with Tally vouchers and collections,
unmatched transaction queues, Bank Reconciliation Statement (BRS) calculation, and audit history.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, desc, or_, and_, func, cast, text
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import io
import csv
import re
import os
import sys
import hashlib

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import msoffcrypto
except ImportError:
    msoffcrypto = None

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.portal_core import (
    User, Company, BankStatement, BankStatementTransaction, ShopPayment, AuditLog
)
from app.models.tally_core import (
    MstLedger, MstGroup, TrnVoucher, TrnAccounting, TrnBankAllocation
)
from app.core.config import settings
from app.core.datetime_utils import get_ist_now, get_ist_date, to_ist_iso

router = APIRouter(prefix="/bank-recon", tags=["Bank Reconciliation"])


# ─── Helper Functions ────────────────────────────────────────────────────────

def clean_amount(val: Any) -> Decimal:
    """Parses currency strings like '₹ 1,50,000.00 Cr', ' (2,500.50) ', '333611.46 Cr.' to Decimal."""
    if val is None or val == "":
        return Decimal("0.00")
    if isinstance(val, (int, float)):
        return Decimal(str(round(val, 2)))
    if isinstance(val, Decimal):
        return val

    s = str(val).strip()
    if not s or s == "-" or s.lower() == "nil":
        return Decimal("0.00")

    upper_s = s.upper()
    is_neg = False
    if upper_s.endswith("DR.") or upper_s.endswith(" DR") or upper_s.endswith("DR") or s.startswith("-") or s.endswith("-"):
        is_neg = True
    elif s.startswith("(") and s.endswith(")"):
        is_neg = True
        s = s[1:-1].strip()

    # Strip Cr/Dr suffix
    s = re.sub(r"(?i)\s*(cr|dr)\.?$", "", s)
    # Remove currency symbols and formatting commas
    s = re.sub(r"[^\d.-]", "", s)
    if not s or s == ".":
        return Decimal("0.00")
    try:
        dec = Decimal(s)
        return -dec if is_neg else dec
    except Exception:
        return Decimal("0.00")


def parse_date_str(val: Any) -> Optional[date]:
    """Parses various date formats common in Indian bank statements (strings or datetime objects)."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    val = str(val).strip()
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y",
        "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d-%B-%Y", "%d/%b/%Y",
        "%d.%m.%Y", "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def normalize_ref(ref: Optional[str]) -> str:
    """Normalizes UTR or Cheque references by stripping whitespace and non-alphanumerics."""
    if not ref:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(ref)).upper()


def compute_row_hash(
    bank_ledger_id: int,
    tx_date: date,
    amount: Decimal,
    tx_type: str,
    reference_no: Optional[str] = None,
    cheque_no: Optional[str] = None,
    running_balance: Optional[Decimal] = None,
    description: Optional[str] = None,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a bank transaction row.
    Guarantees row-level idempotency across statement files and overlapping imports.
    """
    norm_amt = f"{Decimal(str(amount)):.2f}"
    norm_type = (tx_type or "").strip().upper()
    norm_ref = (reference_no or cheque_no or "").strip().upper()
    norm_bal = f"{Decimal(str(running_balance)):.2f}" if running_balance is not None else ""
    norm_desc = " ".join((description or "").split()[:6]).upper()
    raw_key = f"{bank_ledger_id}|{tx_date.isoformat()}|{norm_amt}|{norm_type}|{norm_ref}|{norm_bal}|{norm_desc}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_statement_file(
    filename: str,
    content_bytes: bytes,
    password: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[date], Optional[date], Optional[Decimal], Optional[Decimal]]:
    """
    Parses bank statements in CSV, TSV, or Excel (.xlsx, .xls) format.
    Supports password-protected Excel files (via msoffcrypto) and auto-detects
    metadata (Account Number, Statement Period) and transaction tables for major banks
    (including Punjab National Bank / PNB, HDFC, ICICI, SBI, Axis, Kotak).
    """
    is_excel = filename.lower().endswith((".xlsx", ".xls"))

    # Decrypt if password-protected Office document
    if is_excel and msoffcrypto is not None:
        file_stream = io.BytesIO(content_bytes)
        try:
            office_file = msoffcrypto.OfficeFile(file_stream)
            if office_file.is_encrypted():
                if not password:
                    raise HTTPException(
                        status_code=400,
                        detail="This Excel statement is password-protected. Please enter the file password in the upload form."
                    )
                decrypted_stream = io.BytesIO()
                office_file.load_key(password=password)
                office_file.decrypt(decrypted_stream)
                decrypted_stream.seek(0)
                content_bytes = decrypted_stream.read()
        except HTTPException:
            raise
        except Exception as e:
            err_name = type(e).__name__
            if "InvalidPassword" in err_name or "Password" in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Incorrect password for this encrypted Excel statement. Please check the password and try again."
                )
            # Not an encrypted OLE file or standard zip .xlsx, continue to openpyxl

    detected_account_no = None
    detected_from = None
    detected_to = None
    detected_opening = None
    detected_closing = None

    if is_excel:
        if openpyxl is None:
            raise HTTPException(status_code=500, detail="openpyxl is not installed on the server to read Excel files.")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise HTTPException(
                    status_code=400,
                    detail="This Excel statement is password-protected. Please enter the file password."
                )
            raise HTTPException(
                status_code=400,
                detail=f"Unable to read Excel workbook: {str(e)}"
            )

        sheet = wb.active
        raw_rows = list(sheet.iter_rows(values_only=True))
    else:
        # CSV / TSV text processing
        try:
            text_content = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_content = content_bytes.decode("latin-1")

        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        if not lines:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        # Try to detect delimiter
        sample = "\n".join(lines[:10])
        delim = "\t" if "\t" in sample and sample.count("\t") > sample.count(",") else ","
        raw_rows = list(csv.reader(lines, delimiter=delim))

    if not raw_rows:
        raise HTTPException(status_code=400, detail="The statement file contains no rows.")

    # 1. Inspect top 35 rows for Bank Metadata (Account Number, Statement Period, Opening Balance)
    header_row_idx = -1
    headers = []

    for idx, r in enumerate(raw_rows[:35]):
        if not r:
            continue
        row_str = " ".join(str(c) for c in r if c is not None)

        # Detect Account Number
        if not detected_account_no:
            acc_match = re.search(r"(?:Account\s*(?:Number|No\.?)|A/c\s*(?:No\.?|Number))\s*[:\-]?\s*([A-Za-z0-9]+)", row_str, re.IGNORECASE)
            if acc_match:
                detected_account_no = acc_match.group(1).strip()

        # Detect Statement Period
        if not detected_from:
            period_match = re.search(r"Statement\s+Period\s*:\s*([\d\/\.\-]+)\s+to\s+([\d\/\.\-]+)", row_str, re.IGNORECASE)
            if period_match:
                detected_from = parse_date_str(period_match.group(1))
                detected_to = parse_date_str(period_match.group(2))

        # Detect Opening Balance from metadata rows
        if detected_opening is None:
            open_match = re.search(r"(?:Opening\s+Balance|Balance\s+B/F|B/F\s+Balance)\s*[:\-]?\s*([\d,.]+)", row_str, re.IGNORECASE)
            if open_match:
                detected_opening = clean_amount(open_match.group(1))

        # Check if this row is the Table Header
        lower_cells = [str(c).strip().lower() for c in r if c is not None]
        has_date = any(re.search(r"\b(date|txn date|transaction date)\b", c) for c in lower_cells)
        has_dr = any(re.search(r"\b(dr|debit|withdrawal|dr amount)\b", c) for c in lower_cells)
        has_cr = any(re.search(r"\b(cr|credit|deposit|cr amount)\b", c) for c in lower_cells)
        has_desc = any(re.search(r"\b(description|narration|particulars|remarks)\b", c) for c in lower_cells)

        if has_date and (has_dr or has_cr or has_desc):
            header_row_idx = idx
            headers = [str(c).strip().lower() if c is not None else "" for c in r]
            break

    if header_row_idx == -1:
        # Fallback to row 0 if standard CSV
        header_row_idx = 0
        headers = [str(c).strip().lower() if c is not None else "" for c in raw_rows[0]]

    # Map column indices using word boundary regexes
    date_col = -1
    desc_col = -1
    ref_col = -1
    chq_col = -1
    txn_col = -1
    debit_col = -1
    credit_col = -1
    balance_col = -1

    for idx, h in enumerate(headers):
        if not h:
            continue
        if date_col == -1 and bool(re.search(r"\b(txn date|transaction date|date|value date)\b", h)):
            date_col = idx
        elif desc_col == -1 and bool(re.search(r"\b(narration|description|particulars|remarks|details)\b", h)):
            desc_col = idx
        elif chq_col == -1 and bool(re.search(r"\b(cheque|chq|instrument)\b", h)):
            chq_col = idx
        elif txn_col == -1 and bool(re.search(r"\b(txn no|transaction id|txn id|ref no|reference)\b", h)):
            txn_col = idx
        elif debit_col == -1 and bool(re.search(r"\b(dr amount|withdrawal|debit|dr)\b", h)):
            debit_col = idx
        elif credit_col == -1 and bool(re.search(r"\b(cr amount|deposit|credit|cr)\b", h)):
            credit_col = idx
        elif balance_col == -1 and bool(re.search(r"\b(balance|closing balance|running balance)\b", h)):
            balance_col = idx

    # If general ref_col not found, use chq or txn
    if ref_col == -1:
        ref_col = chq_col if chq_col != -1 else txn_col

    if date_col == -1 or desc_col == -1 or (debit_col == -1 and credit_col == -1):
        clean_headers = [h for h in headers if h][:8]
        raise HTTPException(
            status_code=400,
            detail=f"Unable to parse statement columns. Detected headers: {clean_headers}. Ensure Date, Description, and Debit/Credit columns exist."
        )

    parsed_rows = []
    min_date = None
    max_date = None

    for row in raw_rows[header_row_idx + 1:]:
        if not row or len(row) <= max(date_col, desc_col):
            continue

        raw_date = row[date_col]
        txn_date = parse_date_str(raw_date)
        if not txn_date:
            continue

        description = str(row[desc_col]).strip() if row[desc_col] is not None else ""
        if not description or description.lower() in ["total", "sub total", "page total"]:
            continue

        # Extract Reference / Cheque
        ref_no = None
        chq_no = None
        if chq_col != -1 and len(row) > chq_col and row[chq_col]:
            chq_no = str(row[chq_col]).strip()
            ref_no = chq_no
        if not ref_no and txn_col != -1 and len(row) > txn_col and row[txn_col]:
            ref_no = str(row[txn_col]).strip()

        # Fallback: extract UTR from narration
        if not ref_no:
            utr_match = re.search(r"(?:UPI/|CMS/|INF/|NEFT-|RTGS-|IMPS/)(\w+)", description, re.IGNORECASE)
            if utr_match:
                ref_no = utr_match.group(1)

        debit_val = clean_amount(row[debit_col]) if debit_col != -1 and len(row) > debit_col else Decimal("0.00")
        credit_val = clean_amount(row[credit_col]) if credit_col != -1 and len(row) > credit_col else Decimal("0.00")
        balance_val = clean_amount(row[balance_col]) if balance_col != -1 and len(row) > balance_col and row[balance_col] is not None else None

        if debit_val > 0:
            txn_type = "DEBIT"
            amount = debit_val
        elif credit_val > 0:
            txn_type = "CREDIT"
            amount = credit_val
        else:
            continue

        if min_date is None or txn_date < min_date:
            min_date = txn_date
        if max_date is None or txn_date > max_date:
            max_date = txn_date

        # Capture complete raw row representation for auditing
        raw_row_dict = {}
        for h_idx, cell in enumerate(row):
            h_key = headers[h_idx] if h_idx < len(headers) and headers[h_idx] else f"col_{h_idx}"
            raw_row_dict[str(h_key)] = str(cell) if cell is not None else ""

        parsed_rows.append({
            "transaction_date": txn_date,
            "description": description[:1024],
            "reference_no": ref_no[:128] if ref_no else None,
            "cheque_no": chq_no[:64] if chq_no else None,
            "transaction_type": txn_type,
            "amount": amount,
            "running_balance": balance_val,
            "raw_data": raw_row_dict,
        })

    if not parsed_rows:
        raise HTTPException(status_code=400, detail="No valid transaction rows found in the uploaded file.")

    if not detected_from:
        detected_from = min_date
    if not detected_to:
        detected_to = max_date

    if detected_closing is None and parsed_rows:
        detected_closing = parsed_rows[-1]["running_balance"]

    return parsed_rows, detected_account_no, detected_from, detected_to, detected_opening, detected_closing


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/bank-ledgers")
async def list_bank_ledgers(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all bank ledgers for the company (from MstLedger where is_bank_account or group is Bank Accounts),
    with current ledger closing balance and statement count.
    """
    company_id = user.company_id
    stmt = (
        select(MstLedger, MstGroup.name.label("group_name"))
        .join(MstGroup, MstLedger.group_id == MstGroup.group_id)
        .where(
            MstLedger.company_id == company_id,
            or_(
                MstLedger.is_bank_account == True,
                MstGroup.name.ilike("%Bank%"),
                MstGroup.name.ilike("%Cash%"),
            )
        )
        .order_by(MstLedger.name.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    output = []
    for ledger, group_name in rows:
        # Get count of statements for this ledger
        stmt_count_res = await db.execute(
            select(func.count(BankStatement.statement_id))
            .where(BankStatement.bank_ledger_id == ledger.ledger_id, BankStatement.company_id == company_id)
        )
        statement_count = stmt_count_res.scalar() or 0

        output.append({
            "ledger_id": ledger.ledger_id,
            "name": ledger.name,
            "group_name": group_name,
            "is_bank_account": ledger.is_bank_account,
            "bank_account_no": ledger.bank_account_no,
            "bank_ifsc": ledger.bank_ifsc,
            "closing_balance": float(ledger.closing_balance) if ledger.closing_balance else 0.0,
            "statement_count": statement_count,
        })

    # Prioritize: Punjab National Bank / PNB first, then other bank accounts, then cash accounts
    def ledger_priority(item):
        lname = item["name"].lower()
        if "punjab national bank" in lname or "pnb" in lname:
            return 0
        if "cash" not in lname and item.get("is_bank_account"):
            return 1
        if "cash" not in lname:
            return 2
        return 3

    output.sort(key=ledger_priority)
    return output


@router.post("/upload")
async def upload_bank_statement(
    file: UploadFile = File(...),
    bank_ledger_id: int = Form(...),
    password: Optional[str] = Form(None),
    opening_balance: Optional[float] = Form(None),
    closing_balance: Optional[float] = Form(None),
    statement_from: Optional[str] = Form(None),
    statement_to: Optional[str] = Form(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and parse bank statement in Excel (.xlsx, .xls) or CSV/TSV format.
    Supports password-protected Excel files, auto-detects account number, statement periods,
    and formats for major Indian banks (including Punjab National Bank / PNB, HDFC, ICICI, SBI, Axis, Kotak).
    Runs automated 3-way matching with Tally vouchers and portal collections without creating any vouchers.
    """
    company_id = user.company_id

    # Verify bank ledger exists
    ledger_res = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == bank_ledger_id, MstLedger.company_id == company_id)
    )
    bank_ledger = ledger_res.scalars().first()
    if not bank_ledger:
        raise HTTPException(status_code=404, detail="Bank ledger not found")

    content_bytes = await file.read()
    filename = file.filename or "statement.csv"
    file_hash = hashlib.sha256(content_bytes).hexdigest()

    # Level 1: File-Level Idempotency Check
    existing_stmt_res = await db.execute(
        select(BankStatement)
        .where(
            BankStatement.company_id == company_id,
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatement.file_hash == file_hash,
        )
        .order_by(BankStatement.statement_id.desc())
    )
    existing_stmt = existing_stmt_res.scalars().first()
    if existing_stmt:
        # Re-run auto-matching on any currently unmatched transactions in case new vouchers were entered
        unmatched_txs_res = await db.execute(
            select(BankStatementTransaction)
            .where(
                BankStatementTransaction.statement_id == existing_stmt.statement_id,
                BankStatementTransaction.matched_status != "matched",
            )
        )
        unmatched_txs = unmatched_txs_res.scalars().all()
        match_stats = {"exact": 0, "suggested": 0, "unmatched": len(unmatched_txs)}
        if unmatched_txs:
            match_stats = await _run_auto_matching(db, existing_stmt, unmatched_txs, company_id, bank_ledger_id)
            await db.commit()

        return {
            "statement_id": existing_stmt.statement_id,
            "filename": existing_stmt.filename,
            "account_number": existing_stmt.account_number,
            "total_imported": existing_stmt.total_transactions,
            "new_transactions_imported": 0,
            "duplicate_rows_skipped": existing_stmt.total_transactions,
            "is_duplicate_file": True,
            "message": f"This statement file was already uploaded previously (Statement #{existing_stmt.statement_id}). Reusing existing reconciliation without creating duplicates.",
            "statement_from": existing_stmt.statement_from.isoformat() if existing_stmt.statement_from else None,
            "statement_to": existing_stmt.statement_to.isoformat() if existing_stmt.statement_to else None,
            "exact_matches": match_stats["exact"],
            "suggested_matches": match_stats["suggested"],
            "unmatched": match_stats["unmatched"],
            "status": existing_stmt.status,
        }

    parsed_rows, det_acc_no, det_from, det_to, det_open, det_close = parse_statement_file(
        filename=filename,
        content_bytes=content_bytes,
        password=password,
    )

    if not parsed_rows:
        raise HTTPException(
            status_code=400,
            detail="No valid transaction rows found in the uploaded statement. Please verify file format or header rows."
        )

    # Level 2: Row-Level Idempotency Check (Deduplication of overlapping statement rows)
    candidate_hashes = []
    for r in parsed_rows:
        r_hash = compute_row_hash(
            bank_ledger_id=bank_ledger_id,
            tx_date=r["transaction_date"],
            amount=r["amount"],
            tx_type=r["transaction_type"],
            reference_no=r.get("reference_no"),
            cheque_no=r.get("cheque_no"),
            running_balance=r.get("running_balance"),
            description=r.get("description", "")
        )
        r["row_hash"] = r_hash
        candidate_hashes.append(r_hash)

    # Query already existing transaction row_hashes for this bank ledger
    existing_hashes = set()
    if candidate_hashes:
        ex_res = await db.execute(
            select(BankStatementTransaction.row_hash)
            .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
            .where(
                BankStatement.company_id == company_id,
                BankStatement.bank_ledger_id == bank_ledger_id,
                BankStatementTransaction.row_hash.in_(candidate_hashes)
            )
        )
        existing_hashes = set(ex_res.scalars().all())

    # Separate net-new rows from duplicates
    new_rows = []
    skipped_duplicates = 0
    seen_in_batch = set()

    for r in parsed_rows:
        h = r["row_hash"]
        if h in existing_hashes or h in seen_in_batch:
            skipped_duplicates += 1
            continue
        seen_in_batch.add(h)
        new_rows.append(r)

    # Use explicitly submitted dates if provided, else use auto-detected dates
    final_from = parse_date_str(statement_from) if statement_from else det_from
    final_to = parse_date_str(statement_to) if statement_to else det_to
    if not final_from and parsed_rows:
        final_from = parsed_rows[0]["transaction_date"]
    if not final_to and parsed_rows:
        final_to = parsed_rows[-1]["transaction_date"]

    final_open = Decimal(str(opening_balance)) if opening_balance is not None else (det_open or Decimal("0.00"))
    final_close = Decimal(str(closing_balance)) if closing_balance is not None else (det_close or Decimal("0.00"))

    # If all rows in this file are already present in existing statements
    if not new_rows:
        return {
            "statement_id": None,
            "filename": filename,
            "account_number": det_acc_no or bank_ledger.bank_account_no,
            "total_imported": len(parsed_rows),
            "new_transactions_imported": 0,
            "duplicate_rows_skipped": skipped_duplicates,
            "is_duplicate_file": False,
            "message": f"All {skipped_duplicates} transactions in this statement were already imported previously in other statements for this bank account.",
            "statement_from": final_from.isoformat() if final_from else None,
            "statement_to": final_to.isoformat() if final_to else None,
            "exact_matches": 0,
            "suggested_matches": 0,
            "unmatched": 0,
            "status": "all_duplicates_skipped",
        }

    # Create BankStatement Header
    stmt_record = BankStatement(
        company_id=company_id,
        bank_ledger_id=bank_ledger_id,
        filename=filename,
        file_hash=file_hash,
        account_number=det_acc_no or bank_ledger.bank_account_no,
        statement_from=final_from or date.today(),
        statement_to=final_to or date.today(),
        opening_balance=final_open,
        closing_balance=final_close,
        total_transactions=len(new_rows),
        reconciled_transactions=0,
        unmatched_transactions=len(new_rows),
        reviewed_transactions=0,
        status="imported",
        created_by_user_id=user.user_id,
    )
    db.add(stmt_record)
    await db.flush()

    # Save transaction rows (only net-new rows are added, guaranteed zero duplicates)
    db_transactions = []
    for r in new_rows:
        tx = BankStatementTransaction(
            statement_id=stmt_record.statement_id,
            transaction_date=r["transaction_date"],
            value_date=r.get("value_date"),
            description=r["description"],
            reference_no=r["reference_no"],
            cheque_no=r.get("cheque_no"),
            transaction_type=r["transaction_type"],
            amount=r["amount"],
            running_balance=r["running_balance"],
            raw_data=r.get("raw_data"),
            row_hash=r["row_hash"],
            matched_status="unmatched",
            review_status="pending_review",
        )
        db.add(tx)
        db_transactions.append(tx)

    await db.flush()

    # Run Automatic Matching Engine (Links existing vouchers, never creates vouchers)
    match_stats = await _run_auto_matching(db, stmt_record, db_transactions, company_id, bank_ledger_id)
    await db.commit()

    import_msg = (
        f"Imported {len(new_rows)} new transactions. Skipped {skipped_duplicates} duplicate rows."
        if skipped_duplicates > 0
        else f"Successfully imported {len(new_rows)} transactions."
    )

    return {
        "statement_id": stmt_record.statement_id,
        "filename": stmt_record.filename,
        "account_number": stmt_record.account_number,
        "total_imported": len(parsed_rows),
        "new_transactions_imported": len(new_rows),
        "duplicate_rows_skipped": skipped_duplicates,
        "is_duplicate_file": False,
        "message": import_msg,
        "statement_from": stmt_record.statement_from.isoformat() if stmt_record.statement_from else None,
        "statement_to": stmt_record.statement_to.isoformat() if stmt_record.statement_to else None,
        "exact_matches": match_stats["exact"],
        "suggested_matches": match_stats["suggested"],
        "unmatched": match_stats["unmatched"],
        "status": stmt_record.status,
    }


async def _run_auto_matching(
    db: AsyncSession,
    statement: BankStatement,
    transactions: List[BankStatementTransaction],
    company_id: int,
    bank_ledger_id: int
) -> Dict[str, int]:
    """
    Intelligent 3-way matching engine between Bank Statement lines and:
    1. Tally Vouchers & Bank Allocations on this bank ledger
    2. Portal Field Collections (ShopPayment)
    """
    # Load candidate Tally vouchers on this bank ledger within date range (+/- 10 days)
    date_from = statement.statement_from - timedelta(days=10)
    date_to = statement.statement_to + timedelta(days=10)

    # 1. Fetch Tally accounting entries for this bank ledger
    vouchers_res = await db.execute(
        select(TrnVoucher)
        .join(TrnAccounting, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
        )
        .where(
            TrnVoucher.company_id == company_id,
            TrnAccounting.ledger_id == bank_ledger_id,
            TrnVoucher.voucher_date >= date_from,
            TrnVoucher.voucher_date <= date_to,
        )
    )
    vouchers = vouchers_res.scalars().unique().all()

    # 2. Fetch Portal Shop Payments
    payments_res = await db.execute(
        select(ShopPayment)
        .options(selectinload(ShopPayment.ledger))
        .where(
            ShopPayment.ledger_id == bank_ledger_id,
            ShopPayment.status == "success",
            cast(ShopPayment.created_at, Date) >= date_from,
            cast(ShopPayment.created_at, Date) <= date_to,
        )
    )
    shop_payments = payments_res.scalars().all()

    exact_count = 0
    suggested_count = 0

    # Exclude vouchers already matched to other statement transactions
    already_matched_v_res = await db.execute(
        select(BankStatementTransaction.matched_voucher_id)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.company_id == company_id,
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatementTransaction.matched_voucher_id.isnot(None),
            BankStatementTransaction.statement_id != statement.statement_id
        )
    )
    used_voucher_ids = set(r for r in already_matched_v_res.scalars().all() if r)

    # Exclude shop payments already matched to other statement transactions
    already_matched_sp_res = await db.execute(
        select(BankStatementTransaction.matched_payment_id)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.company_id == company_id,
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatementTransaction.matched_payment_id.isnot(None),
            BankStatementTransaction.statement_id != statement.statement_id
        )
    )
    used_payment_ids = set(r for r in already_matched_sp_res.scalars().all() if r)

    for tx in transactions:
        tx_norm_ref = normalize_ref(tx.reference_no)
        tx_amount = tx.amount
        tx_date = tx.transaction_date

        matched = False

        # Pass A: Exact Match on Reference / UTR / Cheque + Amount
        if tx_norm_ref and len(tx_norm_ref) >= 4:
            for v in vouchers:
                if v.voucher_id in used_voucher_ids:
                    continue

                # Check bank allocations for instrument number / UTR
                for entry in v.entries:
                    if entry.ledger_id != bank_ledger_id:
                        continue
                    damt = abs(Decimal(str(entry.debit_amount or "0.00")))
                    camt = abs(Decimal(str(entry.credit_amount or "0.00")))
                    entry_amt = max(damt, camt)
                    if entry_amt != tx_amount:
                        continue

                    for ba in (entry.bank_allocations or []):
                        ba_ref = normalize_ref(ba.instrument_number or getattr(ba, 'bank_transaction_ref', None))
                        if ba_ref and (ba_ref == tx_norm_ref or tx_norm_ref in ba_ref or ba_ref in tx_norm_ref):
                            tx.matched_status = "matched"
                            tx.review_status = "matched"
                            tx.matched_voucher_id = v.voucher_id
                            tx.matched_allocation_id = ba.allocation_id
                            tx.match_type = "exact_ref"
                            tx.matched_at = get_ist_now()
                            vtype = v.voucher_type.name if v.voucher_type else "Voucher"
                            tx.match_notes = f"Matched with {vtype} #{v.voucher_number} via Ref/Cheque {ba.instrument_number}"
                            used_voucher_ids.add(v.voucher_id)
                            matched = True
                            exact_count += 1
                            break
                    if matched:
                        break
                if matched:
                    break

        # Pass B: Exact Amount & Date Window (+/- 2 days)
        if not matched:
            best_candidate = None
            min_day_diff = 999

            for v in vouchers:
                if v.voucher_id in used_voucher_ids:
                    continue

                for entry in v.entries:
                    if entry.ledger_id != bank_ledger_id:
                        continue
                    damt = abs(Decimal(str(entry.debit_amount or "0.00")))
                    camt = abs(Decimal(str(entry.credit_amount or "0.00")))
                    entry_amt = max(damt, camt)
                    if entry_amt == tx_amount:
                        day_diff = abs((v.voucher_date - tx_date).days)
                        if day_diff <= 2 and day_diff < min_day_diff:
                            min_day_diff = day_diff
                            best_candidate = v

            if best_candidate:
                cand_vtype = best_candidate.voucher_type.name if best_candidate.voucher_type else "Voucher"
                # If date is exact same day, promote to matched; if 1-2 days difference, mark as suggested
                if min_day_diff == 0:
                    tx.matched_status = "matched"
                    tx.review_status = "matched"
                    tx.matched_voucher_id = best_candidate.voucher_id
                    tx.match_type = "exact_amount_date"
                    tx.matched_at = get_ist_now()
                    tx.match_notes = f"Exact amount & same-day match with {cand_vtype} #{best_candidate.voucher_number}"
                    used_voucher_ids.add(best_candidate.voucher_id)
                    exact_count += 1
                else:
                    tx.matched_status = "suggested"
                    tx.review_status = "pending_review"
                    tx.matched_voucher_id = best_candidate.voucher_id
                    tx.match_type = "suggested_date_diff"
                    tx.match_notes = f"Suggested candidate: {cand_vtype} #{best_candidate.voucher_number} ({min_day_diff} days variance)"
                    suggested_count += 1
                matched = True

        # Pass C: Match against Portal Field Collections (ShopPayment)
        if not matched and tx.transaction_type == "CREDIT":
            for sp in shop_payments:
                if sp.id in used_payment_ids:
                    continue
                sp_comments = getattr(sp, 'comments', '') or ""
                sp_ref = normalize_ref(getattr(sp, 'reference_number', None) or getattr(sp, 'cheque_number', None) or sp_comments)
                sp_amt = abs(Decimal(str(sp.amount)))
                if sp_amt == tx_amount and sp_ref and tx_norm_ref and (tx_norm_ref in sp_ref or sp_ref in tx_norm_ref):
                    tx.matched_status = "matched"
                    tx.review_status = "matched"
                    tx.matched_payment_id = sp.id
                    tx.match_type = "exact_ref_collection"
                    tx.matched_at = get_ist_now()
                    mode_str = sp.payment_mode.upper() if sp.payment_mode else 'Ref'
                    cust_name = getattr(sp, 'customer_name', None) or (sp.ledger.name if getattr(sp, 'ledger', None) else 'Customer')
                    tx.match_notes = f"Matched with Collection #{sp.id} ({cust_name}) via {mode_str} {sp_ref}"
                    used_payment_ids.add(sp.id)
                    exact_count += 1
                    matched = True
                    break

    # Count all matched transactions for this statement (including existing ones if re-running)
    reconciled_res = await db.execute(
        select(func.count(BankStatementTransaction.transaction_id))
        .where(
            BankStatementTransaction.statement_id == statement.statement_id,
            BankStatementTransaction.matched_status == "matched"
        )
    )
    total_reconciled = reconciled_res.scalar() or 0
    statement.reconciled_transactions = total_reconciled
    statement.unmatched_transactions = max(0, statement.total_transactions - total_reconciled)
    if total_reconciled == statement.total_transactions and statement.total_transactions > 0:
        statement.status = "reconciled"
    elif total_reconciled > 0:
        statement.status = "in_progress"

    return {
        "exact": exact_count,
        "suggested": suggested_count,
        "unmatched": len(transactions) - exact_count - suggested_count,
    }


@router.get("/statements")
async def list_statements(
    bank_ledger_id: Optional[int] = Query(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List uploaded bank statements with reconciliation statistics."""
    company_id = user.company_id
    query = (
        select(BankStatement)
        .options(selectinload(BankStatement.bank_ledger), selectinload(BankStatement.created_by))
        .where(BankStatement.company_id == company_id)
    )
    if bank_ledger_id:
        query = query.where(BankStatement.bank_ledger_id == bank_ledger_id)

    query = query.order_by(BankStatement.created_at.desc())
    res = await db.execute(query)
    statements = res.scalars().all()

    output = []
    for s in statements:
        reconciled_pct = round((s.reconciled_transactions / s.total_transactions * 100), 1) if s.total_transactions > 0 else 0
        output.append({
            "statement_id": s.statement_id,
            "filename": s.filename,
            "bank_ledger_id": s.bank_ledger_id,
            "bank_name": s.bank_ledger.name if s.bank_ledger else "Unknown Bank",
            "account_number": s.account_number,
            "statement_from": s.statement_from.isoformat() if s.statement_from else None,
            "statement_to": s.statement_to.isoformat() if s.statement_to else None,
            "opening_balance": float(s.opening_balance),
            "closing_balance": float(s.closing_balance),
            "total_transactions": s.total_transactions,
            "reconciled_transactions": s.reconciled_transactions,
            "unmatched_transactions": s.unmatched_transactions,
            "reconciled_pct": reconciled_pct,
            "status": s.status,
            "created_at": to_ist_iso(s.created_at),
            "created_by": s.created_by.username if s.created_by else None,
        })
    return output


@router.get("/date-bounds")
async def get_bank_date_bounds(
    bank_ledger_id: int = Query(...),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns min and max transaction date across all uploaded statements for a bank ledger."""
    company_id = user.company_id
    q = (
        select(
            func.min(BankStatementTransaction.transaction_date).label("min_date"),
            func.max(BankStatementTransaction.transaction_date).label("max_date"),
            func.count(BankStatementTransaction.transaction_id).label("total_txs"),
            func.count(func.distinct(BankStatementTransaction.statement_id)).label("total_statements")
        )
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatement.company_id == company_id
        )
    )
    res = await db.execute(q)
    row = res.first()
    if not row or not row.min_date:
        return {
            "min_date": None,
            "max_date": None,
            "total_transactions": 0,
            "total_statements": 0,
        }
    return {
        "min_date": row.min_date.isoformat() if row.min_date else None,
        "max_date": row.max_date.isoformat() if row.max_date else None,
        "total_transactions": row.total_txs or 0,
        "total_statements": row.total_statements or 0,
    }


@router.get("/summary")
async def get_bank_recon_summary(
    bank_ledger_id: int = Query(...),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    statement_id: Optional[int] = Query(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes BRS summary across all statements for this bank ledger or filtered by date range.
    Does NOT segregate data under different statement uploads.
    """
    company_id = user.company_id

    ledger_res = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == bank_ledger_id)
    )
    bank_ledger = ledger_res.scalars().first()
    if not bank_ledger:
        raise HTTPException(status_code=404, detail="Bank ledger not found")

    books_balance = float(bank_ledger.closing_balance) if bank_ledger.closing_balance else 0.0

    stmt_q = select(BankStatement).where(
        BankStatement.bank_ledger_id == bank_ledger_id,
        BankStatement.company_id == company_id
    )
    if statement_id:
        stmt_q = stmt_q.where(BankStatement.statement_id == statement_id)
    stmt_q = stmt_q.order_by(BankStatement.statement_to.desc(), BankStatement.statement_id.desc())
    stmt_res = await db.execute(stmt_q)
    statements = stmt_res.scalars().all()

    if not statements:
        return {
            "bank_name": bank_ledger.name,
            "statement_balance": 0.0,
            "books_balance": books_balance,
            "uncredited_deposits": 0.0,
            "unpresented_cheques": 0.0,
            "variance": -books_balance,
            "is_reconciled": False,
            "total_transactions": 0,
            "reconciled_count": 0,
            "suggested_count": 0,
            "unmatched_count": 0,
            "reviewed_count": 0,
            "pending_review_count": 0,
            "reconciled_pct": 0,
            "total_statements": 0,
        }

    # Bank statement balance: closing balance of latest relevant statement
    if to_date:
        relevant_stmts = [s for s in statements if s.statement_to <= to_date]
        target_stmt = relevant_stmts[0] if relevant_stmts else statements[0]
    else:
        target_stmt = statements[0]
    bank_balance = float(target_stmt.closing_balance)

    # Query transactions joined with BankStatement
    tx_q = (
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatement.company_id == company_id
        )
    )
    if statement_id:
        tx_q = tx_q.where(BankStatementTransaction.statement_id == statement_id)
    if from_date:
        tx_q = tx_q.where(BankStatementTransaction.transaction_date >= from_date)
    if to_date:
        tx_q = tx_q.where(BankStatementTransaction.transaction_date <= to_date)

    tx_res = await db.execute(tx_q)
    txs = tx_res.scalars().all()

    unmatched_credits = sum(float(t.amount) for t in txs if t.matched_status != "matched" and t.transaction_type == "CREDIT")
    unmatched_debits = sum(float(t.amount) for t in txs if t.matched_status != "matched" and t.transaction_type == "DEBIT")
    reconciled_count = sum(1 for t in txs if t.matched_status == "matched")
    suggested_count = sum(1 for t in txs if t.matched_status == "suggested")
    unmatched_count = sum(1 for t in txs if t.matched_status == "unmatched")
    reviewed_count = sum(1 for t in txs if getattr(t, 'review_status', 'pending_review') not in ('pending_review', 'matched') and t.matched_status != 'matched')
    pending_review_count = sum(1 for t in txs if t.matched_status == "unmatched" and getattr(t, 'review_status', 'pending_review') == 'pending_review')

    adjusted_bank_balance = bank_balance + unmatched_credits - unmatched_debits
    variance = round(adjusted_bank_balance - books_balance, 2)

    return {
        "statement_id": target_stmt.statement_id if target_stmt else None,
        "bank_name": bank_ledger.name,
        "statement_balance": bank_balance,
        "books_balance": books_balance,
        "uncredited_deposits": round(unmatched_credits, 2),
        "unpresented_cheques": round(unmatched_debits, 2),
        "variance": variance,
        "is_reconciled": abs(variance) < 0.01,
        "total_transactions": len(txs),
        "reconciled_count": reconciled_count,
        "suggested_count": suggested_count,
        "unmatched_count": unmatched_count,
        "reviewed_count": reviewed_count,
        "pending_review_count": pending_review_count,
        "reconciled_pct": round((reconciled_count / len(txs) * 100), 1) if txs else 0,
        "total_statements": len(statements),
    }


@router.get("/transactions")
async def list_bank_transactions(
    bank_ledger_id: int = Query(...),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    statement_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="'all', 'matched', 'suggested', 'unmatched', 'reviewed', 'pending_review'"),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns transactions for a bank ledger across all statements, filtered by date range without file segregation."""
    query = (
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .options(
            selectinload(BankStatementTransaction.matched_voucher).selectinload(TrnVoucher.voucher_type),
            selectinload(BankStatementTransaction.matched_payment),
            selectinload(BankStatementTransaction.matched_by),
            selectinload(BankStatementTransaction.reviewed_by),
        )
        .where(
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatement.company_id == user.company_id
        )
    )
    if statement_id:
        query = query.where(BankStatementTransaction.statement_id == statement_id)
    if from_date:
        query = query.where(BankStatementTransaction.transaction_date >= from_date)
    if to_date:
        query = query.where(BankStatementTransaction.transaction_date <= to_date)

    if status and status != "all":
        if status == "reviewed":
            query = query.where(
                BankStatementTransaction.review_status != "pending_review",
                BankStatementTransaction.matched_status != "matched"
            )
        elif status == "pending_review":
            query = query.where(
                BankStatementTransaction.matched_status == "unmatched",
                BankStatementTransaction.review_status == "pending_review"
            )
        else:
            query = query.where(BankStatementTransaction.matched_status == status)

    query = query.order_by(BankStatementTransaction.transaction_date.desc(), BankStatementTransaction.transaction_id.desc())
    res = await db.execute(query)
    rows = res.scalars().all()

    output = []
    for t in rows:
        voucher_info = None
        if t.matched_voucher:
            vtype_name = t.matched_voucher.voucher_type.name if t.matched_voucher.voucher_type else "Voucher"
            voucher_info = {
                "voucher_id": t.matched_voucher.voucher_id,
                "voucher_number": t.matched_voucher.voucher_number,
                "voucher_type": vtype_name,
                "date": t.matched_voucher.voucher_date.isoformat() if t.matched_voucher.voucher_date else None,
                "narration": t.matched_voucher.narration,
            }

        payment_info = None
        if t.matched_payment:
            cust_name = getattr(t.matched_payment, 'customer_name', None) or (t.matched_payment.ledger.name if getattr(t.matched_payment, 'ledger', None) else "Shop Payment")
            ref_no = getattr(t.matched_payment, 'reference_number', None) or getattr(t.matched_payment, 'cheque_number', None) or getattr(t.matched_payment, 'comments', None)
            payment_info = {
                "id": t.matched_payment.id,
                "customer_name": cust_name,
                "amount": float(t.matched_payment.amount),
                "payment_mode": t.matched_payment.payment_mode,
                "reference_number": ref_no,
            }

        output.append({
            "transaction_id": t.transaction_id,
            "statement_id": t.statement_id,
            "transaction_date": t.transaction_date.isoformat(),
            "description": t.description,
            "reference_no": t.reference_no,
            "cheque_no": t.cheque_no,
            "transaction_type": t.transaction_type,
            "amount": float(t.amount),
            "running_balance": float(t.running_balance) if t.running_balance is not None else None,
            "matched_status": t.matched_status,
            "review_status": t.review_status or "pending_review",
            "review_notes": t.review_notes,
            "reviewed_by": t.reviewed_by.username if t.reviewed_by else None,
            "reviewed_at": to_ist_iso(t.reviewed_at) if t.reviewed_at else None,
            "raw_data": t.raw_data,
            "match_type": t.match_type,
            "matched_at": to_ist_iso(t.matched_at),
            "matched_by": t.matched_by.username if t.matched_by else None,
            "match_notes": t.match_notes,
            "voucher": voucher_info,
            "payment": payment_info,
        })

    return output


@router.get("/unmatched-books")
async def list_bank_unmatched_books(
    bank_ledger_id: int = Query(...),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    statement_id: Optional[int] = Query(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns Tally vouchers on this bank ledger that are not yet matched with any statement transaction."""
    matched_q = (
        select(BankStatementTransaction.matched_voucher_id)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.bank_ledger_id == bank_ledger_id,
            BankStatement.company_id == user.company_id,
            BankStatementTransaction.matched_status == "matched",
            BankStatementTransaction.matched_voucher_id != None
        )
    )
    if statement_id:
        matched_q = matched_q.where(BankStatementTransaction.statement_id == statement_id)
    matched_res = await db.execute(matched_q)
    matched_ids = set(matched_res.scalars().all())

    vouchers_q = (
        select(TrnVoucher)
        .join(TrnAccounting, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
        )
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnAccounting.ledger_id == bank_ledger_id,
        )
    )
    if from_date:
        vouchers_q = vouchers_q.where(TrnVoucher.voucher_date >= from_date - timedelta(days=15))
    if to_date:
        vouchers_q = vouchers_q.where(TrnVoucher.voucher_date <= to_date + timedelta(days=15))

    vouchers_q = vouchers_q.order_by(TrnVoucher.voucher_date.desc())
    vouchers_res = await db.execute(vouchers_q)
    vouchers = vouchers_res.scalars().unique().all()

    output = []
    for v in vouchers:
        if v.voucher_id in matched_ids:
            continue

        bank_entry = next((e for e in v.entries if e.ledger_id == bank_ledger_id), None)
        other_party = next((e.ledger.name for e in v.entries if e.ledger_id != bank_ledger_id and e.ledger), "Bank Transaction")
        amount = 0.0
        if bank_entry:
            b_damt = float(bank_entry.debit_amount or 0.0)
            b_camt = float(bank_entry.credit_amount or 0.0)
            amount = max(b_damt, b_camt)

        instrument_no = None
        if bank_entry and bank_entry.bank_allocations:
            instrument_no = bank_entry.bank_allocations[0].instrument_number

        vtype_name = v.voucher_type.name if v.voucher_type else "Voucher"
        output.append({
            "voucher_id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "voucher_type": vtype_name,
            "date": v.voucher_date.isoformat() if v.voucher_date else None,
            "party_name": other_party,
            "amount": amount,
            "instrument_number": instrument_no,
            "narration": v.narration,
        })

    return output


@router.get("/statements/{statement_id}/summary")
async def get_statement_brs_summary(
    statement_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes Bank Reconciliation Statement (BRS) summary:
    - Balance as per Bank Statement
    - Add: Uncredited Deposits (cheques/payments in books not cleared in bank)
    - Less: Unpresented Cheques (payments in books not debited in bank)
    - Balance as per Books
    - Net Difference (₹0.00 when fully reconciled)
    """
    stmt_res = await db.execute(
        select(BankStatement)
        .options(selectinload(BankStatement.bank_ledger))
        .where(BankStatement.statement_id == statement_id, BankStatement.company_id == user.company_id)
    )
    statement = stmt_res.scalars().first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    bank_ledger = statement.bank_ledger
    bank_balance = float(statement.closing_balance)
    books_balance = float(bank_ledger.closing_balance) if bank_ledger and bank_ledger.closing_balance else 0.0

    # Calculate uncredited deposits and unpresented cheques from unmatched transactions
    txs_res = await db.execute(
        select(BankStatementTransaction)
        .where(BankStatementTransaction.statement_id == statement_id)
    )
    txs = txs_res.scalars().all()

    unmatched_credits = sum(float(t.amount) for t in txs if t.matched_status != "matched" and t.transaction_type == "CREDIT")
    unmatched_debits = sum(float(t.amount) for t in txs if t.matched_status != "matched" and t.transaction_type == "DEBIT")
    reconciled_count = sum(1 for t in txs if t.matched_status == "matched")
    suggested_count = sum(1 for t in txs if t.matched_status == "suggested")
    unmatched_count = sum(1 for t in txs if t.matched_status == "unmatched")
    reviewed_count = sum(1 for t in txs if getattr(t, 'review_status', 'pending_review') not in ('pending_review', 'matched') and t.matched_status != 'matched')
    pending_review_count = sum(1 for t in txs if t.matched_status == "unmatched" and getattr(t, 'review_status', 'pending_review') == 'pending_review')

    adjusted_bank_balance = bank_balance + unmatched_credits - unmatched_debits
    variance = round(adjusted_bank_balance - books_balance, 2)

    return {
        "statement_id": statement.statement_id,
        "bank_name": bank_ledger.name if bank_ledger else "Bank Account",
        "statement_balance": bank_balance,
        "books_balance": books_balance,
        "uncredited_deposits": round(unmatched_credits, 2),
        "unpresented_cheques": round(unmatched_debits, 2),
        "variance": variance,
        "is_reconciled": abs(variance) < 0.01,
        "total_transactions": len(txs),
        "reconciled_count": reconciled_count,
        "suggested_count": suggested_count,
        "unmatched_count": unmatched_count,
        "reviewed_count": reviewed_count,
        "pending_review_count": pending_review_count,
        "reconciled_pct": round((reconciled_count / len(txs) * 100), 1) if txs else 0,
    }


@router.get("/statements/{statement_id}/transactions")
async def list_statement_transactions(
    statement_id: int,
    status: Optional[str] = Query(None, description="'all', 'matched', 'suggested', 'unmatched', 'reviewed', 'pending_review'"),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns transactions for a bank statement with match details, admin review status, and raw row details."""
    # Verify statement ownership
    stmt_check = await db.execute(
        select(BankStatement).where(BankStatement.statement_id == statement_id, BankStatement.company_id == user.company_id)
    )
    if not stmt_check.scalars().first():
        raise HTTPException(status_code=404, detail="Statement not found")

    query = (
        select(BankStatementTransaction)
        .options(
            selectinload(BankStatementTransaction.matched_voucher).selectinload(TrnVoucher.voucher_type),
            selectinload(BankStatementTransaction.matched_payment),
            selectinload(BankStatementTransaction.matched_by),
            selectinload(BankStatementTransaction.reviewed_by),
        )
        .where(BankStatementTransaction.statement_id == statement_id)
    )
    if status and status != "all":
        if status == "reviewed":
            query = query.where(
                BankStatementTransaction.review_status != "pending_review",
                BankStatementTransaction.matched_status != "matched"
            )
        elif status == "pending_review":
            query = query.where(
                BankStatementTransaction.matched_status == "unmatched",
                BankStatementTransaction.review_status == "pending_review"
            )
        else:
            query = query.where(BankStatementTransaction.matched_status == status)

    query = query.order_by(BankStatementTransaction.transaction_date.asc(), BankStatementTransaction.transaction_id.asc())
    res = await db.execute(query)
    rows = res.scalars().all()

    output = []
    for t in rows:
        voucher_info = None
        if t.matched_voucher:
            vtype_name = t.matched_voucher.voucher_type.name if t.matched_voucher.voucher_type else "Voucher"
            voucher_info = {
                "voucher_id": t.matched_voucher.voucher_id,
                "voucher_number": t.matched_voucher.voucher_number,
                "voucher_type": vtype_name,
                "date": t.matched_voucher.voucher_date.isoformat() if t.matched_voucher.voucher_date else None,
                "narration": t.matched_voucher.narration,
            }

        payment_info = None
        if t.matched_payment:
            cust_name = getattr(t.matched_payment, 'customer_name', None) or (t.matched_payment.ledger.name if getattr(t.matched_payment, 'ledger', None) else "Shop Payment")
            ref_no = getattr(t.matched_payment, 'reference_number', None) or getattr(t.matched_payment, 'cheque_number', None) or getattr(t.matched_payment, 'comments', None)
            payment_info = {
                "id": t.matched_payment.id,
                "customer_name": cust_name,
                "amount": float(t.matched_payment.amount),
                "payment_mode": t.matched_payment.payment_mode,
                "reference_number": ref_no,
            }

        output.append({
            "transaction_id": t.transaction_id,
            "statement_id": t.statement_id,
            "transaction_date": t.transaction_date.isoformat(),
            "description": t.description,
            "reference_no": t.reference_no,
            "cheque_no": t.cheque_no,
            "transaction_type": t.transaction_type,
            "amount": float(t.amount),
            "running_balance": float(t.running_balance) if t.running_balance is not None else None,
            "matched_status": t.matched_status,
            "review_status": t.review_status or "pending_review",
            "review_notes": t.review_notes,
            "reviewed_by": t.reviewed_by.username if t.reviewed_by else None,
            "reviewed_at": to_ist_iso(t.reviewed_at) if t.reviewed_at else None,
            "raw_data": t.raw_data,
            "match_type": t.match_type,
            "matched_at": to_ist_iso(t.matched_at),
            "matched_by": t.matched_by.username if t.matched_by else None,
            "match_notes": t.match_notes,
            "voucher": voucher_info,
            "payment": payment_info,
        })

    return output


@router.get("/statements/{statement_id}/unmatched-books")
async def list_unmatched_books(
    statement_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns Tally vouchers on this bank ledger that are not yet matched with any statement transaction."""
    stmt_res = await db.execute(
        select(BankStatement).where(BankStatement.statement_id == statement_id, BankStatement.company_id == user.company_id)
    )
    statement = stmt_res.scalars().first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Already matched voucher IDs in this statement
    matched_vouchers_res = await db.execute(
        select(BankStatementTransaction.matched_voucher_id)
        .where(
            BankStatementTransaction.statement_id == statement_id,
            BankStatementTransaction.matched_status == "matched",
            BankStatementTransaction.matched_voucher_id != None
        )
    )
    matched_ids = set(matched_vouchers_res.scalars().all())

    # Find vouchers on this bank ledger within date range
    date_from = statement.statement_from - timedelta(days=15)
    date_to = statement.statement_to + timedelta(days=15)

    vouchers_res = await db.execute(
        select(TrnVoucher)
        .join(TrnAccounting, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
        )
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnAccounting.ledger_id == statement.bank_ledger_id,
            TrnVoucher.voucher_date >= date_from,
            TrnVoucher.voucher_date <= date_to,
        )
        .order_by(TrnVoucher.voucher_date.asc())
    )
    vouchers = vouchers_res.scalars().unique().all()

    output = []
    for v in vouchers:
        if v.voucher_id in matched_ids:
            continue

        # Find entry for this bank
        bank_entry = next((e for e in v.entries if e.ledger_id == statement.bank_ledger_id), None)
        other_party = next((e.ledger.name for e in v.entries if e.ledger_id != statement.bank_ledger_id and e.ledger), "Bank Transaction")
        amount = 0.0
        if bank_entry:
            b_damt = float(bank_entry.debit_amount or 0.0)
            b_camt = float(bank_entry.credit_amount or 0.0)
            amount = max(b_damt, b_camt)

        instrument_no = None
        if bank_entry and bank_entry.bank_allocations:
            instrument_no = bank_entry.bank_allocations[0].instrument_number

        vtype_name = v.voucher_type.name if v.voucher_type else "Voucher"
        output.append({
            "voucher_id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "voucher_type": vtype_name,
            "date": v.voucher_date.isoformat() if v.voucher_date else None,
            "party_name": other_party,
            "amount": amount,
            "instrument_number": instrument_no,
            "narration": v.narration,
        })

    return output


@router.post("/match")
async def match_transaction(
    transaction_id: int = Form(...),
    voucher_id: Optional[int] = Form(None),
    payment_id: Optional[int] = Form(None),
    match_notes: Optional[str] = Form(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Manually or confirmed match between a statement line and a voucher or collection."""
    tx_res = await db.execute(
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatementTransaction.transaction_id == transaction_id,
            BankStatement.company_id == user.company_id
        )
    )
    tx = tx_res.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx.matched_status = "matched"
    tx.review_status = "matched"
    tx.matched_voucher_id = voucher_id
    tx.matched_payment_id = payment_id
    tx.match_type = "manual"
    tx.matched_at = get_ist_now()
    tx.matched_by_user_id = user.user_id
    if match_notes:
        tx.match_notes = match_notes.strip()[:512]

    # Update statement counters
    stmt_res = await db.execute(select(BankStatement).where(BankStatement.statement_id == tx.statement_id))
    statement = stmt_res.scalars().first()
    if statement:
        reconciled_res = await db.execute(
            select(func.count(BankStatementTransaction.transaction_id))
            .where(BankStatementTransaction.statement_id == statement.statement_id, BankStatementTransaction.matched_status == "matched")
        )
        count_matched = reconciled_res.scalar() or 0
        statement.reconciled_transactions = count_matched
        statement.unmatched_transactions = max(0, statement.total_transactions - count_matched)
        if count_matched == statement.total_transactions:
            statement.status = "reconciled"
        elif count_matched > 0:
            statement.status = "in_progress"

    await db.commit()
    return {"success": True, "message": "Transaction matched successfully."}


@router.post("/unmatch")
async def unmatch_transaction(
    transaction_id: int = Form(...),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Reverts a previously matched transaction back to unmatched state."""
    tx_res = await db.execute(
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatementTransaction.transaction_id == transaction_id,
            BankStatement.company_id == user.company_id
        )
    )
    tx = tx_res.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx.matched_status = "unmatched"
    tx.review_status = "pending_review"
    tx.matched_voucher_id = None
    tx.matched_payment_id = None
    tx.matched_allocation_id = None
    tx.match_type = None
    tx.matched_at = None
    tx.matched_by_user_id = None
    tx.match_notes = None

    # Update statement counters
    stmt_res = await db.execute(select(BankStatement).where(BankStatement.statement_id == tx.statement_id))
    statement = stmt_res.scalars().first()
    if statement:
        reconciled_res = await db.execute(
            select(func.count(BankStatementTransaction.transaction_id))
            .where(BankStatementTransaction.statement_id == statement.statement_id, BankStatementTransaction.matched_status == "matched")
        )
        count_matched = reconciled_res.scalar() or 0
        statement.reconciled_transactions = count_matched
        statement.unmatched_transactions = max(0, statement.total_transactions - count_matched)
        statement.status = "in_progress" if count_matched > 0 else "imported"

    await db.commit()
    return {"success": True, "message": "Transaction reverted to unmatched."}


@router.post("/batch-match-suggested")
async def batch_match_suggested(
    statement_id: Optional[int] = Form(None),
    bank_ledger_id: Optional[int] = Form(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """1-click accepts all transactions currently in 'suggested' status for this statement or bank ledger."""
    if not statement_id and not bank_ledger_id:
        raise HTTPException(status_code=400, detail="Either statement_id or bank_ledger_id must be provided")

    tx_q = (
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatement.company_id == user.company_id,
            BankStatementTransaction.matched_status == "suggested",
            BankStatementTransaction.matched_voucher_id != None
        )
    )
    if statement_id:
        tx_q = tx_q.where(BankStatementTransaction.statement_id == statement_id)
    if bank_ledger_id:
        tx_q = tx_q.where(BankStatement.bank_ledger_id == bank_ledger_id)

    txs_res = await db.execute(tx_q)
    suggested = txs_res.scalars().all()

    accepted_count = 0
    affected_statement_ids = set()
    now_ist = get_ist_now()
    for tx in suggested:
        tx.matched_status = "matched"
        tx.review_status = "matched"
        tx.matched_at = now_ist
        tx.matched_by_user_id = user.user_id
        affected_statement_ids.add(tx.statement_id)
        accepted_count += 1

    # Recalculate affected statement stats
    for s_id in affected_statement_ids:
        stmt_res = await db.execute(select(BankStatement).where(BankStatement.statement_id == s_id))
        stmt = stmt_res.scalars().first()
        if stmt:
            reconciled_res = await db.execute(
                select(func.count(BankStatementTransaction.transaction_id))
                .where(BankStatementTransaction.statement_id == s_id, BankStatementTransaction.matched_status == "matched")
            )
            count_matched = reconciled_res.scalar() or 0
            stmt.reconciled_transactions = count_matched
            stmt.unmatched_transactions = max(0, stmt.total_transactions - count_matched)
            if count_matched == stmt.total_transactions:
                stmt.status = "reconciled"
            elif count_matched > 0:
                stmt.status = "in_progress"

    await db.commit()
    return {"success": True, "accepted_count": accepted_count}


@router.post("/review-status")
async def update_review_status(
    transaction_id: int = Form(...),
    review_status: str = Form(...),  # 'pending_review', 'not_specific', 'bank_charges', 'interest', 'internal_transfer', 'other_account', 'under_investigation'
    review_notes: Optional[str] = Form(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Sets or updates the admin review classification for an unmatched bank statement transaction.
    Does NOT create any vouchers; securely preserves the bank transaction row for audit & compliance.
    """
    tx_res = await db.execute(
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatementTransaction.transaction_id == transaction_id,
            BankStatement.company_id == user.company_id
        )
    )
    tx = tx_res.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    valid_statuses = [
        "pending_review",
        "not_specific",
        "bank_charges",
        "interest",
        "internal_transfer",
        "other_account",
        "under_investigation",
    ]
    if review_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid review_status. Allowed values: {valid_statuses}")

    tx.review_status = review_status
    if review_status == "pending_review":
        tx.review_notes = None
        tx.reviewed_by_user_id = None
        tx.reviewed_at = None
    else:
        tx.review_notes = review_notes.strip()[:512] if review_notes else None
        tx.reviewed_by_user_id = user.user_id
        tx.reviewed_at = get_ist_now()

    # Recalculate statement reviewed transactions count
    stmt_res = await db.execute(select(BankStatement).where(BankStatement.statement_id == tx.statement_id))
    statement = stmt_res.scalars().first()
    if statement:
        rev_count_res = await db.execute(
            select(func.count(BankStatementTransaction.transaction_id))
            .where(
                BankStatementTransaction.statement_id == statement.statement_id,
                BankStatementTransaction.review_status != "pending_review",
                BankStatementTransaction.matched_status != "matched"
            )
        )
        statement.reviewed_transactions = rev_count_res.scalar() or 0

    await db.commit()
    return {
        "success": True,
        "transaction_id": tx.transaction_id,
        "review_status": tx.review_status,
        "review_notes": tx.review_notes,
        "reviewed_by": user.username,
        "reviewed_at": to_ist_iso(tx.reviewed_at) if tx.reviewed_at else None,
    }


@router.post("/batch-review")
async def batch_review_status(
    transaction_ids: str = Form(..., description="Comma-separated transaction IDs"),
    review_status: str = Form(...),
    review_notes: Optional[str] = Form(None),
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch-marks multiple transactions as reviewed or not-specific to this account.
    """
    try:
        t_ids = [int(i.strip()) for i in transaction_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transaction_ids format")

    if not t_ids:
        raise HTTPException(status_code=400, detail="No transaction_ids provided")

    txs_res = await db.execute(
        select(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.statement_id)
        .where(
            BankStatementTransaction.transaction_id.in_(t_ids),
            BankStatement.company_id == user.company_id
        )
    )
    txs = txs_res.scalars().all()
    now_ist = get_ist_now()
    statement_ids = set()

    for tx in txs:
        tx.review_status = review_status
        if review_status == "pending_review":
            tx.review_notes = None
            tx.reviewed_by_user_id = None
            tx.reviewed_at = None
        else:
            tx.review_notes = review_notes.strip()[:512] if review_notes else None
            tx.reviewed_by_user_id = user.user_id
            tx.reviewed_at = now_ist
        statement_ids.add(tx.statement_id)

    # Recalculate statement reviewed counts
    for s_id in statement_ids:
        stmt_res = await db.execute(select(BankStatement).where(BankStatement.statement_id == s_id))
        stmt = stmt_res.scalars().first()
        if stmt:
            rev_count_res = await db.execute(
                select(func.count(BankStatementTransaction.transaction_id))
                .where(
                    BankStatementTransaction.statement_id == s_id,
                    BankStatementTransaction.review_status != "pending_review",
                    BankStatementTransaction.matched_status != "matched"
                )
            )
            stmt.reviewed_transactions = rev_count_res.scalar() or 0

    await db.commit()
    return {"success": True, "count": len(txs), "review_status": review_status}
