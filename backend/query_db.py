import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as session:
        # Sundry Debtors
        result_dr = await session.execute(text("""
            SELECT SUM(
                CASE WHEN l.opening_balance_type = 'Dr' THEN COALESCE(l.opening_balance, 0) ELSE -COALESCE(l.opening_balance, 0) END
                + COALESCE(sub.net_bal, 0)
            ) as final_bal
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sundry Debtors'
        """))
        print("Sundry Debtors (Closing Bal Dr):", result_dr.scalar())

        # Sundry Creditors
        result_cr = await session.execute(text("""
            SELECT SUM(
                CASE WHEN l.opening_balance_type = 'Cr' THEN COALESCE(l.opening_balance, 0) ELSE -COALESCE(l.opening_balance, 0) END
                + COALESCE(sub.net_bal, 0)
            ) as final_bal
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sundry Creditors'
        """))
        print("Sundry Creditors (Closing Bal Cr):", result_cr.scalar())

        # Sales Accounts
        result_sales = await session.execute(text("""
            SELECT SUM(
                CASE WHEN l.opening_balance_type = 'Cr' THEN COALESCE(l.opening_balance, 0) ELSE -COALESCE(l.opening_balance, 0) END
                + COALESCE(sub.net_bal, 0)
            ) as final_bal
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sales Accounts'
        """))
        print("Sales Accounts (Closing Bal Cr):", result_sales.scalar())

        # Receipts: Let's see what happens if we sum ALL 'Receipt' vouchers
        result_v_rec = await session.execute(text("""
            SELECT SUM(v.total_amount) 
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            WHERE vt.name = 'Receipt' AND v.is_cancelled = False AND v.is_optional = False
        """))
        print("Total Receipts (Receipt vouchers):", result_v_rec.scalar())

        # Cash / Bank Balances
        result_cash_bank = await session.execute(text("""
            SELECT SUM(
                CASE WHEN l.opening_balance_type = 'Dr' THEN COALESCE(l.opening_balance, 0) ELSE -COALESCE(l.opening_balance, 0) END
                + COALESCE(sub.net_bal, 0)
            ) as final_bal
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name IN ('Cash-in-hand', 'Bank Accounts')
        """))
        print("Cash/Bank (Closing Bal Dr):", result_cash_bank.scalar())

asyncio.run(main())
