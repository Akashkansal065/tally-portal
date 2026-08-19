import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_receipt_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 4: RECEIPT & DEBTOR SETTLEMENT LIFECYCLE")
    print("="*80)

    debtor_id = masters.data["debtor_ledger_id"]
    sales_ledger_id = masters.data["sales_ledger_id"]
    bank_id = masters.data["bank_ledger_id"]
    cash_id = masters.data["cash_ledger_id"]
    vt_sales_id = masters.voucher_types_map.get("Sales", 22)
    vt_receipt_id = masters.voucher_types_map.get("Receipt", 17)

    # 1. Create Baseline Sales Voucher with Bill Reference 'E2E-SAL-RCP-001' for 150,000.00
    print("  [*] Creating baseline Sales Bill (150,000.00 INR)...")
    bill_ref = "E2E-SAL-RCP-001"
    sales_resp = await client.request(
        "POST", "/vouchers",
        step_name="Create Baseline Sales Bill",
        json_data={
            "voucher_type_id": vt_sales_id,
            "voucher_date": "2026-03-01",
            "reference_number": bill_ref,
            "narration": "Baseline Sales for Receipt Settlements",
            "status": "confirmed",
            "party_ledger_id": debtor_id,
            "entries": [
                {
                    "ledger_id": debtor_id,
                    "debit_amount": 150000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Sundry Debtor Receivable",
                    "bill_allocations": [
                        {
                            "bill_reference": bill_ref,
                            "allocation_type": "New Ref",
                            "amount": 150000.0
                        }
                    ]
                },
                {
                    "ledger_id": sales_ledger_id,
                    "debit_amount": 0.0,
                    "credit_amount": 150000.0,
                    "entry_narration": "Domestic Sales"
                }
            ]
        },
        expected_status=201
    )
    s_id = sales_resp["voucher_id"]
    masters.created_masters["vouchers"].append(s_id)

    # 2. CREATE: Bank Receipt Voucher (100,000 INR) with Bank Allocation & Bill Settlement (Against Ref)
    receipt_payload_1 = {
        "voucher_type_id": vt_receipt_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-RCP-BNK-001",
        "narration": "E2E Bank Receipt via Direct Deposit",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "entries": [
            {
                "ledger_id": bank_id,
                "debit_amount": 100000.0,
                "credit_amount": 0.0,
                "entry_narration": "HDFC Direct Deposit",
                "bank_allocations": [
                    {
                        "transaction_type": "Inter Bank Transfer",
                        "instrument_number": "NEFT-998877",
                        "instrument_date": "2026-03-02",
                        "payment_favouring": "Alpha Retailers Corp",
                        "amount": 100000.0
                    }
                ]
            },
            {
                "ledger_id": debtor_id,
                "debit_amount": 0.0,
                "credit_amount": 100000.0,
                "entry_narration": "Settlement of Sales Invoice",
                "bill_allocations": [
                    {
                        "bill_reference": bill_ref,
                        "allocation_type": "Against Ref",
                        "amount": 100000.0
                    }
                ]
            }
        ]
    }

    resp_rcp1 = await client.request(
        "POST", "/vouchers",
        step_name="Post Bank Receipt Voucher (Against Ref)",
        json_data=receipt_payload_1,
        expected_status=201,
        assertion_desc="Receipt voucher created with bank and bill allocation"
    )
    rcp1_id = resp_rcp1["voucher_id"]
    masters.created_masters["vouchers"].append(rcp1_id)

    # 3. CREATE: Advance Receipt Voucher (50,000 INR with Advance bill allocation)
    advance_payload = {
        "voucher_type_id": vt_receipt_id,
        "voucher_date": "2026-03-03",
        "reference_number": "E2E-RCP-ADV-002",
        "narration": "E2E Customer Advance Deposit",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "entries": [
            {
                "ledger_id": bank_id,
                "debit_amount": 50000.0,
                "credit_amount": 0.0,
                "entry_narration": "Customer Advance in HDFC",
                "bank_allocations": [
                    {
                        "transaction_type": "Inter Bank Transfer",
                        "instrument_number": "IMPS-554433",
                        "instrument_date": "2026-03-03",
                        "amount": 50000.0
                    }
                ]
            },
            {
                "ledger_id": debtor_id,
                "debit_amount": 0.0,
                "credit_amount": 50000.0,
                "entry_narration": "Advance from Debtor",
                "bill_allocations": [
                    {
                        "bill_reference": "E2E-ADV-REF-001",
                        "allocation_type": "Advance",
                        "amount": 50000.0
                    }
                ]
            }
        ]
    }

    resp_adv = await client.request(
        "POST", "/vouchers",
        step_name="Post Advance Customer Receipt",
        json_data=advance_payload,
        expected_status=201
    )
    adv_id = resp_adv["voucher_id"]
    masters.created_masters["vouchers"].append(adv_id)

    # 4. CREATE: Cash Receipt Voucher (50,000 INR settling remaining bill balance)
    cash_rcp_payload = {
        "voucher_type_id": vt_receipt_id,
        "voucher_date": "2026-03-04",
        "reference_number": "E2E-RCP-CSH-003",
        "narration": "E2E Final Cash Settlement for Sales Bill",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "entries": [
            {
                "ledger_id": cash_id,
                "debit_amount": 50000.0,
                "credit_amount": 0.0,
                "entry_narration": "Counter Cash Receipt"
            },
            {
                "ledger_id": debtor_id,
                "debit_amount": 0.0,
                "credit_amount": 50000.0,
                "entry_narration": "Full Settlement",
                "bill_allocations": [
                    {
                        "bill_reference": bill_ref,
                        "allocation_type": "Against Ref",
                        "amount": 50000.0
                    }
                ]
            }
        ]
    }

    resp_cash = await client.request(
        "POST", "/vouchers",
        step_name="Post Final Cash Receipt Voucher",
        json_data=cash_rcp_payload,
        expected_status=201
    )
    cash_id_v = resp_cash["voucher_id"]
    masters.created_masters["vouchers"].append(cash_id_v)

    # 5. UPDATE / ALTER: Alter Receipt #1
    receipt_payload_1["entries"][0]["debit_amount"] = 80000.0
    receipt_payload_1["entries"][0]["bank_allocations"][0]["amount"] = 80000.0
    receipt_payload_1["entries"][1]["credit_amount"] = 80000.0
    receipt_payload_1["entries"][1]["bill_allocations"][0]["amount"] = 80000.0

    await client.request(
        "PUT", f"/vouchers/{rcp1_id}",
        step_name="Alter Bank Receipt #1 (100,000 -> 80,000)",
        json_data=receipt_payload_1,
        expected_status=200
    )

    # 6. DELETE: Delete Advance Receipt
    await client.request(
        "DELETE", f"/vouchers/{adv_id}",
        step_name="Delete Advance Receipt Voucher",
        expected_status=200
    )
    masters.created_masters["vouchers"].remove(adv_id)

    print("  [SUCCESS] Receipt & Debtor Settlement E2E Lifecycle Verified.\n")
    return {"receipt_voucher_id": rcp1_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Receipt E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_receipt_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
