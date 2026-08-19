import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_debit_note_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 7: DEBIT NOTE (PURCHASE RETURNS & DISCOUNTS) LIFECYCLE")
    print("="*80)

    stock_item_id = masters.data["stock_item_id"]
    creditor_id = masters.data["creditor_ledger_id"]
    purchase_ledger_id = masters.data["purchase_ledger_id"]
    cgst_id = masters.data["cgst_ledger_id"]
    sgst_id = masters.data["sgst_ledger_id"]
    godown_id = masters.data["godown_blr_id"]
    vt_purchase_id = masters.voucher_types_map.get("Purchase", 15)
    vt_debit_note_id = masters.voucher_types_map.get("Debit Note", 4)

    # 1. Baseline Stock Check
    initial_stock = await masters.get_stock_item_closing_qty(stock_item_id)
    print(f"  [*] Initial stock item quantity: {initial_stock} NOS")

    # 2. Baseline Purchase Voucher (Inward 10 NOS)
    purch_resp = await client.request(
        "POST", "/vouchers",
        step_name="Create Baseline Purchase for Return",
        json_data={
            "voucher_type_id": vt_purchase_id,
            "voucher_date": "2026-03-01",
            "reference_number": "E2E-PUR-RET-001",
            "narration": "Original Purchase for Debit Note Return Test",
            "status": "confirmed",
            "party_ledger_id": creditor_id,
            "is_invoice": True,
            "entries": [
                {
                    "ledger_id": creditor_id,
                    "debit_amount": 0.0,
                    "credit_amount": 236000.0,
                    "entry_narration": "Creditor Payable"
                },
                {
                    "ledger_id": purchase_ledger_id,
                    "debit_amount": 200000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Purchase"
                },
                {
                    "ledger_id": cgst_id,
                    "debit_amount": 18000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Input CGST"
                },
                {
                    "ledger_id": sgst_id,
                    "debit_amount": 18000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Input SGST"
                }
            ],
            "inventory_entries": [
                {
                    "stock_item_id": stock_item_id,
                    "godown_id": godown_id,
                    "quantity": 10.0,
                    "billed_qty": 10.0,
                    "rate": 20000.0,
                    "amount": 200000.0,
                    "is_deemed_positive": True,
                    "accounting_allocations": [
                        {"ledger_id": purchase_ledger_id, "is_deemed_positive": True, "amount": 200000.0},
                        {"ledger_id": cgst_id, "is_deemed_positive": True, "amount": 18000.0},
                        {"ledger_id": sgst_id, "is_deemed_positive": True, "amount": 18000.0}
                    ]
                }
            ]
        },
        expected_status=201
    )
    p_id = purch_resp["voucher_id"]
    masters.created_masters["vouchers"].append(p_id)

    stock_after_purch = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_purch == initial_stock + 10.0
    print(f"  [ASSERT PASS] Stock after purchase: {stock_after_purch} NOS (+10 NOS)")

    # 3. CREATE: Debit Note Voucher (Purchase Return of 3 NOS outward)
    dn_payload = {
        "voucher_type_id": vt_debit_note_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-DN-RET-001",
        "narration": "E2E Debit Note for Damaged Goods Return",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "original_voucher_id": p_id,
        "is_invoice": True,
        "entries": [
            {
                "ledger_id": creditor_id,
                "debit_amount": 70800.0,
                "credit_amount": 0.0,
                "entry_narration": "Debit Note to Creditor"
            },
            {
                "ledger_id": purchase_ledger_id,
                "debit_amount": 0.0,
                "credit_amount": 60000.0,
                "entry_narration": "Purchase Return"
            },
            {
                "ledger_id": cgst_id,
                "debit_amount": 0.0,
                "credit_amount": 5400.0,
                "entry_narration": "Reversal of Input CGST"
            },
            {
                "ledger_id": sgst_id,
                "debit_amount": 0.0,
                "credit_amount": 5400.0,
                "entry_narration": "Reversal of Input SGST"
            }
        ],
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_id,
                "quantity": 3.0,
                "billed_qty": 3.0,
                "rate": 20000.0,
                "amount": 60000.0,
                "is_deemed_positive": False,
                "accounting_allocations": [
                    {"ledger_id": purchase_ledger_id, "is_deemed_positive": False, "amount": 60000.0},
                    {"ledger_id": cgst_id, "is_deemed_positive": False, "amount": 5400.0},
                    {"ledger_id": sgst_id, "is_deemed_positive": False, "amount": 5400.0}
                ]
            }
        ]
    }

    resp_dn = await client.request(
        "POST", "/vouchers",
        step_name="Post Debit Note Voucher with Item Return",
        json_data=dn_payload,
        expected_status=201,
        assertion_desc="Debit Note created with 201 status"
    )
    dn_id = resp_dn["voucher_id"]
    masters.created_masters["vouchers"].append(dn_id)

    # 4. VERIFY: Stock balance decreased by 3 NOS
    stock_after_dn = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_dn == stock_after_purch - 3.0, f"Stock mismatch! Expected {stock_after_purch - 3.0}, got {stock_after_dn}"
    print(f"  [ASSERT PASS] Stock correctly deducted to {stock_after_dn} NOS (-3 NOS return outward)")

    # 5. CANCEL: Cancel Debit Note and verify stock restored
    await client.request(
        "POST", f"/vouchers/{dn_id}/cancel",
        step_name="Cancel Debit Note Voucher",
        expected_status=200
    )
    stock_after_cancel = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_cancel == stock_after_purch, f"Stock mismatch after cancel! Expected {stock_after_purch}, got {stock_after_cancel}"
    print(f"  [ASSERT PASS] Stock restored back to {stock_after_cancel} NOS on Debit Note cancellation")

    print("  [SUCCESS] Debit Note E2E Lifecycle Verified.\n")
    return {"debit_note_id": dn_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Debit Note E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_debit_note_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
