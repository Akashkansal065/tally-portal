import asyncio
import os
import sys
from decimal import Decimal

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_sales_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 1: SALES & DELIVERY NOTES LIFECYCLE")
    print("="*80)

    stock_item_id = masters.data["stock_item_id"]
    debtor_id = masters.data["debtor_ledger_id"]
    sales_ledger_id = masters.data["sales_ledger_id"]
    cgst_id = masters.data["cgst_ledger_id"]
    sgst_id = masters.data["sgst_ledger_id"]
    godown_id = masters.data["godown_blr_id"]
    vt_sales_id = masters.voucher_types_map.get("Sales", 22)

    # 1. Baseline Stock Check
    initial_stock = await masters.get_stock_item_closing_qty(stock_item_id)
    print(f"  [*] Initial stock item quantity: {initial_stock} NOS")

    # 2. CREATE: Sales Item Invoice (10 NOS @ 30,000 with 5% discount + 18% GST)
    # Item: 10 * 30000 = 300000 - 5% (15000) = 285000
    # CGST (9%) = 25650, SGST (9%) = 25650 -> Total = 336300
    item_amt = 285000.0
    cgst_amt = 25650.0
    sgst_amt = 25650.0
    total_sales_amt = 336300.0

    sales_payload = {
        "voucher_type_id": vt_sales_id,
        "voucher_date": "2026-03-01",
        "reference_number": "E2E-SAL-INV-001",
        "narration": "E2E Automated Sales Invoice with Item & GST",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "is_invoice": True,
        "entries": [
            {
                "ledger_id": debtor_id,
                "debit_amount": total_sales_amt,
                "credit_amount": 0.0,
                "entry_narration": "Sundry Debtor Receivable",
                "bill_allocations": [
                    {
                        "bill_reference": "E2E-SAL-INV-001",
                        "allocation_type": "New Ref",
                        "amount": total_sales_amt
                    }
                ]
            },
            {
                "ledger_id": sales_ledger_id,
                "debit_amount": 0.0,
                "credit_amount": item_amt,
                "entry_narration": "Domestic Sales 18%"
            },
            {
                "ledger_id": cgst_id,
                "debit_amount": 0.0,
                "credit_amount": cgst_amt,
                "entry_narration": "Output CGST"
            },
            {
                "ledger_id": sgst_id,
                "debit_amount": 0.0,
                "credit_amount": sgst_amt,
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
                "discount_percent": 5.0,
                "discount_amount": 15000.0,
                "amount": item_amt,
                "is_deemed_positive": False,
                "accounting_allocations": [
                    {"ledger_id": sales_ledger_id, "is_deemed_positive": False, "amount": item_amt},
                    {"ledger_id": cgst_id, "is_deemed_positive": False, "amount": cgst_amt},
                    {"ledger_id": sgst_id, "is_deemed_positive": False, "amount": sgst_amt}
                ]
            }
        ]
    }

    create_resp = await client.request(
        "POST", "/vouchers",
        step_name="Sales Invoice Creation with GST & Inventory",
        json_data=sales_payload,
        expected_status=201,
        assertion_desc="Voucher created with 201 status and balanced debits/credits"
    )
    v1_id = create_resp["voucher_id"]
    masters.created_masters["vouchers"].append(v1_id)
    masters.data["sales_voucher_id"] = v1_id
    masters.data["sales_bill_ref"] = "E2E-SAL-INV-001"
    masters.data["sales_bill_amount"] = total_sales_amt

    # 3. VERIFY: Stock balance decreased from 100 to 90
    stock_after_sales = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_sales == initial_stock - 10.0, f"Stock quantity mismatch! Expected {initial_stock - 10.0}, got {stock_after_sales}"
    print(f"  [ASSERT PASS] Stock correctly deducted to {stock_after_sales} NOS (-10 NOS)")

    # 4. UPDATE / ALTER: Change quantity from 10 to 15 NOS
    # Item: 15 * 30000 = 450000 - 5% (22500) = 427500
    # CGST (9%) = 38475, SGST (9%) = 38475 -> Total = 504450
    upd_item_amt = 427500.0
    upd_cgst = 38475.0
    upd_sgst = 38475.0
    upd_total = 504450.0

    sales_payload["entries"][0]["debit_amount"] = upd_total
    sales_payload["entries"][0]["bill_allocations"][0]["amount"] = upd_total
    sales_payload["entries"][1]["credit_amount"] = upd_item_amt
    sales_payload["entries"][2]["credit_amount"] = upd_cgst
    sales_payload["entries"][3]["credit_amount"] = upd_sgst
    sales_payload["inventory_entries"][0]["quantity"] = 15.0
    sales_payload["inventory_entries"][0]["billed_qty"] = 15.0
    sales_payload["inventory_entries"][0]["discount_amount"] = 22500.0
    sales_payload["inventory_entries"][0]["amount"] = upd_item_amt
    sales_payload["inventory_entries"][0]["accounting_allocations"] = [
        {"ledger_id": sales_ledger_id, "is_deemed_positive": False, "amount": upd_item_amt},
        {"ledger_id": cgst_id, "is_deemed_positive": False, "amount": upd_cgst},
        {"ledger_id": sgst_id, "is_deemed_positive": False, "amount": upd_sgst}
    ]

    await client.request(
        "PUT", f"/vouchers/{v1_id}",
        step_name="Alter Sales Invoice (Qty 10 -> 15 NOS)",
        json_data=sales_payload,
        expected_status=200,
        assertion_desc="Sales Voucher updated successfully"
    )

    # 5. VERIFY: Stock balance updated to 85 NOS (-15 NOS from initial)
    stock_after_update = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_update == initial_stock - 15.0, f"Stock quantity mismatch after update! Expected {initial_stock - 15.0}, got {stock_after_update}"
    print(f"  [ASSERT PASS] Stock correctly recalculated to {stock_after_update} NOS (-15 NOS)")

    # 6. CANCEL VOUCHER: Verify cancellation & complete stock reversal
    await client.request(
        "POST", f"/vouchers/{v1_id}/cancel",
        step_name="Cancel Sales Voucher",
        expected_status=200,
        assertion_desc="Voucher cancelled and pushed to Tally"
    )
    stock_after_cancel = await masters.get_stock_item_closing_qty(stock_item_id)
    assert stock_after_cancel == initial_stock, f"Stock quantity mismatch after cancel! Expected {initial_stock}, got {stock_after_cancel}"
    print(f"  [ASSERT PASS] Stock reversed back to initial {stock_after_cancel} NOS on cancellation")

    # 7. CREATE SECONDARY SALES INVOICE (for testing downstream receipts & deletion)
    sales_payload["reference_number"] = "E2E-SAL-INV-002"
    sales_payload["entries"][0]["bill_allocations"][0]["bill_reference"] = "E2E-SAL-INV-002"
    sales_payload["entries"][0]["debit_amount"] = total_sales_amt
    sales_payload["entries"][0]["bill_allocations"][0]["amount"] = total_sales_amt
    sales_payload["entries"][1]["credit_amount"] = item_amt
    sales_payload["entries"][2]["credit_amount"] = cgst_amt
    sales_payload["entries"][3]["credit_amount"] = sgst_amt
    sales_payload["inventory_entries"][0]["quantity"] = 10.0
    sales_payload["inventory_entries"][0]["billed_qty"] = 10.0
    sales_payload["inventory_entries"][0]["discount_amount"] = 15000.0
    sales_payload["inventory_entries"][0]["amount"] = item_amt
    sales_payload["inventory_entries"][0]["accounting_allocations"] = [
        {"ledger_id": sales_ledger_id, "is_deemed_positive": False, "amount": item_amt},
        {"ledger_id": cgst_id, "is_deemed_positive": False, "amount": cgst_amt},
        {"ledger_id": sgst_id, "is_deemed_positive": False, "amount": sgst_amt}
    ]

    resp_v2 = await client.request(
        "POST", "/vouchers",
        step_name="Create Active Sales Invoice #2",
        json_data=sales_payload,
        expected_status=201
    )
    v2_id = resp_v2["voucher_id"]
    masters.created_masters["vouchers"].append(v2_id)
    masters.data["sales_voucher_id"] = v2_id
    masters.data["sales_bill_ref"] = "E2E-SAL-INV-002"
    masters.data["sales_bill_amount"] = total_sales_amt

    print("  [SUCCESS] Sales & Delivery Notes E2E Lifecycle Verified.\n")
    return {"sales_voucher_id": v2_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Sales E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_sales_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
