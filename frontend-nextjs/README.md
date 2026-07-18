# Tally Portal Frontend (`frontend-nextjs`)

This is the Next.js frontend application for the Tally Portal. Built with the Next.js App Router, Tailwind CSS, Lucide React, and canvas watermarking utilities, it provides a premium web interface for viewing synced Tally data, logging salesperson attendance, conducting geocoded check-ins, and managing users.

---

## 🚀 Core Features

### 🔐 Authentication & Bootstrapping
* **Auto-Bootstrap Wizard**: Automatically detects if the backend database has zero registered administrators. If empty, redirects to a setup wizard to initialize the first company and admin profile.
* **JWT Sign In**: Standard secure sign-in panel verifying against backend JWT authentication.

### 📅 Daily Attendance Log
* **Live Timer Clock**: Dynamic clock displaying local time (`en-IN` formatting) with in-memory hydration fixes to prevent React SSR mismatches.
* **Geocoded Selfie Check-In/Out**: Utilizes HTML5 webcam canvas context to overlay name, date, time, and coordinates directly onto the selfie photo before uploading.

### 📍 GPS Shop Check-In
* **Verification Proofs**: Captures field sales check-in records with real-time browser geolocations, reverse-geocoded map watermarking, and camera photo proofs.

### 🛡️ Admin Oversight Control Panel
* **Directory Management**: Create new user accounts and toggle status (Active/Disabled).
* **Company Registration**: Dynamic dialog to create and seed new company workspaces and admin profiles.
* **Granular Scopes & Permissions**: Override role settings with detailed menu flags (`showLedger`, `showStocks`, `showReports`, `showOrders`, `showCheckIn`) and data query scopes (`ledgerScope`, `stockScope`, allowed stock/ledger groups).
* **Audit & Visit Logs**: Monitor background sync activity, salesperson logins, password resets, and field visit logs.

---

## 📂 Project Structure

```text
frontend-nextjs/
├── src/
│   ├── app/                    # Next.js App Router Pages
│   │   ├── admin/              # Admin oversight directory, logs, and registration
│   │   ├── attendance/         # Geocoded selfie attendance log
│   │   ├── checkin/            # Salesperson shop GPS check-in page
│   │   ├── login/              # Sign in and auto-bootstrap screen
│   │   ├── layout.tsx          # Main html wrapper and layout
│   │   └── page.tsx            # Main dashboard overview landing page
│   ├── components/             # Reusable UI Components
│   │   ├── admin/              # User permissions and scope manager modals
│   │   └── ui/                 # Basic UI blocks (dialog, buttons, cn utils)
│   ├── context/                # AuthContext provider (JWT & login state)
│   └── lib/                    # Shared utility files (API config, headers, roles)
├── public/                     # Static assets (images, icons)
├── package.json                # Project scripts and dependencies
└── tailwind.config.ts          # Tailwind theme styling configs
```

---

## ⚙️ Setup & Configuration

1. **Install Dependencies**:
   Navigate to the folder and run `npm install`:
   ```bash
   cd frontend-nextjs
   npm install
   ```

2. **Environment Configuration**:
   Create a `.env.local` file in the root of the folder:
   ```env
   # API Backend Server endpoint
   NEXT_PUBLIC_API_BASE=http://localhost:8000
   ```

3. **Run Development Server**:
   Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The application will be available at [http://localhost:3000](http://localhost:3000).

4. **Production Build**:
   To compile and run a production-ready build:
   ```bash
   npm run build
   npm run start
   ```

---
