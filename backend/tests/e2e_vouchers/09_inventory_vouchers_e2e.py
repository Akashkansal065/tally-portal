import asyncio
import os
import sys

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager


async def run_inventory_vouchers_e2e(client: E2EClient, masters: MasterDataManager) -> dict:
    recorder = client.recorder
    print("\n" + "="*80)
    print(">> RUNNING E2E SUITE 9: INVENTORY & STOCK JOURNAL VOUCHERS LIFECYCLE")
    print("="*80)

    stock_item_id = masters.data["stock_item_id"]
    godown_blr_id = masters.data["godown_blr_id"]
    godown_delhi_id = masters.data["godown_delhi_id"]
    debtor_id = masters.data["debtor_ledger_id"]
    creditor_id = masters.data["creditor_ledger_id"]

    vt_stock_journal_id = masters.voucher_types_map.get("Stock Journal", 24)
    vt_delivery_note_id = masters.voucher_types_map.get("Delivery Note", 5)
    vt_receipt_note_id = masters.voucher_types_map.get("Receipt Note", 18)
    vt_physical_stock_id = masters.voucher_types_map.get("Physical Stock", 14)
    vt_rej_in_id = masters.voucher_types_map.get("Rejections In", 19)
    vt_rej_out_id = masters.voucher_types_map.get("Rejections Out", 20)

    # 1. Baseline Stock Check
    initial_stock = await masters.get_stock_item_closing_qty(stock_item_id)
    print(f"  [*] Initial stock item quantity: {initial_stock} NOS")

    # 2. CREATE: Stock Journal (Inter-Godown Transfer: 10 NOS from Bangalore -> Delhi)
    stk_journal_payload = {
        "voucher_type_id": vt_stock_journal_id,
        "voucher_date": "2026-03-01",
        "reference_number": "E2E-SJ-TRF-001",
        "narration": "E2E Stock Journal Transfer from Bangalore Central to Delhi Godown",
        "status": "confirmed",
        "inventory_entries": [
            # Source / Consumption (Outward from Bangalore)
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_blr_id,
                "quantity": 10.0,
                "billed_qty": 10.0,
                "rate": 25000.0,
                "amount": 250000.0,
                "is_deemed_positive": False
            },
            # Destination / Production (Inward to Delhi)
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_delhi_id,
                "quantity": 10.0,
                "billed_qty": 10.0,
                "rate": 25000.0,
                "amount": 250000.0,
                "is_deemed_positive": True
            }
        ]
    }

    resp_sj = await client.request(
        "POST", "/vouchers",
        step_name="Post Stock Journal Inter-Godown Transfer",
        json_data=stk_journal_payload,
        expected_status=201,
        assertion_desc="Stock Journal created with balanced consumption & production"
    )
    sj_id = resp_sj["voucher_id"]
    masters.created_masters["vouchers"].append(sj_id)

    # 3. CREATE: Delivery Note Voucher (Goods Dispatched against Order)
    del_payload = {
        "voucher_type_id": vt_delivery_note_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-DN-DSP-001",
        "narration": "E2E Delivery Note for Goods Dispatch",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_delhi_id,
                "quantity": 2.0,
                "billed_qty": 2.0,
                "rate": 30000.0,
                "amount": 60000.0,
                "is_deemed_positive": False
            }
        ]
    }
    resp_dn = await client.request(
        "POST", "/vouchers",
        step_name="Post Delivery Note Voucher",
        json_data=del_payload,
        expected_status=201
    )
    dn_id = resp_dn["voucher_id"]
    masters.created_masters["vouchers"].append(dn_id)

    # 4. CREATE: Receipt Note Voucher (Goods Received from Supplier)
    rcn_payload = {
        "voucher_type_id": vt_receipt_note_id,
        "voucher_date": "2026-03-02",
        "reference_number": "E2E-RN-REC-001",
        "narration": "E2E Receipt Note for Inward Material Arrival",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_blr_id,
                "quantity": 5.0,
                "billed_qty": 5.0,
                "rate": 20000.0,
                "amount": 100000.0,
                "is_deemed_positive": True
            }
        ]
    }
    resp_rn = await client.request(
        "POST", "/vouchers",
        step_name="Post Receipt Note Voucher",
        json_data=rcn_payload,
        expected_status=201
    )
    rn_id = resp_rn["voucher_id"]
    masters.created_masters["vouchers"].append(rn_id)

    # 5. CREATE: Rejections In Voucher (Damaged Goods returned by Debtor)
    rejin_payload = {
        "voucher_type_id": vt_rej_in_id,
        "voucher_date": "2026-03-03",
        "reference_number": "E2E-REJ-IN-001",
        "narration": "E2E Rejections In for Damaged Unit",
        "status": "confirmed",
        "party_ledger_id": debtor_id,
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_blr_id,
                "quantity": 1.0,
                "billed_qty": 1.0,
                "rate": 30000.0,
                "amount": 30000.0,
                "is_deemed_positive": True
            }
        ]
    }
    resp_rejin = await client.request(
        "POST", "/vouchers",
        step_name="Post Rejections In Voucher",
        json_data=rejin_payload,
        expected_status=201
    )
    rejin_id = resp_rejin["voucher_id"]
    masters.created_masters["vouchers"].append(rejin_id)

    # 6. CREATE: Rejections Out Voucher (Defective Goods returned to Creditor)
    rejout_payload = {
        "voucher_type_id": vt_rej_out_id,
        "voucher_date": "2026-03-03",
        "reference_number": "E2E-REJ-OUT-001",
        "narration": "E2E Rejections Out for Defective Batch",
        "status": "confirmed",
        "party_ledger_id": creditor_id,
        "inventory_entries": [
            {
                "stock_item_id": stock_item_id,
                "godown_id": godown_blr_id,
                "quantity": 1.0,
                "billed_qty": 1.0,
                "rate": 20000.0,
                "amount": 20000.0,
                "is_deemed_positive": False
            }
        ]
    }
    resp_rejout = await client.request(
        "POST", "/vouchers",
        step_name="Post Rejections Out Voucher",
        json_data=rejout_payload,
        expected_status=201
    )
    rejout_id = resp_rejout["voucher_id"]
    masters.created_masters["vouchers"].append(rejout_id)

    # 7. UPDATE / ALTER: Alter Stock Journal Transfer
    stk_journal_payload["inventory_entries"][0]["quantity"] = 12.0
    stk_journal_payload["inventory_entries"][0]["amount"] = 300000.0
    stk_journal_payload["inventory_entries"][1]["quantity"] = 12.0
    stk_journal_payload["inventory_entries"][1]["amount"] = 300000.0

    await client.request(
        "PUT", f"/vouchers/{sj_id}",
        step_name="Alter Stock Journal (Transfer Qty 10 -> 12 NOS)",
        json_data=stk_journal_payload,
        expected_status=200
    )

    print("  [SUCCESS] All Inventory & Stock Journal Vouchers E2E Lifecycle Verified.\n")
    return {"stock_journal_id": sj_id, "status": "PASSED"}


if __name__ == "__main__":
    async def main():
        recorder = E2ETraceRecorder("Inventory Vouchers E2E Suite")
        async with E2EClient(recorder) as client:
            masters = MasterDataManager(client)
            await masters.initialize_and_seed_masters()
            try:
                await run_inventory_vouchers_e2e(client, masters)
            finally:
                await masters.teardown_all()
    asyncio.run(main())
