import asyncio
import os
import sys
from sqlalchemy import text

# Add parent directory of scratch to sys.path to enable app module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine

async def clear_data(target_db: str = "all"):
    print("Ensuring databases exist...")
    from app.core.database import create_databases_if_not_exist
    await create_databases_if_not_exist()
    
    print(f"Target database selection: {target_db}")
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # All tables to clear except user management, roles, permissions, companies, and migrations
        tables = [
            "bill_allocations",
            "voucher_entries",
            "vouchers",
            "bills",
            "ledgers",
            "account_groups",
            "stock_entries",
            "stock_items",
            "stock_groups",
            "stock_categories",
            "units_of_measure",
            "godowns",
            "batches",
            "serial_numbers",
            "bill_of_materials",
            "bom_items",
            "challan_entry_map",
            "cost_centers",
            "employees",
            "payroll_periods",
            "payslips",
            "payslip_components",
            "salary_structures",
            "salary_components",
            "salary_structure_components",
            "expenses",
            "shop_payments",
            "temp_orders",
            "temp_order_items",
            "sales_visits",
            "sync_queue",
            "user_sessions",
            "audit_logs",
            "pos_payments",
            "payment_links",
            "gateway_transactions",
            "payment_gateway_configs",
            "webhook_events",
            "tax_challans",
            "tcs_sections",
            "tds_sections",
            "tds_tcs_entries",
            "lower_deduction_certificates",
            "gst_return_periods",
            "gstr1_hsn_summary",
            "gstr1_line_items",
            "gstr3b_summary",
            "itc_entries",
            "einvoice_metadata"
        ]
        
        from app.core.config import settings
        portal_db = settings.DATABASE_URL.rsplit('/', 1)[-1]
        if '?' in portal_db:
            portal_db = portal_db.split('?')[0]
        tally_db = settings.TALLY_DATABASE_NAME
        
        portal_tables = {
            "expenses", "shop_payments", "temp_orders", "temp_order_items",
            "sales_visits", "sync_queue", "user_sessions", "audit_logs",
            "payment_links", "gateway_transactions", "payment_gateway_configs", "webhook_events",
            "bill_of_materials", "bom_items", "batches", "serial_numbers",
            "einvoice_metadata", "lower_deduction_certificates", "tds_tcs_entries",
            "tax_challans", "challan_entry_map", "gst_return_periods",
            "gstr1_line_items", "gstr1_hsn_summary", "gstr3b_summary", "itc_entries"
        }
        
        for table in tables:
            is_portal = table in portal_tables
            
            # Filter tables based on target_db selection
            if target_db == "tally_portal" and not is_portal:
                continue
            elif target_db == "tally_sync" and is_portal:
                continue
                
            db_name = portal_db if is_portal else tally_db
            fq_table = f"`{db_name}`.`{table}`"
            print(f"Truncating table: {fq_table}...")
            try:
                await conn.execute(text(f"TRUNCATE TABLE {fq_table};"))
                print(f" -> Table {fq_table} cleared successfully.")
            except Exception as e:
                print(f" -> Error truncating {fq_table}: {e}")
                
        print("Enabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    print("Database clear operations completed successfully!")

if __name__ == "__main__":
    # Configurable option: "all", "tally_sync", or "tally_portal"
    TARGET_DB = "tally_sync"
    
    asyncio.run(clear_data(TARGET_DB))
