import asyncio
from app.core.database import AsyncSessionLocal
from app.models.voucher import TrnVoucher, TrnAccounting
from app.models.ledger import MstLedger
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
import app.models.user
import app.models.company
import app.models.gst
import datetime

async def main():
    async with AsyncSessionLocal() as db:
        # Fetch all vouchers for April 2026
        start_date = datetime.date(2026, 4, 1)
        end_date = datetime.date(2026, 4, 30)
        
        stmt = select(TrnVoucher).options(
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
        ).where(
            TrnVoucher.is_optional == False,
            TrnVoucher.voucher_date >= start_date,
            TrnVoucher.voucher_date <= end_date
        )
        
        result = await db.execute(stmt)
        vouchers = result.scalars().all()
        
        b2b_taxable = Decimal("0.00")
        b2b_cgst = Decimal("0.00")
        b2b_count = 0
        
        b2c_taxable = Decimal("0.00")
        b2c_cgst = Decimal("0.00")
        b2c_count = 0
        
        cdnr_taxable = Decimal("0.00")
        cdnr_cgst = Decimal("0.00")
        cdnr_count = 0
        
        itc_cgst = Decimal("0.00")
        itc_sgst = Decimal("0.00")
        itc_igst = Decimal("0.00")
        
        for v in vouchers:
            is_purchase = False
            is_sales = False
            for e in v.entries:
                if e.ledger:
                    name_upper = e.ledger.name.upper()
                    if 'PURCHASE' in name_upper:
                        is_purchase = True
                    if 'SALES' in name_upper:
                        is_sales = True
            
            # If it has a purchase ledger, treat as inward (ITC).
            # If it has sales, treat as outward.
            # If neither, but has discount, we might need to guess based on party. 
            # For simplicity, if it's not sales, it's ITC (since all input tax credits come from non-sales vouchers).
            if not is_sales:
                # Calculate ITC
                for e in v.entries:
                    if not e.ledger:
                        continue
                    name_upper = e.ledger.name.upper()
                    net_debit = e.debit_amount - e.credit_amount
                    
                    if 'CGST' in name_upper:
                        itc_cgst += net_debit
                    elif 'SGST' in name_upper:
                        itc_sgst += net_debit
                    elif 'IGST' in name_upper:
                        itc_igst += net_debit
                continue
                
            has_tax = False
            taxable = Decimal("0.00")
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = Decimal("0.00")
            
            from app.routers.vouchers import _resolve_party_and_amount
            party_name, _ = _resolve_party_and_amount(v.entries)
            
            for e in v.entries:
                if not e.ledger:
                    continue
                if e.ledger.name == party_name:
                    continue
                
                name_upper = e.ledger.name.upper()
                
                net_credit = e.credit_amount - e.debit_amount
                
                if 'CGST' in name_upper:
                    cgst += abs(net_credit)
                    has_tax = True
                elif 'SGST' in name_upper:
                    sgst += abs(net_credit)
                    has_tax = True
                elif 'IGST' in name_upper:
                    igst += abs(net_credit)
                    has_tax = True
                elif 'SALES' in name_upper:
                    taxable += e.credit_amount if e.credit_amount > 0 else e.debit_amount
                elif 'DISCOUNT' in name_upper:
                    taxable -= e.debit_amount if e.debit_amount > 0 else e.credit_amount
                    
            if has_tax and taxable != 0:
                party_gstin = None
                if party_name:
                    party_q = await db.execute(
                        select(MstLedger).where(
                            MstLedger.name == party_name,
                            MstLedger.company_id == v.company_id
                        )
                    )
                    party_ledger = party_q.scalars().first()
                    if party_ledger and party_ledger.gstin:
                        party_gstin = party_ledger.gstin
                
                if taxable < 0:
                    cdnr_taxable += taxable
                    # We should just print the voucher details to see what it is
                    print(f"CDNR Voucher: {v.voucher_number}, Date: {v.voucher_date}")
                    for e in v.entries:
                        if e.ledger:
                            print(f"  {e.ledger.name}: Cr={e.credit_amount}, Dr={e.debit_amount}")
                    cdnr_cgst += cgst if cgst < 0 else -cgst
                    cdnr_count += 1
                elif party_gstin:
                    b2b_taxable += taxable
                    b2b_cgst += cgst
                    b2b_count += 1
                else:
                    b2c_taxable += taxable
                    b2c_cgst += cgst
                    b2c_count += 1
                    
        ledger_totals = {}
        for v in vouchers:
            for e in v.entries:
                if e.ledger:
                    name = e.ledger.name
                    if name not in ledger_totals:
                        ledger_totals[name] = {"dr": Decimal("0.00"), "cr": Decimal("0.00")}
                    ledger_totals[name]["dr"] += e.debit_amount
                    ledger_totals[name]["cr"] += e.credit_amount
                    
        print(f"--- April 2026 Analysis ---")
        print(f"B2B Taxable: {b2b_taxable}, CGST: {b2b_cgst}")
        print(f"B2C Taxable: {b2c_taxable}, CGST: {b2c_cgst}")
        
        # Calculate ITC
        purchase_igst = Decimal("0.00")
        purchase_cgst = Decimal("0.00")
        purchase_sgst = Decimal("0.00")
        
        for v in vouchers:
            # Check if this is a purchase voucher (has a ledger containing PURCHASE)
            if any(e.ledger and 'PURCHASE' in e.ledger.name.upper() for e in v.entries):
                for e in v.entries:
                    if e.ledger:
                        name_upper = e.ledger.name.upper()
                        if 'IGST' in name_upper:
                            purchase_igst += e.debit_amount - e.credit_amount
                        elif 'CGST' in name_upper:
                            purchase_cgst += e.debit_amount - e.credit_amount
                        elif 'SGST' in name_upper:
                            purchase_sgst += e.debit_amount - e.credit_amount
                            
        for name, totals in ledger_totals.items():
            if totals["dr"] > 0 or totals["cr"] > 0:
                print(f"{name}: Dr={totals['dr']}, Cr={totals['cr']}")
                
        print(f"Purchase Vouchers Tax (Book ITC): IGST: {purchase_igst}, CGST: {purchase_cgst}, SGST: {purchase_sgst}")

asyncio.run(main())
