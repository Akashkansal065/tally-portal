import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_credit_note_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 8: CREDIT NOTE (SALES RETURNS & REBATES) LIFECYCLE")
    print("="*80)

    stock_item_id = masters.data["stock_item_id"]
    debtor_id = masters.data["debtor_ledger_id"]
    sales_ledger_id = masters.data["sales_ledger_id"]
    cgst_id = masters.data["cgst_ledger_id"]
    sgst_id = masters.data["sgst_ledger_id"]
    godown_id = masters.data["godown_blr_id"]
    vt_sales_id = masters.voucher_types_map.get("Sales", 22)
    vt_credit_note_id = masters.voucher_types_map.get("Credit Note", 3)

    # 1. Baseline Stock Check
    initial_stock = await masters.get_stock_item_closing_qty(stock_item_id)
    print(f"  [*] Initial stock item quantity: {initial_stock} NOS")

    # 2. Baseline Sales Voucher (Outward 10 NOS)
    sales_resp = await client.request(
        "POST", "/vouchers",
        step_name="Create Baseline Sales for Credit Note Return",
        json_data={
            "voucher_type_id": vt_sales_id,
            "voucher_date": "2026-03-01",
            "reference_number": "E2E-SAL-RET-001",
            "narration": "Original Sales for Credit Note Return Test",
            "status": "confirmed",
            "party_ledger_id": debtor_id,
            "is_invoice": True,
            "entries": [
                {
                    "ledger_id": debtor_id,
                    "debit_amount": 354000.0,
                    "credit_amount": 0.0,
                    "entry_narration": "Sundry Debtor Receivable"
                },
                {
                    "ledger_id": sales_ledger_id,
                    "debit_amount": 0.0,
                    "credit_amount": 300000.0,
                    "entry_narration": "Sales"
                },
                {
                    "ledger_id": cgst_id,
                    "debit_amount": 0.0,
                    "credit_amount": 27000.0,
                    "entry_narration": "Output CGST"
                },
                {
                    "ledger_id": sgst_id,
                    "debit_amount": 0.0,
                    "credit_amount": 27000.0,
                    "entry_narration": "Output SGST"
                }
            ],
            "inventory_entries": [
                {
                    "stock_item_id": stock_item_id,
                    "godown_id": godown_id,
                    "quantity": 10.0,
                    "billed_qty": 10.0,
                    "rate": 30000.0,
                    "amount": 300000.0,
                    "is_deemed_positive": False,
                    "accounting_allocations": [
                        {"ledger_id": sales_ledger_id, "is_deemed_positive": False, "amount": 300000.0},
                        {"ledger_id": cgst_id, "is_deemed_positive": False, "amount": 27000.0},
                        {"ledger_id": sgst_id, "is_deemed_positive": False, "amount": 27000.0}
                    ]
                }
            ]
        },
        expected_status=201
    )
    s_id = sales_resp["voucher_id"]
    masters.created_masters["vouchers"].append(s_id)

    stock_after_sales = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_sales == initial_stock - 10.0
    print(f"  [ASSERT PASS] Stock after sales: {stock_after_sales} NOS (-10 NOS)")

    # 3. CREATE: Credit Note Voucher (Sales Return of 4 NOS inward)
    cn_payload = {
        "voucher_type_id": vt_credit_note_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-CN-RET-001",
        "narration": "E2E Credit Note for Customer Sales Return",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "original_voucher_id": s_id,
        "is_invoice": True,
        "entries": [
            {
                "ledger_id": debtor_id,
                "debit_amount": 0.0,
                "credit_amount": 141600.0,
                "entry_narration": "Credit Note to Customer"
            },
            {
                "ledger_id": sales_ledger_id,
                "debit_amount": 120000.0,
                "credit_amount": 0.0,
                "entry_narration": "Sales Return"
            },
            {
                "ledger_id": cgst_id,
                "debit_amount": 10800.0,
                "credit_amount": 0.0,
                "entry_narration": "Output CGST Reversal"
            },
            {
                "ledger_id": sgst_id,
                "debit_amount": 10800.0,
                "credit_amount": 0.0,
                "entry_narration": "Output SGST Reversal"
            }
        ],
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_id,
                "quantity": 4.0,
                "billed_qty": 4.0,
                "rate": 30000.0,
                "amount": 120000.0,
                "is_deemed_positive": True,
                "accounting_allocations": [
                    {"ledger_id": sales_ledger_id, "is_deemed_positive": True, "amount": 120000.0},
                    {"ledger_id": cgst_id, "is_deemed_positive": True, "amount": 10800.0},
                    {"ledger_id": sgst_id, "is_deemed_positive": True, "amount": 10800.0}
                ]
            }
        ]
    }

    resp_cn = await client.request(
        "POST", "/vouchers",
        step_name="Post Credit Note Voucher with Item Return",
        json_data=cn_payload,
        expected_status=201,
        assertion_desc="Credit Note created with 201 status"
    )
    cn_id = resp_cn["voucher_id"]
    masters.created_masters["vouchers"].append(cn_id)

    # 4. VERIFY: Stock balance increased by 4 NOS
    stock_after_cn = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_cn == stock_after_sales + 4.0, f"Stock mismatch! Expected {stock_after_sales + 4.0}, got {stock_after_cn}"
    print(f"  [ASSERT PASS] Stock correctly replenished to {stock_after_cn} NOS (+4 NOS customer return inward)")

    # 5. CANCEL: Cancel Credit Note and verify stock reversed back
    await client.request(
        "POST", f"/vouchers/{cn_id}/cancel",
        step_name="Cancel Credit Note Voucher",
        expected_status=200
    )
    stock_after_cancel = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_cancel == stock_after_sales, f"Stock mismatch after cancel! Expected {stock_after_sales}, got {stock_after_cancel}"
    print(f"  [ASSERT PASS] Stock reversed back to {stock_after_cancel} NOS on Credit Note cancellation")

    print("  [SUCCESS] Credit Note E2E Lifecycle Verified.\n")
    return {"credit_note_id": cn_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Credit Note E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_credit_note_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
