import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_payment_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 3: PAYMENT & BANK ALLOCATIONS LIFECYCLE")
    print("="*80)

    creditor_id = masters.data["creditor_ledger_id"]
    purchase_ledger_id = masters.data["purchase_ledger_id"]
    bank_id = masters.data["bank_ledger_id"]
    cash_id = masters.data["cash_ledger_id"]
    vt_purchase_id = masters.voucher_types_map.get("Purchase", 15)
    vt_payment_id = masters.voucher_types_map.get("Payment", 12)

    # 1. Create Baseline Purchase Voucher with Bill Reference 'E2E-PUR-PAY-001' for 100,000.00
    print("  [*] Creating baseline Purchase Bill (100,000.00 INR)...")
    bill_ref = "E2E-PUR-PAY-001"
    purch_resp = await client.request(
        "POST", "/vouchers",
        step_name="Create Baseline Purchase Bill",
        json_data={
            "voucher_type_id": vt_purchase_id,
            "voucher_date": "2026-03-01",
            "reference_number": bill_ref,
            "narration": "Baseline Purchase to test Payment Settlements",
            "status": "confirmed",
            "party_ledger_id": creditor_id,
            "entries": [
                {
                    "ledger_id": creditor_id,
                    "debit_amount": 0.0,
                    "credit_amount": 100000.0,
                    "entry_narration": "Creditor Payable",
                    "bill_allocations": [
                        {
                            "bill_reference": bill_ref,
                            "allocation_type": "New Ref",
                            "amount": 100000.0
                        }
                    ]
                },
                {
                    "ledger_id": purchase_ledger_id,
                    "debit_amount": 100000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Purchase Expense"
                }
            ]
        },
        expected_status=201
    )
    p_id = purch_resp["voucher_id"]
    masters.created_masters["vouchers"].append(p_id)

    # 2. CREATE: Bank Payment Voucher (40,000 INR against purchase bill) with Bank Allocations
    payment_payload_1 = {
        "voucher_type_id": vt_payment_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-PYT-BNK-001",
        "narration": "E2E Bank Payment via HDFC Cheque",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "entries": [
            {
                "ledger_id": creditor_id,
                "debit_amount": 40000.0,
                "credit_amount": 0.0,
                "entry_narration": "Payment to Creditor",
                "bill_allocations": [
                    {
                        "bill_reference": bill_ref,
                        "allocation_type": "Against Ref",
                        "amount": 40000.0
                    }
                ]
            },
            {
                "ledger_id": bank_id,
                "debit_amount": 0.0,
                "credit_amount": 40000.0,
                "entry_narration": "HDFC Bank Cheque",
                "bank_allocations": [
                    {
                        "transaction_type": "Cheque/DD",
                        "instrument_number": "CHQ-778899",
                        "instrument_date": "2026-03-02",
                        "payment_favouring": "Zenith Global Supplies Ltd",
                        "cheque_cross_comment": "A/C PAYEE ONLY",
                        "bank_name": "HDFC Bank",
                        "amount": 40000.0
                    }
                ]
            }
        ]
    }

    resp_pyt1 = await client.request(
        "POST", "/vouchers",
        step_name="Post Bank Payment Voucher with Bank Allocations",
        json_data=payment_payload_1,
        expected_status=201,
        assertion_desc="Payment voucher with bank and bill allocation created"
    )
    pyt1_id = resp_pyt1["voucher_id"]
    masters.created_masters["vouchers"].append(pyt1_id)

    # 3. CREATE: Cash Payment Voucher (60,000 INR settling remaining bill balance)
    payment_payload_2 = {
        "voucher_type_id": vt_payment_id,
        "voucher_date": "2026-03-03",
        "reference_number": "E2E-PYT-CSH-002",
        "narration": "E2E Cash Payment to fully settle Creditor Bill",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "entries": [
            {
                "ledger_id": creditor_id,
                "debit_amount": 60000.0,
                "credit_amount": 0.0,
                "entry_narration": "Cash Settlement to Creditor",
                "bill_allocations": [
                    {
                        "bill_reference": bill_ref,
                        "allocation_type": "Against Ref",
                        "amount": 60000.0
                    }
                ]
            },
            {
                "ledger_id": cash_id,
                "debit_amount": 0.0,
                "credit_amount": 60000.0,
                "entry_narration": "Petty Cash on Hand"
            }
        ]
    }

    resp_pyt2 = await client.request(
        "POST", "/vouchers",
        step_name="Post Cash Payment Voucher (Settling Bill)",
        json_data=payment_payload_2,
        expected_status=201
    )
    pyt2_id = resp_pyt2["voucher_id"]
    masters.created_masters["vouchers"].append(pyt2_id)

    # 4. UPDATE / ALTER: Alter Payment #2 amount from 60,000 to 50,000
    payment_payload_2["entries"][0]["debit_amount"] = 50000.0
    payment_payload_2["entries"][0]["bill_allocations"][0]["amount"] = 50000.0
    payment_payload_2["entries"][1]["credit_amount"] = 50000.0

    await client.request(
        "PUT", f"/vouchers/{pyt2_id}",
        step_name="Alter Payment #2 Amount (60,000 -> 50,000)",
        json_data=payment_payload_2,
        expected_status=200
    )

    # 5. DELETE: Delete Payment #2
    await client.request(
        "DELETE", f"/vouchers/{pyt2_id}",
        step_name="Delete Payment Voucher #2",
        expected_status=200,
        assertion_desc="Payment voucher deleted cleanly"
    )
    masters.created_masters["vouchers"].remove(pyt2_id)

    print("  [SUCCESS] Payment & Bank Allocations E2E Lifecycle Verified.\n")
    return {"payment_voucher_id": pyt1_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Payment E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_payment_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
