# Revised Roadmap: Standalone Tally-Aligned Web Operations Pages

## Approach

The staging pages (`/temporders`, `/payments`) remain as lightweight field agent tools. We build **separate, standalone pages** that directly create official accounting records in the core `tally_sync` database — exactly mirroring how entries are made in Tally Prime desktop. These records flow through the existing `sync_queue` → Tally Sync Daemon → Tally XML Import pipeline.

---

## ✅ What's Already Ready (No Changes Needed)

| Layer | What Exists | Status |
|:---|:---|:---|
| **Core DB Schema** | `vouchers`, `voucher_entries`, `stock_entries`, `bills`, `bill_allocations`, `ledgers`, `account_groups`, `stock_items`, `godowns`, `voucher_types` | ✅ Complete |
| **Backend Voucher CRUD** | [POST /vouchers](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/vouchers.py#L52-L230) — double-entry validation, auto-numbering, approval rules, auto bill creation, audit log, sync queue enqueue | ✅ Complete |
| **Backend Ledger CRUD** | [POST /ledgers](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/ledgers.py#L211-L280) — group validation, permission checks, duplicate prevention, sync queue enqueue | ✅ Complete |
| **Backend Stock Item CRUD** | [POST /inventory/items](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/inventory.py#L159) — stock groups, UOMs, HSN, GST rate | ✅ Complete |
| **Outbound Sync** | [sync_queue → XML builder → Tally daemon](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/sync.py#L88-L210) — Ledger + Voucher XML generation + daemon push | ✅ Built (needs voucher type fix) |
| **Voucher List Page** | [/vouchers](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/vouchers/page.tsx) — view all synced vouchers by type | ✅ Read-only exists |
| **Ledger List Page** | [/ledgers](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/ledgers/page.tsx) — browse ledgers | ✅ Read-only exists |
| **Stock List Page** | [/stocks](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/stocks/page.tsx) — browse stock items | ✅ Read-only exists |

---

## 🏗️ New Pages to Build

### 📄 Page 1: Sales Invoice Creation (`/vouchers/new/sales`)
Mirrors Tally's **Accounting Voucher → Sales** entry screen.

**How it works in Tally:**
- Select Party (Customer ledger from Sundry Debtors)
- Select Sales Account (Sales ledger)
- Add inventory items (Stock Item → Qty → Rate → Amount)
- GST auto-calculates (CGST/SGST or IGST based on party state)
- Narration

**What we build:**
- **Party picker**: Dropdown of all ledgers under "Sundry Debtors" group
- **Sales account picker**: Dropdown of ledgers under "Sales Accounts" group
- **Item grid**: Add rows — Stock Item search → Qty → Rate → Amount (auto-calc) → Godown
- **GST section**: Auto-compute CGST+SGST or IGST based on party state vs company state
- **Summary**: Shows total taxable value + tax breakdown + grand total
- **Submit**: Calls `POST /vouchers` with:
  - Dr: Customer ledger (total invoice amount)
  - Cr: Sales Account (taxable amount)
  - Cr: CGST ledger, SGST ledger, or IGST ledger
  - + `POST /inventory/stock-entries` for inventory tracking

**Backend addition needed:**
- New endpoint `POST /vouchers/sales` — a wrapper that accepts a simplified sales-specific payload (party, items, godown) and internally builds the double-entry entries + stock entries + bill

---

### 📄 Page 2: Receipt Voucher Creation (`/vouchers/new/receipt`)
Mirrors Tally's **Accounting Voucher → Receipt** entry screen.

**How it works in Tally:**
- Select Cash/Bank account (Dr)
- Select Party (Customer ledger, Cr)
- Enter Amount
- Bill-wise allocation: select which outstanding invoices to apply against (Against Ref / On Account / Advance)
- Narration

**What we build:**
- **Cash/Bank picker**: Dropdown of ledgers under "Cash-in-Hand" or "Bank Accounts" group
- **Party picker**: Dropdown of Sundry Debtors ledgers
- **Amount input**
- **Outstanding bills list**: Show all open `bills` for the selected party with checkboxes + allocation amounts
- **Submit**: Calls `POST /vouchers` with:
  - Dr: Cash/Bank ledger
  - Cr: Customer ledger
  - + Bill allocations via `POST /payment/allocate`

---

### 📄 Page 3: Payment Voucher Creation (`/vouchers/new/payment`)
Mirrors Tally's **Accounting Voucher → Payment** entry screen.

**Same as Receipt but reversed:**
- Dr: Supplier/Expense ledger (Cr)
- Cr: Cash/Bank account
- Bill-wise allocation against Sundry Creditors bills

---

### 📄 Page 4: Purchase Invoice Creation (`/vouchers/new/purchase`)
Mirrors Tally's **Accounting Voucher → Purchase** entry screen.

**Same structure as Sales but reversed:**
- Party picker from Sundry Creditors
- Purchase Account from Purchase Accounts group
- Inventory items (inward)
- GST calculation
- Dr: Purchase Account + GST ledgers
- Cr: Supplier ledger

---

### 📄 Page 5: Journal Voucher Creation (`/vouchers/new/journal`)
Mirrors Tally's **Journal Voucher** — free-form debit/credit entries.

- Dynamic rows: each row = Ledger + Dr/Cr Amount
- Debit total must equal Credit total
- No inventory, no bill allocation
- Used for adjustments, write-offs, inter-account transfers

---

### 📄 Page 6: Credit Note / Debit Note (`/vouchers/new/credit-note`, `/vouchers/new/debit-note`)
**Credit Note**: Sales return — reduces customer balance
**Debit Note**: Purchase return — reduces supplier balance

Same structure as Sales/Purchase but with reversed accounting entries and optional "Against Ref" linking to original invoice.

---

### 📄 Page 7: Ledger Creation (`/ledgers/new`)
Mirrors Tally's **Accounts Info → Ledgers → Create**.

- Name
- Group dropdown (Sundry Debtors, Sundry Creditors, Sales Accounts, Purchase Accounts, Bank Accounts, etc.)
- GSTIN, State, Address, Pincode
- Opening Balance (Dr/Cr)
- Credit Limit, Credit Period Days
- Bank details (if Bank Account group)

Backend `POST /ledgers` already exists and enqueues to `sync_queue`.

---

### 📄 Page 8: Stock Item Creation (`/stocks/new`)
Mirrors Tally's **Inventory Info → Stock Items → Create**.

- Name
- Stock Group dropdown
- UOM dropdown
- HSN Code
- GST Rate %
- Opening Qty, Rate, Value

Backend `POST /inventory/items` already exists.

---

## 🔧 Backend Changes Required

### Fix 1: Outbound XML Voucher Type Mapping
**File**: [sync.py outbound-queue](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/sync.py#L149-L199)

Currently hardcodes `VOUCHERTYPENAME="Journal"` for all vouchers. Fix to:
- Read actual `voucher_type.name` from the `voucher_types` table
- For Sales/Purchase: include `ALLINVENTORYENTRIES.LIST` with stock item name, qty, rate, amount, godown
- For Receipt/Payment: include `BILLALLOCATIONS.LIST` within the party ledger entry
- Add `REMOTEID` (our `voucher_guid`) for idempotent posting

### Fix 2: Add `voucher_guid` Column
**File**: [voucher.py model](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/models/voucher.py#L25-L47)

Add `voucher_guid = Column(String(36), nullable=True, unique=True)` — a UUID4 generated at creation time, used as `REMOTEID` in Tally XML to prevent duplicate vouchers.

### New: Sales-Specific Voucher Endpoint
**File**: New `POST /vouchers/sales` endpoint in [vouchers.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/vouchers.py)

Accepts a simplified payload:
```json
{
  "party_ledger_id": 123,
  "sales_ledger_id": 456,
  "voucher_date": "2026-07-26",
  "items": [
    { "stock_item_id": 1, "godown_id": 1, "qty": 10, "rate": 500, "has_gst": true }
  ],
  "narration": "Invoice for July dispatch"
}
```

Internally builds:
1. `TrnVoucher` (Sales type)
2. `TrnAccounting` entries (Dr Customer, Cr Sales, Cr CGST, Cr SGST / IGST)
3. `TrnInventory` stock entries (outward)
4. `TrnBill` (New Ref)
5. Updates `stock_items.closing_qty`
6. `SyncQueue` entry

### New: Receipt-Specific Voucher Endpoint
**File**: New `POST /vouchers/receipt` endpoint

```json
{
  "cash_bank_ledger_id": 789,
  "party_ledger_id": 123,
  "amount": 50000,
  "voucher_date": "2026-07-26",
  "bill_allocations": [
    { "bill_id": 10, "amount": 30000, "type": "Against Ref" },
    { "amount": 20000, "type": "On Account" }
  ],
  "narration": "Cash collection from XYZ"
}
```

---

## 🧱 Schema Changes (Minimal)

| Change | Table | Column | Type |
|:---|:---|:---|:---|
| **ADD** | `vouchers` | `voucher_guid` | `VARCHAR(36) UNIQUE NULL` |

That's the **only schema change**. Everything else is already built.

---

## 📐 Page Design Pattern

All new voucher creation pages follow a consistent design pattern inspired by Tally:

```
┌──────────────────────────────────────────────────────────┐
│  ← Back              Sales Invoice                       │
│                       Date: [2026-07-26]                 │
├──────────────────────────────────────────────────────────┤
│  Party (Dr):   [ Search Customer Ledger... ▼ ]           │
│  Sales A/c:    [ Search Sales Ledger...    ▼ ]           │
├──────────────────────────────────────────────────────────┤
│  ITEM GRID                                               │
│  ┌──────────────┬──────┬────────┬──────────┬──────────┐  │
│  │ Stock Item   │ Qty  │ Rate   │ Amount   │ Godown   │  │
│  ├──────────────┼──────┼────────┼──────────┼──────────┤  │
│  │ Product A    │ 10   │ 500.00 │ 5000.00  │ Main     │  │
│  │ Product B    │ 5    │ 200.00 │ 1000.00  │ Main     │  │
│  │ [+ Add Row]  │      │        │          │          │  │
│  └──────────────┴──────┴────────┴──────────┴──────────┘  │
├──────────────────────────────────────────────────────────┤
│  GST: [✓] 18%     Taxable: ₹6,000.00                    │
│                    CGST 9%: ₹540.00                      │
│                    SGST 9%: ₹540.00                      │
│                    ─────────────────                      │
│                    Grand Total: ₹7,080.00                │
├──────────────────────────────────────────────────────────┤
│  Narration: [_________________________________]          │
│                                                          │
│           [ Save Voucher ]    [ Cancel ]                 │
└──────────────────────────────────────────────────────────┘
```

---

## ⚡ Execution Order

| Priority | Page | Backend | Frontend | Effort |
|:---:|:---|:---|:---|:---:|
| 🔴 P0 | **Ledger Creation** (`/ledgers/new`) | ✅ Already built | 🔨 Build | ~0.5 day |
| 🔴 P0 | **Sales Invoice** (`/vouchers/new/sales`) | 🔨 New endpoint | 🔨 Build | ~1.5 days |
| 🔴 P0 | **Receipt Voucher** (`/vouchers/new/receipt`) | 🔨 New endpoint | 🔨 Build | ~1 day |
| 🟠 P1 | **Payment Voucher** (`/vouchers/new/payment`) | 🔨 New endpoint | 🔨 Build | ~1 day |
| 🟠 P1 | **Purchase Invoice** (`/vouchers/new/purchase`) | 🔨 New endpoint | 🔨 Build | ~1 day |
| 🟡 P2 | **Stock Item Creation** (`/stocks/new`) | ✅ Already built | 🔨 Build | ~0.5 day |
| 🟡 P2 | **Journal Voucher** (`/vouchers/new/journal`) | ✅ Generic `POST /vouchers` | 🔨 Build | ~0.5 day |
| 🟢 P3 | **Credit Note / Debit Note** | 🔨 New endpoints | 🔨 Build | ~1 day |
| 🟢 P3 | **Fix Outbound XML Builder** | 🔨 Fix sync.py | N/A | ~0.5 day |
| 🔵 P4 | **Contra / Stock Journal** | 🔨 New endpoints | 🔨 Build | ~1 day |

**Total estimated effort: ~8.5 days**

---

## Open Questions

> [!IMPORTANT]
> **Q1**: Which pages do you want built first? I'd recommend: **Ledger Creation → Sales Invoice → Receipt Voucher** as P0.

> [!IMPORTANT]
> **Q2**: For Sales Invoices — do you want the GST calculation to be automatic based on party state (interstate = IGST, intrastate = CGST+SGST), or should the user select the GST type manually?

> [!IMPORTANT]
> **Q3**: Should we also add a "Create New" button on the existing `/vouchers`, `/ledgers`, and `/stocks` list pages that routes to the new creation pages?

> [!IMPORTANT]
> **Q4**: For the outbound XML sync — should we fix that as part of P0 (so new vouchers actually sync to Tally), or defer it and fix later?
