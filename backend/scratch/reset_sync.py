import os
import sys
from sqlalchemy import create_engine, text

def load_env_file(filepath):
    env = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip("'\"")
                    env[k.strip()] = v
    return env

def main():
    # Load environment variables to get DATABASE_URL
    env = load_env_file(".env" if os.path.exists(".env") else "backend/.env")
    mysql_url = env.get("DATABASE_URL")
    
    if not mysql_url:
        print("Error: DATABASE_URL not found in .env file.")
        sys.exit(1)
        
    # Convert async driver to sync driver for SQLAlchemy script compatibility
    if "mysql+aiomysql" in mysql_url:
        mysql_url = mysql_url.replace("mysql+aiomysql", "mysql+pymysql")
        
    try:
        # Resolve base URL and database names to ensure they exist
        base_url, portal_db = mysql_url.rsplit('/', 1)
        if '?' in portal_db:
            portal_db = portal_db.split('?')[0]
        tally_db = env.get("TALLY_DATABASE_NAME", "tally_sync")
        
        # Connect to MySQL server base to create databases synchronously
        temp_engine = create_engine(base_url)
        with temp_engine.connect() as temp_conn:
            temp_conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {portal_db}"))
            temp_conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {tally_db}"))
        temp_engine.dispose()
        
        engine = create_engine(mysql_url)
        with engine.connect() as conn:
            from app.core.config import settings
            print(f"Connecting and switching to sync database '{settings.TALLY_DATABASE_NAME}'...")
            conn.execute(text(f"USE {settings.TALLY_DATABASE_NAME};"))
            
            # Disable FK checks to allow safe truncation/deletion of Tally-linked tables
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            print("Cleaning up existing Tally-synced vouchers (preserving local GEN- creations)...")
            # Delete bill allocations for Tally synced vouchers
            conn.execute(text("""
                DELETE FROM bill_allocations 
                WHERE voucher_entry_id IN (
                    SELECT entry_id FROM voucher_entries 
                    WHERE voucher_id IN (
                        SELECT voucher_id FROM vouchers 
                        WHERE tally_guid IS NOT NULL AND tally_guid NOT LIKE 'GEN-%%'
                    )
                )
            """))
            
            # Delete voucher entries for Tally synced vouchers
            conn.execute(text("""
                DELETE FROM voucher_entries 
                WHERE voucher_id IN (
                    SELECT voucher_id FROM vouchers 
                    WHERE tally_guid IS NOT NULL AND tally_guid NOT LIKE 'GEN-%%'
                )
            """))
            
            # Delete Tally synced vouchers themselves
            conn.execute(text("""
                DELETE FROM vouchers 
                WHERE tally_guid IS NOT NULL AND tally_guid NOT LIKE 'GEN-%%'
            """))
            
            # Reset ledgers AlterIDs
            print("Resetting ledgers AlterIDs...")
            conn.execute(text("UPDATE ledgers SET tally_alter_id = 0"))
            
            # Reset stock items closing balances to opening values
            print("Resetting stock items closing balances to opening balances...")
            conn.execute(text("""
                UPDATE stock_items 
                SET closing_qty = opening_qty, 
                    closing_rate = opening_rate, 
                    closing_value = opening_qty * opening_rate
            """))
            
            # Re-enable FK checks
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            
            conn.commit()
            print("Success: All Tally-synced voucher data cleared, ledgers AlterIDs reset, and stock closing balances reset to opening values in mytally_db.")
            
    except Exception as e:
        print(f"Error resetting database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
