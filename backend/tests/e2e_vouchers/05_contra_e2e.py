import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_contra_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 5: CONTRA (CASH/BANK TRANSFERS) LIFECYCLE")
    print("="*80)

    bank_id = masters.data["bank_ledger_id"]
    cash_id = masters.data["cash_ledger_id"]
    vt_contra_id = masters.voucher_types_map.get("Contra", 2)

    # 1. CREATE: Cash Deposit (Bank Dr 50,000, Cash Cr 50,000)
    deposit_payload = {
        "voucher_type_id": vt_contra_id,
        "voucher_date": "2026-03-01",
        "reference_number": "E2E-CTR-DEP-001",
        "narration": "E2E Cash Deposit into HDFC Bank Account",
        "status": "confirmed",
        "entries": [
            {
                "ledger_id": bank_id,
                "debit_amount": 50000.0,
                "credit_amount": 0.0,
                "entry_narration": "HDFC Deposit",
                "bank_allocations": [
                    {
                        "transaction_type": "Deposit",
                        "instrument_date": "2026-03-01",
                        "amount": 50000.0
                    }
                ]
            },
            {
                "ledger_id": cash_id,
                "debit_amount": 0.0,
                "credit_amount": 50000.0,
                "entry_narration": "Cash Deposited"
            }
        ]
    }

    resp_dep = await client.request(
        "POST", "/vouchers",
        step_name="Post Cash Deposit Contra Voucher",
        json_data=deposit_payload,
        expected_status=201,
        assertion_desc="Contra deposit created with 201 status"
    )
    c1_id = resp_dep["voucher_id"]
    masters.created_masters["vouchers"].append(c1_id)

    # 2. CREATE: Cash Withdrawal (Cash Dr 20,000, Bank Cr 20,000)
    withdrawal_payload = {
        "voucher_type_id": vt_contra_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-CTR-WDL-002",
        "narration": "E2E Cash Withdrawal for Petty Expenses",
        "status": "confirmed",
        "entries": [
            {
                "ledger_id": cash_id,
                "debit_amount": 20000.0,
                "credit_amount": 0.0,
                "entry_narration": "Cash In Hand"
            },
            {
                "ledger_id": bank_id,
                "debit_amount": 0.0,
                "credit_amount": 20000.0,
                "entry_narration": "Self Cheque Withdrawal",
                "bank_allocations": [
                    {
                        "transaction_type": "Cheque/DD",
                        "instrument_number": "CHQ-SELF-01",
                        "instrument_date": "2026-03-02",
                        "payment_favouring": "Self",
                        "amount": 20000.0
                    }
                ]
            }
        ]
    }

    resp_wdl = await client.request(
        "POST", "/vouchers",
        step_name="Post Cash Withdrawal Contra Voucher",
        json_data=withdrawal_payload,
        expected_status=201
    )
    c2_id = resp_wdl["voucher_id"]
    masters.created_masters["vouchers"].append(c2_id)

    # 3. UPDATE / ALTER: Alter Deposit amount from 50,000 to 75,000
    deposit_payload["entries"][0]["debit_amount"] = 75000.0
    deposit_payload["entries"][0]["bank_allocations"][0]["amount"] = 75000.0
    deposit_payload["entries"][1]["credit_amount"] = 75000.0

    await client.request(
        "PUT", f"/vouchers/{c1_id}",
        step_name="Alter Contra Deposit (50,000 -> 75,000)",
        json_data=deposit_payload,
        expected_status=200
    )

    # 4. DELETE: Delete Withdrawal Voucher
    await client.request(
        "DELETE", f"/vouchers/{c2_id}",
        step_name="Delete Contra Withdrawal Voucher",
        expected_status=200
    )
    masters.created_masters["vouchers"].remove(c2_id)

    print("  [SUCCESS] Contra Vouchers E2E Lifecycle Verified.\n")
    return {"contra_voucher_id": c1_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Contra E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_contra_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
