# E2E Voucher Lifecycle & API Test Diagnostic Report

**Execution Timestamp:** 2026-08-17 23:20:31 UTC  
**Total Duration:** 5.72 seconds  
**Total API Steps Executed:** 109  
**Steps Passed:** 109  
**Steps Failed:** 0  

---

## 📊 Test Suite Breakdown

| # | Voucher Test Suite | Status | Duration (s) | Notes / Error |
|---|---|---|---|---|
| 1 | **01. Sales & Delivery Notes** | ✅ PASS | 0.55s | All assertions verified |
| 2 | **02. Purchase & Receipt Notes** | ✅ PASS | 0.4s | All assertions verified |
| 3 | **03. Payment & Bank Allocations** | ✅ PASS | 0.37s | All assertions verified |
| 4 | **04. Receipt & Debtor Settlements** | ✅ PASS | 0.46s | All assertions verified |
| 5 | **05. Contra (Cash/Bank Transfers)** | ✅ PASS | 0.27s | All assertions verified |
| 6 | **06. Journal & Cost Center Allocations** | ✅ PASS | 0.23s | All assertions verified |
| 7 | **07. Debit Note (Purchase Returns)** | ✅ PASS | 0.26s | All assertions verified |
| 8 | **08. Credit Note (Sales Returns)** | ✅ PASS | 0.31s | All assertions verified |
| 9 | **09. Inventory & Stock Journal Transfers** | ✅ PASS | 0.41s | All assertions verified |

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
