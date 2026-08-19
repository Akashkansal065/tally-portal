import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_journal_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 6: JOURNAL & COST CENTER ALLOCATIONS LIFECYCLE")
    print("="*80)

    expense_id = masters.data["expense_ledger_id"]
    creditor_id = masters.data["creditor_ledger_id"]
    cgst_id = masters.data["cgst_ledger_id"]
    sgst_id = masters.data["sgst_ledger_id"]
    cost_center_id = masters.data["cost_center_id"]
    vt_journal_id = masters.voucher_types_map.get("Journal", 8)

    # 1. CREATE: Standard Adjustment Journal with Cost Center Allocation (Rent Dr 45,000, Creditor Cr 45,000)
    journal_payload_1 = {
        "voucher_type_id": vt_journal_id,
        "voucher_date": "2026-03-01",
        "reference_number": "E2E-JRN-EXP-001",
        "narration": "E2E Monthly Corporate Office Rent Adjustment with Cost Center",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "entries": [
            {
                "ledger_id": expense_id,
                "cost_center_id": cost_center_id,
                "debit_amount": 45000.0,
                "credit_amount": 0.0,
                "entry_narration": "Office Rent booked to Bangalore HQ Cost Center"
            },
            {
                "ledger_id": creditor_id,
                "debit_amount": 0.0,
                "credit_amount": 45000.0,
                "entry_narration": "Rent Payable"
            }
        ]
    }

    resp_j1 = await client.request(
        "POST", "/vouchers",
        step_name="Post Cost-Center Allocated Journal Voucher",
        json_data=journal_payload_1,
        expected_status=201,
        assertion_desc="Journal created with 201 status"
    )
    j1_id = resp_j1["voucher_id"]
    masters.created_masters["vouchers"].append(j1_id)

    # 2. CREATE: Multi-line Tax Adjustment Journal (Expense 25,000 + CGST 2,250 + SGST 2,250 = Total 29,500)
    journal_payload_2 = {
        "voucher_type_id": vt_journal_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-JRN-TAX-002",
        "narration": "E2E Multi-line Expense & Tax Adjustment Journal",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "entries": [
            {
                "ledger_id": expense_id,
                "cost_center_id": cost_center_id,
                "debit_amount": 25000.0,
                "credit_amount": 0.0,
                "entry_narration": "Direct Operational Expense"
            },
            {
                "ledger_id": cgst_id,
                "debit_amount": 2250.0,
                "credit_amount": 0.0,
                "entry_narration": "Input CGST 9%"
            },
            {
                "ledger_id": sgst_id,
                "debit_amount": 2250.0,
                "credit_amount": 0.0,
                "entry_narration": "Input SGST 9%"
            },
            {
                "ledger_id": creditor_id,
                "debit_amount": 0.0,
                "credit_amount": 29500.0,
                "entry_narration": "Payable to Zenith Supplies"
            }
        ]
    }

    resp_j2 = await client.request(
        "POST", "/vouchers",
        step_name="Post Multi-Line Tax Adjustment Journal Voucher",
        json_data=journal_payload_2,
        expected_status=201
    )
    j2_id = resp_j2["voucher_id"]
    masters.created_masters["vouchers"].append(j2_id)

    # 3. UPDATE / ALTER: Alter Journal #1 Amount (45,000 -> 55,000)
    journal_payload_1["entries"][0]["debit_amount"] = 55000.0
    journal_payload_1["entries"][1]["credit_amount"] = 55000.0

    await client.request(
        "PUT", f"/vouchers/{j1_id}",
        step_name="Alter Journal #1 Amount (45,000 -> 55,000)",
        json_data=journal_payload_1,
        expected_status=200
    )

    # 4. DELETE: Delete Journal #2
    await client.request(
        "DELETE", f"/vouchers/{j2_id}",
        step_name="Delete Journal Voucher #2",
        expected_status=200
    )
    masters.created_masters["vouchers"].remove(j2_id)

    print("  [SUCCESS] Journal & Cost Center Allocations E2E Lifecycle Verified.\n")
    return {"journal_voucher_id": j1_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Journal E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_journal_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
