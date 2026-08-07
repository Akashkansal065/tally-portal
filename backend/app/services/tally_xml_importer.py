import xml.etree.ElementTree as ET
import logging
import re
from decimal import Decimal
from datetime import datetime, date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func

logger = logging.getLogger("uvicorn.error")

from app.models.ledger import MstGroup, MstLedger
from app.models.voucher import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.payment import TrnBill, BillAllocation
from app.models.user import User, Role, UserCompanyAccess
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

async def ensure_tally_user_exists(db: AsyncSession, company_id: int, user_name: str) -> Optional[User]:
    if not user_name or not str(user_name).strip():
        return None
        
    raw_name = str(user_name).strip()
    if raw_name.lower() in ("sysname:xml", "none", "null", "system", "tally"):
        return None
        
    cache_key = (company_id, raw_name.lower())
    if cache_key in _checked_tally_users:
        return None
        
    # Check if user with this username already exists in DB
    user_stmt = select(User).where(func.lower(User.username) == raw_name.lower())
    res = await db.execute(user_stmt)
    existing_user = res.scalars().first()
    
    if existing_user:
        # Check if user has access mapped to this company
        access_stmt = select(UserCompanyAccess).where(
            UserCompanyAccess.user_id == existing_user.user_id,
            UserCompanyAccess.company_id == company_id
        )
        access_res = await db.execute(access_stmt)
        if not access_res.scalars().first():
            access = UserCompanyAccess(user_id=existing_user.user_id, company_id=company_id)
            db.add(access)
            await db.flush()
            logger.info(f"👥 Linked existing user '{existing_user.username}' (ID: {existing_user.user_id}) to Company #{company_id}")
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

    password_hash = get_password_hash("password123")
    new_user = User(
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

from app.models.inventory import MstStockGroup, MstStockCategory, MstUom, MstGodown, MstStockItem

async def get_or_create_stock_group(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None) -> MstStockGroup:
    stmt = select(MstStockGroup).where(MstStockGroup.company_id == company_id, MstStockGroup.name == name)
    res = await db.execute(stmt)
    group = res.scalars().first()
    
    parent_id = None
    if parent_name:
        parent_group = await get_or_create_stock_group(db, company_id, parent_name)
        parent_id = parent_group.stock_group_id
        
    if group:
        if parent_id is not None and group.parent_id != parent_id:
            group.parent_id = parent_id
            await db.flush()
        return group
        
    group = MstStockGroup(
        company_id=company_id,
        name=name,
        parent_id=parent_id
    )
    db.add(group)
    await db.flush()
    return group

async def get_or_create_stock_category(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None) -> MstStockCategory:
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

async def get_or_create_group(db: AsyncSession, company_id: int, name: str, parent_name: Optional[str] = None) -> MstGroup:
    # Check if group exists
    stmt = select(MstGroup).where(MstGroup.company_id == company_id, MstGroup.name == name)
    res = await db.execute(stmt)
    group = res.scalars().first()
    if group:
        return group
        
    # Get parent id
    parent_id = None
    if parent_name:
        parent_grp = await get_or_create_group(db, company_id, parent_name)
        parent_id = parent_grp.group_id
        
    group = MstGroup(
        company_id=company_id,
        name=name,
        parent_group_id=parent_id,
        nature="Asset", # default fallback
        affects_gross_profit=False,
        is_system_defined=False
    )
    db.add(group)
    await db.flush()
    return group

async def import_tally_xml(xml_data: str, db: AsyncSession, user_id: int, override_company_name: Optional[str] = None) -> dict:
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
        from app.models.company import Company
        from app.models.user import UserCompanyAccess
        
        company_name_node = root.find(".//SVCURRENTCOMPANY")
        company_node = root.find(".//COMPANY")
        
        tally_guid = None
        if company_node is not None:
            tally_guid = company_node.findtext("COMPANYGUID") or company_node.findtext("GUID")
            
        company_name = None
        if override_company_name:
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
                name_stmt = select(Company).join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id).where(
                    UserCompanyAccess.user_id == user_id,
                    func.lower(Company.name) == func.lower(company_name)
                )
                comp_res = await db.execute(name_stmt)
                company_obj = comp_res.scalars().first()
            
            if not company_obj:
                # Auto-create company
                company_obj = Company(
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
                for addr_elem in company_node.findall(".//ADDRESS"):
                    if addr_elem.text and addr_elem.text.strip():
                        txt = addr_elem.text.strip()
                        if txt.lower() not in ("none", "null", "n/a", "na", ""):
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

                # Extract GSTIN
                gstin = get_clean_text("GSTREGISTRATIONNUMBER") or get_clean_text("GSTIN") or get_clean_text("PARTYGSTIN")
                if gstin: company_obj.gstin = gstin[:15]; updated = True

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
                    from datetime import timedelta
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
        
    imported_groups = 0
    imported_ledgers = 0
    imported_vouchers = 0
    imported_stock_groups = 0
    imported_uoms = 0
    imported_godowns = 0
    imported_stock_categories = 0
    imported_stock_items = 0
    
    # 1. Parse Groups (<GROUP>)
    for group_node in root.findall(".//GROUP"):
        name = group_node.get("NAME") or group_node.findtext("NAME")
        if not name:
            continue
        parent_name = group_node.findtext("PARENT")
        await get_or_create_group(db, company_id, name, parent_name)
        imported_groups += 1
        
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
        await get_or_create_stock_group(db, company_id, name, parent_name)
        imported_stock_groups += 1
        
    await db.flush()
    if imported_stock_groups > 0:
        await db.commit()
        logger.info(f"Committed {imported_stock_groups} stock groups")

    # 1.2. Parse Units (<UNIT>)
    for unit_node in root.findall(".//UNIT"):
        symbol = unit_node.get("NAME") or unit_node.findtext("NAME") or unit_node.findtext("SYMBOL")
        if not symbol:
            continue
        name = unit_node.findtext("NAME") or symbol
        dec_places = 0
        dec_str = unit_node.findtext("DECIMALPLACES")
        if dec_str:
            try:
                dec_places = int(dec_str.strip())
            except ValueError:
                pass
        await get_or_create_uom(db, company_id, symbol, name, dec_places)
        imported_uoms += 1
        
    await db.flush()
    if imported_uoms > 0:
        await db.commit()
        logger.info(f"Committed {imported_uoms} UOMs")

    # 1.3. Parse Godowns (<GODOWN>)
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
            
        parent_name = si_node.findtext("PARENT")
        category_name = si_node.findtext("CATEGORY")
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

        stock_group = None
        if parent_name:
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
            if alter_id and item.tally_alter_id and item.tally_alter_id >= alter_id:
                continue
            if stock_group:
                item.stock_group_id = stock_group.stock_group_id
            if stock_category:
                item.stock_category_id = stock_category.stock_category_id
            item.unit_id = uom.unit_id
            item.opening_qty = op_qty
            item.opening_rate = op_rate
            if hsn_code:
                item.hsn_code = hsn_code
            if gst_rate > 0:
                item.gst_rate_percent = gst_rate
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
                is_active=True,
                tally_alter_id=alter_id
            )
            db.add(item)
            await db.flush()
            
        imported_stock_items += 1
        # Batch commit every 50 stock items
        if imported_stock_items % 50 == 0:
            await db.commit()
            logger.info(f"Committed {imported_stock_items} stock items so far...")
        
    await db.flush()
    if imported_stock_items > 0:
        await db.commit()
        logger.info(f"Committed {imported_stock_items} stock items (total)")
    
    # 2. Parse Ledgers (<LEDGER>)
    for ledger_node in root.findall(".//LEDGER"):
        name = ledger_node.get("NAME") or ledger_node.findtext("NAME")
        if not name:
            continue
            
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
            import uuid
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
            import re
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
                tally_guid=guid,
                tally_alter_id=alter_id
            )
            db.add(ledger)
        else:
            if ledger.tally_alter_id and ledger.tally_alter_id >= alter_id:
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
            ledger.is_billwise_on = is_billwise_val
            ledger.tally_guid = guid
            ledger.tally_alter_id = alter_id
            
        imported_ledgers += 1
        # Batch commit every 50 ledgers
        if imported_ledgers % 50 == 0:
            await db.commit()
            logger.info(f"Committed {imported_ledgers} ledgers so far...")
        
    await db.flush()
    if imported_ledgers > 0:
        await db.commit()
        logger.info(f"Committed {imported_ledgers} ledgers (total)")
    
    # 3. Parse Vouchers (<VOUCHER>)
    # Filter out empty/metadata VOUCHER tags (like <VOUCHER>14</VOUCHER> in CMPINFO) by ensuring they have child elements
    voucher_nodes = [v for v in root.findall(".//VOUCHER") if len(v) > 0]
    for v_node in voucher_nodes:
        # Auto-provision user if voucher contains entered_by / altered_by
        entered_by = v_node.findtext("ENTEREDBY") or v_node.findtext("ALTEREDBY") or v_node.findtext("CREATEDBY")
        if entered_by:
            await ensure_tally_user_exists(db, company_id, entered_by)

        guid = v_node.findtext("GUID") or v_node.get("GUID")
        if not guid:
            guid = v_node.findtext("REMOTEID") or v_node.get("REMOTEID")
        if not guid:
            import uuid
            guid = f"GEN-{uuid.uuid4().hex[:12]}"
            
        alter_id_str = v_node.findtext("ALTERID") or "0"
        alter_id = int(alter_id_str)
        
        vtype_name = v_node.findtext("VOUCHERTYPENAME") or v_node.get("VOUCHERTYPENAME") or "Journal"
        v_num = v_node.findtext("VOUCHERNUMBER") or guid[:10]
        
        v_date_str = v_node.findtext("DATE") # e.g. "20260710" or "2026-07-10"
        try:
            if len(v_date_str) == 8:
                v_date = datetime.strptime(v_date_str, "%Y%m%d").date()
            else:
                v_date = datetime.strptime(v_date_str[:10], "%Y-%m-%d").date()
        except Exception:
            v_date = date.today()
            
        narration = v_node.findtext("NARRATION")
        
        # Get or create MstVoucherType
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
            
        # Check if voucher already exists by GUID (idempotency/update)
        stmt = select(TrnVoucher).where(TrnVoucher.company_id == company_id, TrnVoucher.tally_guid == guid)
        res = await db.execute(stmt)
        voucher = res.scalars().first()
        
        # Auto-provision user if voucher contains entered_by / altered_by
        v_user_id = user_id
        entered_by = v_node.findtext("ENTEREDBY") or v_node.findtext("ALTEREDBY") or v_node.findtext("CREATEDBY")
        if entered_by:
            tally_user = await ensure_tally_user_exists(db, company_id, entered_by)
            if tally_user:
                v_user_id = tally_user.user_id

        if voucher:
            # If present and alter_id is same or lower, skip to prevent overriding local changes
            if voucher.tally_alter_id and voucher.tally_alter_id >= alter_id:
                continue
            # Delete old entries to rebuild (must delete child bill_allocations first)
            from app.core.config import settings
            await db.execute(text(f"DELETE FROM `{settings.TALLY_DATABASE_NAME}`.bill_allocations WHERE voucher_entry_id IN (SELECT entry_id FROM `{settings.TALLY_DATABASE_NAME}`.voucher_entries WHERE voucher_id = {voucher.voucher_id})"))
            await db.execute(text(f"DELETE FROM `{settings.TALLY_DATABASE_NAME}`.voucher_entries WHERE voucher_id = {voucher.voucher_id}"))
            await db.flush()
        else:
            voucher = TrnVoucher(
                company_id=company_id,
                voucher_type_id=vtype.voucher_type_id,
                voucher_number=v_num,
                voucher_date=v_date,
                tally_guid=guid,
                tally_alter_id=alter_id,
                created_by=v_user_id
            )
            db.add(voucher)
            await db.flush()
            
        voucher.voucher_number = v_num
        voucher.voucher_date = v_date
        voucher.narration = narration
        voucher.tally_alter_id = alter_id
        
        total_amt = Decimal("0.00")
        
        # Add entries
        # Tally lists entries in <ALLLEDGERENTRIES.LIST> or <LEDGERENTRIES.LIST>
        # Check ALLLEDGERENTRIES.LIST first, falling back to LEDGERENTRIES.LIST if it is missing
        entries_nodes = v_node.findall(".//ALLLEDGERENTRIES.LIST")
        if not entries_nodes:
            entries_nodes = v_node.findall(".//LEDGERENTRIES.LIST")
        for ent_node in entries_nodes:
            led_name = ent_node.findtext("LEDGERNAME")
            if not led_name:
                continue
                
            # Get ledger
            l_stmt = select(MstLedger).where(MstLedger.company_id == company_id, MstLedger.name == led_name)
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
                
            entry = TrnAccounting(
                voucher_id=voucher.voucher_id,
                ledger_id=ledger.ledger_id,
                debit_amount=dr_amt,
                credit_amount=cr_amt
            )
            db.add(entry)
            await db.flush()
            
            
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
                        # Fallback reference name to prevent NOT NULL database constraint issues
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
                
        # Parse inventory entries inside <ALLINVENTORYENTRIES.LIST>
        for inv_node in v_node.findall(".//ALLINVENTORYENTRIES.LIST"):
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
                
            # Get or create MstUom
            uom_stmt = select(MstUom).where(MstUom.company_id == company_id, MstUom.symbol == uom_name)
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
                
            # Determine stock group name (brand)
            group_name = inv_node.findtext("GSTSTOCKGROUPSOURCE") or inv_node.findtext("HSNSTOCKGROUPSOURCE")
            if group_name:
                if group_name == "SURAJ POLY PLAST":
                    group_name = "SURAJ POLY PLAST (JOYWARE)"
                elif group_name == "Nirvaan Metaliks" or group_name == "NIRVAAN METALIKS":
                    group_name = "NIRVAAN METALIKAS"

            # Get or create MstStockItem
            is_deemed_pos = inv_node.findtext("ISDEEMEDPOSITIVE") or "No"
            is_inward = is_deemed_pos.strip().lower() == "yes"

            item_stmt = select(MstStockItem).where(MstStockItem.company_id == company_id, MstStockItem.name == item_name)
            item_res = await db.execute(item_stmt)
            item = item_res.scalars().first()
            
            if not item:
                if not group_name:
                    name_upper = item_name.upper()
                    if any(x in name_upper for x in ["BAJAJ", "BAJA", "PROMIX", "ICX", "IRX", "AT 402", "HB 2", "MX 4", "NEW POPULAR", "40RCAD", "KTX", "SWX", "BURNER", "COOKTOP", "GAS STOVE", "OTG", "MORPHY", "OVEN", "PROCESSOR", "MWO", "DRY IRON", "STEAM IRON", "MR "]):
                        group_name = "BAJAJ ELECTRICALS LIMITED"
                    elif any(x in name_upper for x in ["KGOC", "KRYSTA", "OMEGA", "1101.1", "1135.1", "1235.2", "4150.1", "PC-1125.1", "KB-811/B", "GR-11C", "GR-21C", "21 SS", "21SS", "1131.1", "1138.1", "1148.1", "4130.1", "4144.1", "4244.3", "4148.2", "4166.1", "41106", "41107", "41108", "1201.2", "1102.1", "1103.1", "1303.2", "LR-", "KS-", "SL-", "GL-", "GS-", "M-STAR", "CR-"]):
                        group_name = "KGOC"
                    elif any(x in name_upper for x in ["SURAJ", "JOYWARE", "RUBY", "LINER", "LOCK &", "LOCK", "DUSTBIN", "MODU", "NESTO", "PATLA", "STRAINER", "BOWL", "MUG", "MASALA", "CASE", "PEDAL BIN", "SPINNER MOP", "SWEET BOX", "FOOD FRESH", "BHOJAN THALI", "KITCHEN TOKRA", "SWING BIN", "BATHROOM 8 PCS", "PHANTOM MULTI BOX", "OMEGA TUB", "AQUA GLASS", "TULIP TRAY", "STOOL"]):
                        group_name = "SURAJ POLY PLAST (JOYWARE)"
                    elif any(x in name_upper for x in ["CELLTONE", "DELUXE", "2 IN 1 BLENDMASTER", "EUROPA", "SMART", "STEELO", "SWX 5", "20MS", "20MWS BLACK", "5L CLASSIC", "PRINTED BATHROOM", "VEGETABLE", "CHEESE", "SHARP KNIFE", "PROMOTIONAL ZOOM", "SAFE LASER KNIFE", "SAFE TOMATO KNIFE", "F2O CLEAR LOOK", "SPATULA", "WOODEN CHEF KNIFE", "WOODEN CLEAVER KNIFE", "WOODEN LASER KNIFE", "WOODEN PARING KNIFE", "WOODEN POINT KNIFE", "WOODEN UTILITY KNIFE", "PROMOTIONAL BAGS", "STRAINER & GRATER"]):
                        group_name = "CELLTONE HOME APPLIANCES"
                    else:
                        group_name = "NIRVAAN METALIKAS"
                
                stock_group = await get_or_create_stock_group(db, company_id, group_name)
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
            else:
                if group_name:
                    stock_group = await get_or_create_stock_group(db, company_id, group_name)
                    item.stock_group_id = stock_group.stock_group_id
                elif item.stock_group_id is None:
                    name_upper = item_name.upper()
                    if any(x in name_upper for x in ["BAJAJ", "BAJA", "PROMIX", "ICX", "IRX", "AT 402", "HB 2", "MX 4", "NEW POPULAR", "40RCAD", "KTX", "SWX", "BURNER", "COOKTOP", "GAS STOVE", "OTG", "MORPHY", "OVEN", "PROCESSOR", "MWO", "DRY IRON", "STEAM IRON", "MR "]):
                        fallback_group = "BAJAJ ELECTRICALS LIMITED"
                    elif any(x in name_upper for x in ["KGOC", "KRYSTA", "OMEGA", "1101.1", "1135.1", "1235.2", "4150.1", "PC-1125.1", "KB-811/B", "GR-11C", "GR-21C", "21 SS", "21SS", "1131.1", "1138.1", "1148.1", "4130.1", "4144.1", "4244.3", "4148.2", "4166.1", "41106", "41107", "41108", "1201.2", "1102.1", "1103.1", "1303.2", "LR-", "KS-", "SL-", "GL-", "GS-", "M-STAR", "CR-"]):
                        fallback_group = "KGOC"
                    elif any(x in name_upper for x in ["SURAJ", "JOYWARE", "RUBY", "LINER", "LOCK &", "LOCK", "DUSTBIN", "MODU", "NESTO", "PATLA", "STRAINER", "BOWL", "MUG", "MASALA", "CASE", "PEDAL BIN", "SPINNER MOP", "SWEET BOX", "FOOD FRESH", "BHOJAN THALI", "KITCHEN TOKRA", "SWING BIN", "BATHROOM 8 PCS", "PHANTOM MULTI BOX", "OMEGA TUB", "AQUA GLASS", "TULIP TRAY", "STOOL"]):
                        fallback_group = "SURAJ POLY PLAST (JOYWARE)"
                    elif any(x in name_upper for x in ["CELLTONE", "DELUXE", "2 IN 1 BLENDMASTER", "EUROPA", "SMART", "STEELO", "SWX 5", "20MS", "20MWS BLACK", "5L CLASSIC", "PRINTED BATHROOM", "VEGETABLE", "CHEESE", "SHARP KNIFE", "PROMOTIONAL ZOOM", "SAFE LASER KNIFE", "SAFE TOMATO KNIFE", "F2O CLEAR LOOK", "SPATULA", "WOODEN CHEF KNIFE", "WOODEN CLEAVER KNIFE", "WOODEN LASER KNIFE", "WOODEN PARING KNIFE", "WOODEN POINT KNIFE", "WOODEN UTILITY KNIFE", "PROMOTIONAL BAGS", "STRAINER & GRATER"]):
                        fallback_group = "CELLTONE HOME APPLIANCES"
                    else:
                        fallback_group = "NIRVAAN METALIKAS"
                    stock_group = await get_or_create_stock_group(db, company_id, fallback_group)
                    item.stock_group_id = stock_group.stock_group_id
                if is_inward:
                    item.closing_qty = (item.closing_qty or Decimal("0.000")) + qty_val
                    item.closing_value = (item.closing_value or Decimal("0.00")) + inv_amt
                else:
                    qty_before = (item.closing_qty or Decimal("0.000"))
                    val_before = (item.closing_value or Decimal("0.00"))
                    avg_cost = Decimal("0.00")
                    if qty_before > 0:
                        avg_cost = val_before / qty_before
                    cons_val = qty_val * avg_cost
                    item.closing_qty = qty_before - qty_val
                    item.closing_value = val_before - cons_val

                if rate_val > 0:
                    item.closing_rate = rate_val
                if gst_rate > 0:
                    item.gst_rate_percent = gst_rate
                await db.flush()

            # Insert TrnInventory
            from app.models.inventory import TrnInventory
            stock_entry = TrnInventory(
                voucher_id=voucher.voucher_id,
                stock_item_id=item.stock_item_id,
                quantity=qty_val,
                rate=rate_val,
                amount=inv_amt,
                is_inward=is_inward
            )
            db.add(stock_entry)
            await db.flush()
                
        voucher.total_amount = total_amt
        imported_vouchers += 1
        
        # Batch commit every 25 vouchers to avoid transaction timeout on remote DB
        if imported_vouchers % 25 == 0:
            await db.commit()
            logger.info(f"Committed {imported_vouchers} vouchers so far...")
        
    # Final commit for any remaining records
    await db.commit()
    
    logger.info(
        f"Sync Summary for Company '{resolved_company_name}' (ID: {company_id}): "
        f"Groups: {imported_groups}, "
        f"Ledgers: {imported_ledgers}, "
        f"Vouchers: {imported_vouchers}, "
        f"StockGroups: {imported_stock_groups}, "
        f"UOMs: {imported_uoms}, "
        f"Godowns: {imported_godowns}, "
        f"StockCategories: {imported_stock_categories}, "
        f"StockItems: {imported_stock_items}"
    )
    
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
        "imported_stock_items": imported_stock_items
    }
