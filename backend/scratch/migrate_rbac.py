import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async def main():
    portal_db = settings.PORTAL_DATABASE_NAME
    
    async with engine.begin() as conn:
        print("Starting RBAC Migration...")
        
        # 1. Insert 'gst' module if it does not exist
        res = await conn.execute(text(f"SELECT module_id FROM `{portal_db}`.modules WHERE code = 'gst'"))
        gst_row = res.fetchone()
        if not gst_row:
            print("Seeding 'gst' module...")
            await conn.execute(text(f"""
                INSERT INTO `{portal_db}`.modules (code, name, description, is_system)
                VALUES ('gst', 'GST Return Filing', 'File and view GST return periods', 1)
            """))
            res = await conn.execute(text(f"SELECT module_id FROM `{portal_db}`.modules WHERE code = 'gst'"))
            gst_mod_id = res.fetchone()[0]
        else:
            gst_mod_id = gst_row[0]
            
        # Ensure Admin role has full access to the new 'gst' module
        admin_res = await conn.execute(text(f"SELECT role_id FROM `{portal_db}`.roles WHERE name = 'Admin'"))
        admin_row = admin_res.fetchone()
        if admin_row:
            admin_role_id = admin_row[0]
            # Check if permission already exists
            perm_res = await conn.execute(text(f"""
                SELECT COUNT(*) FROM `{portal_db}`.permissions
                WHERE role_id = {admin_role_id} AND module_id = {gst_mod_id}
            """))
            if perm_res.scalar() == 0:
                print("Seeding Admin permission for 'gst' module...")
                await conn.execute(text(f"""
                    INSERT INTO `{portal_db}`.permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({admin_role_id}, {gst_mod_id}, 1, 1, 1, 1)
                """))

        # 2. Check if show_* columns exist on users table
        columns_res = await conn.execute(text(f"DESCRIBE `{portal_db}`.users"))
        columns = [row[0] for row in columns_res.fetchall()]
        
        has_show_columns = "show_sales_ledgers" in columns
        
        if not has_show_columns:
            print("show_* columns already dropped. Skipping data migration.")
        else:
            # 3. Read current user toggle states
            print("Reading current user toggle states...")
            users_res = await conn.execute(text(f"""
                SELECT user_id, role_id, 
                       show_sales_ledgers, show_purchase_ledgers, show_receipts, show_payments,
                       show_expenses, show_attendance, show_stocks, show_reports,
                       show_orders, show_check_in, show_gst
                FROM `{portal_db}`.users
            """))
            users = users_res.fetchall()
            
            # Fetch all roles to map role names
            roles_res = await conn.execute(text(f"SELECT role_id, name FROM `{portal_db}`.roles"))
            role_names = {row[0]: row[1] for row in roles_res.fetchall()}
            
            # Fetch modules code to ID mapping
            modules_res = await conn.execute(text(f"SELECT module_id, code FROM `{portal_db}`.modules"))
            module_map = {row[1]: row[0] for row in modules_res.fetchall()}
            
            mapping = {
                "ledger_customer": 2,      # index of show_sales_ledgers
                "ledger_supplier": 3,      # index of show_purchase_ledgers
                "vouchers": 4,             # index of show_receipts
                "payments": 5,             # index of show_payments
                "expenses": 6,             # index of show_expenses
                "attendance": 7,           # index of show_attendance
                "inventory": 8,            # index of show_stocks
                "reports": 9,              # index of show_reports
                "orders": 10,              # index of show_orders
                "visits": 11,              # index of show_check_in
                "gst": 12                  # index of show_gst
            }
            
            # For each role, load default permissions
            role_defaults = {}
            for role_id, role_name in role_names.items():
                if role_name.lower() == "admin":
                    # Admins default to True for everything
                    role_defaults[role_id] = {code: True for code in mapping}
                else:
                    role_defaults[role_id] = {}
                    for code in mapping:
                        mod_id = module_map.get(code)
                        if mod_id:
                            p_res = await conn.execute(text(f"""
                                SELECT can_read FROM `{portal_db}`.permissions 
                                WHERE role_id = {role_id} AND module_id = {mod_id}
                            """))
                            p_row = p_res.fetchone()
                            role_defaults[role_id][code] = bool(p_row[0]) if p_row else False
                        else:
                            role_defaults[role_id][code] = False
            
            # Compute and insert overrides
            print("Computing user permission overrides...")
            overrides_inserted = 0
            for u in users:
                u_id = u[0]
                r_id = u[1]
                r_name = role_names.get(r_id, "User")
                
                # Admins don't need overrides
                if r_name.lower() == "admin":
                    continue
                    
                defaults = role_defaults.get(r_id, {})
                for code, col_idx in mapping.items():
                    mod_id = module_map.get(code)
                    if not mod_id:
                        continue
                        
                    user_val = bool(u[col_idx])
                    default_val = defaults.get(code, False)
                    
                    if user_val != default_val:
                        # Check if override already exists
                        ov_exists = await conn.execute(text(f"""
                            SELECT COUNT(*) FROM `{portal_db}`.user_permission_overrides
                            WHERE user_id = {u_id} AND module_id = {mod_id}
                        """))
                        if ov_exists.scalar() == 0:
                            print(f"Adding override for user_id={u_id}, module={code} to {user_val}")
                            await conn.execute(text(f"""
                                INSERT INTO `{portal_db}`.user_permission_overrides
                                (user_id, module_id, can_create, can_read, can_update, can_delete, granted_by, reason)
                                VALUES ({u_id}, {mod_id}, {1 if user_val else 0}, {1 if user_val else 0}, {1 if user_val else 0}, {1 if user_val else 0}, 1, 'Migration Override')
                            """))
                            overrides_inserted += 1
            print(f"Migration: Created {overrides_inserted} user permission override records.")
            
            # 4. Drop columns
            print("Dropping show_* columns from users table...")
            columns_to_drop = [
                "show_ledger", "show_stocks", "show_reports", "show_orders",
                "show_check_in", "show_sales_ledgers", "show_purchase_ledgers",
                "show_receipts", "show_payments", "show_expenses",
                "show_attendance", "show_gst"
            ]
            for col in columns_to_drop:
                try:
                    await conn.execute(text(f"ALTER TABLE `{portal_db}`.users DROP COLUMN `{col}`"))
                    print(f"Dropped column: {col}")
                except Exception as e:
                    print(f"Error dropping column {col}: {e}")
                    
        print("RBAC Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
