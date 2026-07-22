import xml.etree.ElementTree as ET
import logging
import re
from decimal import Decimal
from datetime import datetime, date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

logger = logging.getLogger("uvicorn.error")

from app.models.ledger import MstGroup, MstLedger
from app.models.voucher import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.payment import TrnBill, BillAllocation

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
    return invalid_xml_raw_re.sub("", sanitized)

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

async def import_tally_xml(xml_data: str, db: AsyncSession, company_id: int) -> dict:
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

    # Extract company name and update company model
    try:
        company_name_node = root.find(".//SVCURRENTCOMPANY")
        if company_name_node is not None and company_name_node.text:
            company_name = company_name_node.text.strip()
            if company_name:
                from app.models.company import Company
                stmt = select(Company).where(Company.company_id == company_id)
                comp_res = await db.execute(stmt)
                company_obj = comp_res.scalars().first()
                if company_obj and company_obj.name != company_name:
                    company_obj.name = company_name
                    await db.flush()
                    logger.info(f"Updated company name in database to '{company_name}' based on XML import.")
    except Exception as ex:
        logger.error(f"Error updating company name from XML: {str(ex)}", exc_info=True)
        
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
                is_active=True
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
        gstin = ledger_node.findtext(".//LEDGSTREGDETAILS.LIST/GSTIN") or ledger_node.findtext("GSTIN")
        if gstin:
            gstin = gstin.strip()
            
        # Parse state
        state = ledger_node.findtext(".//LEDMAILINGDETAILS.LIST/STATE")
        if state:
            state = state.strip()
            
        # Parse address
        addr_nodes = ledger_node.findall(".//LEDMAILINGDETAILS.LIST/ADDRESS.LIST/ADDRESS")
        addr_str = ", ".join([a.text.strip() for a in addr_nodes if a.text])
        
        # Parse mobile
        phone = ledger_node.findtext(".//CONTACTDETAILS.LIST/PHONENUMBER")
        isd = ledger_node.findtext(".//CONTACTDETAILS.LIST/COUNTRYISDCODE") or "+91"
        mobile_str = f"{isd} {phone.strip()}" if phone else None
        
        combined_address = addr_str
        if mobile_str:
            combined_address = f"{addr_str} | Mobile: {mobile_str}"
        
        # Opening balance
        op_bal_str = ledger_node.findtext("OPENINGBALANCE") or "0"
        try:
            op_bal_val = Decimal(op_bal_str)
        except Exception:
            op_bal_val = Decimal("0.00")
            
        # Standard Tally: Negative is Debit, Positive is Credit for assets,
        # but to keep it simple, we check sign:
        # Negative -> Debit, Positive -> Credit (standard)
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
                address=combined_address,
                state=state,
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
            ledger.address = combined_address
            ledger.state = state
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
                created_by=1 # fallback default admin user
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
    if imported_vouchers > 0:
        logger.info(f"Committed {imported_vouchers} vouchers (total)")
    
    return {
        "status": "success",
        "imported_groups": imported_groups,
        "imported_ledgers": imported_ledgers,
        "imported_vouchers": imported_vouchers,
        "imported_stock_groups": imported_stock_groups,
        "imported_uoms": imported_uoms,
        "imported_godowns": imported_godowns,
        "imported_stock_categories": imported_stock_categories,
        "imported_stock_items": imported_stock_items
    }
