# Tally Portal (`tally-portal`)

`tally-portal` is a secure, real-time, bidirectional synchronization engine and management portal that bridges local **Tally Prime** ERP installations with a modern cloud-ready Web/Mobile ERP platform. 

It enables field agents, accountants, sales executives, and managers to access offline inventory, ledger balances, transaction voucher registers, collect payments with camera proofing, record customer orders, track GPS check-ins, file GST returns, create & post vouchers directly to Tally, manage debtors aging & payment reminders, and run daily operations from any device while maintaining database integrity.

---

## 🏗️ System Architecture

The application operates on a **hybrid multi-database architecture** with three deployment tiers:

```
┌─────────────────────────┐          ┌───────────────────────────┐          ┌─────────────────────────┐
│   Tally Prime (ODBC)    │  XML/TDL │  Desktop Sync Agent       │ REST API │   FastAPI ERP Backend   │
│ Local Desktop Instance  │ ◄──────► │  (`desktop-sync-agent/`)  │ ◄──────► │  Python 3.10 / MySQL    │
└─────────────────────────┘          └───────────────────────────┘          └────────────┬────────────┘
                                                                                         │
                                                                       ┌─────────────────┴─────────────────┐
                                                                       ▼                                   ▼
                                                          ┌───────────────────────────┐       ┌───────────────────────────┐
                                                          │ Core Synced DB            │       │ Portal Staging DB         │
                                                          │ (`tally_sync`)            │       │ (`mytally_db`)            │
                                                          │ Synced Ledgers, Vouchers, │       │ Field Orders, Payments,   │
                                                          │ Stock Balances, Masters   │       │ Check-ins, Attendance,    │
                                                          │ Cost Centres, Currencies  │       │ Payroll, Gateway Txns,    │
                                                          └───────────────────────────┘       │ Sync Queue, Audit Logs    │
                                                                                              └───────────────────────────┘
```

### Component Breakdown

1. **Local Tally Prime Server**: Runs locally at the business site with the XML ODBC Server enabled on a designated port (e.g., `9000`).
2. **Desktop Sync Agent (`desktop-sync-agent/`)**: A standalone Windows background connector that bridges the local Tally Prime XML Server (`localhost:9000`) with the cloud ERP backend. Supports automatic Tally host discovery, bidirectional sync, and can be distributed as a single `.exe` without Python installed.
3. **Core Synced Database (`tally_sync`)**: Holds real-time snapshots of Tally master ledgers, groups, stock items, voucher types, cost centres, currencies, UOMs, godowns, and all accounting vouchers synced bidirectionally with Tally Prime.
4. **Portal Staging Database (`mytally_db`)**: Stores field-created records (`temp_orders`, `payments`, `attendance_logs`, `shop_checkins`, `manual_purchases`), sync queue, traffic logs, deleted record audits, payroll, payment gateway transactions, user sessions, RBAC, and approval workflows.
5. **Next.js Web & Mobile Client (`frontend-nextjs/`)**: A responsive interface built with Next.js 16, Tailwind CSS 4, Radix UI, shadcn/ui, Recharts, and Lucide icons — featuring mobile card views, desktop data tables, and a progressive web app experience.

---

## 📁 Project Structure

```
tally-portal/
├── backend/                     # FastAPI backend (Python 3.10+)
│   ├── app/
│   │   ├── core/                # Config, DB, security, RBAC permissions, cache, seed
│   │   ├── models/
│   │   │   ├── portal_core.py   # Portal staging DB models (50+ tables)
│   │   │   └── tally_core.py    # Tally synced DB models (60+ tables)
│   │   ├── routers/             # API router modules for auth, finance, masters, sync, and reporting
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── services/            # Tally XML builder, importer, GST service
│   ├── scratch/                 # Admin scripts & Tally sync daemon
│   ├── tests/                   # Test suite
│   └── requirements.txt
├── frontend-nextjs/             # Next.js 16 + Tailwind CSS 4 frontend
│   ├── src/
│   │   ├── app/                 # 42 App Router pages
│   │   ├── components/          # Reusable UI, forms, reports, and admin components
│   │   ├── context/             # Auth & Period context providers
│   │   ├── constants/           # App-wide constants
│   │   ├── lib/                 # Utility functions
│   │   └── types/               # TypeScript type definitions
│   └── vercel.json              # Vercel deployment config
├── desktop-sync-agent/          # Standalone Windows Tally connector
│   ├── agent.py                 # Main sync agent daemon
│   ├── tally_client.py          # Tally XML API client
│   ├── cloud_client.py          # Cloud ERP REST client
│   ├── config.py                # Agent configuration
│   └── installer/               # Windows .exe builder & auto-start scripts
├── docs/                        # Comprehensive documentation (16 docs)
├── docker-compose.yml           # MySQL 8.0 container
└── README.md
```

---

## 🔄 Tally Prime & Portal End-to-End Workflow

```mermaid
flowchart TD
    %% Phase 1: Company Setup
    subgraph PHASE1["1️⃣ Phase 1: Initial Setup & Configuration"]
        A["1. Create Company in Tally Prime<br/>(Name, Address, Financial Year, GSTIN)"] --> B["2. Enable F11 Features<br/>(Accounting, Inventory, GST, Bill-wise, Godowns)"]
    end

    %% Phase 2: Master Creation Hierarchy
    subgraph PHASE2["2️⃣ Phase 2: Master Creation Hierarchy (Prerequisites First)"]
        B --> C1["Step 2A: Create Units of Measure (UOM)<br/>(e.g., Pcs, Nos, Kg, Box)"]
        B --> C2["Step 2B: Create Account & Stock Groups<br/>(e.g., Sundry Debtors, Electronics, Expenses)"]
        
        C1 & C2 --> C3["Step 2C: Create Stock Items & Godowns<br/>(Linked to UOM + Stock Group + HSN/GST Rate)"]
        C2 --> C4["Step 2D: Create Ledger Accounts<br/>(Customers, Vendors, Sales AC, Tax Ledgers, Bank)"]
    end

    %% Phase 3: Transaction Execution Workflows
    subgraph PHASE3["3️⃣ Phase 3: Daily Transaction Workflows"]
        direction TB
        
        %% Sales Flow
        subgraph SALES["Sales & Collection Cycle"]
            S1["Sales Order / Quotation"] --> S2["Delivery Note / Challan"]
            S2 --> S3["Sales Invoice<br/>(Updates Customer Ledger & Deducts Stock)"]
            S3 --> S4["Receipt Voucher<br/>(Payment Collected via Cash/Bank/UPI)"]
        end

        %% Purchase Flow
        subgraph PURCHASE["Purchase & Payable Cycle"]
            P1["Purchase Order"] --> P2["Receipt Note / GRN"]
            P2 --> P3["Purchase Invoice<br/>(Creates Payable & Adds Stock)"]
            P3 --> P4["Payment Voucher<br/>(Vendor Payment via Bank/Cash)"]
        end

        %% Banking & Adjustments
        subgraph BANKING["Banking & Adjustments"]
            B1["Contra Voucher<br/>(Cash Deposit / Bank-to-Bank Transfer)"]
            J1["Journal Voucher<br/>(Adjustments, Expense Provisions, Depreciation)"]
        end
    end

    C3 & C4 --> PHASE3

    %% Phase 4: Web/Mobile Portal Sync
    subgraph PHASE4["4️⃣ Phase 4: Field Operations & Bidirectional Sync"]
        M1["Field Salesperson GPS Check-In"] --> M2["Create Field Order / Collect Payment"]
        M2 --> M3["Manager Review & Approval"]
        M3 --> M4["Desktop Sync Agent<br/>Realtime Bidirectional XML Push/Pull"]
    end

    PHASE3 <--> PHASE4

    %% Phase 5: Reporting & Tax Compliance
    subgraph PHASE5["5️⃣ Phase 5: Financial Reporting & Tax Compliance"]
        R1["Daybook & Sales Register"]
        R2["Profit & Loss Statement"]
        R3["Balance Sheet & Cash Flow"]
        R4["GST Returns (GSTR-1, GSTR-3B, GSTR-2B Recon)"]
        R5["Trial Balance & Ratio Analysis"]
    end

    PHASE3 & PHASE4 --> PHASE5
```

---

## 🚀 Key Features Overview

### 📊 1. Executive Dashboard (`/`)
* **Real-Time KPI Summary**: Period-filtered dashboard with total sales, purchases, receipts, payments, and net position.
* **Financial Year & Custom Period Selector**: Global date range context shared across all modules.
* **Quick Navigation Cards**: Role-aware cards linking to all portal modules based on RBAC permissions.
* **Detail Drill-Down Modals**: Click any KPI to view underlying voucher details.

---

### 🧾 2. Full Voucher Management (`/vouchers`)
* **Create, Edit, Delete & Cancel Vouchers**: Full CRUD for Sales, Purchase, Receipt, Payment, Journal, Contra, Credit Note, and Debit Note vouchers — directly from the web portal.
* **Bidirectional Tally Sync**: Every voucher created/edited/deleted in the portal is automatically pushed to Tally Prime as XML via the real-time sync engine. Changes in Tally are pulled back to the portal.
* **Multi-Ledger Accounting Entries**: Full double-entry accounting with party ledger, income/expense allocation, and tax ledger posting.
* **Inventory-Linked Vouchers**: Sales & Purchase vouchers automatically update stock quantities and godown allocations.
* **Bank Allocations & Discounts**: Assign bank instruments, track bill-wise allocations, and handle discount ledgers.
* **Bill-wise Settlement**: Automatic bill creation and settlement tracking for party outstanding management.
* **Cost Centre Allocations**: Voucher entries support cost centre tagging for departmental accounting.
* **Voucher Status Workflow**: Draft → Confirmed → Cancelled lifecycle with approval rules.
* **Mobile-Responsive Modal**: Full voucher creation form with responsive design, close/cancel touch handlers, and backdrop dismiss.
* **Financial Year Month Filters**: Quick filter by FY months, voucher type categories, and sort by date/amount.

---

### 📒 3. Ledger & Group Management (`/ledgers`)
* **Full Ledger CRUD**: Create, edit, and delete customer/supplier/expense/income/tax ledger accounts with GSTIN, State, Address, Credit Period, Pincode, and group assignments.
* **Group Hierarchy**: Manage nested account groups (Sundry Debtors, Sundry Creditors, Sales Accounts, Purchase Accounts, etc.).
* **Real-Time Tally Sync**: Ledger and Group changes are immediately pushed to Tally Prime as XML.
* **Deletion Audit Trail**: All deletions are logged in `deleted_records_audit` with full JSON snapshots for rollback capability.

---

### 📦 4. Complete Inventory Management (`/stocks`, `/masters/*`)
* **Units of Measure (UOM)**: Create simple & compound units with conversion factors (e.g., "Box of 12 Pcs").
* **Stock Groups & Categories**: Hierarchical stock group management with aliases and parent/child relationships.
* **Godowns / Warehouses**: Multi-location warehouse management with parent godown hierarchy.
* **Stock Items**: Full item master with HSN codes, GST rates, opening balances, godown allocations, alternate units, standard cost/price, and brand/part number mapping.
* **Price Levels & Price Lists**: Define pricing tiers and assign item-specific rates per price level.
* **Bill of Materials (BOM)**: Create manufacturing BOMs with component items, quantities, and manufacturing journal voucher generation.
* **Batch & Serial Number Tracking**: Track inventory by batch numbers and individual serial numbers.
* **Stock Item Voucher History**: View complete transaction history (purchases, sales, journals) for any stock item.
* **Real-Time Sync**: All inventory masters (UOM, Stock Group, Stock Category, Godown, Stock Item) are pushed to Tally in real-time via XML.

---

### 🧭 5. Accounting Masters (`/masters/*`)

12 master management modules accessible from the Masters section:

| Module | Route | Description |
| :--- | :--- | :--- |
| **Units of Measure** | `/masters/units` | Simple & compound UOM management |
| **Stock Groups** | `/masters/stock-groups` | Hierarchical stock classification |
| **Stock Categories** | `/masters/stock-categories` | Secondary stock classification |
| **Stock Items** | `/masters/stock-items` | Full stock item master with HSN/GST |
| **Godowns** | `/masters/godowns` | Warehouse / location management |
| **Price Levels** | `/masters/price-levels` | Pricing tier definitions |
| **Price Lists** | `/masters/price-lists` | Item-specific price level rates |
| **Voucher Types** | `/masters/voucher-types` | Custom voucher type configuration |
| **Currencies** | `/masters/currencies` | Multi-currency with ISO 4217 seed data |
| **Cost Categories** | `/masters/cost-categories` | Revenue/non-revenue cost categorization |
| **Cost Centres** | `/masters/cost-centres` | Hierarchical cost centre tree management |
| **Cost Centre Classes** | `/masters/cost-centre-classes` | Cost allocation class definitions |

---

### 💰 6. Outstanding & Aging Dashboard (`/outstanding`)
* **Debtors Aging Analysis**: Automatic bucketing of customer receivables into aging brackets (Current, 1–30, 31–60, 61–90, 90+ days).
* **Per-Customer Bill Drill-Down**: Expand any customer row to view individual open/overdue bills with due dates and outstanding amounts.
* **Dunning Level Classification**: Automatic classification into `CURRENT`, `GENTLE`, `FORMAL`, and `URGENT` reminder levels based on overdue severity.
* **KPI Summary Bar**: Total receivables, total overdue, current, and per-bucket aggregated amounts.
* **WhatsApp Payment Reminder Generation**: 1-click generation of formatted WhatsApp reminder messages (with UPI payment link) per customer or bulk generation across all overdue debtors.
* **Filterable by Sundry Debtors/Creditors**: Scoped to party ledgers under Sundry Debtors and Sundry Creditors groups only.

---

### 💸 7. Field Payment Collection & Watermarked Receipts (`/payments`)
* **Multi-Mode Support**: Collect payments via **Cash**, **Cheque**, or **UPI**.
* **Mandatory Receipt Proofing**: Requires photo upload for all payment modes before submission.
* **Cheque Date Inputs**: Dedicated date column for cheque clearance tracking.
* **Automated Watermark Stamping**: Uploaded receipts are dynamically stamped with Salesperson Name, Shop Title, Date & Time, and GPS Coordinates.
* **Review & Approval Workflow**: Pending payments are reviewed by managers to change status to `Approved` or `Cancelled`.
* **Date & Salesperson Filters**: Default date filter set to the current date with clear button for all-time view, plus admin salesperson dropdown filters.
* **Responsive Layouts**: Desktop Data Table view and compact Mobile Card layout.

---

### 📦 8. Field Sales Order Creation (`/temporders`)
* **3-Step Order Wizard**:
  - **Step 1**: Customer outlet selection (registered Tally ledgers or manual unregistered shop name mode).
  - **Step 2**: Stock item selection with multi-field instant auto-suggestions (matches product name, brand mapping, parent category, stock group, part number, and HSN code), manual rate entry (no auto-prefilling), 18% GST toggle, and field validation with red highlight indicators for missing inputs.
  - **Step 3**: Order narration and confirmation summary.
* **Order Edit & Expiry Control**: Editable within 30 minutes of creation prior to manager processing.

---

### 📍 9. GPS Shop Check-In & Visit Tracking (`/check-in`)
* **Location Verification**: Uses device GPS coordinates for client site check-ins.
* **Selfie & Proof Stamping**: Camera proof capture with watermarked location overlays.
* **Interactive Map Links**: Direct Google Maps links generated for every recorded visit.
* **Visit Logs & Filters**: Date picker filter defaulting to current date, salesperson filter, shop name search bar, and mobile card view.

---

### 📅 10. Attendance & Geofence Logs (`/attendance`)
* **Daily Punch-In / Punch-Out**: Tracks salesperson duty duration with real-time timers.
* **Selfie Stamping & Network Logs**: Geolocation verification, IP address logging, and watermarked selfies.

---

### 📊 11. Comprehensive Reporting Suite (`/reports`)

The reports module provides a full financial analytics suite with **2-hour in-memory caching** and date-range filtering:

| Report | Description |
| :--- | :--- |
| **Dashboard Summary** | Aggregated KPIs — total sales, purchases, receipts, payments, and net position |
| **Executive Analytics** | Revenue trends, expense breakdowns, top customers/suppliers with chart visualizations |
| **Daybook** | Complete chronological transaction journal |
| **Sales Register** | Itemized sales voucher register |
| **Outstanding Payables** | Supplier payable balances |
| **Trial Balance** | Account-wise debit/credit balance summary |
| **Profit & Loss** | Income vs. expense statement with group hierarchy |
| **Balance Sheet** | Assets, Liabilities, and Capital position |
| **Cash Flow Statement** | Operating, Investing, and Financing activity classification |
| **Ratio Analysis** | Current Ratio, Quick Ratio, Debt-to-Equity, and profitability metrics |
| **Top Customers** | Revenue-ranked customer analysis |
| **Inventory Analytics** | Stock valuation, movement analysis, and slow-moving items |
| **Inactive Parties** | Identify dormant customer/supplier accounts |
| **Inactive Items** | Identify dormant stock items with no recent transactions |

---

### 📊 12. Complete GST Returns & Reconciliation Suite (`/gst`)
* **GSTR-1 Return Filing**: Auto-aggregates outward sales supplies, tax components (IGST/CGST/SGST), and HSN summaries. Exports official GSTR-1 JSON files for portal uploading.
* **GSTR-3B Government PDF Layout**: Identical mirror of official GST Portal PDF summary (Table 3.1 Outward Taxable Supplies, Table 4 Eligible ITC, Table 5 Exempt/Nil-rated). Number formatting matches government PDF standards (`0.00`).
* **GSTR-2B Portal Reconciliation Engine**:
  - **Direct GST Portal API Sync**: Multi-step OTP authentication flow via GSTN API (Request OTP, Verify OTP, Session Token Management) with live stream terminal & browser console request/response logs.
  - **Official Portal JSON Import**: Upload & parse official GSTR-2B JSON files (`b2b` and `cdnr` document arrays) with automatic local disk archiving under `storage/gstr2b/`.
  - **Dual-Pass Smart Matching Engine**: Reconciles GSTR-2B portal entries against Tally purchase vouchers, Manual Purchases, and ITC entries. Matches via invoice numbers or smart fallback matching (Supplier Name/GSTIN + Net Tax Amounts within ₹2.00 tolerance across Fixed Assets, Equipment, Laptops/Printers, and Expenses).
  - **"+ Add to Books" Quick Action**: 1-click button on unmatched GSTR-2B rows to add company asset/expense purchases into `manual_purchases` table, auto-matching the row and claiming ITC in GSTR-3B Table 4.
* **Manual Purchases Register**: Track, manage, and claim ITC on non-inventory or direct company asset/expense purchases.
* **GSTR-9 Annual Return & E-Invoicing**: Annual return generation & e-invoice IRN / QR code management.
* **GST Compliance Control Tower**: Period validation, persisted exception queues, append-only filing evidence, and period locking before provider submission.
* **GST Provider Boundary**: Idempotent mock/sandbox submission with immutable payload/response evidence; production connectors remain deployment-configured behind the same interface.

---

### 🔄 13. Bidirectional Tally Sync Engine

The sync engine provides full bidirectional data synchronization between the cloud portal and local Tally Prime installations:

#### Outbound (Portal → Tally)
* **Real-Time Entity Push**: All portal-created/edited masters and vouchers are immediately pushed to Tally as XML via the Sync Queue.
* **Supported Entities**: Vouchers, Ledgers, Groups, Stock Items, UOMs, Stock Groups, Stock Categories, Godowns, Cost Categories, Cost Centres, Cost Centre Classes, Currencies, Voucher Types.
* **Retry & Error Handling**: Failed sync items are tracked with attempt count, error messages, last payload/response, and can be retried individually.

#### Inbound (Tally → Portal)
* **Incremental Sync via AlterID**: The inbound sync uses Tally's `AlterID` tracking to pull only newly created/modified records since last sync.
* **Full XML Import Engine**: The `tally_xml_importer.py` service parses complex Tally XML collections and maps them to the relational database schema.
* **Desktop Sync Agent**: A standalone Windows connector (`desktop-sync-agent/`) handles bidirectional communication without requiring router port forwarding.

#### Sync Audit & Monitoring
* **Sync Traffic Logs**: Every sync operation is logged with outbound payload, inbound response, parsed metrics (created/altered/deleted/errors), duration, and copy-paste cURL command for debugging.
* **Deleted Record Audit Trail**: All deletions maintain a full JSON snapshot of the entity before deletion, with Tally sync status tracking (Pending, Synced, Failed).
* **Conflict Resolution Console**: Compare local portal edits vs. Tally edits and choose "Keep Tally Version" or "Push Web Version".
* **Health Endpoint**: Real-time sync health check reporting Tally connectivity status.

---

### 🖥️ 14. Desktop Sync Agent (`desktop-sync-agent/`)

A standalone Windows background connector for environments where Tally runs on a local PC/VM:

* **Zero Router Port Forwarding**: Makes secure outbound connections from the office PC to the cloud backend.
* **Automatic Tally Discovery**: Auto-detects Tally installation path, company data path, `tallysave.tsf`, `tally.ini`, and active company name.
* **Bidirectional Sync**: Pulls pending creates/edits from the cloud queue and pushes to Tally; extracts new vouchers/masters from Tally and syncs to cloud.
* **Resilient Retry**: Gracefully handles network drops and Tally restarts without losing transactions.
* **Standalone `.exe` Distribution**: Build a single Windows executable via `build_windows_exe.bat` for client distribution without Python.
* **Auto-Start on Boot**: 1-click batch scripts or CLI commands to enable/disable Windows startup persistence.
* **Windows Service (NSSM)**: Run as a background Windows service for headless VMs.

---

### 💳 15. Payment Gateway Integration (`/gateways`)
* **Razorpay & Stripe Support**: Configure gateway API keys (public/secret/webhook) per company.
* **Payment Link Generation**: Create shareable payment links tied to specific outstanding bills.
* **Webhook Processing**: Automatic webhook event ingestion with signature verification.
* **Auto-Settlement**: Gateway transactions automatically create bill allocations and receipt vouchers.
* **Test & Live Mode**: Toggle between sandbox and production gateway environments.

---

### 👥 16. Advanced Modules

#### Payroll & HR (`/payroll/*`)
* **Employee Master**: Link employees to user accounts with employee codes, designations, departments, and payment ledgers.
* **Salary Components**: Define earning and deduction components (Fixed, % of Basic, Formula-based) with statutory flags.
* **Salary Structures**: Assign component-wise CTC structures with effective date ranges.
* **Payroll Periods**: Monthly payroll processing with Draft → Processed → Paid → Locked lifecycle.
* **Payslip Generation**: Auto-computed payslips with gross earnings, deductions, net pay, and linked voucher posting.

#### Currency & TDS (`/currencies/*`, `/tds/*`)
* **Multi-Currency Support**: ISO 4217 currency master with 40+ pre-seeded global currencies including symbol placement, decimal settings, and amount-in-words configuration.
* **Exchange Rates**: Manual/RBI/API-sourced exchange rate management per currency per date.
* **TDS/TCS Sections**: Define TDS sections with rate thresholds and PAN-linked applicability.
* **Lower Deduction Certificates**: Track LDC details for reduced TDS deduction.
* **TDS/TCS Entry Register**: Record and manage TDS/TCS deducted/collected entries.

#### E-Invoicing
* **IRN & QR Code Management**: Generate/store Invoice Reference Numbers and acknowledgement details.
* **E-Way Bill Tracking**: E-Way bill number and date management per voucher.
* **Mock & Production Modes**: Test e-invoicing flow before connecting to live NIC portal.

#### POS Payments
* **Point-of-Sale Payment Recording**: Multi-method (Cash, Card, UPI, Wallet) payment capture with linked voucher creation.

---

### 🏢 17. Multi-Company Architecture (`/companies`)
* **Multi-Tenancy**: Create and manage multiple companies with independent financial years, features, and user access.
* **Company Switcher**: Users with `UserCompanyAccess` records can switch between companies without re-login.
* **Feature Toggles**: Enable/disable company-specific features via a JSON `features` configuration.
* **Financial Year Management**: Define and lock financial year periods per company.
* **Company Import from Tally**: Tally sync automatically imports company metadata (GSTIN, PAN, address, FY dates) during initial sync.

---

## 🛡️ Roles & Permissions Matrix

The portal initializes 2 standard system roles with the following default module authorization scopes:

| Module / Feature | Admin | User (Default) |
| :--- | :---: | :---: |
| **User Directory** | CRUD | None |
| **Tally Sync** | CRUD | None |
| **Ledgers & Groups** | CRUD | None |
| **Vouchers & Invoices** | CRUD | None |
| **Inventory & Stocks** | CRUD | None |
| **Orders & Expenses** | CRUD | CRUD (Orders Only) |
| **GST Returns & Reconciliations** | CRUD | Read |
| **Reports (P&L, Balance Sheet)** | CRUD | None |
| **Shop GPS Check-In** | CRUD | CRUD |
| **Attendance Portal** | CRUD | CRUD |
| **Payroll** | CRUD | None |
| **Payment Gateways** | CRUD | None |
| **Settings** | CRUD | None |

> *Legend: **C** = Create, **R** = Read, **U** = Update, **D** = Delete*

### ⚙️ Granular User Scope Visibility Settings
Administrators can override these standard roles with granular user-specific permission flags and data visibility scopes:

* **Menu Access Visibility**:
  - `showLedger` (Ledger Directory menu item visibility)
  - `showSalesLedgers` (Debit balances / Customer ledgers visibility)
  - `showPurchaseLedgers` (Credit balances / Supplier ledgers visibility)
  - `showReceipts` (Cash & bank receipt records visibility)
  - `showPayments` (Cash & bank payment records visibility)
  - `showExpenses` (Expenses submission & approval visibility)
  - `showStocks` (Stock item list and stock groups visibility)
  - `showReports` (P&L Statement, Balance Sheet & GST Returns visibility)
  - `showOrders` (Sales order submission visibility)
  - `showCheckIn` (GPS-verified Shop Check-In visibility)
  - `showGst` (GST module visibility)
  - `showAttendance` (Attendance module visibility)
* **Data Limit Scopes**:
  - `ledgerScope`: Filter ledger accounts visibility (`full` / `dr_only` / `cr_only` / `none`).
  - `stockScope`: Filter stock inventory visibility (`full` / `none`).
  - `allowedStockGroups` / `allowedLedgerGroups`: Limit user data query scopes to specific stock/ledger groups only.
  - `allowedReportCategories`: Restrict which report categories a user can access.

### 🔐 Advanced Permission Features
* **User Permission Overrides**: Grant or revoke individual CRUD permissions per module per user, with reason, granter tracking, and optional expiry date.
* **User Data Scopes**: Restrict data access by Godown, Cost Center, or Voucher Type.
* **Session Management**: Token-based sessions with IP/User-Agent tracking, expiry, and revocation.
* **Audit Logging**: All entity mutations are logged with old/new values, user ID, and timestamp.

---

## 🛠️ Complete Step-by-Step Setup Guide (From Scratch)

### 📋 Prerequisites & System Requirements

Before starting, ensure your machine has the following tools installed:

| Component | Minimum Version | Verification Command | Purpose |
|---|---|---|---|
| **Python** | 3.10+ | `python3 --version` | FastAPI backend & sync daemons |
| **Node.js** | 18.x or 20+ | `node -v` & `npm -v` | Next.js frontend & Capacitor CLI |
| **MySQL** | 8.0+ | `mysql --version` | Primary transactional databases |
| **Java JDK** | 17 or 21 | `javac -version` & `keytool` | Android APK compilation & signing |
| **Android SDK** | API 34+ (UpsideDownCake) | `echo $ANDROID_HOME` | Native Android build tools |
| **Tally Prime** | 3.0+ / 4.0+ | Port `9000` | Local ERP instance (optional for pure web testing) |

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/Akashkansal065/tally-portal.git
cd tally-portal
```

---

### Step 2: Database Setup

The backend uses a dual-database architecture:
1. `mytally_db`: Operational data (attendance, shop check-ins, temporary orders, payments, audit logs, users, RBAC).
2. `tally_sync`: Synced mirror of Tally Prime ledgers, stock items, vouchers, cost centres, and tax masters.

#### Option A: Using Docker (Recommended for quick local setup)
Start the pre-configured MySQL 8.0 container:
```bash
docker-compose up -d
```
*Starts MySQL on `localhost:3306` with user `root` and default password `root`.*

#### Option B: Using Existing / Local MySQL Server
Ensure your local MySQL service is running:
```sql
CREATE DATABASE IF NOT EXISTS mytally_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS tally_sync CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

### Step 3: Backend Setup & Seeding (FastAPI)

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a Python virtual environment**:
   ```bash
   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate

   # Windows (Command Prompt)
   python -m venv venv
   venv\Scripts\activate.bat
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create `backend/.env` with your database and authentication configuration:
   ```env
   # Database Connection (aiomysql async driver)
   DATABASE_URL=mysql+aiomysql://root:root@127.0.0.1:3306/mytally_db
   TALLY_DATABASE_NAME=tally_sync

   # Security & Session Secrets
   JWT_SECRET=change-this-to-a-very-secure-random-secret-key-32chars
   ACCESS_TOKEN_EXPIRE_MINUTES=43200

   # SSL Connection (Set to true if using cloud managed DB like Aiven/AWS RDS)
   DB_SSL=false

   # Tally Connectivity Defaults
   TALLY_URL=http://127.0.0.1:9000
   ERP_URL=http://127.0.0.1:8000
   ERP_EMAIL=admin@snehdistributors.com
   ERP_PASSWORD=SecurePassword123!
   SYNC_FREQUENCY=120
   ```

5. **Initialize Database Tables & Seed Roles**:
   ```bash
   python3 -m app.core.seed
   ```

6. **Seed Default Company & Admin Workspace**:
   ```bash
   python3 scratch/reset_companies.py
   ```

7. **Start the FastAPI Backend**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - **API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

> [!NOTE]
> On startup, the backend automatically runs `auto_sync_all_model_schemas()` which creates or migrates missing tables in both `mytally_db` and `tally_sync`.

---

### Step 4: Web Frontend Setup (Next.js 16 PWA)

1. **Open a new terminal and navigate to the frontend directory**:
   ```bash
   cd frontend-nextjs
   ```

2. **Install Node packages**:
   ```bash
   npm install
   ```

3. **Configure Environment Variables**:
   Create `frontend-nextjs/.env.local`:
   ```env
   # API Backend Server endpoint
   NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000

   # ImageKit CDN (Optional: for receipt & photo hosting)
   NEXT_PUBLIC_IMAGEKIT_PUBLIC_KEY=your_imagekit_public_key
   NEXT_PUBLIC_IMAGEKIT_URL_ENDPOINT=https://ik.imagekit.io/your_endpoint
   ```

4. **Start Development Server**:
   ```bash
   npm run dev
   ```
   *The web portal is accessible at [http://localhost:3000](http://localhost:3000).*

---

### Step 5: Mobile App Setup & Build (Capacitor Android & iOS)

The mobile client is built on a **co-located Capacitor 7 native shell** inside `frontend-nextjs`, enabling native background GPS tracking, camera proofs, audio notes, biometrics, and push notifications.

```
frontend-nextjs/
├── capacitor.config.ts          # Native bridge configuration
├── android/                    # Complete Android Studio project (Gradle 8.14)
│   ├── app/build.gradle        # App build config with automated signing
│   ├── key.properties.example  # Keystore credentials template
│   └── key.properties          # Local signing secrets (gitignored)
└── ios/                        # Complete Xcode project (CocoaPods/SPM)
```

#### 5.1 Native Platform Dependencies
Ensure Java 17/21 and Android SDK tools are present:
```bash
java -version
keytool
```

#### 5.2 Synchronize Web Code with Native Shells
Whenever web code or plugins change, sync the native Android and iOS wrappers:
```bash
cd frontend-nextjs
npm run cap:sync
```

#### 5.3 Building the Android Debug APK
Build a debug APK directly from the terminal without opening Android Studio:
```bash
npm run build:apk
```
*Generated output:*
`frontend-nextjs/android/app/build/outputs/apk/debug/app-debug.apk`

To install on a connected phone/emulator via ADB:
```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

---

#### 5.4 Automated Release Signing (Production APK)

Release signing is fully automated via Gradle and `android/key.properties`.

1. **Generate a Release Keystore (One-Time Setup)**:
   ```bash
   cd frontend-nextjs/android
   keytool -genkeypair -v \
     -keystore mytally-release.keystore \
     -alias mytally \
     -keyalg RSA \
     -keysize 2048 \
     -validity 10000 \
     -storepass "YourSecurePassword123!" \
     -keypass "YourSecurePassword123!" \
     -dname "CN=MyTally, OU=Mobile, O=Sneh Distributors, L=Noida, ST=UP, C=IN"
   ```

2. **Configure `android/key.properties`**:
   Copy the example file:
   ```bash
   cp key.properties.example key.properties
   ```
   Fill in your keystore credentials:
   ```properties
   storeFile=mytally-release.keystore
   storePassword=YourSecurePassword123!
   keyAlias=mytally
   keyPassword=YourSecurePassword123!
   ```
   *(Note: `key.properties` and `*.keystore` are protected in `.gitignore` and will never be committed to git).*

3. **Build the Signed Release APK (1-Command Build)**:
   ```bash
   cd frontend-nextjs
   npm run build:apk-release
   ```
   *Generated output:*
   `frontend-nextjs/android/app/build/outputs/apk/release/app-release.apk`

4. **Verify Cryptographic Signature**:
   ```bash
   apksigner verify --verbose android/app/build/outputs/apk/release/app-release.apk
   ```
   Expected output: `Verifies: true` & `APK Signature Scheme v2: true`.

---

#### 5.5 Native Permissions Configured in `AndroidManifest.xml`

All 30 essential mobile permissions are pre-configured:
- 📍 **Location**: `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`
- 📸 **Camera**: `CAMERA` with autofocus and front-facing support
- 🎙️ **Microphone**: `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`
- 📁 **Storage & Media**: `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, `READ_MEDIA_IMAGES/VIDEO/AUDIO`
- 🔋 **Background Persistence**: `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, `WAKE_LOCK`, `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`
- 🔔 **System**: `POST_NOTIFICATIONS`, `VIBRATE`, `SCHEDULE_EXACT_ALARM`, `RECEIVE_BOOT_COMPLETED`
- 🔒 **Biometrics & Hardware**: `USE_BIOMETRIC`, `USE_FINGERPRINT`, `CALL_PHONE`, `READ_PHONE_STATE`, `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN`

---

#### 5.6 Background GPS & OEM Battery Bypass

Field force tracking requires location updates while the app is closed or the screen is locked:
1. **Foreground Service Notification**: While attendance is active, Android displays a sticky status notification: *"MyTally Shift Active — Recording field location"*, preventing OS kills.
2. **OEM Battery Killer Bypass**: Devices from Xiaomi, Samsung, Vivo, and Oppo aggressively kill background tasks. The app provides built-in guidance (`getOEMBatteryGuidance()`) directing users to set battery optimization to **"Unrestricted / No restrictions"**.

---

#### 5.7 iOS Platform Setup (Optional)
To test or build on iOS (macOS with Xcode required):
```bash
cd frontend-nextjs
npx cap open ios
```
All 12 required `Info.plist` usage descriptions (Camera, Location, Microphone, Photo Library, Biometrics, Motion) and `UIBackgroundModes` (`location`, `fetch`, `remote-notification`, `audio`) are pre-configured.

---

### Step 6: Desktop Sync Agent Setup (Windows)

For environments where Tally Prime runs on a local Windows machine or VM:

1. Navigate to `desktop-sync-agent/`.
2. Configure `agent_config.json`:
   ```json
   {
       "backend_url": "http://your-cloud-backend:8000",
       "tally_url": "http://127.0.0.1:9000",
       "auth_token": "",
       "company_name": "Sneh Distributors",
       "sync_interval_seconds": 5,
       "inbound_interval_seconds": 60,
       "auto_discover_paths": true
   }
   ```
3. Test Tally discovery:
   ```bash
   python agent.py --discover
   ```
4. Start the background sync daemon:
   ```bash
   python agent.py
   ```
5. **Build Standalone Windows `.exe`** (no Python required on client machines):
   ```cmd
   cd desktop-sync-agent/installer
   build_windows_exe.bat
   ```
   *Generated output:* `desktop-sync-agent/dist/SnehDistribuorsSync.exe`

---

### Step 7: Running the Legacy Tally Sync Daemon (Optional)

To run the cloud-side background sync utility (alternative to the Desktop Sync Agent):

1. Ensure the backend FastAPI server and Tally Prime are both running.
2. Run the sync daemon from the backend virtual environment:
   ```bash
   python3 scratch/tally_sync_daemon.py
   ```

---

## 🧹 Maintenance & Reset Tools

The project includes administrative scripts inside `backend/scratch/` for database maintenance:

| Script | Purpose |
| :--- | :--- |
| `reset_sync.py` | Truncates all Tally-synced vouchers, resets AlterIDs to `0`, and rolls back stock balances to initial opening states. |
| `clear_tally_data.py` | Truncates all accounting and transactional data tables for a completely clean start. |
| `reset_companies.py` | Clears and recreates default companies, admin users, and company permissions. |
| `clear_companies_data.py` | Clears all company-specific data while preserving company records. |
| `clear_logs.py` | Purges sync traffic logs and audit entries. |
| `clear_modules.py` | Resets module definitions. |
| `wipe_all.py` | Nuclear reset — truncates all tables across both databases. |
| `setup_databases.py` | Manually creates database schemas if auto-creation is unavailable. |
| `migrate_rbac.py` | Migrates legacy permission structures to the current RBAC model. |
| `compare_dbs.py` | Compares data between two database instances for sync validation. |
| `find_gst_diff.py` | Identifies GST calculation discrepancies between Tally and portal. |
| `check_sync_counts.py` | Verifies record counts between Tally and the synced database. |
| `run_sync_manually.py` | Triggers a one-time manual sync cycle. |

---

## 🧰 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.10+, FastAPI 0.139, SQLAlchemy 2.0 (async), Pydantic 2.13 |
| **Frontend** | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, Radix UI, shadcn/ui |
| **Database** | MySQL 8.0 (dual-database: `mytally_db` + `tally_sync`) |
| **Auth** | JWT (PyJWT) with bcrypt password hashing, session management |
| **Charts** | Recharts 3.9 |
| **PDF** | jsPDF 4.2, QR Code (qrcode.react) |
| **Deployment** | Vercel (frontend), Docker Compose (MySQL), Windows `.exe` (Sync Agent) |
| **Sync Engine** | XML/TDL over HTTP to Tally Prime port 9000 |
| **Monitoring** | Vercel Speed Insights |

---

## 📄 Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
| :--- | :--- |
| `DATABASE_DOCUMENTATION.md` | Complete database schema reference for both databases |
| `TALLY_SYNC_FLOW.md` | Detailed sync flow documentation |
| `TALLY_DISTRIBUTED_SYNC.md` | Distributed sync architecture guide |
| `TALLY_SYNC_VALIDATION.md` | Sync validation procedures |
| `TALLY_CRASH_PREVENTION_GUIDE.md` | Tally XML crash prevention patterns |
| `TallyPrime_API_Reference.md` | Tally XML/TDL API reference |
| `TallyPrime_API_Tag_ReferenceV3.md` | Tally XML tag reference (v3) |
| `Tally_Inventory_Integration_Guide.md` | Inventory sync integration guide |
| `Tally_Vouchers_Integration_Guide.md` | Voucher sync integration guide |
| `Tally_Ledger_apis.md` | Ledger API integration reference |
| `Tally_System_Discovery_and_Sync_Guide.md` | Tally system discovery documentation |
| `ERP_FEATURES_DOCUMENTATION.md` | Feature roadmap and capabilities |
| `tally_implement.md` | Implementation notes |
| `tally_integration_guide.md` | General integration guide |
| `livekeeping.md` | Live bookkeeping workflow guide |
| `sync_failure_analysis.md` | Sync failure debugging guide |
