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
│   │   ├── routers/             # 21 API router modules
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── services/            # Tally XML builder, importer, GST service
│   ├── scratch/                 # Admin scripts & Tally sync daemon
│   ├── tests/                   # Test suite
│   └── requirements.txt
├── frontend-nextjs/             # Next.js 16 + Tailwind CSS 4 frontend
│   ├── src/
│   │   ├── app/                 # 16+ route pages
│   │   ├── components/          # 20+ reusable components
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

## 🛠️ Step-by-Step Installation & Setup

### 1. Prerequisites
- **Python**: Version `3.10` or higher.
- **Node.js**: Version `18` or higher (with `npm`).
- **Database**: MySQL Server (or Docker — see `docker-compose.yml`).
- **Tally Prime**: Local client with XML Server enabled (under *F1 > Settings > Connectivity > Enable XML Server*).

---

### 2. Database Setup (Optional Docker)

To quickly spin up a MySQL instance:
```bash
docker-compose up -d
```

This starts MySQL 8.0 on port `3306` with database `mytally_db`. The backend will automatically create both `mytally_db` and `tally_sync` databases on first startup.

---

### 3. Backend Setup & Seeding

1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the environment variables:
   - Copy `.env.template` (or create a new `.env` file):
     ```bash
     cp .env.template .env
     ```
   - Open `.env` and fill in your MySQL details:
     ```env
     DATABASE_URL=mysql+aiomysql://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:3306/mytally_db
     JWT_SECRET=change-this-to-a-very-secure-secret-key
     ACCESS_TOKEN_EXPIRE_MINUTES=1440
     
     # Tally Database Name
     TALLY_DATABASE_NAME=tally_sync
     
     # SSL Connection (Set to true if using Aiven/cloud databases requiring SSL/TLS)
     DB_SSL=true
     
     # Tally Synchronization Settings
     TALLY_URL=http://127.0.0.1:9000
     ERP_URL=http://127.0.0.1:8000
     ERP_EMAIL=admin_test@test.com
     ERP_PASSWORD=securepassword123
     SYNC_FREQUENCY=120
     ```

 5. Initialize Database and Seed Roles:
    ```bash
    python3 -m app.core.seed
    ```

 6. Seed Default Company and Admin:
    ```bash
    python3 scratch/reset_companies.py
    ```

 7. Start the FastAPI Backend:
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

> **Note**: On first startup, the backend automatically creates both databases (`mytally_db` and `tally_sync`), runs schema migrations via `auto_sync_all_model_schemas()`, and seeds default roles/permissions if the database is empty.

---

### 4. Frontend Setup

1. Open a new terminal and navigate to `frontend-nextjs`:
   ```bash
   cd frontend-nextjs
   ```

2. Install Node modules:
   ```bash
   npm install
   ```

3. Configure the environment:
   ```bash
   cp .env.local.example .env.local
   ```
   Set `NEXT_PUBLIC_API_URL` to your backend URL (default: `http://localhost:8000`).

4. Run the Next.js development server:
   ```bash
   npm run dev
   ```
   *The client dashboard will be available at [http://localhost:3000](http://localhost:3000).*

---

### 5. Running the Desktop Sync Agent (Windows)

For environments where Tally Prime runs on a local Windows PC or VM:

1. Navigate to `desktop-sync-agent/`.
2. Configure `agent_config.json`:
   ```json
   {
       "backend_url": "http://your-cloud-backend:8000",
       "tally_url": "http://127.0.0.1:9000",
       "auth_token": "",
       "company_name": "Your Company Name",
       "sync_interval_seconds": 5,
       "inbound_interval_seconds": 60,
       "auto_discover_paths": true
   }
   ```
3. Run discovery to verify Tally connectivity:
   ```bash
   python agent.py --discover
   ```
4. Start the background sync daemon:
   ```bash
   python agent.py
   ```

**For standalone distribution** (no Python needed on client machines):
```cmd
cd installer
build_windows_exe.bat
```
→ Output: `dist/MyTallySyncAgent.exe`

---

### 6. Running the Legacy Tally Sync Daemon

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
