import asyncio
import os
import sys
import traceback

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager, Colors

# Pacing delay in seconds between lifecycle steps for easy readability
STEP_DELAY = 0.8


async def run_purchase_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*85}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}>> RUNNING E2E SUITE 2: PURCHASE & RECEIPT NOTES LIFECYCLE (Paced Mode){Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*85}{Colors.RESET}\n")

    try:
        stock_item_id = masters.data["stock_item_id"]
        creditor_id = masters.data["creditor_ledger_id"]
        purchase_ledger_id = masters.data["purchase_ledger_id"]
        cgst_id = masters.data["cgst_ledger_id"]
        sgst_id = masters.data["sgst_ledger_id"]
        godown_id = masters.data["godown_blr_id"]
        vt_purchase_id = masters.voucher_types_map.get("Purchase", 15)

        # -------------------------------------------------------------------------
        # 1. Baseline Stock Check
        # -------------------------------------------------------------------------
        print(f"  {Colors.CYAN}⚙ [STEP 1/7]{Colors.RESET} Checking initial baseline stock...")
        initial_stock = await masters.get_stock_item_closing_qty(stock_item_id)
        print(f"  {Colors.BOLD}{Colors.GREEN}✔ [BASELINE]{Colors.RESET} Stock item initial closing quantity: {Colors.BOLD}{initial_stock} NOS{Colors.RESET}")
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 2. CREATE: Purchase Item Invoice (20 NOS @ 20,000 with 2% discount + 18% GST)
        # -------------------------------------------------------------------------
        # Item: 20 * 20000 = 400000 - 2% (8000) = 392000
        # CGST (9%) = 35280, SGST (9%) = 35280 -> Total = 462560
        item_amt = 392000.0
        cgst_amt = 35280.0
        sgst_amt = 35280.0
        total_purch_amt = 462560.0

        print(f"\n  {Colors.CYAN}⚙ [STEP 2/7]{Colors.RESET} Creating Purchase Invoice: 20 NOS @ ₹20,000 (with 2% Disc + 18% GST)...")
        purchase_payload = {
            "voucher_type_id": vt_purchase_id,
            "voucher_date": "2026-03-01",
            "reference_number": "E2E-PUR-INV-001",
            "narration": "E2E Automated Purchase Inward Invoice with GST",
            "status": "confirmed",
            "party_ledger_id": creditor_id,
            "is_invoice": True,
            "entries": [
                {
                    "ledger_id": creditor_id,
                    "debit_amount": 0.0,
                    "credit_amount": total_purch_amt,
                    "entry_narration": "Sundry Creditor Payable",
                    "bill_allocations": [
                        {
                            "bill_reference": "E2E-PUR-INV-001",
                            "allocation_type": "New Ref",
                            "amount": total_purch_amt
                        }
                    ]
                },
                {
                    "ledger_id": purchase_ledger_id,
                    "debit_amount": item_amt,
                    "credit_amount": 0.0,
                    "entry_narration": "Domestic Purchase 18%"
                },
                {
                    "ledger_id": cgst_id,
                    "debit_amount": cgst_amt,
                    "credit_amount": 0.0,
                    "entry_narration": "Input CGST"
                },
                {
                    "ledger_id": sgst_id,
                    "debit_amount": sgst_amt,
                    "credit_amount": 0.0,
                    "entry_narration": "Input SGST"
                }
            ],
            "inventory_entries": [
                {
                    "stock_item_id": stock_item_id,
                    "godown_id": godown_id,
                    "quantity": 20.0,
                    "billed_qty": 20.0,
                    "rate": 20000.0,
                    "discount_percent": 2.0,
                    "discount_amount": 8000.0,
                    "amount": item_amt,
                    "is_deemed_positive": True,
                    "accounting_allocations": [
                        {"ledger_id": purchase_ledger_id, "is_deemed_positive": True, "amount": item_amt},
                        {"ledger_id": cgst_id, "is_deemed_positive": True, "amount": cgst_amt},
                        {"ledger_id": sgst_id, "is_deemed_positive": True, "amount": sgst_amt}
                    ]
                }
            ]
        }

        create_resp = await client.request(
            "POST", "/vouchers",
            step_name="Purchase Invoice Creation with GST & Inward Inventory",
            json_data=purchase_payload,
            expected_status=201,
            assertion_desc="Purchase voucher created with 201 status"
        )
        p1_id = create_resp["voucher_id"]
        masters.created_masters["vouchers"].append(p1_id)
        masters.data["purchase_voucher_id"] = p1_id
        masters.data["purchase_bill_ref"] = "E2E-PUR-INV-001"
        masters.data["purchase_bill_amount"] = total_purch_amt
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 3. VERIFY: Stock balance increased by +20 NOS
        # -------------------------------------------------------------------------
        print(f"\n  {Colors.CYAN}⚙ [STEP 3/7]{Colors.RESET} Verifying inward inventory stock addition...")
        stock_after_purch = await masters.get_stock_item_closing_qty(stock_item_id)
        expected_stock_1 = initial_stock + 20.0
        if stock_after_purch != expected_stock_1:
            err = f"Stock mismatch! Expected {expected_stock_1} NOS, but got {stock_after_purch} NOS"
            print(f"  {Colors.BOLD}{Colors.RED}✖ [ASSERT FAIL] {err}{Colors.RESET}")
            raise AssertionError(err)
        print(f"  {Colors.BOLD}{Colors.GREEN}✔ [ASSERT PASS]{Colors.RESET} Stock correctly increased to {Colors.BOLD}{stock_after_purch} NOS{Colors.RESET} (+20 NOS inward)")
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 4. UPDATE / ALTER: Change quantity to 30 NOS
        # -------------------------------------------------------------------------
        # Item: 30 * 20000 = 600000 - 2% (12000) = 588000
        # CGST (9%) = 52920, SGST (9%) = 52920 -> Total = 693840
        upd_item_amt = 588000.0
        upd_cgst = 52920.0
        upd_sgst = 52920.0
        upd_total = 693840.0

        print(f"\n  {Colors.CYAN}⚙ [STEP 4/7]{Colors.RESET} Altering Purchase Invoice: Increasing quantity from 20 -> 30 NOS...")
        purchase_payload["entries"][0]["credit_amount"] = upd_total
        purchase_payload["entries"][0]["bill_allocations"][0]["amount"] = upd_total
        purchase_payload["entries"][1]["debit_amount"] = upd_item_amt
        purchase_payload["entries"][2]["debit_amount"] = upd_cgst
        purchase_payload["entries"][3]["debit_amount"] = upd_sgst
        purchase_payload["inventory_entries"][0]["quantity"] = 30.0
        purchase_payload["inventory_entries"][0]["billed_qty"] = 30.0
        purchase_payload["inventory_entries"][0]["discount_amount"] = 12000.0
        purchase_payload["inventory_entries"][0]["amount"] = upd_item_amt
        purchase_payload["inventory_entries"][0]["accounting_allocations"] = [
            {"ledger_id": purchase_ledger_id, "is_deemed_positive": True, "amount": upd_item_amt},
            {"ledger_id": cgst_id, "is_deemed_positive": True, "amount": upd_cgst},
            {"ledger_id": sgst_id, "is_deemed_positive": True, "amount": upd_sgst}
        ]

        await client.request(
            "PUT", f"/vouchers/{p1_id}",
            step_name="Alter Purchase Invoice (Qty 20 -> 30 NOS)",
            json_data=purchase_payload,
            expected_status=200,
            assertion_desc="Purchase Voucher updated successfully"
        )
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 5. VERIFY: Stock balance updated to initial + 30 NOS
        # -------------------------------------------------------------------------
        print(f"\n  {Colors.CYAN}⚙ [STEP 5/7]{Colors.RESET} Verifying updated stock after quantity alteration...")
        stock_after_update = await masters.get_stock_item_closing_qty(stock_item_id)
        expected_stock_2 = initial_stock + 30.0
        if stock_after_update != expected_stock_2:
            err = f"Stock mismatch! Expected {expected_stock_2} NOS, but got {stock_after_update} NOS"
            print(f"  {Colors.BOLD}{Colors.RED}✖ [ASSERT FAIL] {err}{Colors.RESET}")
            raise AssertionError(err)
        print(f"  {Colors.BOLD}{Colors.GREEN}✔ [ASSERT PASS]{Colors.RESET} Stock updated to {Colors.BOLD}{stock_after_update} NOS{Colors.RESET} (+30 NOS inward)")
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 6. STATUS TRANSITION: Toggle to 'draft' -> verify stock drops by 30 NOS
        # -------------------------------------------------------------------------
        print(f"\n  {Colors.CYAN}⚙ [STEP 6/7]{Colors.RESET} Transitioning Purchase Voucher status to '{Colors.YELLOW}draft{Colors.CYAN}'...")
        await client.request(
            "PATCH", f"/vouchers/{p1_id}/status",
            step_name="Transition Purchase to Draft Status",
            params={"status_val": "draft"},
            expected_status=200,
            assertion_desc="Status changed to draft"
        )
        stock_after_draft = await masters.get_stock_item_closing_qty(stock_item_id)
        if stock_after_draft != initial_stock:
            err = f"Stock mismatch after draft! Expected {initial_stock} NOS, but got {stock_after_draft} NOS"
            print(f"  {Colors.BOLD}{Colors.RED}✖ [ASSERT FAIL] {err}{Colors.RESET}")
            raise AssertionError(err)
        print(f"  {Colors.BOLD}{Colors.GREEN}✔ [ASSERT PASS]{Colors.RESET} Stock reversed to initial {Colors.BOLD}{stock_after_draft} NOS{Colors.RESET} while in draft status")
        await asyncio.sleep(STEP_DELAY)

        # -------------------------------------------------------------------------
        # 7. STATUS TRANSITION: Toggle back to 'confirmed' -> verify stock restored
        # -------------------------------------------------------------------------
        print(f"\n  {Colors.CYAN}⚙ [STEP 7/7]{Colors.RESET} Transitioning Purchase Voucher status back to '{Colors.GREEN}confirmed{Colors.CYAN}'...")
        await client.request(
            "PATCH", f"/vouchers/{p1_id}/status",
            step_name="Transition Purchase back to Confirmed Status",
            params={"status_val": "confirmed"},
            expected_status=200,
            assertion_desc="Status changed to confirmed"
        )
        stock_after_confirmed = await masters.get_stock_item_closing_qty(stock_item_id)
        if stock_after_confirmed != expected_stock_2:
            err = f"Stock mismatch after confirm! Expected {expected_stock_2} NOS, but got {stock_after_confirmed} NOS"
            print(f"  {Colors.BOLD}{Colors.RED}✖ [ASSERT FAIL] {err}{Colors.RESET}")
            raise AssertionError(err)
        print(f"  {Colors.BOLD}{Colors.GREEN}✔ [ASSERT PASS]{Colors.RESET} Stock re-applied to {Colors.BOLD}{stock_after_confirmed} NOS{Colors.RESET} upon confirmation")
        await asyncio.sleep(STEP_DELAY)

        print(f"\n  {Colors.BOLD}{Colors.GREEN}✨ [SUCCESS] Purchase & Receipt Notes E2E Lifecycle Verified.{Colors.RESET}\n")
        return {"purchase_voucher_id": p1_id, "status": "PASSED"}

    except Exception as ex:
        print(f"\n{Colors.BOLD}{Colors.RED}{'!'*85}")
        print(f"✖ [ERROR IN PURCHASE E2E SUITE]: {str(ex)}")
        print(f"{'!'*85}{Colors.RESET}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Purchase E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_purchase_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())

