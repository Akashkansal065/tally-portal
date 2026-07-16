# Tally Portal (`tally-portal`)

`tally-portal` is a secure, real-time, bidirectional synchronization engine and management portal that bridges local **Tally Prime** ERP installations with a modern cloud-ready Web/Mobile ERP platform. 

It enables businesses to take local offline inventory, ledger balances, and transaction voucher registers and access them dynamically via a Next.js web application, while maintaining perfect database integrity.

---

## 🏗️ System Architecture

The application contains three core components:
1. **Local Tally Prime Server**: Runs locally at the business site with the XML ODBC Server enabled on a designated port (e.g., `9000`).
2. **Tally Sync Daemon (`tally_sync_daemon.py`)**: A lightweight background service running locally that queries Tally collections using TDL/XML, converts payloads, and pushes incremental data to the ERP backend.
3. **ERP Cloud Platform (FastAPI & Next.js)**: 
   - **Backend**: A Python FastAPI REST API connected to a MySQL database that parses Tally XML messages and updates accounts, transactions, and inventory.
   - **Frontend**: A Next.js Web App featuring a rich, responsive interface for viewing stocks, invoices, ledgers, and tracking orders.

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
     
     # Tally Synchronization Settings
     TALLY_URL=http://127.0.0.1:9000
     ERP_URL=http://127.0.0.1:8000
     ERP_EMAIL=admin_test@test.com
     ERP_PASSWORD=securepassword123
     SYNC_FREQUENCY=120
     ```

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

## 🔐 Logging In

For your initial login to the web portal, use the seeded admin credentials:

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
