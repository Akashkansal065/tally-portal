import xml.etree.ElementTree as ET
import logging
import re
import secrets
import uuid
import difflib
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func, delete, update

logger = logging.getLogger("uvicorn.error")

from app.core.config import settings
from app.models.tally_core import (
    MstGroup, MstLedger, MstStockGroup, MstStockCategory, 
    MstGodown, MstStockItem, MstVoucherType, MstUom,
    MstVoucherTypePrefix, MstVoucherTypeSuffix, MstVoucherTypeRestart,
    MstVoucherTypeClass, MstVoucherTypeClassGroup,
    MstCostCategory, MstCostCentre, CostCenter, MstAttendanceType, MstPayHead, TrnAttendance, TrnPayHead,
    TrnVoucher, TrnAccounting, TrnInventory, TrnBill, TrnBankAllocation,
    BillAllocation, MstLedgerGstRegistration, TrnEwayBill, MstHsnDetail,
    MstLedgerMsmeDetail, MstLedgerAddress, MstLedgerTdsLowerDeduction, TrnCostCentreAllocation
)
from app.models.portal_core import Company, User, Role, UserCompanyAccess, Currency, DeletedRecordAudit
from app.services.voucher_kinds import is_physical_stock, is_payroll
from app.core.security import get_password_hash

_checked_tally_users = set()

def parse_tally_date(date_str: str) -> Optional[date]:
    if not date_str or not str(date_str).strip():
        return None
    clean = str(date_str).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None

def parse_tally_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str or not str(dt_str).strip():
        return None
    clean = str(dt_str).strip().replace("/", "-")
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None

async def ensure_tally_user_exists(db: AsyncSession, company_id: int, user_name: str) -> Optional[User]:
    if not user_name or not str(user_name).strip():
        return None
        
    raw_name = str(user_name).strip()
    if raw_name.lower() in ("sysname:xml", "none", "null", "system", "tally"):
        return None
        
    cache_key = (company_id, raw_name.lower())
    if cache_key in _checked_tally_users:
        return None
        
    # Reuse a user with this username only if they already belong to this company. A name in imported
    # XML must never grant an existing portal user access to another company.
    user_stmt = select(User).outerjoin(
        UserCompanyAccess,
        (UserCompanyAccess.user_id == User.user_id) & (UserCompanyAccess.company_id == company_id)
    ).where(
        func.lower(User.username) == raw_name.lower(),
        (User.company_id == company_id) | (UserCompanyAccess.company_id == company_id)
    )
    res = await db.execute(user_stmt)
    existing_user = res.scalars().first()
    
    if existing_user:
        _checked_tally_users.add(cache_key)
        return existing_user

    # Get default 'User' or 'Staff' role
    role_stmt = select(Role).where(Role.name.in_(["User", "Staff"]))
    role_res = await db.execute(role_stmt)
    default_role = role_res.scalars().first()
    if not default_role:
        role_stmt2 = select(Role).limit(1)
        role_res2 = await db.execute(role_stmt2)
        default_role = role_res2.scalars().first()

    if not default_role:
        logger.warning(f"Could not auto-create user '{raw_name}': No roles found in database.")
        return None

    # Generate a clean email for the new user
    safe_slug = re.sub(r'[^a-z0-9]', '', raw_name.lower()) or "user"
    generated_email = f"{safe_slug}_{company_id}@mytally.local"

    email_check = await db.execute(select(User).where(User.email == generated_email))
    if email_check.scalars().first():
        generated_email = f"{safe_slug}_{company_id}_{int(datetime.now().timestamp())}@mytally.local"

    # Auto-provisioned Tally operators exist for attribution only. Give them an unguessable,
    # never-disclosed password; an admin must use "Reset password" to enable a real login.
    password_hash = get_password_hash(secrets.token_urlsafe(32))
    new_user = User(
        account_id=(await db.execute(select(Company.account_id).where(Company.company_id == company_id))).scalar(),
        company_id=company_id,
        username=raw_name,
        email=generated_email,
        password_hash=password_hash,
        role_id=default_role.role_id,
        is_active=True,
        ledger_scope='full',
        stock_scope='full'
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    # Link access to this company
    access = UserCompanyAccess(user_id=new_user.user_id, company_id=company_id)
    db.add(access)
    await db.flush()

    logger.info(f"👥 [AUTO-PROVISIONED TALLY USER] Created new user '{raw_name}' (Email: {generated_email}, ID: {new_user.user_id}) for Company #{company_id}")
    _checked_tally_users.add(cache_key)
    return new_user

def is_valid_xml_char(cp: int) -> bool:
    return (
        cp == 0x9 or
        cp == 0xA or
        cp == 0xD or
        (0x20 <= cp <= 0xD7FF) or
        (0xE000 <= cp <= 0xFFFD) or
        (0x10000 <= cp <= 0x10FFFF)
    )

def sanitize_xml(xml_data: str) -> str:
    # 1. Replace invalid numeric/hex character references (e.g. &#4;, &#x04;)
    entity_pattern = re.compile(r'&#(\d+);|&#[xX]([0-9a-fA-F]+);')
    
    def entity_repl(match):
        dec_val = match.group(1)
        hex_val = match.group(2)
        try:
            if dec_val:
                cp = int(dec_val)
            else:
                cp = int(hex_val, 16)
            
            if is_valid_xml_char(cp):
                return match.group(0) # Keep valid reference
            else:
                return "" # Remove invalid character reference
        except Exception:
            return ""
            
    sanitized = entity_pattern.sub(entity_repl, xml_data)
    
    # 2. Filter out raw characters that are invalid in XML 1.0
    invalid_xml_raw_re = re.compile(
        r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]'
    )
    sanitized = invalid_xml_raw_re.sub("", sanitized)

    # 3. Strip unbound 'UDF:' XML prefixes returned by Tally (e.g. <UDF:LWLEDADHARNOSTORE> -> <LWLEDADHARNOSTORE>)
    if "UDF:" in sanitized:
        sanitized = re.sub(r'</?UDF:', lambda m: m.group(0).replace('UDF:', ''), sanitized)

    return sanitized

async def get_or_create_stock_group(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None,
                                    sync_parent: bool = False) -> MstStockGroup:
    """
    A top-level stock group has no parent here. Tally reports the top level as the reserved name "Primary";
    that is a marker, not a group, and is never stored as one (tally_parent_name).
    sync_parent: the caller read this group itself from Tally, so an existing group is moved to the parent
    given, or to the top level when there is none.
    """
    clean_name = name.strip()
    parent_name = tally_parent_name(parent_name)
    stmt = select(MstStockGroup).where(
        MstStockGroup.company_id == company_id,
        func.lower(func.trim(MstStockGroup.name)) == clean_name.lower()
    )
    res = await db.execute(stmt)
    group = res.scalars().first()
    
    parent_id = None
    if parent_name and (group is None or sync_parent):
        parent_group = await get_or_create_stock_group(db, company_id, parent_name)
        parent_id = parent_group.stock_group_id
        
    if group:
        if sync_parent and group.parent_id != parent_id and parent_id != group.stock_group_id:
            group.parent_id = parent_id
            await db.flush()
        return group
        
    group = MstStockGroup(
        company_id=company_id,
        name=clean_name,
        parent_id=parent_id
    )
    db.add(group)
    await db.flush()
    return group

async def resolve_stock_group_dynamically(
    db: AsyncSession,
    company_id: int,
    candidate_group: Optional[str] = None,
    item_name: Optional[str] = None,
    party_name: Optional[str] = None
) -> MstStockGroup:
    """
    Dynamically resolves the appropriate MstStockGroup for a stock item without
    hardcoding any brand names or keywords.
    
    Resolution hierarchy:
    1. Candidate group match (exact case-insensitive, substring/containment, fuzzy typo match ratio >= 0.85).
    2. If candidate is a novel group from Tally, auto-creates it dynamically.
    3. Match party ledger name against active database stock groups.
    4. Match item name against active database stock groups.
    5. Sibling item match: checks if existing items in DB share leading tokens/prefix.
    6. Default fallback to 'General' (or existing default group).
    """
    # 1. Fetch active non-Primary groups for this company
    stmt = select(MstStockGroup).where(
        MstStockGroup.company_id == company_id,
        func.trim(MstStockGroup.name) != "Primary"
    )
    res = await db.execute(stmt)
    existing_groups = list(res.scalars().all())

    # 2. Check candidate_group if provided (e.g. from GSTSTOCKGROUPSOURCE / HSNSTOCKGROUPSOURCE)
    if candidate_group:
        cand_clean = candidate_group.strip()
        cand_lower = cand_clean.lower()
        if cand_clean:
            # a) Case-insensitive exact match
            for g in existing_groups:
                if g.name.strip().lower() == cand_lower:
                    return g

            # b) Substring / containment match (e.g. 'SURAJ POLY PLAST' matches 'SURAJ POLY PLAST (JOYWARE)')
            for g in existing_groups:
                g_lower = g.name.strip().lower()
                if len(cand_lower) >= 4 and (cand_lower in g_lower or g_lower in cand_lower):
                    return g

            # c) Fuzzy match for typos / spelling variants (e.g. 'NIRVAAN METALIKAS' vs 'NIRVAAN METALIKS')
            cand_norm = re.sub(r'[^a-zA-Z0-9]', '', cand_lower)
            best_match = None
            best_ratio = 0.0
            for g in existing_groups:
                g_norm = re.sub(r'[^a-zA-Z0-9]', '', g.name.lower())
                ratio = difflib.SequenceMatcher(None, cand_norm, g_norm).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = g
            if best_match and best_ratio >= 0.85:
                return best_match

            # d) Novel brand/group: create dynamically
            return await get_or_create_stock_group(db, company_id, cand_clean)

    # 3. Match against existing groups via party_name
    generic_words = {"limited", "appliances", "electricals", "india", "pvt", "ltd", "corp", "group", "enterprises", "plast", "poly"}
    if party_name:
        party_lower = party_name.strip().lower()
        for g in existing_groups:
            g_lower = g.name.strip().lower()
            if len(g_lower) >= 3 and g_lower in party_lower:
                return g
        for g in existing_groups:
            words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', g.name) if len(w) >= 4]
            sig_words = [w for w in words if w not in generic_words]
            if any(w in party_lower for w in sig_words):
                return g

    # 4. Match against existing groups via item_name
    if item_name:
        item_lower = item_name.strip().lower()
        for g in existing_groups:
            g_lower = g.name.strip().lower()
            if len(g_lower) >= 3 and g_lower in item_lower:
                return g
        for g in existing_groups:
            words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', g.name) if len(w) >= 4]
            sig_words = [w for w in words if w not in generic_words]
            if any(w in item_lower for w in sig_words):
                return g

    # 5. Sibling item matching: look up existing DB items sharing prefix tokens
    if item_name:
        words = [w for w in re.findall(r'[a-zA-Z0-9.\-/]+', item_name) if len(w) >= 2]
        matched_group_id = None
        if len(words) >= 2:
            prefix_pattern = f"{words[0]} {words[1]}%"
            res_similar = await db.execute(
                select(MstStockItem.stock_group_id)
                .where(
                    MstStockItem.company_id == company_id,
                    MstStockItem.stock_group_id.isnot(None),
                    MstStockItem.name.ilike(prefix_pattern)
                )
                .limit(1)
            )
            matched_group_id = res_similar.scalar_one_or_none()

        if not matched_group_id and len(words) >= 1 and len(words[0]) >= 4:
            token_pattern = f"{words[0]}%"
            res_similar = await db.execute(
                select(MstStockItem.stock_group_id)
                .where(
                    MstStockItem.company_id == company_id,
                    MstStockItem.stock_group_id.isnot(None),
                    MstStockItem.name.ilike(token_pattern)
                )
                .limit(1)
            )
            matched_group_id = res_similar.scalar_one_or_none()

        if matched_group_id:
            for g in existing_groups:
                if g.stock_group_id == matched_group_id:
                    return g
            group_by_id = await db.get(MstStockGroup, matched_group_id)
            if group_by_id:
                return group_by_id

    # 6. Fallback to 'General' (or existing default group)
    for g in existing_groups:
        if g.name.strip().lower() in ["general", "others", "miscellaneous"]:
            return g
    return await get_or_create_stock_group(db, company_id, "General")

async def get_or_create_stock_category(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None) -> MstStockCategory:
    # "Primary" is Tally's marker for the top level, not a category
    name = (name or "").strip()
    parent_name = tally_parent_name(parent_name)
    stmt = select(MstStockCategory).where(MstStockCategory.company_id == company_id, MstStockCategory.name == name)
    res = await db.execute(stmt)
    cat = res.scalars().first()
    
    parent_id = None
    if parent_name:
        parent_cat = await get_or_create_stock_category(db, company_id, parent_name)
        parent_id = parent_cat.stock_category_id
        
    if cat:
        if parent_id is not None and cat.parent_id != parent_id:
            cat.parent_id = parent_id
            await db.flush()
        return cat
        
    cat = MstStockCategory(
        company_id=company_id,
        name=name,
        parent_id=parent_id
    )
    db.add(cat)
    await db.flush()
    return cat

async def get_or_create_uom(db: AsyncSession, company_id: int, symbol: str, name: Optional[str] = None, decimal_places: int = 0) -> MstUom:
    # Tally's "no unit" marker arrives as " Not Applicable" (its control character sanitised to a space)
    symbol = (symbol or "").strip()
    name = name.strip() if name else name
    stmt = select(MstUom).where(MstUom.company_id == company_id, MstUom.symbol == symbol)
    res = await db.execute(stmt)
    uom = res.scalars().first()
    if uom:
        if name and uom.name != name:
            uom.name = name
            await db.flush()
        return uom
    uom = MstUom(
        company_id=company_id,
        symbol=symbol,
        name=name or symbol,
        decimal_places=decimal_places
    )
    db.add(uom)
    await db.flush()
    return uom

async def get_or_create_godown(db: AsyncSession, company_id: int, name: str, address: Optional[str] = None) -> MstGodown:
    stmt = select(MstGodown).where(MstGodown.company_id == company_id, MstGodown.name == name)
    res = await db.execute(stmt)
    godown = res.scalars().first()
    if godown:
        if address and godown.address != address:
            godown.address = address
            await db.flush()
        return godown
    godown = MstGodown(
        company_id=company_id,
        name=name,
        address=address
    )
    db.add(godown)
    await db.flush()
    return godown

GROUP_EXTRA_FIELDS = (
    'alias_name', 'is_addable', 'is_revenue', 'is_deemed_positive', 'affects_gross_profit',
    'is_subledger', 'is_billwise_on', 'used_for_calculation', 'method_to_allocate',
    'tally_guid', 'tally_alter_id',
)

# Tally's two flags to the nature they encode: (is_revenue, is_deemed_positive)
GROUP_NATURE_BY_FLAGS = {
    (False, True): "Asset",
    (False, False): "Liability",
    (True, False): "Income",
    (True, True): "Expense",
}

def tally_parent_name(raw: Optional[str]) -> Optional[str]:
    """
    A group's real parent name, or None for a top-level group. Tally reports the top level as the
    reserved name "Primary" behind a control character, which sanitising leaves as " Primary".
    """
    name = (raw or "").strip()
    return None if not name or name.lower() == "primary" else name

def apply_group_extra_data(group: MstGroup, extra_data: Optional[dict]):
    if not extra_data:
        return
    for field in GROUP_EXTRA_FIELDS:
        if field in extra_data:
            setattr(group, field, extra_data[field])
    if 'is_revenue' in extra_data and 'is_deemed_positive' in extra_data:
        group.nature = GROUP_NATURE_BY_FLAGS[(extra_data['is_revenue'], extra_data['is_deemed_positive'])]

def _trim_marker(text_value) -> str:
    """Tally prefixes its built-in names (Primary, Not Applicable) with a control character."""
    return (text_value or "").replace("\x04", "").strip()


async def _rename_employee_lines(db: AsyncSession, company_id: int, old_name: str, new_name: str) -> None:
    """Attendance and payroll lines name their employee; they follow a rename made in Tally."""
    in_company = select(TrnVoucher.voucher_id).where(TrnVoucher.company_id == company_id)
    for model in (TrnAttendance, TrnPayHead):
        await db.execute(update(model).where(model.employee_name == old_name, model.voucher_id.in_(in_company)).values(employee_name=new_name))


async def _read_payroll_cost_centre(db: AsyncSession, company_id: int, row, node, guid: Optional[str]) -> None:
    """Employee group / employee fields and salary details of a cost centre. A field Tally did not send is left alone."""
    from app.models.tally_core import MstEmployeeSalaryRate
    if guid:
        row.tally_guid = guid
        master_id = (node.findtext("MASTERID") or "").strip()
        if master_id.isdigit():
            row.tally_master_id = int(master_id)
    if node.find("ISEMPLOYEEGROUP") is not None:
        row.is_employee_group = (node.findtext("ISEMPLOYEEGROUP") or "").strip().lower() == "yes"
    if node.find("DATEOFJOIN") is not None:
        row.date_of_join = parse_tally_date((node.findtext("DATEOFJOIN") or "").strip())
    if node.find("DESIGNATION") is not None:
        row.designation = (node.findtext("DESIGNATION") or "").strip()[:100] or None
    if node.find("GENDER") is not None:
        row.gender = (node.findtext("GENDER") or "").strip()[:20] or None
    if node.find("MAILINGNAME.LIST") is not None:
        row.employee_number = (node.findtext("MAILINGNAME.LIST/MAILINGNAME") or "").strip()[:50] or None
    periods = node.findall("EMPLOYEEPERIOD.LIST")
    if not periods:
        return
    await db.flush()
    await db.execute(delete(MstEmployeeSalaryRate).where(MstEmployeeSalaryRate.cost_centre_id == row.cost_centre_id))
    position = 0
    for period in periods:
        start = parse_tally_date((period.findtext("PERIODFROM") or "").strip())
        if not start:
            continue
        for rate in period.findall("EMPLOYEERATE.LIST"):
            head = (rate.findtext("NAME") or "").strip()
            if head:
                db.add(MstEmployeeSalaryRate(company_id=company_id, cost_centre_id=row.cost_centre_id, effective_from=start, pay_head_name=head[:100],
                                             rate=_decimal_or_none(rate.findtext("EMPTIMERATE")), position=position))
                position += 1


def _decimal_or_none(text_value) -> Optional[Decimal]:
    """A Tally number such as " 30" or "-4838.71 Days"; None when there is nothing usable."""
    cleaned = (text_value or "").replace(",", "").strip().split(" ")[0]
    try:
        return Decimal(cleaned) if cleaned else None
    except Exception:
        return None

# Master types whose Tally identity (GUID, master id) is kept on the app's row: XML tag, model, name column
def _identity_types():
    return (
        ("GROUP", MstGroup, MstGroup.name),
        ("LEDGER", MstLedger, MstLedger.name),
        ("STOCKGROUP", MstStockGroup, MstStockGroup.name),
        ("STOCKITEM", MstStockItem, MstStockItem.name),
        ("UNIT", MstUom, MstUom.symbol),
    )


def _master_identity(node) -> tuple:
    name = (node.get("NAME") or node.findtext("NAME") or "").strip()
    guid = (node.findtext("GUID") or "").strip() or None
    master_id = (node.findtext("MASTERID") or "").strip()
    return name, guid, int(master_id) if master_id.isdigit() else None


async def follow_tally_renames(db: AsyncSession, company_id: int, root) -> int:
    """
    A master renamed in Tally keeps its GUID. The import matches masters by name, so before it runs, a row
    that carries a node's GUID under another name takes the node's name; otherwise the rename would arrive as
    a second record and leave the old one behind. Skipped when the new name is already taken here.
    """
    renamed = 0
    for tag, model, name_col in _identity_types():
        for node in root.findall(f".//{tag}"):
            name, guid, _ = _master_identity(node)
            if not name or not guid or tally_parent_name(name) is None:
                continue
            row = (await db.execute(select(model).where(model.company_id == company_id, model.tally_guid == guid))).scalars().first()
            if row is None or getattr(row, name_col.key) == name:
                continue
            taken = (await db.execute(select(model).where(model.company_id == company_id, name_col == name))).scalars().first()
            if taken is not None:
                continue
            logger.info(f"[RENAMED IN TALLY] {tag} '{getattr(row, name_col.key)}' is now '{name}' (GUID {guid})")
            if model is MstUom and row.name == row.symbol:
                row.name = name
            setattr(row, name_col.key, name)
            renamed += 1
    if renamed:
        await db.flush()
    return renamed


async def store_master_identities(db: AsyncSession, company_id: int, root) -> None:
    """Writes each imported master's GUID and master id onto the app's row of the same name."""
    for tag, model, name_col in _identity_types():
        for node in root.findall(f".//{tag}"):
            name, guid, master_id = _master_identity(node)
            if not name or not (guid or master_id):
                continue
            row = (await db.execute(select(model).where(model.company_id == company_id, name_col == name))).scalars().first()
            if row is None:
                continue
            if guid and row.tally_guid != guid:
                row.tally_guid = guid
            if master_id and row.tally_master_id != master_id:
                row.tally_master_id = master_id
    await db.flush()


async def get_or_create_group(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None, extra_data: dict = None, sync_parent: bool = False) -> MstGroup:
    """sync_parent: the caller knows the group's parent for certain (it read the group itself from
    Tally), so an existing group is moved to it, or to the top level when parent_name is empty."""
    parent_name = tally_parent_name(parent_name)
    # A ledger directly under Tally's top level (Profit & Loss A/c) names " Primary" as its group
    name = (name or "").strip()

    # Check if group exists
    stmt = select(MstGroup).where(MstGroup.company_id == company_id, MstGroup.name == name)
    res = await db.execute(stmt)
    group = res.scalars().first()

    # Get parent id
    parent_id = None
    if parent_name and (group is None or sync_parent):
        parent_grp = await get_or_create_group(db, company_id, parent_name)
        parent_id = parent_grp.group_id

    if group:
        apply_group_extra_data(group, extra_data)
        if sync_parent and group.parent_group_id != parent_id and parent_id != group.group_id:
            group.parent_group_id = parent_id
        return group
        
    group = MstGroup(
        company_id=company_id,
        name=name,
        parent_group_id=parent_id,
        nature="Asset", # default fallback
        affects_gross_profit=False,
        is_system_defined=False
    )
    apply_group_extra_data(group, extra_data)
        
    db.add(group)
    await db.flush()
    return group

async def import_tally_xml(
    xml_data: str,
    db: AsyncSession,
    user_id: int,
    override_company_name: Optional[str] = None,
    force_overwrite: bool = False,
    allow_company_create: bool = False,
    company_guid: Optional[str] = None
) -> dict:
    """Import Tally XML into the mirror for a company the user can access.
    allow_company_create: create the company (and grant the user access) when it doesn't exist yet.
    Only administrator-initiated syncs should pass True.
    company_guid: the Tally company GUID the sender says this export is from. When given, it decides the
    company: a name is only used to link a company that has no GUID yet, never one linked to another GUID."""
    if not xml_data or not xml_data.strip():
        return {"status": "error", "message": "Empty XML payload."}
        
    # Sanitize XML data before parsing to handle invalid control characters
    xml_data = sanitize_xml(xml_data)
    try:
        # Parse XML
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        try:
            lines = xml_data.splitlines()
            line_no, col_no = e.position
            start = max(0, line_no - 5)
            end = min(len(lines), line_no + 5)
            context_lines = []
            context_lines.append(f"XML Parsing Exception: {str(e)}")
            context_lines.append("--- XML Context Around Error ---")
            for i in range(start, end):
                curr_line_no = i + 1
                line_content = lines[i]
                if curr_line_no == line_no:
                    context_lines.append(f"-> {curr_line_no:5d}: {line_content}")
                    # Align pointer to column (prefix has 10 chars)
                    pointer_line = " " * (10 + col_no) + "^"
                    context_lines.append(pointer_line)
                else:
                    context_lines.append(f"   {curr_line_no:5d}: {line_content}")
            context_lines.append("--------------------------------")
            detailed_err = "\n".join(context_lines)
            logger.error(detailed_err)
        except Exception as log_ex:
            logger.error(f"Error parsing XML and formatting error: {str(log_ex)}", exc_info=True)
            logger.error(f"Original XML ParseError: {str(e)}", exc_info=True)
            
        return {"status": "error", "message": f"XML parse error: {str(e)}"}

    company_id = None
    resolved_company_name = "Unknown Company"
    # Extract company name and update/create company model
    try:
        company_name_node = root.find(".//SVCURRENTCOMPANY")
        company_node = root.find(".//COMPANY")
        
        tally_guid = None
        if company_guid:
            # Tally lists every open company in a Company export, so the first one may be another company
            tally_guid = company_guid
            company_node = next(
                (node for node in root.iter("COMPANY")
                 if ((node.findtext("COMPANYGUID") or node.findtext("GUID") or "").strip() == company_guid)),
                None)
        elif company_node is not None:
            tally_guid = company_node.findtext("COMPANYGUID") or company_node.findtext("GUID")
            
        company_name = None
        if company_guid and company_node is not None:
            company_name = company_node.get("NAME") or company_node.findtext("NAME") or override_company_name
        elif override_company_name:
            company_name = override_company_name.strip()
        elif company_node is not None:
            company_name = company_node.get("NAME") or company_node.findtext("NAME")
        elif company_name_node is not None and company_name_node.text:
            company_name = company_name_node.text.strip()
            
        if company_name: company_name = company_name.strip()
        if tally_guid: tally_guid = tally_guid.strip()
            
        # Fallback to user's first company if no company name or GUID in XML
        if not company_name and not tally_guid:
            fallback_stmt = select(Company).join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == user_id).order_by(Company.company_id.asc())
            fallback_res = await db.execute(fallback_stmt)
            fallback_comp = fallback_res.scalars().first()
            if fallback_comp:
                company_name = fallback_comp.name
                
        if company_name or tally_guid:
            company_obj = None
            
            # 1. Try finding by tally_guid mapped to this user
            if tally_guid:
                guid_stmt = select(Company).join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id).where(
                    UserCompanyAccess.user_id == user_id,
                    Company.tally_guid == tally_guid
                )
                comp_res = await db.execute(guid_stmt)
                company_obj = comp_res.scalars().first()

            # 2. If not found by GUID, try finding by name (case-insensitive) mapped to this user
            if not company_obj and company_name:
                name_stmt = select(Company).outerjoin(
                    UserCompanyAccess, (Company.company_id == UserCompanyAccess.company_id) & (UserCompanyAccess.user_id == user_id)
                ).outerjoin(
                    User, (Company.company_id == User.company_id) & (User.user_id == user_id)
                ).where(
                    (UserCompanyAccess.user_id == user_id) | (User.user_id == user_id),
                    func.lower(Company.name) == func.lower(company_name)
                ).order_by(Company.company_id.asc()) # Prefer primary/older company
                
                comp_res = await db.execute(name_stmt)
                company_obj = comp_res.scalars().first()
            
            if company_guid and company_obj and company_obj.tally_guid and company_obj.tally_guid != company_guid:
                # Found by name only, and that company belongs to a different Tally company of the same name
                logger.warning(
                    f"Inbound import refused for user_id={user_id}: '{company_name}' (company #{company_obj.company_id}) is "
                    f"linked to Tally GUID {company_obj.tally_guid}, not {company_guid}.")
                return {
                    "status": "error",
                    "message": f"Company '{company_name}' is linked to a different Tally company (GUID {company_obj.tally_guid}). "
                               "This Tally company has the same name but is not the same company, so nothing was imported."
                }
            if not company_obj and not allow_company_create:
                logger.warning(f"Inbound import refused for user_id={user_id}: no accessible company named '{company_name}' (guid={tally_guid}).")
                return {
                    "status": "error",
                    "message": f"Company '{company_name}' was not found among the companies you can access. "
                               "Ask an administrator to create it or grant you access."
                }
            if not company_obj:
                # Auto-create company (administrator-initiated sync only)
                company_obj = Company(
                    account_id=(await db.execute(select(User.account_id).where(User.user_id == user_id))).scalar(),
                    name=company_name or "Unknown Sync Company",
                    tally_guid=tally_guid,
                    books_begin_date=date.today(),
                    is_active=True
                )
                db.add(company_obj)
                await db.flush()
                
                # Grant access to user
                access = UserCompanyAccess(user_id=user_id, company_id=company_obj.company_id)
                db.add(access)
                await db.flush()
                logger.info(f"Auto-created new company '{company_obj.name}' and mapped to user_id={user_id}.")
            else:
                # If existing company was matched by name, link the tally_guid if missing
                if tally_guid and not company_obj.tally_guid:
                    company_obj.tally_guid = tally_guid
                    await db.flush()
            
            company_id = company_obj.company_id
            resolved_company_name = company_obj.name
            
            # Now update the details from XML
            updated = False
            if company_node is not None:
                if company_name and company_obj.name != company_name:
                    company_obj.name = company_name
                    updated = True
                
                if tally_guid and company_obj.tally_guid != tally_guid:
                    company_obj.tally_guid = tally_guid
                    updated = True

                def get_clean_text(elem_name: str) -> Optional[str]:
                    node = company_node.find(f".//{elem_name}") or company_node.find(elem_name)
                    if node is not None and node.text:
                        val = node.text.strip()
                        if val and val.lower() not in ("none", "null", "n/a", "na", ""):
                            return val
                    return None

                # Extract address
                addr_lines = []
                for addr_elem in (company_node.findall(".//ADDRESS") + company_node.findall(".//BASICCOMPANYADDRESS") + company_node.findall(".//ADDRESS.LIST/*") + company_node.findall(".//BASICCOMPANYADDRESS.LIST/*")):
                    if addr_elem.text and addr_elem.text.strip():
                        txt = addr_elem.text.strip()
                        if txt.lower() not in ("none", "null", "n/a", "na", "") and txt not in addr_lines:
                            addr_lines.append(txt)
                if addr_lines:
                    company_obj.address_line1 = ", ".join(addr_lines[:2])
                    if len(addr_lines) > 2:
                        company_obj.address_line2 = ", ".join(addr_lines[2:])
                    updated = True

                # Extract state, country, pincode
                state = get_clean_text("STATENAME") or get_clean_text("STATE")
                if state: company_obj.state = state; updated = True
                
                country = get_clean_text("COUNTRYNAME") or get_clean_text("COUNTRY")
                if country: company_obj.country = country; updated = True
                
                pincode = get_clean_text("PINCODE") or get_clean_text("PIN") or get_clean_text("PERSONRESPONSIBLEPINCODE")
                if pincode: company_obj.pincode = pincode; updated = True

                # Extract telephone & mobile
                telephone = get_clean_text("TELEPHONE") or get_clean_text("BASICCOMPANYPHONE") or get_clean_text("TELEPHONENUMBER") or get_clean_text("PERSONRESPONSIBLEPHONE")
                if telephone: company_obj.telephone = telephone; updated = True
                
                mobile = get_clean_text("MOBILE") or get_clean_text("BASICCOMPANYMOBILE") or get_clean_text("MOBILENUMBER") or get_clean_text("COMPANYCONTACTNUMBER") or get_clean_text("PERSONRESPONSIBLEMOBILE")
                if mobile: company_obj.mobile = mobile; updated = True

                # Extract email
                email = get_clean_text("EMAIL") or get_clean_text("BASICCOMPANYEMAIL") or get_clean_text("EMAILID") or get_clean_text("ADMINEMAILID") or get_clean_text("PERSONRESPONSIBLEEMAIL")
                if email: company_obj.email = email; updated = True

                # Extract website
                website = get_clean_text("WEBSITE") or get_clean_text("BASICCOMPANYWEBSITE")
                if website: company_obj.website = website; updated = True

                # Extract GSTIN & PAN
                gstin = get_clean_text("GSTREGISTRATIONNUMBER") or get_clean_text("GSTIN") or get_clean_text("PARTYGSTIN")
                if gstin: company_obj.gstin = gstin[:15]; updated = True

                pan = get_clean_text("INCOMETAXNUMBER") or get_clean_text("PAN") or get_clean_text("COMPANYPAN")
                if pan: company_obj.pan = pan[:10]; updated = True

                # Extract base currency
                base_curr = get_clean_text("CURRENCYSYMBOL") or get_clean_text("BASECURRENCY") or get_clean_text("FORMALNAME")
                if base_curr: company_obj.base_currency = base_curr; updated = True

                # Extract dates using flexible parser
                books_from_str = get_clean_text("BOOKSFROM") or get_clean_text("BOOKSBEGINNINGFROM")
                if books_from_str:
                    bf_date = parse_tally_date(books_from_str)
                    if bf_date:
                        company_obj.books_begin_date = bf_date
                        updated = True
                    
                fy_start_str = get_clean_text("STARTINGFROM") or get_clean_text("FINANCIALYEARFROM")
                if fy_start_str:
                    fy_date = parse_tally_date(fy_start_str)
                    if fy_date:
                        company_obj.financial_year_start = fy_date
                        updated = True

                fy_end_str = get_clean_text("ENDINGAT") or get_clean_text("FINANCIALYEAREND")
                if fy_end_str:
                    fe_date = parse_tally_date(fy_end_str)
                    if fe_date:
                        company_obj.financial_year_end = fe_date
                        updated = True
                elif company_obj.financial_year_start and not company_obj.financial_year_end:
                    try:
                        next_yr = company_obj.financial_year_start.year + 1
                        company_obj.financial_year_end = date(next_yr, company_obj.financial_year_start.month, company_obj.financial_year_start.day) - timedelta(days=1)
                        updated = True
                    except Exception:
                        pass

                # Discover & auto-provision Tally users associated with this company
                user_nodes = company_node.findall(".//USERLIST.LIST") + company_node.findall(".//SECURITYUSERS.LIST") + company_node.findall(".//USER.LIST")
                for u_node in user_nodes:
                    u_name = u_node.findtext("NAME") or u_node.findtext("USERNAME")
                    if u_name:
                        await ensure_tally_user_exists(db, company_obj.company_id, u_name)
                        
                basic_user = company_node.findtext("BASICCOMPANYUSER") or company_node.findtext("SECURITYAUTHOR")
                if basic_user:
                    await ensure_tally_user_exists(db, company_obj.company_id, basic_user)

            if updated or company_obj:
                await db.flush()
                logger.info(
                    f"🏢 [COMPANY PROFILE LOG] Name: '{company_obj.name}' (ID: {company_obj.company_id}, GUID: {company_obj.tally_guid}) | "
                    f"Address: '{company_obj.address_line1 or ''} {company_obj.address_line2 or ''}' | "
                    f"State: '{company_obj.state or ''}' | Pincode: '{company_obj.pincode or ''}' | Country: '{company_obj.country or ''}' | "
                    f"Telephone: '{company_obj.telephone or ''}' | Mobile: '{company_obj.mobile or ''}' | "
                    f"Email: '{company_obj.email or ''}' | Website: '{company_obj.website or ''}' | "
                    f"GSTIN: '{company_obj.gstin or ''}' | Books Begin: '{company_obj.books_begin_date or ''}' | "
                    f"FY Start: '{company_obj.financial_year_start or ''}'"
                )
    except Exception as ex:
        logger.error(f"Error updating company profile from XML: {str(ex)}", exc_info=True)
        
    if not company_id:
        return {"status": "error", "message": "Could not identify or auto-create company from XML payload."}
        
    import_errors = []
    
    # Discovery counts logging for debugging
    v_nodes = [v for v in root.findall(".//VOUCHER") if len(v) > 0]
    g_nodes = root.findall(".//GROUP")
    l_nodes = [l for l in root.findall(".//LEDGER") if (l.get("NAME") or l.findtext("NAME"))]
    si_nodes = root.findall(".//STOCKITEM")
    sg_nodes = root.findall(".//STOCKGROUP")
    sc_nodes = root.findall(".//STOCKCATEGORY")
    gd_nodes = root.findall(".//GODOWN")
    uom_nodes = root.findall(".//UNIT")
    vt_nodes = root.findall(".//VOUCHERTYPE")
    curr_nodes = root.findall(".//CURRENCY")
    ccat_nodes = root.findall(".//COSTCATEGORY")
    cc_nodes = root.findall(".//COSTCENTRE")
    
    element_summary = {
        "groups": len(g_nodes), "ledgers": len(l_nodes), "vouchers": len(v_nodes),
        "stock_items": len(si_nodes), "stock_groups": len(sg_nodes),
        "stock_categories": len(sc_nodes), "godowns": len(gd_nodes),
        "uoms": len(uom_nodes), "voucher_types": len(vt_nodes), "currencies": len(curr_nodes),
        "cost_categories": len(ccat_nodes), "cost_centres": len(cc_nodes)
    }
    non_zero = {k: v for k, v in element_summary.items() if v > 0}
    logger.info(f"📥 [IMPORT START] Payload size: {len(xml_data)} bytes. Found elements: {non_zero or 'None'}")

    imported_groups = 0
    imported_ledgers = 0
    imported_vouchers = 0
    imported_stock_groups = 0
    imported_uoms = 0
    imported_godowns = 0
    imported_stock_categories = 0
    imported_stock_items = 0
    imported_currencies = 0
    imported_voucher_types = 0
    
    await follow_tally_renames(db, company_id, root)

    # 1. Parse Groups (<GROUP>)
    for group_node in root.findall(".//GROUP"):
        name = group_node.get("NAME") or group_node.findtext("NAME")
        if not name:
            continue
        parent_name = group_node.findtext("PARENT")
        
        extra_data = {}
        guid = group_node.findtext("GUID")
        if guid: extra_data['tally_guid'] = guid
        alter_id = (group_node.findtext("ALTERID") or "").strip()  # Tally pads numbers with a leading space
        if alter_id.isdigit(): extra_data['tally_alter_id'] = int(alter_id)
        
        for tag, field in (
            ("ISADDABLE", 'is_addable'), ("ISREVENUE", 'is_revenue'), ("ISDEEMEDPOSITIVE", 'is_deemed_positive'),
            ("AFFECTSGROSSPROFIT", 'affects_gross_profit'), ("ISSUBLEDGER", 'is_subledger'),
            ("ISBILLWISEON", 'is_billwise_on'), ("BASICGROUPISCALCULABLE", 'used_for_calculation'),
        ):
            value = (group_node.findtext(tag) or "").strip()
            if value: extra_data[field] = (value.lower() == 'yes')

        alloc = (group_node.findtext("ADDLALLOCTYPE") or "").strip()
        if alloc: extra_data['method_to_allocate'] = alloc
        
        lang_name = group_node.findtext("LANGUAGENAME.LIST/NAME.LIST/TYPE/NAME")
        if lang_name and lang_name != name:
            extra_data['alias_name'] = lang_name
            
        if tally_parent_name(name) is None:
            continue  # "Primary" is Tally's marker for the top level, not a group
        await get_or_create_group(db, company_id, name, parent_name, extra_data, sync_parent=True)
        imported_groups += 1

    if imported_groups:
        # Earlier imports stored the "Primary" marker as a real group; lift its children to the top level
        marker_res = await db.execute(select(MstGroup).where(
            MstGroup.company_id == company_id,
            func.lower(func.trim(MstGroup.name)) == "primary"
        ))
        for marker in marker_res.scalars().all():
            await db.execute(update(MstGroup).where(MstGroup.parent_group_id == marker.group_id).values(parent_group_id=None))
            has_ledgers = (await db.execute(select(MstLedger.ledger_id).where(MstLedger.group_id == marker.group_id).limit(1))).first()
            if not has_ledgers:
                await db.delete(marker)
        
    await db.flush()
    if imported_groups > 0:
        await db.commit()
        logger.info(f"Committed {imported_groups} groups")

    # 1.1. Parse Stock Groups (<STOCKGROUP>)
    for sg_node in root.findall(".//STOCKGROUP"):
        name = sg_node.get("NAME") or sg_node.findtext("NAME")
        if not name:
            continue
        parent_name = sg_node.findtext("PARENT")
        if tally_parent_name(name) is None:
            continue  # "Primary" is Tally's marker for the top level, not a stock group
        stock_group = await get_or_create_stock_group(db, company_id, name, parent_name, sync_parent=True)
        # Tally lists the name first and its aliases after it
        names = [(n.text or "").strip() for n in sg_node.findall("LANGUAGENAME.LIST/NAME.LIST/NAME")]
        if names:
            from app.models.tally_core import StockGroupAlias
            wanted = [n for n in names[1:] if n]
            current = (await db.execute(select(StockGroupAlias).where(StockGroupAlias.stock_group_id == stock_group.stock_group_id))).scalars().all()
            if sorted(a.alias for a in current) != sorted(wanted):
                for row in current:
                    await db.delete(row)
                for alias in wanted:
                    db.add(StockGroupAlias(stock_group_id=stock_group.stock_group_id, alias=alias))
        imported_stock_groups += 1

    if imported_stock_groups:
        # Earlier imports stored the "Primary" marker as a real stock group: lift what sits under it to the
        # top level and drop it
        marker_res = await db.execute(select(MstStockGroup).where(
            MstStockGroup.company_id == company_id,
            func.lower(func.trim(MstStockGroup.name)) == "primary"
        ))
        for marker in marker_res.scalars().all():
            await db.execute(update(MstStockGroup).where(MstStockGroup.parent_id == marker.stock_group_id).values(parent_id=None))
            await db.execute(update(MstStockItem).where(MstStockItem.stock_group_id == marker.stock_group_id).values(stock_group_id=None))
            await db.delete(marker)
        
    await db.flush()
    if imported_stock_groups > 0:
        await db.commit()
        logger.info(f"Committed {imported_stock_groups} stock groups")

    # 1.2. Parse Units (<UNIT>): simple units first, so a compound unit finds its two parts
    unit_nodes = [n for n in root.findall(".//UNIT") if n.get("NAME") or n.findtext("NAME") or n.findtext("SYMBOL")]

    def unit_is_compound(node) -> bool:
        return (node.findtext("ISSIMPLEUNIT") or "").strip().lower() == "no" or bool((node.findtext("BASEUNITS") or "").strip())

    for unit_node in sorted(unit_nodes, key=unit_is_compound):
        symbol = (unit_node.get("NAME") or unit_node.findtext("NAME") or unit_node.findtext("SYMBOL")).strip()
        dec_places = 0
        dec_str = unit_node.findtext("DECIMALPLACES")
        if dec_str:
            try:
                dec_places = int(dec_str.strip())
            except ValueError:
                pass
        uom = await get_or_create_uom(db, company_id, symbol, symbol, dec_places)
        formal = (unit_node.findtext("ORIGINALNAME") or "").strip()
        if formal:
            uom.original_name = formal
        if dec_str:
            uom.decimal_places = dec_places
        if unit_is_compound(unit_node):
            base_symbol = (unit_node.findtext("BASEUNITS") or "").strip()
            add_symbol = (unit_node.findtext("ADDITIONALUNITS") or "").strip()
            if base_symbol and add_symbol:
                uom.is_simple_unit = False
                uom.base_unit_id = (await get_or_create_uom(db, company_id, base_symbol)).unit_id
                uom.additional_unit_id = (await get_or_create_uom(db, company_id, add_symbol)).unit_id
                try:
                    uom.conversion_factor = Decimal((unit_node.findtext("CONVERSION") or "").strip())
                except Exception:
                    pass
        elif unit_node.findtext("ISSIMPLEUNIT"):
            uom.is_simple_unit = True
        imported_uoms += 1
        
    await db.flush()
    if imported_uoms > 0:
        await db.commit()
        logger.info(f"Committed {imported_uoms} UOMs")
        
    # Parse Currencies (<CURRENCY>)
    # Tally uses symbols (₹, $, €) as the NAME. Map them to ISO 4217 codes.
    TALLY_SYMBOL_TO_ISO = {
        '₹': 'INR', 'â¹': 'INR', 'INR': 'INR', 'Rs': 'INR', 'Rs.': 'INR',
        '$': 'USD', 'US$': 'USD', 'USD': 'USD',
        '€': 'EUR', 'EUR': 'EUR',
        '£': 'GBP', 'GBP': 'GBP',
        '¥': 'JPY', 'JPY': 'JPY', 'CN¥': 'CNY', 'CNY': 'CNY',
        'A$': 'AUD', 'AUD': 'AUD', 'C$': 'CAD', 'CAD': 'CAD',
        'CHF': 'CHF', 'Fr': 'CHF',
        'HK$': 'HKD', 'HKD': 'HKD', 'S$': 'SGD', 'SGD': 'SGD',
        'kr': 'SEK', 'SEK': 'SEK', 'NOK': 'NOK', 'DKK': 'DKK',
        'NZ$': 'NZD', 'NZD': 'NZD', 'R': 'ZAR', 'ZAR': 'ZAR',
        'AED': 'AED', 'SAR': 'SAR', 'QAR': 'QAR', 'OMR': 'OMR',
        'KWD': 'KWD', 'BHD': 'BHD', 'MYR': 'MYR', 'RM': 'MYR',
        'THB': 'THB', '฿': 'THB', 'IDR': 'IDR', 'Rp': 'IDR',
        'PHP': 'PHP', '₱': 'PHP', 'KRW': 'KRW', '₩': 'KRW',
        'BDT': 'BDT', '৳': 'BDT', 'LKR': 'LKR', 'NPR': 'NPR',
        'PKR': 'PKR', 'RUB': 'RUB', '₽': 'RUB', 'TRY': 'TRY', '₺': 'TRY',
        'BRL': 'BRL', 'R$': 'BRL', 'MXN': 'MXN', 'Mex$': 'MXN',
        'PLN': 'PLN', 'zł': 'PLN', 'CZK': 'CZK', 'Kč': 'CZK',
        'HUF': 'HUF', 'Ft': 'HUF', 'RON': 'RON', 'TWD': 'TWD', 'NT$': 'TWD',
        'ILS': 'ILS', '₪': 'ILS', 'EGP': 'EGP', 'NGN': 'NGN', '₦': 'NGN',
        'KES': 'KES', 'GHS': 'GHS', '₵': 'GHS', 'CLP': 'CLP',
        'COP': 'COP', 'ARS': 'ARS', 'PEN': 'PEN', 'VND': 'VND', '₫': 'VND',
        'MMK': 'MMK', 'KHR': 'KHR',
    }

    for curr_node in root.findall(".//CURRENCY"):
        symbol = curr_node.get("NAME") or curr_node.findtext("NAME") or curr_node.findtext("ORIGINALNAME")
        if not symbol:
            continue
            
        formal_name = curr_node.findtext("MAILINGNAME.LIST/MAILINGNAME")
        iso_code_raw = curr_node.findtext("ISOCURRENCYCODE") or curr_node.findtext("EXPANDEDNAME")
        
        # Derive ISO code: prefer explicit XML field, then lookup, then formal_name, then symbol
        code = None
        if iso_code_raw and len(iso_code_raw.strip()) == 3:
            code = iso_code_raw.strip().upper()
        if not code:
            code = TALLY_SYMBOL_TO_ISO.get(symbol.strip())
        if not code and formal_name:
            code = TALLY_SYMBOL_TO_ISO.get(formal_name.strip())
        if not code:
            # Last resort: use formal_name or symbol truncated to 3 chars
            code = (formal_name or symbol)[:3].upper()
        
        logger.info(f"Parsing Currency from XML -> Symbol: {symbol}, FormalName: {formal_name}, ISO: {code}")
        decimals = curr_node.findtext("DECIMALPLACES", "2")
        decimals = int(decimals) if decimals.isdigit() else 2
        
        show_millions = curr_node.findtext("INMILLIONS", "No").lower() == "yes"
        is_suffix = curr_node.findtext("ISSUFFIX", "No").lower() == "yes"
        has_space = curr_node.findtext("HASSPACE", "Yes").lower() == "yes"
        dec_symbol = curr_node.findtext("DECIMALSYMBOL", "")
        dec_print = curr_node.findtext("DECIMALPLACESFORPRINTING", "2")
        dec_print = int(dec_print) if dec_print.isdigit() else 2
        
        # Match by code OR by symbol to avoid duplicates
        existing_curr = (await db.execute(
            select(Currency).where((Currency.code == code) | (Currency.symbol == symbol))
        )).scalars().first()
        if existing_curr:
            logger.info(f"Updating existing currency: {existing_curr.code} -> {code}")
            existing_curr.code = code
            existing_curr.symbol = symbol
            existing_curr.formal_name = formal_name
            existing_curr.decimal_places = decimals
            existing_curr.show_amount_in_millions = show_millions
            existing_curr.suffix_symbol_to_amount = is_suffix
            existing_curr.add_space_between_amount_and_symbol = has_space
            existing_curr.word_representing_amount_after_decimal = dec_symbol
            existing_curr.decimal_places_for_words = dec_print
        else:
            logger.info(f"Creating new currency: {code}")
            new_curr = Currency(
                code=code,
                symbol=symbol,
                formal_name=formal_name,
                decimal_places=decimals,
                show_amount_in_millions=show_millions,
                suffix_symbol_to_amount=is_suffix,
                add_space_between_amount_and_symbol=has_space,
                word_representing_amount_after_decimal=dec_symbol,
                decimal_places_for_words=dec_print,
                is_base_currency=False
            )
            db.add(new_curr)
        
        imported_currencies += 1
        
    await db.flush()
    if imported_currencies > 0:
        await db.commit()
        logger.info(f"Committed {imported_currencies} Currencies")

    # 1.3 Parse Voucher Types (<VOUCHERTYPE>)
    for vt_node in root.findall(".//VOUCHERTYPE"):
        name = vt_node.get("NAME") or vt_node.findtext("NAME")
        if not name:
            continue
            
        parent_name = vt_node.findtext("PARENT")
        numbering_method = vt_node.findtext("NUMBERINGMETHOD") or "Automatic"
        allowed_methods = ['Automatic', 'Automatic (Manual Override)', 'Manual', 'Multi-user Auto', 'None']
        if numbering_method not in allowed_methods:
            numbering_method = 'Automatic'
        prevent_dup = vt_node.findtext("PREVENTDUPLICATES", "No").lower() == "yes"
        use_effective = vt_node.findtext("EFFECTIVEDATE", "No").lower() == "yes"
        allow_zero = vt_node.findtext("USEZEROENTRIES", "No").lower() == "yes"
        is_opt = vt_node.findtext("ISOPTIONAL", "No").lower() == "yes"
        allow_narr = vt_node.findtext("COMMONNARRATION", "Yes").lower() == "yes"
        multi_narr = vt_node.findtext("MULTINARRATION", "No").lower() == "yes"
        print_save = vt_node.findtext("PRINTAFTERSAVE", "No").lower() == "yes"
        default_alloc = vt_node.findtext("ISDEFAULTALLOCENABLED", "No").lower() == "yes"
        track_costs = vt_node.findtext("TRACKADDLCOST", "No").lower() == "yes"
        def_jurisdiction = vt_node.findtext("VCHPRINTJURISDICTION") or None
        def_title = vt_node.findtext("VCHPRINTTITLE") or None

        whatsapp = vt_node.findtext("WHATSAPPAFTERSAVE", "No").lower() == "yes"
        
        # Parse Advanced Numbering
        num_series = vt_node.find("VOUCHERNUMBERSERIES.LIST")
        num_behavior = None
        width = 0
        prefill = False
        unused = False
        prefixes_data = []
        suffixes_data = []
        restarts_data = []
        
        if num_series is not None:
            num_behavior = num_series.findtext("NUMBERINGSUBMETHOD")
            width = int(num_series.findtext("WIDTHOFNUMBER") or "0")
            prefill = num_series.findtext("PREFILLZERO", "No").lower() == "yes"
            unused = num_series.findtext("USEDELETEDVCHNUM", "No").lower() == "yes"
            
            for p in num_series.findall("PREFIXLIST.LIST"):
                try:
                    d_str = p.findtext("DATE")
                    if d_str and len(d_str) >= 8:
                        dt = datetime.strptime(d_str[:8], "%Y%m%d").date()
                        prefixes_data.append({"applicable_from": dt, "particulars": p.findtext("PARTICULARS") or ""})
                except Exception: pass
                
            for s in num_series.findall("SUFFIXLIST.LIST"):
                try:
                    d_str = s.findtext("DATE")
                    if d_str and len(d_str) >= 8:
                        dt = datetime.strptime(d_str[:8], "%Y%m%d").date()
                        suffixes_data.append({"applicable_from": dt, "particulars": s.findtext("PARTICULARS") or ""})
                except Exception: pass
                
            for r in num_series.findall("RESTARTFROMLIST.LIST"):
                try:
                    d_str = r.findtext("DATE")
                    if d_str and len(d_str) >= 8:
                        dt = datetime.strptime(d_str[:8], "%Y%m%d").date()
                        restarts_data.append({"applicable_from": dt, "starting_number": int(r.findtext("PERIODBEGINNIGNUM") or "1"), "periodicity": r.findtext("RESTARTFROM") or ""})
                except Exception: pass
                
        # Parse Classes
        classes_data = []
        for c_node in vt_node.findall("VOUCHERCLASSLIST.LIST"):
            c_name = c_node.findtext("CLASSNAME")
            if not c_name: continue
            alloc = c_node.findtext("BANKALLOCFOR")
            def_ledger = None
            groups = []
            
            # (Groups parsing could go here if needed, but Tally usually exports it differently)
            classes_data.append({
                "class_name": c_name,
                "bank_alloc_for": alloc,
                "default_ledger_name": def_ledger,
                "groups": groups
            })
            
        guid = vt_node.findtext("GUID") or vt_node.get("GUID")
        alter_id_str = vt_node.findtext("ALTERID")
        
        alter_id = None
        if alter_id_str and alter_id_str.isdigit():
            alter_id = int(alter_id_str)

        stmt = select(MstVoucherType).where(MstVoucherType.company_id == company_id, MstVoucherType.name == name)
        existing_vt = (await db.execute(stmt)).scalars().first()
        
        if existing_vt:
            if not force_overwrite and alter_id and existing_vt.tally_alter_id and existing_vt.tally_alter_id >= alter_id:
                continue
                
            existing_vt.parent_type = parent_name
            existing_vt.numbering_method = numbering_method
            existing_vt.prevent_duplicates = prevent_dup
            existing_vt.use_effective_dates = use_effective
            existing_vt.allow_zero_valued_transactions = allow_zero
            existing_vt.is_optional_by_default = is_opt
            existing_vt.allow_narration_in_voucher = allow_narr
            existing_vt.provide_narrations_for_each_ledger = multi_narr
            existing_vt.print_voucher_after_saving = print_save
            existing_vt.enable_default_accounting_allocations = default_alloc
            existing_vt.track_additional_costs_for_purchases = track_costs
            existing_vt.default_jurisdiction = def_jurisdiction
            existing_vt.default_title_to_print = def_title
            
            existing_vt.numbering_behavior = num_behavior
            existing_vt.width_of_numerical_part = width
            existing_vt.prefill_with_zero = prefill
            existing_vt.show_unused_vch_nos = unused
            existing_vt.whatsapp_voucher_after_saving = whatsapp
            
            if guid: existing_vt.tally_guid = guid
            if alter_id: existing_vt.tally_alter_id = alter_id
            
            # Recreate nested
            await db.execute(delete(MstVoucherTypePrefix).where(MstVoucherTypePrefix.voucher_type_id == existing_vt.voucher_type_id))
            await db.execute(delete(MstVoucherTypeSuffix).where(MstVoucherTypeSuffix.voucher_type_id == existing_vt.voucher_type_id))
            await db.execute(delete(MstVoucherTypeRestart).where(MstVoucherTypeRestart.voucher_type_id == existing_vt.voucher_type_id))
            await db.execute(delete(MstVoucherTypeClass).where(MstVoucherTypeClass.voucher_type_id == existing_vt.voucher_type_id))
            
            vt_id = existing_vt.voucher_type_id
            for p in prefixes_data: db.add(MstVoucherTypePrefix(voucher_type_id=vt_id, **p))
            for s in suffixes_data: db.add(MstVoucherTypeSuffix(voucher_type_id=vt_id, **s))
            for r in restarts_data: db.add(MstVoucherTypeRestart(voucher_type_id=vt_id, **r))
            for c in classes_data:
                g_data = c.pop("groups", [])
                nc = MstVoucherTypeClass(voucher_type_id=vt_id, **c)
                db.add(nc)
                await db.flush()
                for g in g_data: db.add(MstVoucherTypeClassGroup(class_id=nc.class_id, **g))
                
        else:
            new_vt = MstVoucherType(
                company_id=company_id,
                name=name,
                parent_type=parent_name,
                numbering_method=numbering_method,
                numbering_behavior=num_behavior,
                prevent_duplicates=prevent_dup,
                use_effective_dates=use_effective,
                allow_zero_valued_transactions=allow_zero,
                is_optional_by_default=is_opt,
                allow_narration_in_voucher=allow_narr,
                provide_narrations_for_each_ledger=multi_narr,
                print_voucher_after_saving=print_save,
                enable_default_accounting_allocations=default_alloc,
                track_additional_costs_for_purchases=track_costs,
                default_jurisdiction=def_jurisdiction,
                default_title_to_print=def_title,
                width_of_numerical_part=width,
                prefill_with_zero=prefill,
                show_unused_vch_nos=unused,
                whatsapp_voucher_after_saving=whatsapp,
                tally_guid=guid,
                tally_alter_id=alter_id,
                is_system_defined=False
            )
            db.add(new_vt)
            await db.flush()
            
            vt_id = new_vt.voucher_type_id
            for p in prefixes_data: db.add(MstVoucherTypePrefix(voucher_type_id=vt_id, **p))
            for s in suffixes_data: db.add(MstVoucherTypeSuffix(voucher_type_id=vt_id, **s))
            for r in restarts_data: db.add(MstVoucherTypeRestart(voucher_type_id=vt_id, **r))
            for c in classes_data:
                g_data = c.pop("groups", [])
                nc = MstVoucherTypeClass(voucher_type_id=vt_id, **c)
                db.add(nc)
                await db.flush()
                for g in g_data: db.add(MstVoucherTypeClassGroup(class_id=nc.class_id, **g))
            
        imported_voucher_types += 1

    await db.flush()
    if imported_voucher_types > 0:
        await db.commit()
        logger.info(f"Committed {imported_voucher_types} Voucher Types")

    # 1.3 Parse Cost Categories (<COSTCATEGORY>)
    for cc_node in root.findall(".//COSTCATEGORY"):
        name = cc_node.get("NAME") or cc_node.findtext("NAME")
        if not name:
            continue
        
        allocate_revenue = cc_node.findtext("ALLOCATEREVENUE", "Yes").lower() == "yes"
        allocate_non_revenue = cc_node.findtext("ALLOCATENONREVENUE", "No").lower() == "yes"
        
        alias = None
        name_list = cc_node.findall(".//NAME.LIST/NAME")
        if len(name_list) > 1 and name_list[1].text:
            alias = name_list[1].text

        existing_cc = (await db.execute(select(MstCostCategory).where(
            MstCostCategory.company_id == company_id, 
            func.lower(MstCostCategory.name) == name.lower()
        ))).scalars().first()
        
        if existing_cc:
            existing_cc.allocate_revenue = allocate_revenue
            existing_cc.allocate_non_revenue = allocate_non_revenue
            existing_cc.alias = alias
        else:
            new_cc = MstCostCategory(
                company_id=company_id,
                name=name,
                alias=alias,
                allocate_revenue=allocate_revenue,
                allocate_non_revenue=allocate_non_revenue,
                is_active=True
            )
            db.add(new_cc)
            
        imported_stock_categories += 1
        
    await db.flush()
    if imported_stock_categories > 0:
        await db.commit()
        logger.info(f"Committed Cost Categories")

    # 1.4 Parse Cost Centres (<COSTCENTRE>)
    for cc_node in root.findall(".//COSTCENTRE"):
        name = cc_node.get("NAME") or cc_node.findtext("NAME")
        if not name:
            continue
            
        category_name = cc_node.findtext("CATEGORY") or "Primary Cost Category"
        parent_name = cc_node.findtext("PARENT")
        
        alias = None
        name_list = cc_node.findall(".//NAME.LIST/NAME")
        if len(name_list) > 1 and name_list[1].text:
            alias = name_list[1].text

        # Resolve category ID
        cat = (await db.execute(select(MstCostCategory).where(
            MstCostCategory.company_id == company_id, 
            func.lower(MstCostCategory.name) == category_name.lower()
        ))).scalars().first()
        if not cat:
            continue
            
        # Resolve parent ID
        parent_id = None
        if parent_name:
            parent = (await db.execute(select(MstCostCentre).where(
                MstCostCentre.company_id == company_id, 
                func.lower(MstCostCentre.name) == parent_name.lower()
            ))).scalars().first()
            if parent:
                parent_id = parent.cost_centre_id

        # By Tally's own GUID first, so a cost centre renamed in Tally is followed instead of duplicated
        cc_guid = (cc_node.findtext("GUID") or "").strip() or None
        existing_cc = (await db.execute(select(MstCostCentre).where(
            MstCostCentre.company_id == company_id, MstCostCentre.tally_guid == cc_guid))).scalars().first() if cc_guid else None
        if existing_cc is None:
            existing_cc = (await db.execute(select(MstCostCentre).where(
                MstCostCentre.company_id == company_id, 
                func.lower(MstCostCentre.name) == name.lower()
            ))).scalars().first()
        elif existing_cc.name != name:
            await _rename_employee_lines(db, company_id, existing_cc.name, name)
            existing_cc.name = name
        
        # An employee is a cost centre marked for payroll
        for_payroll_text = (cc_node.findtext("FORPAYROLL") or "").strip().lower()
        if existing_cc:
            existing_cc.category_id = cat.category_id
            existing_cc.parent_id = parent_id
            existing_cc.alias = alias
            if for_payroll_text:
                existing_cc.for_payroll = for_payroll_text == "yes"
        else:
            new_cc = MstCostCentre(
                company_id=company_id,
                name=name,
                alias=alias,
                category_id=cat.category_id,
                parent_id=parent_id,
                for_payroll=for_payroll_text == "yes",
                is_active=True
            )
            db.add(new_cc)
        await _read_payroll_cost_centre(db, company_id, existing_cc or new_cc, cc_node, cc_guid)
            
    await db.flush()
    await db.commit()
    logger.info(f"Committed Cost Centres")

    # 1.4b Attendance types (<ATTENDANCETYPE NAME="...">; the same tag inside a voucher is a plain value)
    for at_node in root.findall(".//ATTENDANCETYPE"):
        at_name = (at_node.get("NAME") or "").strip()
        if not at_name:
            continue
        kind = (at_node.findtext("ATTENDANCEPRODUCTIONTYPE") or "").strip() or "Attendance / Leave with Pay"
        at_guid = (at_node.findtext("GUID") or "").strip() or None
        existing_at = (await db.execute(select(MstAttendanceType).where(
            MstAttendanceType.company_id == company_id, MstAttendanceType.tally_guid == at_guid))).scalars().first() if at_guid else None
        if existing_at is None:
            existing_at = (await db.execute(select(MstAttendanceType).where(
                MstAttendanceType.company_id == company_id, MstAttendanceType.name == at_name))).scalars().first()
        elif existing_at.name != at_name:
            # Renamed in Tally: the attendance lines that name it follow
            await db.execute(update(TrnAttendance).where(
                TrnAttendance.attendancetype_name == existing_at.name,
                TrnAttendance.voucher_id.in_(select(TrnVoucher.voucher_id).where(TrnVoucher.company_id == company_id))).values(attendancetype_name=at_name))
            existing_at.name = at_name[:100]
        if existing_at is None:
            existing_at = MstAttendanceType(company_id=company_id, name=at_name[:100])
            db.add(existing_at)
        existing_at.type_of_attendance = kind[:50]
        if at_node.find("ATTENDANCEPERIOD") is not None or at_node.find("BASEUNITS") is not None:
            unit = _trim_marker(at_node.findtext("BASEUNITS"))
            existing_at.period = (at_node.findtext("ATTENDANCEPERIOD") or "").strip()[:20] or None
            existing_at.unit_name = unit[:50] if unit and unit.lower() != "not applicable" else None
        if at_guid:
            existing_at.tally_guid = at_guid
            existing_at.tally_master_id = int(at_node.findtext("MASTERID").strip()) if (at_node.findtext("MASTERID") or "").strip().isdigit() else existing_at.tally_master_id
    await db.flush()

    # 1.5. Parse Godowns (<GODOWN>)
    for gd_node in root.findall(".//GODOWN"):
        name = gd_node.get("NAME") or gd_node.findtext("NAME")
        if not name:
            continue
        address = gd_node.findtext("ADDRESS")
        await get_or_create_godown(db, company_id, name, address)
        imported_godowns += 1
        
    await db.flush()
    if imported_godowns > 0:
        await db.commit()
        logger.info(f"Committed {imported_godowns} godowns")

    # 1.4. Parse Stock Categories (<STOCKCATEGORY>)
    for sc_node in root.findall(".//STOCKCATEGORY"):
        name = sc_node.get("NAME") or sc_node.findtext("NAME")
        if not name:
            continue
        parent_name = sc_node.findtext("PARENT")
        if tally_parent_name(name) is None:
            continue
        await get_or_create_stock_category(db, company_id, name, parent_name)
        imported_stock_categories += 1
        
    await db.flush()
    if imported_stock_categories > 0:
        await db.commit()
        logger.info(f"Committed {imported_stock_categories} stock categories")

    # 1.5. Parse Stock Items (<STOCKITEM>)
    for si_node in root.findall(".//STOCKITEM"):
        name = si_node.get("NAME") or si_node.findtext("NAME")
        if not name:
            continue
        try:
            parent_name = si_node.findtext("PARENT")
            # "Not Applicable" is how Tally says "no category"; it is a marker, not a category
            has_category_tag = si_node.find("CATEGORY") is not None
            category_name = (si_node.findtext("CATEGORY") or "").strip()
            if category_name.lower() == "not applicable":
                category_name = ""
            uom_symbol = si_node.findtext("BASEUNITS")
            
            op_bal_str = si_node.findtext("OPENINGBALANCE")
            op_val_str = si_node.findtext("OPENINGVALUE")
            
            # Parse GST HSN Code and GST rate
            hsn_code = si_node.findtext("INFGSTHSNCODE")
            if hsn_code:
                hsn_code = hsn_code.strip()[:10]
                
            gst_rate = Decimal("0.00")
            gst_rate_str = si_node.findtext("INFGSTIGSTRATE")
            if gst_rate_str:
                try:
                    gst_rate = Decimal(gst_rate_str.strip())
                except (ValueError, ArithmeticError):
                    pass
            
            op_qty = Decimal("0.000")
            if op_bal_str:
                try:
                    clean_qty = op_bal_str.strip().split()[0].replace(",", "").strip()
                    op_qty = Decimal(clean_qty)
                except (IndexError, ValueError, ArithmeticError):
                    pass
                    
            op_val = Decimal("0.00")
            if op_val_str:
                try:
                    op_val = abs(Decimal(op_val_str.strip().replace(",", "")))
                except (ValueError, ArithmeticError):
                    pass
                    
            op_rate = Decimal("0.00")
            if op_qty > 0:
                op_rate = op_val / op_qty
                
            alter_id_str = si_node.findtext("ALTERID")
            alter_id = None
            if alter_id_str:
                try:
                    alter_id = int(alter_id_str.strip())
                except ValueError:
                    pass

            # New Schema v7.0 fields
            costing_method = si_node.findtext("COSTINGMETHOD")
            valuation_method = si_node.findtext("VALUATIONMETHOD")
            gst_type_of_supply = si_node.findtext("GSTTYPEOFSUPPLY") or "Goods"
            # None when the export did not carry the flag: an absent tag says nothing, and must not turn
            # batch tracking off on an item that has it
            def flag(tag: str):
                text = si_node.findtext(tag)
                return None if text is None else text.strip().lower() in ("yes", "true", "1")
            is_batch_wise = flag("ISBATCHWISEON")
            is_perishable = flag("ISPERISHABLEON")
            ignore_negative = flag("IGNORENEGATIVESTOCK")

            stock_group = None
            if tally_parent_name(parent_name):  # an item directly under "Primary" has no stock group
                stock_group = await get_or_create_stock_group(db, company_id, parent_name)
                
            stock_category = None
            if category_name:
                stock_category = await get_or_create_stock_category(db, company_id, category_name)
                
            uom = None
            if uom_symbol:
                uom = await get_or_create_uom(db, company_id, uom_symbol)
            else:
                uom = await get_or_create_uom(db, company_id, "PCS")
                
            stmt = select(MstStockItem).where(MstStockItem.company_id == company_id, MstStockItem.name == name)
            res = await db.execute(stmt)
            item = res.scalars().first()
            
            if item:
                if not force_overwrite and alter_id and item.tally_alter_id and item.tally_alter_id >= alter_id:
                    continue
                if stock_group:
                    item.stock_group_id = stock_group.stock_group_id
                if stock_category:
                    item.stock_category_id = stock_category.stock_category_id
                elif has_category_tag:
                    item.stock_category_id = None
                item.unit_id = uom.unit_id
                item.opening_qty = op_qty
                item.opening_rate = op_rate
                if hsn_code:
                    item.hsn_code = hsn_code
                if gst_rate > 0:
                    item.gst_rate_percent = gst_rate
                if costing_method:
                    item.costing_method = costing_method
                if valuation_method:
                    item.valuation_method = valuation_method
                if gst_type_of_supply:
                    item.gst_type_of_supply = gst_type_of_supply
                if is_batch_wise is not None:
                    item.is_batch_wise = is_batch_wise
                if is_perishable is not None:
                    item.is_perishable = is_perishable
                if ignore_negative is not None:
                    item.ignore_negative_stock = ignore_negative
                if alter_id:
                    item.tally_alter_id = alter_id
                await db.flush()
            else:
                item = MstStockItem(
                    company_id=company_id,
                    name=name,
                    stock_group_id=stock_group.stock_group_id if stock_group else None,
                    stock_category_id=stock_category.stock_category_id if stock_category else None,
                    unit_id=uom.unit_id,
                    opening_qty=op_qty,
                    opening_rate=op_rate,
                    closing_qty=op_qty,
                    closing_rate=op_rate,
                    closing_value=op_val,
                    hsn_code=hsn_code,
                    gst_rate_percent=gst_rate,
                    costing_method=costing_method,
                    valuation_method=valuation_method,
                    gst_type_of_supply=gst_type_of_supply,
                    is_batch_wise=bool(is_batch_wise),
                    is_perishable=bool(is_perishable),
                    ignore_negative_stock=bool(ignore_negative),
                    is_active=True,
                    tally_alter_id=alter_id
                )
                db.add(item)
                await db.flush()

            # What a later push from here sends back whole, and would otherwise wipe in Tally:
            # the description, the alternate unit and the aliases
            description = (si_node.findtext("DESCRIPTION") or "").strip()
            if description:
                item.description = description

            alt_symbol = tally_parent_name(si_node.findtext("ADDITIONALUNITS"))
            if alt_symbol and alt_symbol.lower() != "not applicable":
                alt_uom = await get_or_create_uom(db, company_id, alt_symbol)
                item.alt_unit_id = alt_uom.unit_id
                # Tally: CONVERSION alternate units = DENOMINATOR base units; kept as that pair, so 1:3 stays exact
                try:
                    conversion = Decimal((si_node.findtext("CONVERSION") or "").strip())
                    denominator = Decimal((si_node.findtext("DENOMINATOR") or "1").strip() or "1")
                    if conversion > 0 and denominator > 0:
                        item.alt_unit_conversion = conversion
                        item.alt_unit_denominator = denominator
                except Exception:
                    pass
            elif si_node.find("ADDITIONALUNITS") is not None:
                item.alt_unit_id = None
                item.alt_unit_conversion = None
                item.alt_unit_denominator = None

            alias_names = [(n.text or "").strip() for n in si_node.findall("LANGUAGENAME.LIST/NAME.LIST/NAME")]
            if alias_names:
                from app.models.tally_core import StockItemAlias
                wanted = [n for n in alias_names[1:] if n]
                current = (await db.execute(select(StockItemAlias).where(StockItemAlias.stock_item_id == item.stock_item_id))).scalars().all()
                if sorted(a.alias for a in current) != sorted(wanted):
                    for row in current:
                        await db.delete(row)
                    for alias in wanted:
                        db.add(StockItemAlias(stock_item_id=item.stock_item_id, alias=alias, alias_type="name"))
            # Opening stock by godown and batch. A push sends this list back whole, so it has to hold what
            # Tally has, batch names included, or an edit here would rename the batches there.
            batch_nodes = [b for b in si_node.findall("BATCHALLOCATIONS.LIST") if (b.findtext("OPENINGBALANCE") or "").strip()]
            if batch_nodes or si_node.find("BATCHALLOCATIONS.LIST") is not None:
                from app.models.tally_core import StockItemOpeningBalance

                def leading_number(text: Optional[str]) -> Decimal:
                    m = re.match(r"\s*-?\s*([\d,]+(?:\.\d+)?)", text or "")
                    return Decimal(m.group(1).replace(",", "")) if m else Decimal("0")

                for row in (await db.execute(select(StockItemOpeningBalance).where(StockItemOpeningBalance.stock_item_id == item.stock_item_id))).scalars().all():
                    await db.delete(row)
                for b in batch_nodes:
                    qty = leading_number(b.findtext("OPENINGBALANCE"))
                    if qty <= 0:
                        continue
                    godown_name = tally_parent_name(b.findtext("GODOWNNAME")) or "Main Location"
                    godown = await get_or_create_godown(db, company_id, godown_name)
                    rate = leading_number(b.findtext("OPENINGRATE"))
                    amount = leading_number(b.findtext("OPENINGVALUE")) or (qty * rate)
                    db.add(StockItemOpeningBalance(
                        stock_item_id=item.stock_item_id, godown_id=godown.godown_id,
                        batch_name=(b.findtext("BATCHNAME") or "").strip() or "Primary Batch",
                        quantity=qty, rate=rate, amount=amount))
            await db.flush()

            # Parse HSN Details for Stock Item (<HSNDETAILS.LIST>)
            for hsn_node in si_node.findall(".//HSNDETAILS.LIST"):
                h_code = hsn_node.findtext("HSNCODE") or hsn_code
                if not h_code:
                    continue
                h_desc = hsn_node.findtext("HSNDESCRIPTION")
                h_app_from = parse_tally_date(hsn_node.findtext("APPLICABLEFROM"))
                h_taxability = hsn_node.findtext("TAXABILITY") or "Taxable"
                
                # Check if already exists for this stock item
                h_stmt = select(MstHsnDetail).where(
                    MstHsnDetail.stock_item_id == item.stock_item_id,
                    MstHsnDetail.hsn_code == h_code
                )
                h_res = await db.execute(h_stmt)
                h_obj = h_res.scalars().first()
                if not h_obj:
                    h_obj = MstHsnDetail(
                        company_id=company_id,
                        stock_item_id=item.stock_item_id,
                        hsn_code=h_code,
                        hsn_description=h_desc,
                        source_type="Stock Item",
                        taxability=h_taxability,
                        igst_rate=gst_rate,
                        cgst_rate=gst_rate / Decimal("2.0") if gst_rate else Decimal("0.00"),
                        sgst_rate=gst_rate / Decimal("2.0") if gst_rate else Decimal("0.00"),
                        applicable_from=h_app_from
                    )
                    db.add(h_obj)
                    await db.flush()
                
            imported_stock_items += 1
            # Batch commit every 50 stock items
            if imported_stock_items % 50 == 0:
                await db.commit()
                logger.info(f"Committed {imported_stock_items} stock items so far...")
        except Exception as si_err:
            logger.error(f"❌ [STOCK ITEM ERROR] Failed importing stock item '{name}': {str(si_err)}", exc_info=True)
            import_errors.append(f"StockItem '{name}': {str(si_err)}")
        
    await db.flush()
    if imported_stock_items > 0:
        # Earlier imports stored Tally's "Not Applicable" marker as a stock category; drop it once unused
        marker_res = await db.execute(select(MstStockCategory).where(
            MstStockCategory.company_id == company_id,
            func.lower(func.trim(MstStockCategory.name)) == "not applicable"
        ))
        for marker in marker_res.scalars().all():
            in_use = (await db.execute(select(MstStockItem.stock_item_id).where(
                MstStockItem.stock_category_id == marker.stock_category_id).limit(1))).first()
            if not in_use:
                await db.delete(marker)
        await db.commit()
        logger.info(f"Committed {imported_stock_items} stock items (total)")
    
    # 2. Parse Ledgers (<LEDGER>)
    for ledger_node in root.findall(".//LEDGER"):
        name = ledger_node.get("NAME") or ledger_node.findtext("NAME")
        if not name:
            continue
        try:
            parent_name = ledger_node.findtext("PARENT")
            if not parent_name:
                if name == "Profit & Loss A/c":
                    parent_name = "Primary"
                elif name == "Cash":
                    parent_name = "Cash-in-Hand"
                else:
                    parent_name = "Suspense Accounts"
                    
            group = await get_or_create_group(db, company_id, parent_name)
            
            # Check if ledger exists
            stmt = select(MstLedger).where(MstLedger.company_id == company_id, MstLedger.name == name)
            res = await db.execute(stmt)
            ledger = res.scalars().first()
            
            guid = ledger_node.findtext("GUID") or ledger_node.get("GUID")
            if not guid:
                guid = ledger_node.findtext("REMOTEID") or ledger_node.get("REMOTEID")
            if not guid:
                guid = f"GEN-{uuid.uuid4().hex[:12]}"
                
            # Parse nested GSTIN
            gstin = (
                ledger_node.findtext(".//LEDGSTREGDETAILS.LIST/GSTIN") or 
                ledger_node.findtext("GSTIN") or 
                ledger_node.findtext("PARTYGSTIN")
            )
            if gstin: gstin = gstin.strip()

            # Parse GST Registration Type
            gst_reg_type = (
                ledger_node.findtext(".//LEDGSTREGDETAILS.LIST/GSTREGISTRATIONTYPE") or 
                ledger_node.findtext("GSTREGISTRATIONTYPE")
            )
            if gst_reg_type: gst_reg_type = gst_reg_type.strip()
            if not gst_reg_type:
                gst_reg_type = "Regular" if gstin else "Unregistered/Consumer"

            # Parse PAN
            pan = (
                ledger_node.findtext("INCOMETAXNUMBER") or 
                ledger_node.findtext("PANNUMBER") or 
                ledger_node.findtext("PAN")
            )
            if not pan and gstin and len(gstin) >= 12:
                pan = gstin[2:12].upper()
            if pan: pan = pan.strip().upper()

            # Parse Aadhaar UDF
            aadhar = ledger_node.findtext("LWLEDADHARNOSTORE") or ledger_node.findtext(".//LWLEDADHARNOSTORE")
            if aadhar: aadhar = aadhar.strip()

            # Parse State
            state = (
                ledger_node.findtext(".//LEDMAILINGDETAILS.LIST/STATE") or 
                ledger_node.findtext("PRIORSTATENAME") or 
                ledger_node.findtext("STATENAME") or 
                ledger_node.findtext("STATE")
            )
            if state: state = state.strip()

            # Parse Country
            country = (
                ledger_node.findtext(".//LEDMAILINGDETAILS.LIST/COUNTRY") or 
                ledger_node.findtext("COUNTRYOFRESIDENCE") or 
                ledger_node.findtext("COUNTRYNAME") or 
                ledger_node.findtext("COUNTRY") or "India"
            )
            if country: country = country.strip()

            # Parse Pincode
            pincode = (
                ledger_node.findtext(".//LEDMAILINGDETAILS.LIST/PINCODE") or 
                ledger_node.findtext("PINCODE") or 
                ledger_node.findtext("PIN")
            )
            if pincode: pincode = pincode.strip()

            # Parse Address
            addr_nodes = (
                ledger_node.findall(".//LEDMAILINGDETAILS.LIST/ADDRESS.LIST/ADDRESS") or 
                ledger_node.findall(".//ADDRESS.LIST/ADDRESS") or 
                ledger_node.findall("ADDRESS")
            )
            addr_lines = [a.text.strip() for a in addr_nodes if a.text and a.text.strip()]
            address_str = ", ".join(addr_lines) if addr_lines else None

            # Parse Contact Person
            contact_person = (
                ledger_node.findtext("LEDGERCONTACT") or 
                ledger_node.findtext("CONTACTPERSON") or 
                ledger_node.findtext("CONTACT")
            )
            if contact_person: contact_person = contact_person.strip()

            # Parse Phone & Mobile
            phone = (
                ledger_node.findtext("LEDGERPHONE") or 
                ledger_node.findtext("PHONE") or 
                ledger_node.findtext("TELEPHONE") or
                ledger_node.findtext(".//CONTACTDETAILS.LIST/PHONENUMBER")
            )
            if phone: phone = phone.strip()

            mobile = (
                ledger_node.findtext("LEDGERMOBILE") or 
                ledger_node.findtext("MOBILE") or 
                ledger_node.findtext("MOBILENUMBER")
            )
            if mobile: mobile = mobile.strip()

            # Parse Email & Email CC
            email = ledger_node.findtext("EMAIL") or ledger_node.findtext("BASICCOMPANYEMAIL")
            if email: email = email.strip()

            email_cc = ledger_node.findtext("EMAILCC")
            if email_cc: email_cc = email_cc.strip()

            # Parse Website, Description, Fax
            website = ledger_node.findtext("WEBSITE")
            if website: website = website.strip()

            description = ledger_node.findtext("DESCRIPTION") or ledger_node.findtext("NARRATION")
            if description: description = description.strip()

            fax = ledger_node.findtext("LEDGERFAX") or ledger_node.findtext("FAX")
            if fax: fax = fax.strip()

            # Parse Alias Name (e.g. secondary name in LANGUAGENAME.LIST or MAILINGNAME.LIST)
            alias_name = None
            lang_names = ledger_node.findall(".//LANGUAGENAME.LIST/NAME.LIST/NAME") + ledger_node.findall(".//MAILINGNAME.LIST/MAILINGNAME")
            if len(lang_names) > 1 and lang_names[1].text:
                alias_name = lang_names[1].text.strip()

            # Parse Credit Limit
            credit_limit_str = ledger_node.findtext("CREDITLIMIT")
            credit_limit_val = None
            if credit_limit_str:
                try:
                    credit_limit_val = abs(Decimal(credit_limit_str.strip()))
                except Exception:
                    credit_limit_val = None

            # Parse Credit Period Days
            credit_days_str = ledger_node.findtext("BILLCREDITPERIOD") or ledger_node.findtext("CREDITDAYS")
            credit_days_val = None
            if credit_days_str:
                digits = re.findall(r'\d+', credit_days_str)
                if digits:
                    credit_days_val = int(digits[0])

            # Parse Is Billwise On
            is_billwise_str = ledger_node.findtext("ISBILLWISEON")
            is_billwise_val = True
            if is_billwise_str:
                is_billwise_val = is_billwise_str.strip().lower() in ("yes", "true", "1")
            
            # Opening balance
            op_bal_str = ledger_node.findtext("OPENINGBALANCE") or "0"
            try:
                op_bal_val = Decimal(op_bal_str)
            except Exception:
                op_bal_val = Decimal("0.00")
                
            bal_type = "Dr"
            if op_bal_val < 0:
                op_bal_val = abs(op_bal_val)
                bal_type = "Dr"
            elif op_bal_val > 0:
                bal_type = "Cr"
                
            alter_id_str = ledger_node.findtext("ALTERID") or "0"
            alter_id = int(alter_id_str)

            # Parse Closing Balance & Tax Classification from Schema v7.0
            closing_bal_str = (
                ledger_node.findtext("CLOSINGBALANCE") or 
                ledger_node.findtext(".//LEDGERCLOSINGVALUES.LIST/CLOSINGBALANCE")
            )
            closing_bal_val = None
            if closing_bal_str:
                try:
                    closing_bal_val = Decimal(closing_bal_str.strip())
                except Exception:
                    closing_bal_val = None
                    
            ledger_type = ledger_node.findtext("LEDGERTYPE")
            tax_class_name = ledger_node.findtext("TAXCLASSIFICATIONNAME")

            if not ledger:
                ledger = MstLedger(
                    company_id=company_id,
                    name=name,
                    group_id=group.group_id,
                    opening_balance=op_bal_val,
                    opening_balance_type=bal_type,
                    gstin=gstin,
                    gst_registration_type=gst_reg_type,
                    pan_number=pan,
                    aadhar_number=aadhar,
                    address=address_str,
                    state=state,
                    country=country,
                    pincode=pincode,
                    contact_person=contact_person,
                    phone=phone,
                    mobile=mobile,
                    email=email,
                    credit_limit=credit_limit_val,
                    credit_period_days=credit_days_val,
                    is_billwise_on=is_billwise_val,
                    alias_name=alias_name,
                    website=website,
                    description=description,
                    fax=fax,
                    email_cc=email_cc,
                    ledger_type=ledger_type,
                    closing_balance=closing_bal_val,
                    tax_classification_name=tax_class_name,
                    tally_guid=guid,
                    tally_alter_id=alter_id
                )
                db.add(ledger)
            else:
                if not force_overwrite and ledger.tally_alter_id and ledger.tally_alter_id >= alter_id:
                    continue
                ledger.opening_balance = op_bal_val
                ledger.opening_balance_type = bal_type
                ledger.gstin = gstin
                if gst_reg_type: ledger.gst_registration_type = gst_reg_type
                if pan: ledger.pan_number = pan
                if aadhar: ledger.aadhar_number = aadhar
                if address_str: ledger.address = address_str
                if state: ledger.state = state
                if country: ledger.country = country
                if pincode: ledger.pincode = pincode
                if contact_person: ledger.contact_person = contact_person
                if phone: ledger.phone = phone
                if mobile: ledger.mobile = mobile
                if email: ledger.email = email
                if email_cc: ledger.email_cc = email_cc
                if website: ledger.website = website
                if description: ledger.description = description
                if fax: ledger.fax = fax
                if alias_name: ledger.alias_name = alias_name
                if credit_limit_val is not None: ledger.credit_limit = credit_limit_val
                if credit_days_val is not None: ledger.credit_period_days = credit_days_val
                if ledger_type: ledger.ledger_type = ledger_type
                if closing_bal_val is not None: ledger.closing_balance = closing_bal_val
                if tax_class_name: ledger.tax_classification_name = tax_class_name
                ledger.is_billwise_on = is_billwise_val
                ledger.tally_guid = guid
                ledger.tally_alter_id = alter_id
                
            await db.flush()
            
            # Parse Multi-GST Registrations (<LEDGSTREGDETAILS.LIST>)
            for gst_node in ledger_node.findall(".//LEDGSTREGDETAILS.LIST"):
                g_gstin = gst_node.findtext("GSTIN")
                if not g_gstin or not str(g_gstin).strip():
                    continue
                g_gstin = str(g_gstin).strip().upper()
                g_app_from = parse_tally_date(gst_node.findtext("APPLICABLEFROM"))
                g_reg_type = gst_node.findtext("GSTREGISTRATIONTYPE") or "Regular"
                g_state = gst_node.findtext("STATENAME") or state
                g_pos = gst_node.findtext("PLACEOFSUPPLY") or g_state
                
                reg_stmt = select(MstLedgerGstRegistration).where(
                    MstLedgerGstRegistration.ledger_id == ledger.ledger_id,
                    MstLedgerGstRegistration.gstin == g_gstin
                )
                reg_res = await db.execute(reg_stmt)
                reg_obj = reg_res.scalars().first()
                if not reg_obj:
                    reg_obj = MstLedgerGstRegistration(
                        ledger_id=ledger.ledger_id,
                        gstin=g_gstin,
                        state_name=g_state,
                        place_of_supply=g_pos,
                        registration_type=g_reg_type,
                        applicable_from=g_app_from,
                        is_default=(g_gstin == gstin)
                    )
                    db.add(reg_obj)
                    await db.flush()

            # Parse HSN Details for Service Ledgers (<HSNDETAILS.LIST>)
            for hsn_node in ledger_node.findall(".//HSNDETAILS.LIST"):
                h_code = hsn_node.findtext("HSNCODE")
                if not h_code:
                    continue
                h_desc = hsn_node.findtext("HSNDESCRIPTION")
                h_app_from = parse_tally_date(hsn_node.findtext("APPLICABLEFROM"))
                h_taxability = hsn_node.findtext("TAXABILITY") or "Taxable"
                
                h_stmt = select(MstHsnDetail).where(
                    MstHsnDetail.ledger_id == ledger.ledger_id,
                    MstHsnDetail.hsn_code == h_code
                )
                h_res = await db.execute(h_stmt)
                h_obj = h_res.scalars().first()
                if not h_obj:
                    h_obj = MstHsnDetail(
                        company_id=company_id,
                        ledger_id=ledger.ledger_id,
                        hsn_code=h_code,
                        hsn_description=h_desc,
                        source_type="Ledger",
                        taxability=h_taxability,
                        applicable_from=h_app_from
                    )
                    db.add(h_obj)
                    await db.flush()

            # Parse MSME Registration Details (<MSMEREGISTRATIONDETAILS.LIST>)
            for msme_node in ledger_node.findall(".//MSMEREGISTRATIONDETAILS.LIST"):
                ent_type = msme_node.findtext("ENTERPRISETYPE")
                udyam_no = msme_node.findtext("UDYAMREGNO") or msme_node.findtext("MSMEREGNUMBER") or ledger_node.findtext("MSMEREGNUMBER")
                if not udyam_no and not ent_type:
                    continue
                app_from = parse_tally_date(msme_node.findtext("APPLICABLEFROM"))
                
                m_stmt = select(MstLedgerMsmeDetail).where(
                    MstLedgerMsmeDetail.ledger_id == ledger.ledger_id,
                    MstLedgerMsmeDetail.udyam_reg_no == udyam_no
                ) if udyam_no else select(MstLedgerMsmeDetail).where(MstLedgerMsmeDetail.ledger_id == ledger.ledger_id)
                m_res = await db.execute(m_stmt)
                m_obj = m_res.scalars().first()
                if not m_obj:
                    m_obj = MstLedgerMsmeDetail(
                        ledger_id=ledger.ledger_id,
                        enterprise_type=ent_type or "Micro",
                        udyam_reg_no=udyam_no,
                        applicable_from=app_from
                    )
                    db.add(m_obj)
                    await db.flush()

            # Parse Multi-Mailing / Branch Addresses (<LEDMAILINGDETAILS.LIST> & <LEDMULTIADDRESSLIST.LIST>)
            addr_nodes = ledger_node.findall(".//LEDMAILINGDETAILS.LIST") + ledger_node.findall(".//LEDMULTIADDRESSLIST.LIST")
            for m_node in addr_nodes:
                addr_name = m_node.findtext("ADDRESSNAME") or m_node.findtext("APPLICABLENAME") or "Primary"
                m_name = m_node.findtext("MAILINGNAME") or ledger.name
                
                m_addr_nodes = m_node.findall(".//ADDRESS.LIST/ADDRESS")
                m_addr_lines = [a.text.strip() for a in m_addr_nodes if a.text and a.text.strip()]
                m_address_str = ", ".join(m_addr_lines) if m_addr_lines else (m_node.findtext("ADDRESS") or None)
                
                st = m_node.findtext("STATE") or m_node.findtext("STATENAME")
                co = m_node.findtext("COUNTRY") or "India"
                pin = m_node.findtext("PINCODE")
                
                a_stmt = select(MstLedgerAddress).where(
                    MstLedgerAddress.ledger_id == ledger.ledger_id,
                    MstLedgerAddress.address_name == addr_name
                )
                a_res = await db.execute(a_stmt)
                a_obj = a_res.scalars().first()
                if not a_obj:
                    a_obj = MstLedgerAddress(
                        ledger_id=ledger.ledger_id,
                        address_name=addr_name,
                        mailing_name=m_name,
                        address=m_address_str,
                        state_name=st,
                        country_name=co,
                        pincode=pin,
                        is_default=(addr_name == "Primary")
                    )
                    db.add(a_obj)
                    await db.flush()

            # Parse Lower TDS Deduction Certificates (<LOWERDEDUCTION.LIST>)
            for ld_node in ledger_node.findall(".//LOWERDEDUCTION.LIST"):
                sec_no = ld_node.findtext("SECTIONNUMBER") or ld_node.findtext("TDSCATEGORY") or "194C"
                cert_no = ld_node.findtext("CERTIFICATENO")
                if not cert_no:
                    continue
                rate_str = ld_node.findtext("RATEOFDEDUCTION") or "0"
                try:
                    r_ded = Decimal(rate_str.replace("%", "").strip())
                except Exception:
                    r_ded = Decimal("0.00")
                ld_app_from = parse_tally_date(ld_node.findtext("APPLICABLEFROM"))
                ld_app_to = parse_tally_date(ld_node.findtext("APPLICABLETO"))
                limit_str = ld_node.findtext("LIMIT") or ld_node.findtext("THRESHOLDLIMIT")
                t_limit = None
                if limit_str:
                    try:
                        t_limit = Decimal(limit_str.replace(",", "").strip())
                    except Exception:
                        t_limit = None
                
                ld_stmt = select(MstLedgerTdsLowerDeduction).where(
                    MstLedgerTdsLowerDeduction.ledger_id == ledger.ledger_id,
                    MstLedgerTdsLowerDeduction.certificate_no == cert_no
                )
                ld_res = await db.execute(ld_stmt)
                ld_obj = ld_res.scalars().first()
                if not ld_obj:
                    ld_obj = MstLedgerTdsLowerDeduction(
                        ledger_id=ledger.ledger_id,
                        section_number=sec_no,
                        certificate_no=cert_no,
                        rate_of_deduction=r_ded,
                        applicable_from=ld_app_from,
                        applicable_to=ld_app_to,
                        threshold_limit=t_limit
                    )
                    db.add(ld_obj)
                    await db.flush()
                
            imported_ledgers += 1
            # Batch commit every 50 ledgers
            if imported_ledgers % 50 == 0:
                await db.commit()
                logger.info(f"Committed {imported_ledgers} ledgers so far...")
        except Exception as l_err:
            logger.error(f"❌ [LEDGER ERROR] Failed importing ledger '{name}': {str(l_err)}", exc_info=True)
            import_errors.append(f"Ledger '{name}': {str(l_err)}")
        
    # A ledger with a pay type is a pay head (Basic Salary, PF deduction, ...)
    for ledger_node in root.findall(".//LEDGER"):
        pay_head_name = (ledger_node.get("NAME") or ledger_node.findtext("NAME") or "").strip()
        pay_type = (ledger_node.findtext("PAYTYPE") or "").strip()
        if not pay_head_name or ledger_node.find("PAYTYPE") is None:
            continue
        existing_ph = (await db.execute(select(MstPayHead).where(
            MstPayHead.company_id == company_id, MstPayHead.name == pay_head_name))).scalars().first()
        if not pay_type or pay_type.lower() == "not applicable":
            if existing_ph:
                await db.delete(existing_ph)
        else:
            if not existing_ph:
                existing_ph = MstPayHead(company_id=company_id, name=pay_head_name[:100])
                db.add(existing_ph)
            existing_ph.pay_head_type = pay_type[:50]
            pay_ledger = (await db.execute(select(MstLedger).where(
                MstLedger.company_id == company_id, func.lower(MstLedger.name) == pay_head_name.lower()))).scalars().first()
            if pay_ledger:
                existing_ph.ledger_id, existing_ph.under_group_id = pay_ledger.ledger_id, pay_ledger.group_id
            if ledger_node.find("CALCULATIONTYPE") is not None:
                existing_ph.calculation_type = (ledger_node.findtext("CALCULATIONTYPE") or "").strip()[:50] or None
            if ledger_node.find("PAYSLIPNAME") is not None:
                existing_ph.payslip_name = (ledger_node.findtext("PAYSLIPNAME") or "").strip()[:100] or None

    await db.flush()
    await store_master_identities(db, company_id, root)
    if imported_ledgers > 0:
        await db.commit()
        logger.info(f"Committed {imported_ledgers} ledgers (total)")
    
    # 3. Parse Vouchers (<VOUCHER>)
    # Filter out empty/metadata VOUCHER tags (like <VOUCHER>14</VOUCHER> in CMPINFO) by ensuring they have child elements
    voucher_nodes = [v for v in root.findall(".//VOUCHER") if len(v) > 0]

    # Session-level caches to eliminate N+1 select queries across thousands of vouchers
    vtypes_by_name: Dict[str, MstVoucherType] = {}
    vt_res = await db.execute(select(MstVoucherType).where(MstVoucherType.company_id == company_id))
    for vt in vt_res.scalars().all():
        vtypes_by_name[vt.name.strip().lower()] = vt

    ledgers_by_name: Dict[str, MstLedger] = {}
    items_by_name: Dict[str, MstStockItem] = {}
    uoms_by_symbol: Dict[str, MstUom] = {}

    # Pre-extract GUIDs for batch lookup
    node_guid_map: Dict[int, str] = {}
    for idx, v_node in enumerate(voucher_nodes):
        guid = v_node.findtext("GUID") or v_node.get("GUID")
        if not guid:
            guid = v_node.findtext("REMOTEID") or v_node.get("REMOTEID")
        if not guid:
            guid = f"GEN-{uuid.uuid4().hex[:12]}"
        node_guid_map[idx] = guid

    all_guids = list(node_guid_map.values())

    # Pre-fetch deleted vouchers audit in bulk (1 query instead of N queries)
    deleted_guids = set()
    if all_guids:
        for i in range(0, len(all_guids), 1000):
            batch = all_guids[i:i+1000]
            del_check_stmt = select(DeletedRecordAudit.tally_guid).where(
                DeletedRecordAudit.company_id == company_id,
                DeletedRecordAudit.entity_type == "Voucher",
                DeletedRecordAudit.tally_guid.in_(batch)
            )
            del_res = await db.execute(del_check_stmt)
            deleted_guids.update(del_res.scalars().all())

    # Pre-fetch existing vouchers by GUID in bulk (1 query instead of N queries)
    vouchers_by_guid: Dict[str, TrnVoucher] = {}
    if all_guids:
        for i in range(0, len(all_guids), 1000):
            batch = all_guids[i:i+1000]
            stmt = select(TrnVoucher).where(
                TrnVoucher.company_id == company_id,
                TrnVoucher.tally_guid.in_(batch)
            )
            res = await db.execute(stmt)
            for v in res.scalars().all():
                vouchers_by_guid[v.tally_guid] = v

    for idx, v_node in enumerate(voucher_nodes):
        guid = node_guid_map[idx]
            
        v_num = v_node.findtext("VOUCHERNUMBER") or guid[:10]
        vtype_name = v_node.findtext("VOUCHERTYPENAME") or v_node.get("VOUCHERTYPENAME") or "Journal"

        try:
            # Auto-provision user if voucher contains entered_by / altered_by
            entered_by = v_node.findtext("ENTEREDBY") or v_node.findtext("ALTEREDBY") or v_node.findtext("CREATEDBY")
            if entered_by:
                await ensure_tally_user_exists(db, company_id, entered_by)
                
            alter_id_str = v_node.findtext("ALTERID") or "0"
            alter_id = int(alter_id_str)
            
            v_date_str = v_node.findtext("DATE") # e.g. "20260710" or "2026-07-10"
            try:
                if len(v_date_str) == 8:
                    v_date = datetime.strptime(v_date_str, "%Y%m%d").date()
                else:
                    v_date = datetime.strptime(v_date_str[:10], "%Y-%m-%d").date()
            except Exception:
                v_date = date.today()
                
            narration = v_node.findtext("NARRATION")
            is_cancelled_val = (v_node.findtext("ISCANCELLED") or "No").strip().lower() == "yes"
            is_optional_val = (v_node.findtext("ISOPTIONAL") or "No").strip().lower() == "yes"
            is_post_dated_val = (v_node.findtext("ISPOSTDATED") or "No").strip().lower() == "yes"
            
            # Schema v7.0 Voucher Fields
            eff_date_str = v_node.findtext("EFFECTIVEDATE")
            effective_date = parse_tally_date(eff_date_str) if eff_date_str else v_date
            
            ref_date_str = v_node.findtext("REFERENCEDATE")
            reference_date = parse_tally_date(ref_date_str) if ref_date_str else None
            
            place_of_supply = v_node.findtext("PLACEOFSUPPLY") or v_node.findtext("STATENAME")
            buyer_name = v_node.findtext("BASICBUYERNAME") or v_node.findtext("PARTYNAME")
            consignee_name = v_node.findtext("CONSIGNEEMAILINGNAME") or v_node.findtext("CONSIGNEENAME")
            
            # Buyer Address
            b_addr_nodes = v_node.findall(".//BASICBUYERADDRESS.LIST/BASICBUYERADDRESS") or v_node.findall(".//ADDRESS.LIST/ADDRESS")
            b_addr_lines = [a.text.strip() for a in b_addr_nodes if a.text and a.text.strip()]
            buyer_address = ", ".join(b_addr_lines) if b_addr_lines else None
            
            # Consignee Address
            c_addr_nodes = v_node.findall(".//CONSIGNEEADDRESS.LIST/CONSIGNEEADDRESS")
            c_addr_lines = [a.text.strip() for a in c_addr_nodes if a.text and a.text.strip()]
            consignee_address = ", ".join(c_addr_lines) if c_addr_lines else None
            
            order_reference = v_node.findtext("BASICORDERREF") or v_node.findtext("ORDERREFERENCE")
            despatch_doc_no = v_node.findtext("BASICSHIPDELIVERYNOTE") or v_node.findtext("DESPATCHDOCNO")

            # e-Invoice Fields (Schema v7.0 GSTeInvoiceDetail)
            irn = v_node.findtext("IRN")
            irn_ack_no = v_node.findtext("IRNACKNO")
            irn_ack_date = parse_tally_datetime(v_node.findtext("IRNACKDATE"))
            irn_qr_code = v_node.findtext("IRNQRCODE")
            irn_cancelled = (v_node.findtext("IRNCANCELLED") or "No").strip().lower() == "yes"
            irn_cancel_date = parse_tally_datetime(v_node.findtext("IRNCANCELDATE"))
            irn_cancel_reason = v_node.findtext("IRNCANCELREASON")
            irn_source = v_node.findtext("IRNIRPSOURCE")
            
            # Get or create MstVoucherType with in-memory lookup
            vtype_key = vtype_name.strip().lower()
            vtype = vtypes_by_name.get(vtype_key)
            if not vtype:
                vt_stmt = select(MstVoucherType).where(MstVoucherType.company_id == company_id, MstVoucherType.name == vtype_name)
                vt_res = await db.execute(vt_stmt)
                vtype = vt_res.scalars().first()
                if not vtype:
                    vtype = MstVoucherType(
                        company_id=company_id,
                        name=vtype_name,
                        is_system_defined=False,
                        next_number=1
                    )
                    db.add(vtype)
                    await db.flush()
                vtypes_by_name[vtype_key] = vtype
                
            # Zombie-Resurrection Guard: Skip re-importing vouchers that were explicitly deleted in MyTally
            if guid in deleted_guids:
                logger.info(f"🛡️ [ZOMBIE GUARD] Skipping inbound import of deleted voucher (GUID: {guid}, #{v_num})")
                continue

            # Check if voucher already exists by GUID (in-memory lookup)
            voucher = vouchers_by_guid.get(guid)

            # A voucher this app sent whose reply never arrived: the app does not know its GUID yet, but Tally
            # hands back the identifier the app sent it under, so it is recognised instead of imported twice
            remote_alt = (v_node.findtext("REMOTEALTGUID") or "").strip()
            if not voucher and remote_alt:
                sent = (await db.execute(select(TrnVoucher).where(
                    TrnVoucher.company_id == company_id, TrnVoucher.tally_remote_id == remote_alt))).scalars().first()
                if sent is not None and (sent.tally_guid is None or sent.tally_guid == guid):
                    logger.info(f"🔗 [VOUCHER MATCH] Voucher #{sent.voucher_id} recognised by the identifier it was sent under; GUID {guid}")
                    sent.tally_guid = guid
                    voucher = vouchers_by_guid[guid] = sent
            
            # Fallback dedup lookup: by (company_id, voucher_type_id, voucher_number, voucher_date) if GUID is generated/absent
            if not voucher and guid.startswith("GEN-"):
                fallback_stmt = select(TrnVoucher).where(
                    TrnVoucher.company_id == company_id,
                    TrnVoucher.voucher_type_id == vtype.voucher_type_id,
                    TrnVoucher.voucher_number == v_num,
                    TrnVoucher.voucher_date == v_date
                )
                fb_res = await db.execute(fallback_stmt)
                voucher = fb_res.scalars().first()
                if voucher:
                    logger.info(f"🔗 [VOUCHER MATCH] Matched existing voucher #{v_num} by (type, number, date). Linking GUID: {guid}")
                    voucher.tally_guid = guid
                    vouchers_by_guid[guid] = voucher
            
            # Auto-provision user if voucher contains entered_by / altered_by
            v_user_id = user_id
            entered_by = v_node.findtext("ENTEREDBY") or v_node.findtext("ALTEREDBY") or v_node.findtext("CREATEDBY")
            if entered_by:
                tally_user = await ensure_tally_user_exists(db, company_id, entered_by)
                if tally_user:
                    v_user_id = tally_user.user_id
                if tally_user:
                    v_user_id = tally_user.user_id

            if voucher:
                # If present and alter_id is same or lower, skip unless force_overwrite is True
                if not force_overwrite and voucher.tally_alter_id and voucher.tally_alter_id >= alter_id:
                    logger.debug(f"⏭️ [VOUCHER SKIP] Voucher #{v_num} (ID: {voucher.voucher_id}) alter_id {voucher.tally_alter_id} >= {alter_id}")
                    continue
                
                logger.info(f"🔄 [VOUCHER ALTER] Updating voucher #{v_num} (ID: {voucher.voucher_id}, alter_id: {voucher.tally_alter_id} -> {alter_id})")
                vid = voucher.voucher_id
                tally_db = settings.TALLY_DATABASE_NAME

                # 1. Reverse stock movements on MstStockItem BEFORE deleting existing entries
                old_inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == vid)
                old_inv_res = await db.execute(old_inv_stmt)
                old_inv_list = old_inv_res.scalars().all()
                for old_inv in old_inv_list:
                    item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == old_inv.stock_item_id))
                    stock_item = item_res.scalars().first()
                    if stock_item:
                        qty_val = old_inv.quantity or Decimal("0.000")
                        amt_val = old_inv.amount or Decimal("0.00")
                        if old_inv.is_inward:
                            stock_item.closing_qty = (stock_item.closing_qty or Decimal("0.000")) - qty_val
                            stock_item.closing_value = (stock_item.closing_value or Decimal("0.00")) - amt_val
                        else:
                            stock_item.closing_qty = (stock_item.closing_qty or Decimal("0.000")) + qty_val
                            avg_cost = Decimal("0.00")
                            if (stock_item.closing_qty or Decimal("0.000")) > 0:
                                avg_cost = (stock_item.closing_value or Decimal("0.00")) / stock_item.closing_qty
                            cons_val = qty_val * avg_cost
                            stock_item.closing_value = (stock_item.closing_value or Decimal("0.00")) + cons_val

                # 2. Delete ALL existing child records in strict FK dependency order
                await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_accounting_allocations WHERE stock_entry_id IN (SELECT stock_entry_id FROM `{tally_db}`.stock_entries WHERE voucher_id = {vid})"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.stock_entries WHERE voucher_id = {vid}"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_entry_cost_centres WHERE entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.bank_allocations WHERE entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.bill_allocations WHERE voucher_entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid}"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.eway_bills WHERE voucher_id = {vid}"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.trn_attendance WHERE voucher_id = {vid}"))
                await db.execute(text(f"DELETE FROM `{tally_db}`.trn_payhead WHERE voucher_id = {vid}"))
                await db.flush()
            else:
                logger.info(f"➕ [VOUCHER NEW] Creating voucher #{v_num} ({vtype_name}, Date: {v_date}, Alter: {alter_id})")
                voucher = TrnVoucher(
                    company_id=company_id,
                    voucher_type_id=vtype.voucher_type_id,
                    voucher_number=v_num,
                    voucher_date=v_date,
                    effective_date=effective_date,
                    reference_date=reference_date,
                    place_of_supply=place_of_supply,
                    buyer_name=buyer_name,
                    buyer_address=buyer_address,
                    consignee_name=consignee_name,
                    consignee_address=consignee_address,
                    order_reference=order_reference,
                    despatch_doc_no=despatch_doc_no,
                    irn=irn,
                    irn_ack_no=irn_ack_no,
                    irn_ack_date=irn_ack_date,
                    irn_qr_code=irn_qr_code,
                    irn_cancelled=irn_cancelled,
                    irn_cancel_date=irn_cancel_date,
                    irn_cancel_reason=irn_cancel_reason,
                    irn_source=irn_source,
                    tally_guid=guid,
                    tally_alter_id=alter_id,
                    is_cancelled=is_cancelled_val,
                    is_optional=is_optional_val,
                    is_post_dated=is_post_dated_val,
                    created_by=v_user_id
                )
                db.add(voucher)
                await db.flush()
                vouchers_by_guid[guid] = voucher
                
            voucher.voucher_number = v_num
            # Keep the app's counter ahead of Tally's, so a provisional number given offline is a likely one
            if v_num.isdigit() and (vtype.numbering_method or "Automatic") == "Automatic" and int(v_num) >= (vtype.next_number or 1):
                vtype.next_number = int(v_num) + 1
            # The number is Tally's own, and its master id is what addresses the voucher in a later push
            voucher.number_is_provisional = False
            master_id_str = (v_node.findtext("MASTERID") or "").strip()
            if master_id_str.isdigit():
                voucher.tally_master_id = int(master_id_str)
            voucher.tally_date = v_date
            voucher.voucher_date = v_date
            voucher.effective_date = effective_date
            if reference_date: voucher.reference_date = reference_date
            if place_of_supply: voucher.place_of_supply = place_of_supply
            if buyer_name: voucher.buyer_name = buyer_name
            if buyer_address: voucher.buyer_address = buyer_address
            if consignee_name: voucher.consignee_name = consignee_name
            if consignee_address: voucher.consignee_address = consignee_address
            if order_reference: voucher.order_reference = order_reference
            if despatch_doc_no: voucher.despatch_doc_no = despatch_doc_no
            if irn: voucher.irn = irn
            if irn_ack_no: voucher.irn_ack_no = irn_ack_no
            if irn_ack_date: voucher.irn_ack_date = irn_ack_date
            if irn_qr_code: voucher.irn_qr_code = irn_qr_code
            voucher.irn_cancelled = irn_cancelled
            if irn_cancel_date: voucher.irn_cancel_date = irn_cancel_date
            if irn_cancel_reason: voucher.irn_cancel_reason = irn_cancel_reason
            if irn_source: voucher.irn_source = irn_source
            voucher.narration = narration
            voucher.tally_alter_id = alter_id
            voucher.is_cancelled = is_cancelled_val
            voucher.is_optional = is_optional_val
            voucher.is_post_dated = is_post_dated_val
            
            total_amt = Decimal("0.00")
            
            # Add entries
            # Tally lists entries in <ALLLEDGERENTRIES.LIST> or <LEDGERENTRIES.LIST>
            entries_nodes = v_node.findall(".//ALLLEDGERENTRIES.LIST")
            if not entries_nodes:
                entries_nodes = v_node.findall(".//LEDGERENTRIES.LIST")
            for ent_node in entries_nodes:
                led_name = ent_node.findtext("LEDGERNAME")
                if not led_name:
                    continue
                    
                # Get ledger (with in-memory cache to prevent N+1 queries)
                led_key = led_name.strip().lower()
                ledger = ledgers_by_name.get(led_key)
                if not ledger:
                    l_stmt = select(MstLedger).where(MstLedger.company_id == company_id, func.lower(MstLedger.name) == led_key)
                    l_res = await db.execute(l_stmt)
                    ledger = l_res.scalars().first()
                    if not ledger:
                        # Auto create missing ledger under standard suspense/current group
                        grp = await get_or_create_group(db, company_id, "Suspense Accounts")
                        ledger = MstLedger(
                            company_id=company_id,
                            name=led_name,
                            group_id=grp.group_id,
                            opening_balance=0.00
                        )
                        db.add(ledger)
                        await db.flush()
                    ledgers_by_name[led_key] = ledger
                    
                amt_str = ent_node.findtext("AMOUNT") or "0"
                try:
                    amt_val = Decimal(amt_str)
                except Exception:
                    amt_val = Decimal("0.00")
                    
                # Tally sign mapping: Negative -> Debit, Positive -> Credit
                dr_amt = Decimal("0.00")
                cr_amt = Decimal("0.00")
                
                if amt_val < 0:
                    dr_amt = abs(amt_val)
                    total_amt += dr_amt
                else:
                    cr_amt = amt_val
                    
                nature_of_tx = (
                    ent_node.findtext("NATUREOFTRANSACTION") or 
                    ent_node.findtext("VATNATUREOFTRANSACTION")
                )
                entry = TrnAccounting(
                    voucher_id=voucher.voucher_id,
                    ledger_id=ledger.ledger_id,
                    debit_amount=dr_amt,
                    credit_amount=cr_amt,
                    nature_of_transaction=nature_of_tx
                )
                db.add(entry)
                await db.flush()
                
                # Parse cost category / cost centre allocations
                cc_name = ent_node.findtext(".//COSTCENTREALLOCATIONS.LIST/NAME") or ent_node.findtext(".//COSTCENTRE")
                if cc_name:
                    cc_stmt = select(CostCenter).where(CostCenter.company_id == company_id, CostCenter.name == cc_name)
                    cc_res = await db.execute(cc_stmt)
                    cc_obj = cc_res.scalars().first()
                    if not cc_obj:
                        cc_obj = CostCenter(company_id=company_id, name=cc_name)
                        db.add(cc_obj)
                        await db.flush()
                    entry.cost_center_id = cc_obj.cost_center_id

                # Parse bank allocations inside <BANKALLOCATIONS.LIST>
                for bank_node in ent_node.findall(".//BANKALLOCATIONS.LIST"):
                    inst_date_str = bank_node.findtext("INSTRUMENTDATE")
                    inst_date = None
                    if inst_date_str:
                        try:
                            inst_date = datetime.strptime(inst_date_str, "%Y%m%d").date()
                        except ValueError:
                            pass
                    
                    b_amt_str = bank_node.findtext("AMOUNT") or "0"
                    try:
                        b_amt = abs(Decimal(b_amt_str))
                    except Exception:
                        b_amt = Decimal("0.00")
                    
                    is_conn = bank_node.findtext("ISCONNECTEDPAYMENT") or "No"
                    bank_alloc = TrnBankAllocation(
                        entry_id=entry.entry_id,
                        instrument_date=inst_date,
                        transaction_type=bank_node.findtext("TRANSACTIONTYPE") or "Others",
                        payment_favouring=bank_node.findtext("PAYMENTFAVOURING") or bank_node.findtext("BANKPARTYNAME"),
                        instrument_number=bank_node.findtext("INSTRUMENTNUMBER"),
                        amount=b_amt,
                        transfer_mode=bank_node.findtext("TRANSFERMODE"),
                        virtual_payment_address=bank_node.findtext("VIRTUALPAYMENTADDRESS"),
                        cheque_cross_comment=bank_node.findtext("CHEQUECROSSCOMMENT"),
                        bank_name=bank_node.findtext("BANKNAME"),
                        account_number=bank_node.findtext("ACCOUNTNUMBER"),
                        ifs_code=bank_node.findtext("IFSCODE"),
                        is_connected_payment=is_conn.strip().lower() == "yes"
                    )
                    db.add(bank_alloc)
                
                # Parse bills inside <BILLALLOCATIONS.LIST>
                for bill_node in ent_node.findall(".//BILLALLOCATIONS.LIST"):
                    b_ref = bill_node.findtext("NAME")
                    b_amt_str = bill_node.findtext("AMOUNT") or "0"
                    try:
                        b_amt = abs(Decimal(b_amt_str))
                    except Exception:
                        b_amt = Decimal("0.00")
                    
                    b_type = bill_node.findtext("BILLTYPE")
                    if b_type not in ["Against Ref", "Advance", "On Account", "New Ref"]:
                        b_type = "Against Ref" if amt_val > 0 else "New Ref"
                    
                    bill_id = None
                    
                    # 'On Account' allocations are not tracked as distinct, open bills unless a reference name is provided
                    if b_type != "On Account" or b_ref:
                        if not b_ref:
                            b_ref = v_num or f"Ref-{voucher.voucher_id}"
                        
                        b_ref = b_ref[:50]  # Truncate to avoid String(50) overflow
                        
                        # Get or create TrnBill
                        b_stmt = select(TrnBill).where(TrnBill.company_id == company_id, TrnBill.bill_reference == b_ref)
                        b_res = await db.execute(b_stmt)
                        bill = b_res.scalars().first()
                        if not bill:
                            bill = TrnBill(
                                company_id=company_id,
                                party_ledger_id=ledger.ledger_id,
                                voucher_id=voucher.voucher_id,
                                bill_reference=b_ref,
                                bill_date=v_date,
                                bill_amount=b_amt,
                                status="Open"
                            )
                            db.add(bill)
                            await db.flush()
                        bill_id = bill.bill_id
                    
                    # Create allocation
                    alloc = BillAllocation(
                        voucher_entry_id=entry.entry_id,
                        bill_id=bill_id,
                        allocation_type=b_type,
                        amount=b_amt
                    )
                    db.add(alloc)
                    await db.flush()

                # Parse Multi-Cost-Centre allocations (<COSTCENTREALLOCATIONS.LIST>)
                for cc_alloc_node in ent_node.findall(".//COSTCENTREALLOCATIONS.LIST"):
                    cc_alloc_name = cc_alloc_node.findtext("NAME")
                    if not cc_alloc_name:
                        continue
                    cc_alloc_amt_str = cc_alloc_node.findtext("AMOUNT") or "0"
                    try:
                        cc_alloc_amt = abs(Decimal(cc_alloc_amt_str.replace(",", "").strip()))
                    except Exception:
                        cc_alloc_amt = Decimal("0.00")
                    
                    cc_sub_stmt = select(MstCostCentre).where(MstCostCentre.company_id == company_id, MstCostCentre.name == cc_alloc_name)
                    cc_sub_res = await db.execute(cc_sub_stmt)
                    cc_sub_obj = cc_sub_res.scalars().first()
                    if not cc_sub_obj:
                        cat_stmt = select(MstCostCategory).where(MstCostCategory.company_id == company_id)
                        cat_res = await db.execute(cat_stmt)
                        cat_obj = cat_res.scalars().first()
                        if not cat_obj:
                            cat_obj = MstCostCategory(company_id=company_id, name="Primary Cost Category")
                            db.add(cat_obj)
                            await db.flush()
                        cc_sub_obj = MstCostCentre(company_id=company_id, category_id=cat_obj.category_id, name=cc_alloc_name)
                        db.add(cc_sub_obj)
                        await db.flush()
                        
                    cc_alloc = TrnCostCentreAllocation(
                        entry_id=entry.entry_id,
                        cost_centre_id=cc_sub_obj.cost_centre_id,
                        amount=cc_alloc_amt
                    )
                    db.add(cc_alloc)
                    await db.flush()
                    
            # A Stock Journal keeps what it produces in INVENTORYENTRIESIN.LIST and what it consumes in
            # INVENTORYENTRIESOUT.LIST; Tally may repeat those lines in ALLINVENTORYENTRIES.LIST, so when the
            # two lists are there, they alone are read. Everything else uses ALLINVENTORYENTRIES.LIST.
            journal_nodes = ([(n, "destination") for n in v_node.findall("INVENTORYENTRIESIN.LIST")]
                             + [(n, "source") for n in v_node.findall("INVENTORYENTRIESOUT.LIST")])
            journal_nodes = [(n, flow) for n, flow in journal_nodes if n.findtext("STOCKITEMNAME")]
            for inv_node, flow_type in (journal_nodes or [(n, None) for n in v_node.findall(".//ALLINVENTORYENTRIES.LIST")]):
                item_name = inv_node.findtext("STOCKITEMNAME")
                if not item_name:
                    continue
                    
                # Extract UOM
                uom_name = "PCS"
                rate_str = inv_node.findtext("RATE") or ""
                if "/" in rate_str:
                    parts = rate_str.split("/")
                    if len(parts) > 1:
                        uom_name = parts[1].strip()
                else:
                    qty_str = inv_node.findtext("BILLEDQTY") or inv_node.findtext("ACTUALQTY") or ""
                    qty_parts = qty_str.strip().split()
                    if len(qty_parts) > 1:
                        uom_name = qty_parts[1].strip()
                        
                # Parse GST rate from RATEDETAILS.LIST
                gst_rate = Decimal("0.00")
                for rate_dt in inv_node.findall(".//RATEDETAILS.LIST"):
                    duty_head = rate_dt.findtext("GSTRATEDUTYHEAD")
                    if duty_head in ["IGST", "CGST", "SGST"]:
                        r_val = rate_dt.findtext("GSTRATE")
                        if r_val:
                            try:
                                gst_rate = Decimal(r_val.strip())
                                if duty_head in ["CGST", "SGST"]:
                                    gst_rate *= 2
                            except Exception:
                                pass
                                
                # Parse rate and qty
                rate_val = Decimal("0.00")
                if rate_str:
                    clean_rate = rate_str.split("/")[0].replace(",", "").strip()
                    try:
                        rate_val = Decimal(clean_rate)
                    except Exception:
                        pass
                        
                qty_val = Decimal("0.00")
                qty_str = inv_node.findtext("BILLEDQTY") or inv_node.findtext("ACTUALQTY") or ""
                if qty_str:
                    clean_qty = qty_str.strip().split()[0].replace(",", "").strip()
                    try:
                        qty_val = Decimal(clean_qty)
                    except Exception:
                        pass
                        
                amt_str = inv_node.findtext("AMOUNT") or "0"
                try:
                    inv_amt = abs(Decimal(amt_str))
                except Exception:
                    inv_amt = Decimal("0.00")
                    
                # Get or create MstUom (with in-memory cache)
                uom_key = uom_name.strip().lower()
                uom = uoms_by_symbol.get(uom_key)
                if not uom:
                    uom_stmt = select(MstUom).where(MstUom.company_id == company_id, func.lower(MstUom.symbol) == uom_key)
                    uom_res = await db.execute(uom_stmt)
                    uom = uom_res.scalars().first()
                    if not uom:
                        uom = MstUom(
                            company_id=company_id,
                            name=uom_name,
                            symbol=uom_name,
                            decimal_places=0
                        )
                        db.add(uom)
                        await db.flush()
                    uoms_by_symbol[uom_key] = uom
                    
                # Determine stock group candidate and party context
                cand_group_raw = inv_node.findtext("GSTSTOCKGROUPSOURCE") or inv_node.findtext("HSNSTOCKGROUPSOURCE")
                party_context = v_node.findtext("PARTYLEDGERNAME") or v_node.findtext("PARTYNAME") or buyer_name or ""

                # Get or create MstStockItem (with in-memory cache)
                is_deemed_pos = inv_node.findtext("ISDEEMEDPOSITIVE") or "No"
                is_inward = is_deemed_pos.strip().lower() == "yes"
                if flow_type:
                    is_inward = flow_type == "destination"
                physical_count = is_physical_stock(vtype)
                counted_qty = None
                if physical_count:
                    flow_type = None

                item_key = item_name.strip().lower()
                item = items_by_name.get(item_key)
                if not item:
                    item_stmt = select(MstStockItem).where(MstStockItem.company_id == company_id, func.lower(MstStockItem.name) == item_key)
                    item_res = await db.execute(item_stmt)
                    item = item_res.scalars().first()

                if not item:
                    stock_group = await resolve_stock_group_dynamically(
                        db=db,
                        company_id=company_id,
                        candidate_group=cand_group_raw,
                        item_name=item_name,
                        party_name=party_context
                    )
                    init_qty = qty_val if is_inward else -qty_val
                    init_val = inv_amt if is_inward else -inv_amt
                    item = MstStockItem(
                        company_id=company_id,
                        name=item_name,
                        stock_group_id=stock_group.stock_group_id,
                        unit_id=uom.unit_id,
                        gst_rate_percent=gst_rate,
                        opening_qty=Decimal("0.000"),
                        opening_rate=Decimal("0.00"),
                        closing_qty=init_qty,
                        closing_rate=rate_val,
                        closing_value=init_val,
                        is_active=True
                    )
                    db.add(item)
                    await db.flush()
                    items_by_name[item_key] = item
                else:
                    items_by_name[item_key] = item
                    # An item Tally keeps at the top level stays there: giving it a guessed group here
                    # would send that group back to Tally as its parent on the next push
                    if physical_count:
                        # A stock count: kept as the movement that brings the books to the counted figure
                        counted_qty = qty_val
                        difference = counted_qty - (item.closing_qty or Decimal("0.000"))
                        is_inward, qty_val, inv_amt = difference >= 0, abs(difference), Decimal("0.00")
                    if is_inward:
                        item.closing_qty = (item.closing_qty or Decimal("0.000")) + qty_val
                        item.closing_value = (item.closing_value or Decimal("0.00")) + inv_amt
                        if item.closing_qty > 0:
                            item.closing_rate = item.closing_value / item.closing_qty
                        elif rate_val > 0:
                            item.closing_rate = rate_val
                    else:
                        qty_before = (item.closing_qty or Decimal("0.000"))
                        val_before = (item.closing_value or Decimal("0.00"))
                        avg_cost = Decimal("0.00")
                        if qty_before > 0:
                            avg_cost = val_before / qty_before
                        elif item.closing_rate and item.closing_rate > 0:
                            avg_cost = item.closing_rate
                        cons_val = qty_val * avg_cost
                        item.closing_qty = qty_before - qty_val
                        item.closing_value = max(Decimal("0.00"), val_before - cons_val) if item.closing_qty > 0 else Decimal("0.00")
                        if item.closing_qty > 0 and avg_cost > 0:
                            item.closing_rate = avg_cost

                    if gst_rate > 0:
                        item.gst_rate_percent = gst_rate
                    await db.flush()

                # Parse discount if present
                disc_str = inv_node.findtext("DISCOUNT") or "0"
                try:
                    disc_val = Decimal(disc_str.replace("%", "").strip())
                except Exception:
                    disc_val = Decimal("0.00")

                # Parse actual vs billed quantity
                act_qty_str = inv_node.findtext("ACTUALQTY") or ""
                act_qty_val = qty_val
                if act_qty_str:
                    try:
                        clean_act_qty = act_qty_str.strip().split()[0].replace(",", "").strip()
                        act_qty_val = Decimal(clean_act_qty)
                    except Exception:
                        pass

                item_desc = inv_node.findtext("ITEMDESCRIPTION") or inv_node.findtext("NARRATION") or inv_node.findtext("DESCRIPTION")

                # Insert TrnInventory
                stock_entry = TrnInventory(
                    voucher_id=voucher.voucher_id,
                    stock_item_id=item.stock_item_id,
                    quantity=qty_val,
                    billed_qty=qty_val,
                    actual_quantity=counted_qty if counted_qty is not None else act_qty_val,
                    rate=rate_val,
                    amount=inv_amt,
                    discount_percent=disc_val,
                    item_description=item_desc,
                    is_inward=is_inward,
                    is_deemed_positive=is_inward,
                    flow_type=flow_type
                )
                db.add(stock_entry)
                await db.flush()

            # Attendance lines: an employee, an attendance type and how much of it
            for att_node in v_node.findall("ATTENDANCEENTRIES.LIST"):
                att_employee = (att_node.findtext("NAME") or "").strip()
                if not att_employee:
                    continue
                db.add(TrnAttendance(voucher_id=voucher.voucher_id, guid=guid[:64], employee_name=att_employee,
                                     attendancetype_name=(att_node.findtext("ATTENDANCETYPE") or "").strip(),
                                     time_value=_decimal_or_none(att_node.findtext("ATTDTYPETIMEVALUE")),
                                     type_value=_decimal_or_none(att_node.findtext("ATTDTYPEVALUE"))))

            # Payroll lines: per cost category, per employee, the pay heads and their amounts. Tally uses the
            # same lists for the cost centre allocations of ordinary vouchers, so only Payroll vouchers count.
            for cat_node in (v_node.findall("CATEGORYENTRY.LIST") if is_payroll(vtype) else []):
                pay_category = (cat_node.findtext("CATEGORY") or "").strip()
                for emp_node in cat_node.findall("EMPLOYEEENTRIES.LIST"):
                    pay_employee = (emp_node.findtext("EMPLOYEENAME") or "").strip()
                    for head_node in emp_node.findall("PAYHEADALLOCATIONS.LIST"):
                        head_name = (head_node.findtext("PAYHEADNAME") or "").strip()
                        if pay_employee and head_name:
                            db.add(TrnPayHead(voucher_id=voucher.voucher_id, guid=guid[:64], category=pay_category, employee_name=pay_employee,
                                              payhead_name=head_name, amount=_decimal_or_none(head_node.findtext("AMOUNT"))))

            # Parse e-Way Bill Details (<EWAYBILLDETAILS.LIST>)
            for eb_node in v_node.findall(".//EWAYBILLDETAILS.LIST"):
                eb_num = eb_node.findtext("BILLNUMBER") or eb_node.findtext("EWAYBILLNO")
                if not eb_num and not eb_node.findtext("DOCNUMBER"):
                    continue
                eb_date = parse_tally_date(eb_node.findtext("BILLDATE"))
                eb_valid_up_to = parse_tally_datetime(eb_node.findtext("VALIDUPTO"))
                eb_dist_str = eb_node.findtext("DISTANCE") or "0"
                try:
                    eb_dist = Decimal(eb_dist_str.replace(",", "").strip())
                except Exception:
                    eb_dist = None
                    
                eb_trans_id = eb_node.findtext("TRANSPORTERID")
                eb_trans_name = eb_node.findtext("TRANSPORTERNAME")
                eb_doc_no = eb_node.findtext("DOCNUMBER") or eb_node.findtext("LRRRNO")
                eb_doc_date = parse_tally_date(eb_node.findtext("DOCDATE"))
                eb_veh_no = eb_node.findtext("VEHICLENUMBER") or eb_node.findtext("VEHICLENO")
                eb_veh_type = eb_node.findtext("VEHICLETYPE") or "Regular"
                eb_mode = eb_node.findtext("TRANSPORTMODE") or "Road"
                eb_subtype = eb_node.findtext("SUBTYPE") or "Supply"
                eb_doctype = eb_node.findtext("DOCTYPE") or "Tax Invoice"
                
                # Check if already exists
                eb_stmt = select(TrnEwayBill).where(
                    TrnEwayBill.voucher_id == voucher.voucher_id,
                    TrnEwayBill.bill_number == eb_num
                ) if eb_num else select(TrnEwayBill).where(
                    TrnEwayBill.voucher_id == voucher.voucher_id,
                    TrnEwayBill.doc_number == eb_doc_no
                )
                eb_res = await db.execute(eb_stmt)
                eb_obj = eb_res.scalars().first()
                if not eb_obj:
                    eb_obj = TrnEwayBill(
                        voucher_id=voucher.voucher_id,
                        bill_number=eb_num,
                        bill_date=eb_date,
                        valid_up_to=eb_valid_up_to,
                        distance_km=eb_dist,
                        transporter_id=eb_trans_id,
                        transporter_name=eb_trans_name,
                        doc_number=eb_doc_no,
                        doc_date=eb_doc_date,
                        vehicle_number=eb_veh_no,
                        vehicle_type=eb_veh_type,
                        transport_mode=eb_mode,
                        sub_type=eb_subtype,
                        doc_type=eb_doctype
                    )
                    db.add(eb_obj)
                    await db.flush()
                    
            if journal_nodes and not total_amt and not is_physical_stock(vtype):
                # A Stock Journal has no ledger lines to total: its value is what it produces (else consumes)
                def line_amount(node) -> Decimal:
                    try:
                        return abs(Decimal((node.findtext("AMOUNT") or "0").replace(",", "").strip() or "0"))
                    except Exception:
                        return Decimal("0.00")

                def side_total(flow):
                    return sum((line_amount(n) for n, f in journal_nodes if f == flow), Decimal("0.00"))
                total_amt = side_total("destination") or side_total("source")
            voucher.total_amount = total_amt
            imported_vouchers += 1
            
            # Batch commit every 25 vouchers to avoid transaction timeout on remote DB
            if imported_vouchers % 25 == 0:
                await db.commit()
                logger.info(f"Committed {imported_vouchers} vouchers so far...")
        except Exception as v_err:
            logger.error(f"❌ [VOUCHER ERROR] Failed importing voucher #{v_num} ({vtype_name}, GUID: {guid}): {str(v_err)}", exc_info=True)
            import_errors.append(f"Voucher #{v_num} ({vtype_name}): {str(v_err)}")
        
    if imported_vouchers:
        # Vouchers arrive in no particular date order; items covered by a Physical Stock count are settled
        # once everything is in
        from app.services.stock_counts import items_with_counts, rebalance_stock_counts
        await db.flush()
        await rebalance_stock_counts(db, company_id, await items_with_counts(db, company_id))

    # Final commit for any remaining records
    await db.commit()
    
    summary_msg = (
        f"✅ [IMPORT SUMMARY] Company '{resolved_company_name}' (ID: {company_id}) | "
        f"Groups: {imported_groups}, Ledgers: {imported_ledgers}, Vouchers: {imported_vouchers}, "
        f"StockItems: {imported_stock_items}, StockGroups: {imported_stock_groups}, UOMs: {imported_uoms}, "
        f"Godowns: {imported_godowns}, StockCategories: {imported_stock_categories}, Currencies: {imported_currencies}, "
        f"VoucherTypes: {imported_voucher_types}"
    )
    if import_errors:
        summary_msg += f" | ⚠️ Errors encountered ({len(import_errors)}): {import_errors[:5]}"
        logger.warning(summary_msg)
    else:
        logger.info(summary_msg)
    
    return {
        "status": "success",
        "company_id": company_id,
        "company_name": resolved_company_name,
        "imported_groups": imported_groups,
        "imported_ledgers": imported_ledgers,
        "imported_vouchers": imported_vouchers,
        "imported_stock_groups": imported_stock_groups,
        "imported_uoms": imported_uoms,
        "imported_godowns": imported_godowns,
        "imported_stock_categories": imported_stock_categories,
        "imported_stock_items": imported_stock_items,
        "imported_currencies": imported_currencies,
        "imported_voucher_types": imported_voucher_types,
        "errors": import_errors
    }
