# Tally Portal (`tally-portal`)

`tally-portal` is a secure, real-time, bidirectional synchronization engine and management portal that bridges local **Tally Prime** ERP installations with a modern cloud-ready Web/Mobile ERP platform. 

It enables field agents, accountants, sales executives, and managers to access offline inventory, ledger balances, transaction voucher registers, collect payments with camera proofing, record customer orders, track GPS check-ins, file GST returns, and manage daily operations from any device while maintaining database integrity.

---

## 🏗️ System Architecture & Staging Database Layer

The application operates on a hybrid dual-database architecture designed to isolate unvalidated field data from core accounting ledgers until manager approval:

```
┌─────────────────────────┐          ┌───────────────────────────┐          ┌─────────────────────────┐
│   Tally Prime (ODBC)    │  XML/TDL │ Tally Sync Daemon Service │ REST API │   FastAPI ERP Backend   │
│ Local Desktop Instance  │ ◄──────► │ (`tally_sync_daemon.py`)  │ ◄──────► │  Python 3.10 / MySQL    │
└─────────────────────────┘          └───────────────────────────┘          └────────────┬────────────┘
                                                                                         │
                                                                       ┌─────────────────┴─────────────────┐
                                                                       ▼                                   ▼
                                                          ┌───────────────────────────┐       ┌───────────────────────────┐
                                                          │ Core Synced DB            │       │ Portal Staging DB         │
                                                          │ (`tally_sync`)            │       │ (`mytally_db`)            │
                                                          │ Synced Ledgers, Vouchers, │       │ Field Orders, Payments,   │
                                                          │ & Stock Balances          │       │ Check-ins, Attendance     │
                                                          └───────────────────────────┘       └───────────────────────────┘
```

1. **Local Tally Prime Server**: Runs locally at the business site with the XML ODBC Server enabled on a designated port (e.g., `9000`).
2. **Tally Sync Daemon (`tally_sync_daemon.py`)**: A lightweight background service running locally that queries Tally collections using TDL/XML, converts payloads, and pushes incremental data to the cloud ERP backend.
3. **Core Synced Database (`tally_sync`)**: Holds real-time read-only snapshots of Tally master ledgers, stock items, vouchers, and opening/closing balances synced from Tally Prime.
4. **Portal Staging Database (`mytally_db`)**: Stores field-created records (`temp_orders`, `payments`, `attendance_logs`, `shop_checkins`, `manual_purchases`) for administrative review and approval before posting to core Tally tables.
5. **Next.js Web & Mobile Client (`frontend-nextjs`)**: A responsive interface built with Tailwind CSS, Next.js, and Lucide icons featuring mobile card views and desktop data tables.

---

## 🔄 Tally Prime & Portal Master-to-Voucher End-to-End Workflow

The following workflow diagram illustrates how accounting & inventory data originates, the mandatory creation order of master entities, daily voucher execution paths, field mobile integration, and final financial/tax reporting:

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
    subgraph PHASE4["4️⃣ Phase 4: Field Operations & Web Sync (Tally Portal)"]
        M1["Field Salesperson GPS Check-In"] --> M2["Create Field Order / Collect Payment"]
        M2 --> M3["Manager Review & Approval"]
        M3 --> M4["Tally Sync Daemon (XML/TDL)<br/>Posts Vouchers & Pulls Incremental AlterID"]
    end

    PHASE3 <--> PHASE4

    %% Phase 5: Reporting & Tax Compliance
    subgraph PHASE5["5️⃣ Phase 5: Financial Reporting & Tax Compliance"]
        R1["Daybook & Sales Register"]
        R2["Profit & Loss Statement"]
        R3["Balance Sheet"]
        R4["GST Returns (GSTR-1, GSTR-3B, GSTR-2B Recon)"]
    end

    PHASE3 & PHASE4 --> PHASE5
```

### 📋 Detailed Phase Breakdown & Execution Rules

1. **Phase 1: Setup & Configuration**
   - Establish company details, financial year start date, and enable required *F11 Features* (Inventory, GST, Billwise tracking, Cost Centers).

2. **Phase 2: Master Creation Hierarchy (Strict Prerequisite Order)**
   - **Step 2A (Units of Measure)**: Create UOMs (`Nos`, `Pcs`, `Box`, `Kg`) *first*, as Stock Items cannot exist without an assigned unit.
   - **Step 2B (Groups)**: Create Parent Account Groups (`Sundry Debtors`, `Sundry Creditors`) and Stock Groups (`Electronics`, `Apparel`).
   - **Step 2C (Stock Items)**: Create inventory stock items with HSN codes, GST tax percentages, opening quantities, and godown allocations.
   - **Step 2D (Ledger Accounts)**: Create customer/supplier party ledgers with GSTINs, credit limits, and statutory tax ledgers (`Output CGST`, `Output SGST`, `Input IGST`).

3. **Phase 3: Daily Voucher Execution Workflows**
   - **Sales Cycle**: Sales Quotation $\rightarrow$ Sales Order $\rightarrow$ Delivery Challan $\rightarrow$ **Sales Invoice** $\rightarrow$ **Receipt Voucher**.
   - **Purchase Cycle**: Purchase Order $\rightarrow$ Receipt Note (GRN) $\rightarrow$ **Purchase Invoice** $\rightarrow$ **Payment Voucher**.
   - **Banking & Adjustment**: Use **Contra Vouchers** for Cash/Bank transfers and **Journal Vouchers** for depreciation, tax adjustments, and year-end closing entries.

4. **Phase 4: Field Operations & Web Sync Integration**
   - Mobile users perform GPS Check-Ins, collect payments with camera proofing, and record field orders. Managers approve staged records, which the `tally_sync_daemon.py` service automatically posts into Tally Prime as XML vouchers.

5. **Phase 5: Financial Statements & GST Compliance**
   - System aggregates real-time transactions into Daybook, Sales Register, Stock Summary, Profit & Loss Statement, Balance Sheet, and files GSTR-1, GSTR-3B, and GSTR-2B reconciliations.

---

## 🚀 Key Features Overview

### 💸 1. Field Payment Collection & Watermarked Receipts (`/payments`)
* **Multi-Mode Support**: Collect payments via **Cash**, **Cheque**, or **UPI**.
* **Mandatory Receipt Proofing**: Requires photo upload for all payment modes before submission.
* **Cheque Date Inputs**: Dedicated date column for cheque clearance tracking.
* **Automated Watermark Stamping**: Uploaded receipts are dynamically stamped with Salesperson Name, Shop Title, Date & Time, and GPS Coordinates.
* **Review & Approval Workflow**: Pending payments are reviewed by managers to change status to `Approved` or `Cancelled`.
* **Date & Salesperson Filters**: Default date filter set to the current date (`YYYY-MM-DD`) with clear button for all-time view, plus admin salesperson dropdown filters.
* **Responsive Layouts**: Desktop Data Table view and compact Mobile Card layout.

### 📦 2. Field Sales Order Creation (`/temporders`)
* **3-Step Order Wizard**:
  - **Step 1**: Customer outlet selection (registered Tally ledgers or manual unregistered shop name mode).
  - **Step 2**: Stock item selection with multi-field instant auto-suggestions (matches product name, brand mapping, parent category, stock group, part number, and HSN code), manual rate entry (no auto-prefilling), 18% GST toggle, and field validation with red highlight indicators (`border-rose-500`) for missing inputs.
  - **Step 3**: Order narration and confirmation summary.
* **Order Edit & Expiry Control**: Editable within 30 minutes of creation prior to manager processing.

### 📍 3. GPS Shop Check-In & Visit Tracking (`/check-in`)
* **Location Verification**: Uses device GPS coordinates for client site check-ins.
* **Selfie & Proof Stamping**: Camera proof capture with watermarked location overlays.
* **Interactive Map Links**: Direct Google Maps links generated for every recorded visit.
* **Visit Logs & Filters**: Date picker filter defaulting to current date, salesperson filter, shop name search bar, and mobile card view.

### 📅 4. Attendance & Geofence Logs (`/attendance`)
* **Daily Punch-In / Punch-Out**: Tracks salesperson duty duration with real-time timers.
* **Selfie Stamping & Network Logs**: Geolocation verification, IP address logging, and watermarked selfies.

### 📊 5. Complete GST Returns & Reconciliation Suite (`/gst`)
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
| **Reports (P&L, Balance)** | CRUD | None |
| **Shop GPS Check-In** | CRUD | CRUD |
| **Attendance Portal** | CRUD | CRUD |

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
* **Data Limit Scopes**:
  - `ledgerScope`: Filter ledger accounts visibility (`full` / `dr_only` / `cr_only` / `none`).
  - `stockScope`: Filter stock inventory visibility (`full` / `none`).
  - `allowedStockGroups` / `allowedLedgerGroups`: Limit user data query scopes to specific stock/ledger groups only.

---

## 🔮 Roadmap: Complete Web-Based Tally Operations & Conflict-Free Sync Engine

Currently, temporary orders (`temp_orders`) and field payments (`payments`) are captured in portal staging tables (`mytally_db`). To transform `tally-portal` into a **complete substitute for native Tally Prime desktop operations**, the following feature roadmap and conflict-free synchronization engine will be implemented:

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                           WEB PORTAL FULL TALLY OPERATIONS ROADMAP                        │
├──────────────────────────┬──────────────────────────┬─────────────────────────────────────┤
│ 1. Voucher Creation      │ 2. Master Management     │ 3. Advanced Inventory & Warehouse   │
│  - Sales Invoices        │  - Customer/Supplier     │  - Godown-to-Godown Stock Transfers │
│  - Purchase Bills        │    Ledgers with GSTIN    │  - Physical Stock Verification      │
│  - Receipt Vouchers      │  - Stock Item Creation   │  - Delivery Challan & Quotations    │
│  - Payment Vouchers      │  - Price Lists & Levels  │  - Proforma Invoice Conversions     │
└──────────────────────────┴──────────────────────────┴─────────────────────────────────────┘
```

### 1. Bidirectional Voucher Posting Pipeline
- **Approved Order Posting**: Approved temporary field orders will automatically trigger Tally XML `Sales` / `Sales Order` voucher creation.
- **Approved Payment Posting**: Approved field payment receipts will post official Tally `Receipt` / `Payment` vouchers.
- **Direct Web Voucher Entry**: Allow authorized users to create Sales Invoices, Purchase Bills, Credit Notes, and Debit Notes directly from the web application.

### 2. Conflict-Free Data Sync & Concurrency Control
To prevent data discrepancies between local Tally Prime installations and the Web Portal:
- **Tally `AlterID` & `MasterID` Lock Tracking**:
  - Tally assigns an incremental `AlterID` to every master and voucher whenever edited.
  - Before modifying or posting a record from the web portal, the system checks `tally_alter_id`. If Tally modified the voucher locally in the interim, the portal flags a **Sync Conflict** for admin review rather than overwriting.
- **Idempotent Voucher Pushing (Client GUID Matching)**:
  - Web-created vouchers generate a unique UUID / Client GUID (`voucher_guid`).
  - During Tally XML import (`<VOUCHER REMOTEID="..." VOUCHERKEY="...">`), Tally uses this GUID to ensure that network drops or retry attempts never create duplicate vouchers in Tally.
- **Conflict Resolution Console**:
  - A dedicated UI screen for administrators to compare conflicting fields (e.g., local Tally edit vs web portal edit) and choose **"Keep Tally Version"** or **"Push Web Version"**.

### 3. Web Master Creation & Editing
- **Ledger Master Creation**: Create and edit Customer/Supplier ledgers directly on the web app (GSTIN validation, State, Address, Pincode, Credit Limit, and Group assignment), automatically pushing `<LEDGER>` XML to Tally.
- **Stock Item & Price Level Management**: Add new stock items, assign HSN codes, UOMs, tax rates, and manage party-wise Price Lists/Levels.

### 4. Inventory & Warehouse Workflows
- **Godown-to-Godown Stock Transfers**: Record `Stock Journal` vouchers on mobile for shifting stock between warehouses/godowns.
- **Physical Stock Verification**: Conduct stock counts on mobile devices and generate `Physical Stock` adjustment vouchers in Tally.
- **Sales Orders & Delivery Challans**: Full workflow supporting Sales Quotation -> Sales Order -> Delivery Note -> Sales Invoice.

### 5. Automated Bank Reconciliation & Gateways
- **Bank Statement Import**: Import bank e-statements (CSV/Excel) and match against Tally bank vouchers.
- **Razorpay / UPI Payment Gateway Integration**: Generate dynamic UPI QR codes for invoices with automatic Tally Receipt voucher creation upon payment webhook confirmation.

---

## 🛠️ Step-by-Step Installation & Setup

### 1. Prerequisites
- **Python**: Version `3.10` or higher.
- **Node.js**: Version `18` or higher (with `npm`).
- **Database**: MySQL Server.
- **Tally Prime**: Local client with XML Server enabled (under *F1 > Settings > Connectivity > Enable XML Server*).

---

### 2. Backend Setup & Seeding

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

---

### 3. Frontend Setup

1. Open a new terminal and navigate to `frontend-nextjs`:
   ```bash
   cd frontend-nextjs
   ```

2. Install Node modules:
   ```bash
   npm install
   ```

3. Run the Next.js development server:
   ```bash
   npm run dev
   ```
   *The client dashboard will be available at [http://localhost:3000](http://localhost:3000).*

---

### 4. Running the Tally Sync Daemon

To run the background sync utility that automatically queries your local Tally Prime instance and sends updates:

1. Ensure the backend FastAPI server and Tally Prime are both running.
2. Run the sync daemon from the backend virtual environment:
   ```bash
   python3 scratch/tally_sync_daemon.py
   ```

---

## 🧹 Maintenance & Reset Tools

The project includes administrative scripts inside `backend/scratch/` for database maintenance:

* **`reset_sync.py`**: Truncates all Tally-synced vouchers, resets transaction sync AlterIDs to `0`, and rolls back stock item closing balances to their initial opening states.
  ```bash
  python3 scratch/reset_sync.py
  ```
* **`clear_tally_data.py`**: Truncates all accounting and transactional data tables, preparing the database for a completely clean start.
  ```bash
  python3 scratch/clear_tally_data.py
  ```
* **`reset_companies.py`**: Clears and recreates default companies, default administrator users, and company permissions.
  ```bash
  python3 scratch/reset_companies.py
  ```
