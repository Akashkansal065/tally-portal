import os
from sqlalchemy import text
from sqlalchemy.orm import Session

def seed_global_data(db: Session):
    """
    Seeds global tables (modules, and the permissions of roles that exist) that do not depend on a specific company.
    """
    # 1. Roles are not seeded here. Every account gets its own Admin and Sales roles when it is created
    #    (app.core.account_roles.create_default_roles). A role with no account would belong to nobody and would
    #    stop the database from requiring an account on every role.

    # 2. Seed Modules if not populated
    modules_exist = db.execute(text("SELECT COUNT(*) FROM modules")).scalar()
    if modules_exist == 0:
        print("Seeding modules...")
        db.execute(text("""
            INSERT INTO modules (code, name, description, is_system) VALUES
            ('ledgers',   'Ledgers & Groups',      'Chart of accounts management', 1),
            ('ledger_customer', 'Ledgers - Customers', 'Customer ledgers (Sundry Debtors)', 1),
            ('ledger_supplier', 'Ledgers - Suppliers', 'Supplier ledgers (Sundry Creditors)', 1),
            ('vouchers',  'Vouchers',              'Payment, Receipt, Journal, Sales, Purchase, etc.', 1),
            ('inventory', 'Inventory',             'Stock items, godowns, stock movement', 1),
            ('orders',    'Orders',                'Sales and Purchase orders', 1),
            ('payments',  'Payments & Bills',      'Bill-wise allocation, outstanding, gateway payments', 1),
            ('outstanding', 'Outstanding & Reminders', 'Customer dues, aging and payment reminders', 1),
            ('reports',   'Reports',               'Trial Balance, P&L, Balance Sheet, GST reports', 1),
            ('users',     'User Management',       'Create/manage users', 1),
            ('roles',     'Roles & Permissions',   'Manage roles and permission matrix', 1),
            ('settings',  'Company Settings',      'Company profile, GST config, gateway config, feature toggles', 1),
            ('payroll',   'Payroll Management',    'Employees, salary components, structures, payslips', 1),
            ('visits',    'Shop Check-In',         'GPS check-in records for sales visits', 1),
            ('expenses',  'Expenses',              'Expense claim submission and approval', 1),
            ('attendance', 'Attendance',            'Daily check-in and check-out logs', 1),
            ('gst',       'GST Return Filing',     'File and view GST return periods', 1),
            ('customers', 'Customer Directory & Profiles', 'Customer directory, shop profiles, GPS tagging, owner media & photos', 1),
            ('sync',      'Tally Sync Agent',      'Desktop Sync Agent: push Tally data, pull and acknowledge the outbound queue', 1)
        """))
        db.commit()
        print("Modules seeded successfully.")
    else:
        # Ensure 'gst' module exists on update
        gst_exists = db.execute(text("SELECT COUNT(*) FROM modules WHERE code = 'gst'")).scalar()
        if gst_exists == 0:
            print("Adding missing 'gst' module...")
            db.execute(text("""
                INSERT INTO modules (code, name, description, is_system)
                VALUES ('gst', 'GST Return Filing', 'File and view GST return periods', 1)
            """))
            db.commit()

        # Ensure 'sync' module exists on update (Desktop Sync Agent endpoints)
        sync_exists = db.execute(text("SELECT COUNT(*) FROM modules WHERE code = 'sync'")).scalar()
        if sync_exists == 0:
            print("Adding missing 'sync' module...")
            db.execute(text("""
                INSERT INTO modules (code, name, description, is_system)
                VALUES ('sync', 'Tally Sync Agent', 'Desktop Sync Agent: push Tally data, pull and acknowledge the outbound queue', 1)
            """))
            db.commit()

        # Ensure 'outstanding' module exists on update. It used to ride on 'payments', which field staff
        # need for collecting, so it is its own module now and only admins start with it.
        outstanding_exists = db.execute(text("SELECT COUNT(*) FROM modules WHERE code = 'outstanding'")).scalar()
        if outstanding_exists == 0:
            print("Adding missing 'outstanding' module...")
            db.execute(text("""
                INSERT INTO modules (code, name, description, is_system)
                VALUES ('outstanding', 'Outstanding & Reminders', 'Customer dues, aging and payment reminders', 1)
            """))
            db.commit()

        # Ensure 'customers' module exists on update
        cust_exists = db.execute(text("SELECT COUNT(*) FROM modules WHERE code = 'customers'")).scalar()
        if cust_exists == 0:
            print("Adding missing 'customers' module...")
            db.execute(text("""
                INSERT INTO modules (code, name, description, is_system)
                VALUES ('customers', 'Customer Directory & Profiles', 'Customer directory, shop profiles, GPS tagging, owner media & photos', 1)
            """))
            db.commit()

    # 3. Seed Default Permissions Matrix
    permissions_exist = db.execute(text("SELECT COUNT(*) FROM permissions")).scalar()
    
    # Get roles mapping name -> id
    roles = {r[1]: r[0] for r in db.execute(text("SELECT role_id, name FROM roles")).all()}
    # Get modules mapping code -> id
    modules = {m[1]: m[0] for m in db.execute(text("SELECT module_id, code FROM modules")).all()}

    if permissions_exist == 0:
        print("Seeding permissions matrix...")
        
        # Admin gets full CRUD on all modules
        if 'Admin' in roles:
            for mod_code, mod_id in modules.items():
                db.execute(text(f"""
                    INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({roles['Admin']}, {mod_id}, 1, 1, 1, 1)
                """))
            
        # Sales role permissions (check-in/visits, payments, orders, attendance, customers)
        sales_role_id = roles.get('Sales') or roles.get('User')
        if sales_role_id:
            user_perms = {
                'visits': (1, 1, 1, 1),
                'payments': (1, 1, 1, 1),
                'orders': (1, 1, 1, 1),
                'attendance': (1, 1, 1, 1),
                'customers': (1, 1, 1, 0),
            }
            for mod_code, (c, r, u, d) in user_perms.items():
                if mod_code in modules:
                    db.execute(text(f"""
                        INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                        VALUES ({sales_role_id}, {modules[mod_code]}, {c}, {r}, {u}, {d})
                    """))
                
        db.commit()
        print("Permissions matrix seeded successfully.")
    else:
        # Ensure Admin role has permission for 'gst' if it was just added
        if 'Admin' in roles and 'gst' in modules:
            admin_role_id = roles['Admin']
            gst_mod_id = modules['gst']
            gst_perm_exists = db.execute(text(f"""
                SELECT COUNT(*) FROM permissions 
                WHERE role_id = {admin_role_id} AND module_id = {gst_mod_id}
            """)).scalar()
            if gst_perm_exists == 0:
                print("Seeding Admin permission for new 'gst' module...")
                db.execute(text(f"""
                    INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({admin_role_id}, {gst_mod_id}, 1, 1, 1, 1)
                """))
                db.commit()

        # Admin gets full access to 'sync'; other roles must be granted it explicitly
        if 'Admin' in roles and 'sync' in modules:
            admin_sync_exists = db.execute(text(f"""
                SELECT COUNT(*) FROM permissions
                WHERE role_id = {roles['Admin']} AND module_id = {modules['sync']}
            """)).scalar()
            if admin_sync_exists == 0:
                print("Seeding Admin permission for new 'sync' module...")
                db.execute(text(f"""
                    INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({roles['Admin']}, {modules['sync']}, 1, 1, 1, 1)
                """))
                db.commit()

        # Admin gets full access to 'outstanding'; other roles must be granted it explicitly
        if 'Admin' in roles and 'outstanding' in modules:
            admin_outstanding_exists = db.execute(text(f"""
                SELECT COUNT(*) FROM permissions
                WHERE role_id = {roles['Admin']} AND module_id = {modules['outstanding']}
            """)).scalar()
            if admin_outstanding_exists == 0:
                db.execute(text(f"""
                    INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({roles['Admin']}, {modules['outstanding']}, 1, 1, 1, 1)
                """))
                db.commit()

        # Ensure permissions exist for 'customers' module
        if 'customers' in modules:
            cust_mod_id = modules['customers']
            if 'Admin' in roles:
                admin_role_id = roles['Admin']
                admin_cust_exists = db.execute(text(f"""
                    SELECT COUNT(*) FROM permissions 
                    WHERE role_id = {admin_role_id} AND module_id = {cust_mod_id}
                """)).scalar()
                if admin_cust_exists == 0:
                    db.execute(text(f"""
                        INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                        VALUES ({admin_role_id}, {cust_mod_id}, 1, 1, 1, 1)
                    """))
                    db.commit()

            sales_role_id = roles.get('Sales') or roles.get('User')
            if sales_role_id:
                sales_cust_exists = db.execute(text(f"""
                    SELECT COUNT(*) FROM permissions 
                    WHERE role_id = {sales_role_id} AND module_id = {cust_mod_id}
                """)).scalar()
                if sales_cust_exists == 0:
                    db.execute(text(f"""
                        INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                        VALUES ({sales_role_id}, {cust_mod_id}, 1, 1, 1, 0)
                    """))
                    db.commit()

def ensure_admin_roles_have_every_module(db: Session) -> None:
    """Each account has its own Admin role. When a module is added, every one of them gets full access to it."""
    admin_ids = [row[0] for row in db.execute(text("SELECT role_id FROM roles WHERE LOWER(name) = 'admin'")).all()]
    module_ids = [row[0] for row in db.execute(text("SELECT module_id FROM modules WHERE code <> 'sync_agent'")).all()]
    added = False
    for role_id in admin_ids:
        held = {row[0] for row in db.execute(text("SELECT module_id FROM permissions WHERE role_id = :r"), {"r": role_id}).all()}
        for module_id in module_ids:
            if module_id not in held:
                db.execute(text("INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete) "
                                "VALUES (:r, :m, 1, 1, 1, 1)"), {"r": role_id, "m": module_id})
                added = True
    if added:
        db.commit()


def seed_company_defaults(db: Session, company_id: int, commit: bool = True):
    """
    Seeds company-specific defaults (account groups, voucher types)
    for a newly created company. Pass commit=False to keep it inside the caller's transaction.
    """
    current_dir = os.path.dirname(__file__)
    seed_file_path = os.path.abspath(os.path.join(current_dir, 'seed_defaults.sql'))
    
    if not os.path.exists(seed_file_path):
        raise FileNotFoundError(f"Seed defaults SQL file not found at: {seed_file_path}")
        
    with open(seed_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
        
    statements = []
    current_stmt = []
    for line in sql_content.split('\n'):
        stripped = line.split('--')[0].strip()
        if not stripped or stripped.startswith('SET '):
            continue
        current_stmt.append(stripped)
        if stripped.endswith(';'):
            statements.append(' '.join(current_stmt))
            current_stmt = []
    from app.core.config import settings
    db.execute(text(f"USE {settings.TALLY_DATABASE_NAME};"))
    db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    for statement in statements:
        stmt = statement.strip()
        if stmt and ('account_groups' in stmt or 'voucher_types' in stmt):
            stmt = stmt.replace('@company_id', str(company_id))
            db.execute(text(stmt))
            
    db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    # Restore the connection's default schema; pooled connections are reused by unrelated requests
    db.execute(text(f"USE {settings.PORTAL_DATABASE_NAME};"))
    if commit:
        db.commit()
    print(f"Company {company_id} defaults seeded successfully.")

if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from dotenv import load_dotenv
    
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    db_url = os.getenv("DATABASE_URL")
    if db_url and "mysql+aiomysql://" in db_url:
        db_url = db_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        
    if not db_url:
        print("DATABASE_URL not set in .env")
        exit(1)
        
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        seed_global_data(db)
    finally:
        db.close()
