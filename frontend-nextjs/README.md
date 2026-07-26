# Tally Portal Frontend (`frontend-nextjs`)

This is the Next.js frontend application for the Tally Portal. Built with Next.js 16 (App Router), Tailwind CSS v4, Lucide React, and Radix UI primitives, it provides a modern web interface for viewing synced Tally ERP data, managing ledgers & stock items, conducting geocoded check-ins, tracking attendance, creating sales orders, and overseeing user permissions.

---

## 🚀 Core Features & Modules

### 🔐 Authentication & Bootstrapping
* **Auto-Bootstrap Wizard**: Automatically detects if the backend database has zero registered administrators. If empty, redirects to a setup wizard to initialize the first company and admin profile.
* **JWT Sign In**: Secure sign-in panel verifying against backend JWT authentication.

### 📊 Ledgers & Vouchers
* **Ledgers Overview**: View synced customer and supplier accounts, ledger groups, balances, and search/filter accounts.
* **Ledger Detail & History**: Detailed transaction logs, outstanding balances, and voucher drill-downs.
* **Voucher Viewer**: View sales invoices, receipts, payment vouchers, and journal entries with PDF generator export capabilities.

### 📦 Inventory & Stock Items
* **Stock Management**: Search and filter stock items, view stock groups, current stock quantities, rates, and unit measurements.

### 📝 Sales Orders (Temp Orders)
* **Order Creation & Editing**: Create new sales orders with dynamic stock item selection, rate calculation, tax computations, and customer selection.
* **Order Tracking**: Manage temporary order statuses, view history, and export PDF quotes/orders.

### 💰 Finance, GST & Expenses
* **Expense Management**: Track daily operational expenses with category breakdowns.
* **GST Summary**: Overview of GST outputs/inputs and tax reports.
* **Payments Management**: Record and track customer/vendor payments.

### 📅 Attendance & GPS Check-In
* **Live Timer Clock**: Dynamic clock displaying local time (`en-IN` formatting) with in-memory hydration fixes to prevent React SSR mismatches.
* **Geocoded Selfie Attendance**: Utilizes HTML5 webcam canvas context to overlay name, date, time, and coordinates directly onto selfie photos before uploading.
* **GPS Shop Check-In**: Captures field sales check-in records with real-time browser geolocation, reverse-geocoded map watermarking, and camera photo proofs.

### 🛡️ Admin Oversight Control Panel
* **Directory Management**: Create new user accounts and toggle status (Active/Disabled).
* **Company Workspaces**: Dynamic dialog to create and seed new company workspaces and admin profiles.
* **Granular Scopes & Permissions**: Override role settings with detailed menu flags (`showLedger`, `showStocks`, `showReports`, `showOrders`, `showCheckIn`) and data query scopes (`ledgerScope`, `stockScope`, allowed stock/ledger groups).
* **Audit & Visit Logs**: Monitor background sync activity, salesperson logins, password resets, and field visit logs.

---

## 📂 Project Structure

```text
frontend-nextjs/
├── src/
│   ├── app/                    # Next.js App Router Pages
│   │   ├── admin/              # Admin oversight, permissions & visit logs
│   │   ├── attendance/         # Geocoded selfie attendance log
│   │   ├── check-in/           # Salesperson shop GPS check-in page
│   │   ├── expenses/           # Expense tracking
│   │   ├── gst/                # GST summary and tax reports
│   │   ├── ledgers/            # Ledger directory & details ([id])
│   │   ├── login/              # Sign in and auto-bootstrap screen
│   │   ├── payments/           # Payment entry & history
│   │   ├── reports/            # Business reporting dashboard
│   │   ├── stocks/             # Inventory stock items viewer
│   │   ├── temporders/         # Sales orders management (/new, /edit/[id])
│   │   ├── vouchers/           # Voucher transactions & PDF view ([id])
│   │   ├── layout.tsx          # Main HTML wrapper & navigation sidebar
│   │   └── page.tsx            # Main dashboard overview landing page
│   ├── components/             # Reusable UI & Modal Components
│   │   ├── admin/              # User permissions and scope manager modals
│   │   └── ui/                 # Basic UI blocks (dialog, buttons, cn utils)
│   ├── context/                # AuthContext provider (JWT & login state)
│   └── lib/                    # Shared utility files (API config, headers, PDF export)
├── public/                     # Static assets (images, icons)
├── next.config.ts              # Next.js configuration
├── vercel.json                 # Vercel deployment configuration
└── package.json                # Project scripts and dependencies
```

---

## ⚙️ Local Setup & Configuration

1. **Install Dependencies**:
   Navigate to the folder and run `npm install`:
   ```bash
   cd frontend-nextjs
   npm install
   ```

2. **Environment Configuration**:
   Create a `.env.local` file in `frontend-nextjs/`:
   ```env
   # API Backend Server endpoint
   NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000

   # ImageKit Configuration (Optional - for image storage)
   NEXT_PUBLIC_IMAGEKIT_PUBLIC_KEY=your_public_key
   NEXT_PUBLIC_IMAGEKIT_URL_ENDPOINT=https://ik.imagekit.io/your_endpoint
   ```

3. **Run Development Server**:
   Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The application will be available at [http://localhost:3000](http://localhost:3000).

4. **Production Build**:
   To test a production build locally:
   ```bash
   npm run build
   npm run start
   ```

---

## 🌐 Deploying to Vercel

Since the project is structured as a monorepo (`frontend-nextjs/` and `backend/` in the same git repo), follow these steps to deploy the frontend to Vercel:

### Option A: Vercel Dashboard (Recommended)

1. Go to **[Vercel Dashboard](https://vercel.com/dashboard)** → **Add New...** → **Project**.
2. Import the `MyTally` repository.
3. Under **Build and Output Settings**, open **Root Directory**:
   - Click **Edit** and set it to **`frontend-nextjs`**.
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_BASE`: URL of your deployed Python backend (e.g. `https://your-backend-api.com`)
   - `NEXT_PUBLIC_IMAGEKIT_PUBLIC_KEY`: ImageKit public key (if applicable)
   - `NEXT_PUBLIC_IMAGEKIT_URL_ENDPOINT`: ImageKit endpoint URL (if applicable)
5. Click **Deploy**.

### Option B: Vercel CLI

Deploy directly from your command line:

```bash
cd frontend-nextjs
npx vercel
```
Follow the interactive prompts to complete deployment.
