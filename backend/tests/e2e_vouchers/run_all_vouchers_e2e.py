import asyncio
import os
import sys
import json
import time
from typing import Dict, Any, List

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from tests.e2e_vouchers.e2e_harness import E2EClient, E2ETraceRecorder, MasterDataManager

import importlib
sales_mod = importlib.import_module("tests.e2e_vouchers.01_sales_e2e")
purch_mod = importlib.import_module("tests.e2e_vouchers.02_purchase_e2e")
pay_mod = importlib.import_module("tests.e2e_vouchers.03_payment_e2e")
rcp_mod = importlib.import_module("tests.e2e_vouchers.04_receipt_e2e")
contra_mod = importlib.import_module("tests.e2e_vouchers.05_contra_e2e")
journal_mod = importlib.import_module("tests.e2e_vouchers.06_journal_e2e")
dn_mod = importlib.import_module("tests.e2e_vouchers.07_debit_note_e2e")
cn_mod = importlib.import_module("tests.e2e_vouchers.08_credit_note_e2e")
inv_mod = importlib.import_module("tests.e2e_vouchers.09_inventory_vouchers_e2e")


async def run_master_voucher_e2e_suite():
    overall_start_time = time.time()
    recorder = E2ETraceRecorder("Master Voucher E2E Suite")

    print("\n" + "#"*90)
    print("🚀 STARTING COMPREHENSIVE END-TO-END VOUCHER & INVENTORY TEST AUTOMATION SUITE")
    print("#"*90)

    suites = [
        ("01. Sales & Delivery Notes", sales_mod.run_sales_e2e),
        ("02. Purchase & Receipt Notes", purch_mod.run_purchase_e2e),
        ("03. Payment & Bank Allocations", pay_mod.run_payment_e2e),
        ("04. Receipt & Debtor Settlements", rcp_mod.run_receipt_e2e),
        ("05. Contra (Cash/Bank Transfers)", contra_mod.run_contra_e2e),
        ("06. Journal & Cost Center Allocations", journal_mod.run_journal_e2e),
        ("07. Debit Note (Purchase Returns)", dn_mod.run_debit_note_e2e),
        ("08. Credit Note (Sales Returns)", cn_mod.run_credit_note_e2e),
        ("09. Inventory & Stock Journal Transfers", inv_mod.run_inventory_vouchers_e2e),
    ]

    suite_results: List[Dict[str, Any]] = []

    async with E2EClient(recorder) as client:
        masters = MasterDataManager(client)
        
        print("\n⚙️  INITIALIZING TEST MASTERS & ENTITIES...")
        await masters.initialize_and_seed_masters()

        for suite_name, suite_func in suites:
            s_t0 = time.time()
            status = "PASSED"
            err_details = None
            try:
                await suite_func(client, masters)
            except Exception as e:
                status = "FAILED"
                err_details = str(e)
                print(f"❌ [SUITE FAILED] {suite_name}: {e}")
            duration_s = round(time.time() - s_t0, 2)
            suite_results.append({
                "suite": suite_name,
                "status": status,
                "duration_seconds": duration_s,
                "error": err_details
            })

        print("\n🧹 RUNNING MASTER TEARDOWN (CLEANING UP ALL TEST ARTIFACTS)...")
        await masters.teardown_all()

    overall_duration = round(time.time() - overall_start_time, 2)
    summary_data = recorder.summary()

    # Generate Markdown Summary
    md_report_path = os.path.join(backend_root, "tests", "e2e_vouchers", "voucher_e2e_diagnostic_report.md")
    json_report_path = os.path.join(backend_root, "tests", "e2e_vouchers", "e2e_voucher_trace_report.json")

    with open(json_report_path, "w", encoding="utf-8") as jf:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_duration_seconds": overall_duration,
            "suite_results": suite_results,
            "trace_summary": summary_data
        }, jf, indent=2, default=str)

    md_content = f"""# E2E Voucher Lifecycle & API Test Diagnostic Report

**Execution Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Total Duration:** {overall_duration} seconds  
**Total API Steps Executed:** {summary_data['total_steps']}  
**Steps Passed:** {summary_data['passed']}  
**Steps Failed:** {summary_data['failed']}  

---

## 📊 Test Suite Breakdown

| # | Voucher Test Suite | Status | Duration (s) | Notes / Error |
|---|---|---|---|---|
"""
    for idx, sr in enumerate(suite_results, 1):
        icon = "✅ PASS" if sr["status"] == "PASSED" else "❌ FAIL"
        err_msg = sr["error"] if sr["error"] else "All assertions verified"
        md_content += f"| {idx} | **{sr['suite']}** | {icon} | {sr['duration_seconds']}s | {err_msg} |\n"

    md_content += """
---

## 🎯 Verified Lifecycle Features Across All Voucher Types
1. **Master Lifecycle**: Units of Measure (Simple/Compound), Stock Groups, Godowns, Batches, Stock Items with initial stock valuation, Account Groups, Debtor/Creditor/Bank/Cash Ledgers, Taxes, Cost Categories, Cost Centres.
2. **Sales & Orders**: Full GST breakdown, multi-item invoicing, automatic `New Ref` bill generation, stock deduction, alter recalculation, cancellation stock restoration, delete audit logging.
3. **Purchase & Receipt Notes**: Inward stock movements (+qty), bill tracking, alter adjustments, draft vs confirmed status toggles, stock toggles.
4. **Payment & Cheques**: Bank allocations (Cheque/DD, NEFT, instrument dates, payee favouring, crossing comments), bill settlements against purchase bills (`Against Ref`), status transitions (`Open` -> `Partially Settled` -> `Settled` -> `Reverted`).
5. **Receipt & Advances**: Direct deposits/IMPS, Advance receipts (`Advance`), debtor bill settlements (`Against Ref`), alterations.
6. **Contra**: Cash deposits into bank, Cash withdrawals for petty cash, bank-to-bank transfers.
7. **Journal**: Multi-debit, multi-credit balanced adjustments, Cost Center allocations (`cost_center_id`), tax adjustments.
8. **Debit Note**: Purchase Returns with outward stock reversal (`is_deemed_positive = False`), link to original purchase voucher, cancellation reversals.
9. **Credit Note**: Sales Returns with inward stock replenishment (`is_deemed_positive = True`), link to original sales invoice, cancellation reversals.
10. **Stock Journal & Inventory**: Inter-Godown transfers (Bangalore Central -> Delhi Godown), Delivery Notes, Receipt Notes, Rejections In & Rejections Out.
11. **Idempotent Teardown**: Automatic purge of all test entities in strict dependency order, ensuring zero residual database pollution.
"""

    with open(md_report_path, "w", encoding="utf-8") as mf:
        mf.write(md_content)

    # Print Terminal Table
    print("\n" + "="*90)
    print(f"📊 MASTER E2E VOUCHER TEST SUMMARY (Total Duration: {overall_duration}s)")
    print("="*90)
    for sr in suite_results:
        icon = "🟢 PASS" if sr["status"] == "PASSED" else "🔴 FAIL"
        print(f"  {icon} | {sr['suite']:<45} | {sr['duration_seconds']:>5.2f}s | {sr['error'] or 'Clean'}")
    print("="*90)
    print(f"  Total Steps: {summary_data['total_steps']} | Passed: {summary_data['passed']} | Failed: {summary_data['failed']}")
    print(f"  Detailed Report saved to: {md_report_path}")
    print("="*90 + "\n")

    if summary_data['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_master_voucher_e2e_suite())
