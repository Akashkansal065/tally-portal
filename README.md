# Tally Portal (`tally-portal`)

`tally-portal` is a secure, real-time, bidirectional synchronization engine and management portal that bridges local **Tally Prime** ERP installations with a modern cloud-ready Web/Mobile ERP platform. 

It enables businesses to take local offline inventory, ledger balances, and transaction voucher registers and access them dynamically via a Next.js web application, while maintaining perfect database integrity.

---

## 🏗️ System Architecture

The application contains three core components:
1. **Local Tally Prime Server**: Runs locally at the business site with the XML ODBC Server enabled on a designated port (e.g., `9000`).
2. **Tally Sync Daemon (`tally_sync_daemon.py`)**: A lightweight background service running locally that queries Tally collections using TDL/XML, converts payloads, and pushes incremental data to the ERP backend.
3. **ERP Cloud Platform (FastAPI & Next.js)**: 
   - **Backend**: A Python FastAPI REST API connected to a MySQL database that parses Tally XML messages, handles GST return filing & reconciliation, and manages accounts, transactions, and inventory.
   - **Frontend**: A Next.js Web App featuring a rich, responsive interface for viewing stocks, invoices, GST returns (GSTR-1, GSTR-3B, GSTR-2B, GSTR-9), ledgers, and tracking orders.

---

## 🚀 Key Features

* **🔄 Bidirectional Tally Sync**: Incremental ledger, transaction voucher, and stock group synchronization with offline Tally Prime setups.
* **📊 Complete GST Returns & Reconciliation Suite (`/gst`)**:
  * **GSTR-1 Return Filing**: Auto-aggregates outward sales supplies, tax components (IGST/CGST/SGST), and HSN summary. Export official GSTR-1 JSON files for portal uploading.
  * **GSTR-3B Government PDF Layout**: Identical mirror of official GST Portal PDF summary (Table 3.1 Outward Taxable Supplies, Table 4 Eligible ITC, Table 5 Exempt/Nil-rated). Number formatting exactly matches government PDF standards (`0.00` without currency symbols or commas).
  * **GSTR-2B Portal Reconciliation Engine**:
    * **Direct GST Portal API Sync**: Multi-step OTP authentication flow via GSTN API (Request OTP, Verify OTP, Session Token Management) with live stream terminal & browser console request/response logs.
    * **Official Portal JSON Import**: Upload & parse official GSTR-2B JSON files (`b2b` and `cdnr` document arrays) with automatic local disk archiving under `storage/gstr2b/`.
    * **Dual-Pass Smart Matching Engine**: Reconciles GSTR-2B portal entries against Tally purchase vouchers, Manual Purchases, and ITC entries. Matches via invoice/reference numbers or smart fallback matching (Supplier Name/GSTIN + Net Tax Amounts within ₹2.00 tolerance across Fixed Assets, Equipment, Laptops/Printers, and Expenses).
    * **"+ Add to Books" Quick Action**: 1-click button on unmatched GSTR-2B rows to quickly add company asset/expense purchases (laptops, printers, office supplies, Amazon/Clicktech purchases) into `manual_purchases` table, auto-matching the row and claiming the ITC in GSTR-3B Table 4.
  * **Manual Purchases Register**: Track, manage, and claim ITC on non-inventory or direct company asset/expense purchases.
  * **GSTR-9 Annual Return & E-Invoicing**: Annual return generation & e-invoice IRN / QR code management.
* **📅 Attendance Log Portal**: Daily salesperson clock-in and checkout system. Features live session durations, geolocation verification, and watermarked webcam selfie stamping.
* **📍 GPS Shop Check-In**: GPS-verified client site check-ins with camera proofing and reverse-geocoded map watermarking overlays.
* **💼 Expense & Order Management**: Submit and review sales orders and expense claims directly from the field with receipt attachments.
* **🛡️ Admin Oversight Console**: User access role toggles, granular ledger/stock access scope scopes, and administrator password resets.

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
   - **SSL CA Certificate (For Cloud/Aiven Databases)**: 
     If your MySQL database requires certificate-validated SSL connections (e.g., Aiven MySQL), place your `ca.pem` certificate file directly inside the `backend/` folder. The application is configured to automatically detect and load it, and `.gitignore` ensures it is never pushed to Git.

 5. Initialize the Database and Seed Roles:
    Create the database schema and run the seed script:
    ```bash
    python3 -m app.core.seed
    ```

 6. Seed default Company and Admin:
    Run the company recreation utility to create company `Sneh Distributors` and the default admin user:
    ```bash
    python3 scratch/reset_companies.py
    ```

 7. Start the FastAPI backend:
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

---

### 3. Frontend Setup

1. Open a new terminal and navigate to the `frontend-nextjs` folder:
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
   *The daemon will load configuration endpoints and credentials directly from the `backend/.env` file.*

---

## 🔐 First-time Setup & Logging In

### Option A: Auto-Bootstrap (Recommended for New Installations)
If the database has zero registered administrator accounts (e.g., brand-new deployment), navigating to `http://localhost:3000/login` will automatically activate the **Bootstrap Setup Wizard**:
1. Provide your Company Name, Books Start Date, Administrator Name, Email, and Password.
2. Click **Register & Log In**. This initializes company defaults and registers your main administrator profile.
3. Once completed, public registration is automatically blocked on both backend and frontend layers.

### Option B: Use Seeded Credentials (If database was seeded)
If you ran seed scripts, log in using the default administrative credentials:
* **URL**: [http://localhost:3000/login](http://localhost:3000/login)
* **Email**: `admin_test@test.com`
* **Password**: `securepassword123`

---

## 🧹 Utilities and Reset Tools

The project includes administrative scripts inside `backend/scratch/` for database maintenance:

* **`reset_sync.py`**: Truncates all Tally-synced vouchers, resets the transaction sync AlterIDs to `0`, and rolls back stock item closing balances to their initial opening states.
  ```bash
  python3 scratch/reset_sync.py
  ```
* **`clear_tally_data.py`**: Truncates all accounting and transactional data tables, preparing the database for a completely clean start.
  ```bash
  python3 scratch/clear_tally_data.py
  ```
* **`reset_companies.py`**: Clears and recreates default companies, the default administrator user, and company permissions.
  ```bash
  python3 scratch/reset_companies.py
  ```
