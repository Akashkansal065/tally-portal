import os
import sys
from decimal import Decimal
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

def normalize_string(val):
    if val is None:
        return ""
    return " ".join(val.strip().lower().split())

def main():
    print("=" * 60)
    print(" TALLY DATABASE COMPARISON TOOL")
    print("=" * 60)

    # 1. Load database connections
    backend_env = load_env_file("/Users/akashkansal/Documents/Github/MyTally/backend/.env")
    tally_web_env = load_env_file("/Users/akashkansal/Documents/Github/tally-web/.env.local")
    
    mysql_url = backend_env.get("DATABASE_URL")
    if mysql_url and "mysql+aiomysql" in mysql_url:
        mysql_url = mysql_url.replace("mysql+aiomysql", "mysql+pymysql")
        
    pg_url = tally_web_env.get("DATABASE_URL")
    
    if not mysql_url or not pg_url:
        print("Error: Could not load connection strings from .env files.")
        return
        
    try:
        mysql_engine = create_engine(mysql_url)
        pg_engine = create_engine(pg_url)
    except Exception as e:
        print(f"Error creating db engines: {e}")
        return

    with mysql_engine.connect() as mysql_conn, pg_engine.connect() as pg_conn:
        
        # -------------------------------------------------------------
        # 1. COMPARE LEDGERS
        # -------------------------------------------------------------
        print("\n--- Comparing Ledgers (MySQL: ledgers vs Postgres: mst_ledger) ---")
        
        # Fetch MySQL ledgers
        mysql_ledgers = {}
        # We need to map group_id to group name
        groups_res = mysql_conn.execute(text("SELECT group_id, name FROM account_groups")).fetchall()
        mysql_groups = {g[0]: g[1] for g in groups_res}
        
        ledgers_res = mysql_conn.execute(text("SELECT ledger_id, name, group_id, opening_balance, opening_balance_type, gstin, address, state, tally_guid FROM ledgers")).fetchall()
        for r in ledgers_res:
            guid = r[8]
            if not guid:
                continue
            mysql_ledgers[guid] = {
                "ledger_id": r[0],
                "name": r[1],
                "group_name": mysql_groups.get(r[2], ""),
                "opening_balance": r[3],
                "opening_balance_type": r[4],
                "gstin": r[5],
                "address": r[6],
                "state": r[7]
            }
            
        # Fetch Postgres ledgers
        pg_ledgers = {}
        pg_ledgers_res = pg_conn.execute(text("SELECT guid, name, parent, opening_balance, gstn, mailing_address, mailing_state FROM mst_ledger")).fetchall()
        for r in pg_ledgers_res:
            guid = r[0]
            pg_ledgers[guid] = {
                "name": r[1],
                "group_name": r[2],
                "opening_balance": r[3],
                "gstin": r[4],
                "address": r[5],
                "state": r[6]
            }
            
        # Compare
        all_guids = set(mysql_ledgers.keys()) | set(pg_ledgers.keys())
        ledger_mismatches = []
        ledger_missing_mysql = []
        ledger_missing_pg = []
        
        for guid in all_guids:
            if guid not in mysql_ledgers:
                ledger_missing_mysql.append((guid, pg_ledgers[guid]['name']))
                continue
            if guid not in pg_ledgers:
                ledger_missing_pg.append((guid, mysql_ledgers[guid]['name']))
                continue
                
            m = mysql_ledgers[guid]
            p = pg_ledgers[guid]
            
            diffs = []
            if normalize_string(m["name"]) != normalize_string(p["name"]):
                diffs.append(f"Name: MySQL='{m['name']}' vs Postgres='{p['name']}'")
                
            # Normalize group name comparison (Tally is case-insensitive)
            if normalize_string(m["group_name"]) != normalize_string(p["group_name"]):
                diffs.append(f"Group: MySQL='{m['group_name']}' vs Postgres='{p['group_name']}'")
                
            # Opening balance conversion: MySQL Dr -> negative, Cr -> positive
            m_val = Decimal(m["opening_balance"] or 0)
            if m["opening_balance_type"] == "Dr":
                m_val = -m_val
            p_val = Decimal(p["opening_balance"] or 0)
            if abs(m_val - p_val) > Decimal("0.01"):
                diffs.append(f"Opening Balance: MySQL={m_val} vs Postgres={p_val}")
                
            if normalize_string(m["gstin"]) != normalize_string(p["gstin"]):
                diffs.append(f"GSTIN: MySQL='{m['gstin']}' vs Postgres='{p['gstin']}'")
                
            # Clean/strip address strings for comparison
            m_addr = m["address"] or ""
            p_addr = p["address"] or ""
            if " | Mobile:" in m_addr:
                m_addr = m_addr.split(" | Mobile:")[0] # Strip mobile suffix from MyTally
            if normalize_string(m_addr) != normalize_string(p_addr):
                # Only report if they are substantially different (not just spacing)
                if abs(len(normalize_string(m_addr)) - len(normalize_string(p_addr))) > 5:
                    diffs.append(f"Address: MySQL='{m['address']}' vs Postgres='{p['address']}'")
                
            if normalize_string(m["state"]) != normalize_string(p["state"]):
                diffs.append(f"State: MySQL='{m['state']}' vs Postgres='{p['state']}'")
                
            if diffs:
                ledger_mismatches.append((guid, m["ledger_id"], m["name"], diffs))
                
        print(f"Total matched GUIDs: {len(all_guids) - len(ledger_missing_mysql) - len(ledger_missing_pg)}")
        print(f"Missing in MySQL (present in Postgres): {len(ledger_missing_mysql)}")
        for guid, name in ledger_missing_mysql[:5]:
            print(f"  - GUID: {guid}, Name: {name}")
        if len(ledger_missing_mysql) > 5:
            print(f"  ... and {len(ledger_missing_mysql)-5} more")
            
        print(f"Missing in Postgres (present in MySQL): {len(ledger_missing_pg)}")
        for guid, name in ledger_missing_pg[:5]:
            print(f"  - GUID: {guid}, Name: {name}")
        if len(ledger_missing_pg) > 5:
            print(f"  ... and {len(ledger_missing_pg)-5} more")
            
        print(f"Mismatched attributes for same GUID: {len(ledger_mismatches)}")
        for guid, row_id, name, diffs in ledger_mismatches[:5]:
            print(f"  - Ledger ID: {row_id}, Name: {name} (GUID: {guid})")
            for d in diffs:
                print(f"    * {d}")
        if len(ledger_mismatches) > 5:
            print(f"  ... and {len(ledger_mismatches)-5} more")

        # -------------------------------------------------------------
        # 2. COMPARE VOUCHERS
        # -------------------------------------------------------------
        print("\n--- Comparing Vouchers (MySQL: vouchers vs Postgres: trn_voucher) ---")
        
        # Fetch MySQL vouchers
        mysql_vouchers = {}
        vouchers_res = mysql_conn.execute(text("SELECT voucher_id, voucher_number, voucher_date, narration, total_amount, tally_guid FROM vouchers")).fetchall()
        for r in vouchers_res:
            guid = r[5]
            if not guid:
                continue
            mysql_vouchers[guid] = {
                "voucher_id": r[0],
                "voucher_number": r[1],
                "voucher_date": r[2],
                "narration": r[3],
                "total_amount": r[4]
            }
            
        # Fetch Postgres vouchers
        pg_vouchers = {}
        pg_vouchers_res = pg_conn.execute(text("SELECT guid, voucher_number, date, narration FROM trn_voucher")).fetchall()
        for r in pg_vouchers_res:
            guid = r[0]
            pg_vouchers[guid] = {
                "voucher_number": r[1],
                "voucher_date": r[2],
                "narration": r[3]
            }
            
        all_v_guids = set(mysql_vouchers.keys()) | set(pg_vouchers.keys())
        v_mismatches = []
        v_missing_mysql = []
        v_missing_pg = []
        
        for guid in all_v_guids:
            if guid not in mysql_vouchers:
                v_missing_mysql.append((guid, pg_vouchers[guid]['voucher_number']))
                continue
            if guid not in pg_vouchers:
                v_missing_pg.append((guid, mysql_vouchers[guid]['voucher_number']))
                continue
                
            m = mysql_vouchers[guid]
            p = pg_vouchers[guid]
            
            diffs = []
            if normalize_string(m["voucher_number"]) != normalize_string(p["voucher_number"]):
                diffs.append(f"Number: MySQL='{m['voucher_number']}' vs Postgres='{p['voucher_number']}'")
                
            # Compare dates
            if str(m["voucher_date"]) != str(p["voucher_date"]):
                diffs.append(f"Date: MySQL='{m['voucher_date']}' vs Postgres='{p['voucher_date']}'")
                
            if normalize_string(m["narration"]) != normalize_string(p["narration"]):
                # Some narration text length differences might be due to truncation or format
                if abs(len(normalize_string(m["narration"] or "")) - len(normalize_string(p["narration"] or ""))) > 5:
                    diffs.append(f"Narration: MySQL='{m['narration']}' vs Postgres='{p['narration']}'")
                    
            if diffs:
                v_mismatches.append((guid, m["voucher_id"], m["voucher_number"], diffs))
                
        print(f"Total matched GUIDs: {len(all_v_guids) - len(v_missing_mysql) - len(v_missing_pg)}")
        print(f"Missing in MySQL (present in Postgres): {len(v_missing_mysql)}")
        for guid, num in v_missing_mysql[:5]:
            print(f"  - GUID: {guid}, Number: {num}")
        if len(v_missing_mysql) > 5:
            print(f"  ... and {len(v_missing_mysql)-5} more")
            
        print(f"Missing in Postgres (present in MySQL): {len(v_missing_pg)}")
        for guid, num in v_missing_pg[:5]:
            print(f"  - GUID: {guid}, Number: {num}")
        if len(v_missing_pg) > 5:
            print(f"  ... and {len(v_missing_pg)-5} more")
            
        print(f"Mismatched attributes for same GUID: {len(v_mismatches)}")
        for guid, row_id, num, diffs in v_mismatches[:5]:
            print(f"  - Voucher ID: {row_id}, Number: {num} (GUID: {guid})")
            for d in diffs:
                print(f"    * {d}")
        if len(v_mismatches) > 5:
            print(f"  ... and {len(v_mismatches)-5} more")

        # -------------------------------------------------------------
        # 3. COMPARE VOUCHER ENTRIES / ACCOUNTING ROWS
        # -------------------------------------------------------------
        print("\n--- Comparing Voucher Entries (MySQL: voucher_entries vs Postgres: trn_accounting) ---")
        
        # Load ledger names in MySQL
        ledgers_res = mysql_conn.execute(text("SELECT ledger_id, name FROM ledgers")).fetchall()
        mysql_ledger_names = {l[0]: l[1] for l in ledgers_res}
        
        # Get MySQL voucher entries grouped by voucher GUID
        mysql_entries = {}
        entries_res = mysql_conn.execute(text("""
            SELECT v.tally_guid, ve.ledger_id, ve.debit_amount, ve.credit_amount 
            FROM voucher_entries ve
            JOIN vouchers v ON ve.voucher_id = v.voucher_id
            WHERE v.tally_guid IS NOT NULL
        """)).fetchall()
        
        for r in entries_res:
            v_guid = r[0]
            ledger_name = mysql_ledger_names.get(r[1], "")
            deb = Decimal(r[2] or 0)
            cred = Decimal(r[3] or 0)
            
            # Map debit to negative, credit to positive
            amount = cred - deb if cred > 0 else -deb
            
            if v_guid not in mysql_entries:
                mysql_entries[v_guid] = []
            mysql_entries[v_guid].append((normalize_string(ledger_name), amount))
            
        # Get Postgres accounting entries grouped by voucher GUID
        pg_entries = {}
        pg_entries_res = pg_conn.execute(text("SELECT guid, ledger, amount FROM trn_accounting")).fetchall()
        for r in pg_entries_res:
            v_guid = r[0]
            ledger_name = r[1]
            amount = Decimal(r[2] or 0)
            
            if v_guid not in pg_entries:
                pg_entries[v_guid] = []
            pg_entries[v_guid].append((normalize_string(ledger_name), amount))
            
        entry_mismatches = 0
        matching_v_entries = 0
        
        # Only compare vouchers that exist in both sets
        common_v_guids = set(mysql_entries.keys()) & set(pg_entries.keys())
        for guid in common_v_guids:
            m_list = sorted(mysql_entries[guid], key=lambda x: (x[0], x[1]))
            p_list = sorted(pg_entries[guid], key=lambda x: (x[0], x[1]))
            
            # Helper to match lists of entries with slight tolerances for decimals
            list_matches = True
            if len(m_list) != len(p_list):
                list_matches = False
            else:
                for idx in range(len(m_list)):
                    m_led, m_amt = m_list[idx]
                    p_led, p_amt = p_list[idx]
                    if m_led != p_led or abs(m_amt - p_amt) > Decimal("0.02"):
                        list_matches = False
                        break
                        
            if not list_matches:
                entry_mismatches += 1
                if entry_mismatches <= 5:
                    print(f"  - Entry mismatch for Voucher GUID: {guid}")
                    print("    MySQL entries:")
                    for led, amt in m_list:
                        print(f"      * {led}: {amt}")
                    print("    Postgres entries:")
                    for led, amt in p_list:
                        print(f"      * {led}: {amt}")
            else:
                matching_v_entries += 1
                
        print(f"Vouchers with perfectly matching accounting entries: {matching_v_entries}")
        print(f"Vouchers with mismatched accounting entries: {entry_mismatches}")

if __name__ == "__main__":
    main()
