import os
from sqlalchemy import text
from sqlalchemy.orm import Session

def seed_global_data(db: Session):
    """
    Seeds global tables (like roles, modules, and permissions) that do not depend on a specific company.
    """
    # 1. Seed Roles
    roles_exist = db.execute(text("SELECT COUNT(*) FROM roles")).scalar()
    if roles_exist == 0:
        print("Seeding default roles...")
        db.execute(text("""
            INSERT INTO roles (name, description) VALUES
            ('Admin', 'Full access to all modules including user management'),
            ('User', 'Standard user with check-in, payments, orders, and attendance access')
        """))
        db.commit()
        print("Roles seeded successfully.")
    
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
            ('reports',   'Reports',               'Trial Balance, P&L, Balance Sheet, GST reports', 1),
            ('users',     'User Management',       'Create/manage users', 1),
            ('roles',     'Roles & Permissions',   'Manage roles and permission matrix', 1),
            ('settings',  'Company Settings',      'Company profile, GST config, gateway config, feature toggles', 1),
            ('payroll',   'Payroll Management',    'Employees, salary components, structures, payslips', 1),
            ('visits',    'Shop Check-In',         'GPS check-in records for sales visits', 1),
            ('expenses',  'Expenses',              'Expense claim submission and approval', 1),
            ('attendance', 'Attendance',            'Daily check-in and check-out logs', 1),
            ('gst',       'GST Return Filing',     'File and view GST return periods', 1)
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

    # 3. Seed Default Permissions Matrix
    permissions_exist = db.execute(text("SELECT COUNT(*) FROM permissions")).scalar()
    
    # Get roles mapping name -> id
    roles = {r[1]: r[0] for r in db.execute(text("SELECT role_id, name FROM roles")).all()}
    # Get modules mapping code -> id
    modules = {m[1]: m[0] for m in db.execute(text("SELECT module_id, code FROM modules")).all()}

    if permissions_exist == 0:
        print("Seeding permissions matrix...")
        
        # Admin gets full CRUD on all modules
        for mod_code, mod_id in modules.items():
            db.execute(text(f"""
                INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                VALUES ({roles['Admin']}, {mod_id}, 1, 1, 1, 1)
            """))
            
        # User role permissions (check-in/visits, payments, orders, attendance)
        user_perms = {
            'visits': (1, 1, 1, 1),
            'payments': (1, 1, 1, 1),
            'orders': (1, 1, 1, 1),
            'attendance': (1, 1, 1, 1),
        }
        for mod_code, (c, r, u, d) in user_perms.items():
            if mod_code in modules:
                db.execute(text(f"""
                    INSERT INTO permissions (role_id, module_id, can_create, can_read, can_update, can_delete)
                    VALUES ({roles['User']}, {modules[mod_code]}, {c}, {r}, {u}, {d})
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

def seed_company_defaults(db: Session, company_id: int):
    """
    Seeds company-specific defaults (account groups, voucher types)
    for a newly created company.
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
