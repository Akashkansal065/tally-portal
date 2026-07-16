# tally-web — Repository Analysis & Implementation Plan

## What Is This Repo?

`tally-web` is a production-grade **Next.js 16 (App Router) PWA** built for **Sneh Distributors**. It acts as a **read/write mobile front-end** over a Tally-synced PostgreSQL database hosted on **Neon (serverless Postgres)**. It is a completely separate, more mature codebase from `MyTally/frontend-nextjs`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack) |
| Database | Neon Serverless Postgres |
| ORM | Drizzle ORM (schema-first) |
| UI Library | shadcn/ui + Radix UI primitives |
| Styling | Tailwind CSS v4 |
| Auth | Custom JWT (HMAC-SHA256) via HTTP-only cookie |
| Image Upload | ImageKit CDN |
| Push Notifications | Web Push / VAPID |
| PDF Generation | jsPDF + jsPDF-AutoTable |
| Charts | Recharts |
| Email | Nodemailer (SMTP via Gmail) |
| Data Tables | TanStack Table |

---

## Architecture

```
tally-web/
├── app/               # Next.js App Router pages + Server Actions
│   ├── actions/       # 19 server action files (all DB queries live here)
│   ├── vouchers/      # Voucher list + detail pages
│   ├── ledgers/       # Ledger balance + statement pages
│   ├── stocks/        # Stock inventory summary
│   ├── payments/      # Shop payment collection
│   ├── orders/        # Temporary order management
│   ├── check-in/      # GPS shop visit with photo
│   ├── expenses/      # Expense claims + approvals
│   ├── reports/       # Reports hub (analytics, statements, exports)
│   └── admin/         # Admin panel (user CRUD, device management)
├── components/        # Shared components
│   ├── MobileBottomNav.tsx    # Mobile bottom tab bar (already well-built)
│   ├── GlobalHeader.tsx       # Top bar with hamburger menu
│   ├── DashboardChartsWrapper.tsx  # Stock trend charts on home
│   └── ui/            # shadcn/ui component library
├── drizzle/schema.ts  # Full Postgres schema (Drizzle ORM)
├── lib/
│   ├── auth.ts        # JWT sign/verify, getCurrentUser()
│   ├── rbac.ts        # Role-based permission resolver
│   ├── roles.json     # Default permissions per role
│   ├── audit.ts       # Audit log writer
│   ├── pdf-generator.ts    # PDF generation for reports
│   └── kgoc-mapping.ts    # Business-specific stock item mapping
└── db/index.ts        # Drizzle + Neon DB connection
```

---

## Database Schema — Key Tables

| Table | Purpose |
|---|---|
| `mst_ledger` | Ledger master from Tally (parties, bank accounts, etc.) |
| `mst_group` | Tally account groups hierarchy |
| `mst_stock_item` | Stock/inventory items with closing balance |
| `mst_stock_group` | Stock category groups |
| `mst_vouchertype` | Voucher type definitions (Sales, Purchase, etc.) |
| `trn_voucher` | All posted vouchers |
| `trn_accounting` | Accounting ledger entries per voucher |
| `trn_inventory` | Inventory batch entries per voucher |
| `users` | App users with granular permission flags |
| `sales_visits` | Shop check-in records (GPS + photo + device) |
| `temp_orders` + `temp_order_items` | Temporary orders pre-Tally |
| `shop_payments` | Payment collections (cash/cheque/online) |
| `expenses` | Expense claims with receipt photos |
| `audit_logs` | Full audit trail of user actions |
| `user_devices` | Device fingerprinting for security |
| `push_subscriptions` | Web Push notification endpoints |

---

## Authentication & RBAC

- Login creates a **custom JWT** signed with HMAC-SHA256 stored as an **HTTP-only cookie** (`session`)
- `getCurrentUser()` reads the cookie and re-queries the DB on every request (no stale state)
- Permissions are **per-user overrides** merged on top of **role defaults** (`roles.json`):
  - Roles: `admin`, `sales`, others
  - Per-user flags: `showLedger`, `showStocks`, `showReports`, `showCheckIn`, `showOrders`, `showExpenses`, `showSalesLedgers`, `showPurchaseLedgers`, `showReceipts`, `showPayments`
  - Scope controls: `ledgerScope` (all / dr_only / restricted), `stockScope` (full / restricted)
  - Fine-grained: `allowedStockGroups`, `allowedLedgerGroups`, `allowedReportCategories` (comma-separated strings)

---

## Feature Map — What's Built

| Feature | Status | Notes |
|---|---|---|
| Login / Signup | ✅ Complete | Cookie-based JWT auth |
| Dashboard (Home) | ✅ Complete | RBAC-gated cards + stock trend charts |
| Ledger Balance Sheet | ✅ Complete | Group hierarchy, balance display |
| Ledger Statement | ✅ Complete | Date-filtered Dr/Cr transaction list |
| Voucher List | ✅ Complete | 40KB+ voucher client with PDF export |
| Voucher Detail | ✅ Complete | Accounting + inventory entries, PDF |
| Stocks & Inventory | ✅ Complete | Group-level summary + item details |
| Stock Statement | ✅ Complete | Date-filtered batch-level view |
| Reports Hub | ✅ Complete | Multiple report categories, exports |
| Shop Check-In | ✅ Complete | GPS + photo + device fingerprinting |
| Temporary Orders | ✅ Complete | Full CRUD with stock item linking |
| Shop Payments | ✅ Complete | Cash/Cheque/Online with photo proof |
| Expense Tracker | ✅ Complete | Submit claims, receipt upload, approval |
| Admin Panel | ✅ Complete | User management, device blocking, audit logs |
| PWA / Installable | ✅ Complete | Service worker, manifest, push notifications |
| PDF Generation | ✅ Complete | jsPDF for vouchers, statements, reports |
| Theme Toggle | ✅ Complete | Dark/light with next-themes |
| Mobile Bottom Nav | ✅ Complete | RBAC-gated tabs, active pill, scroll |

---

## Open Questions / Decisions Needed

> [!IMPORTANT]
> **What do you want to do with this repo?** Choose a direction below so I can scope the plan accurately.

### Option A — Migrate `MyTally` features into `tally-web`
The `MyTally` backend (FastAPI + SQLite) has different data (custom voucher posting, bill allocations). We could migrate the XML import feature and any missing functionality **into** `tally-web`, which is the more mature and production-ready codebase.

### Option B — Tally XML Sync Integration
Add a **Tally XML sync mechanism** directly into `tally-web` — a background job or admin-triggered import that reads Tally XML exports and upserts data into the Neon Postgres database (similar to what `MyTally/backend/tally_xml_importer.py` does but in TypeScript server actions).

### Option C — Feature Gaps / Bug Fixes
Identify and fix specific gaps in the current `tally-web` feature set (e.g. missing UI polish, broken flows, adding new report types, etc.).

### Option D — Run & Verify Locally
Simply run the dev server and verify the current state of the app, checking what's working and what needs attention.

---

## Key Observations

1. **This is production-connected** — `.env.local` has real Neon DB credentials, real ImageKit keys, and real VAPID push keys. Be careful with any DB-modifying actions.

2. **The codebase is well-structured** — Server Actions follow a clean pattern. RBAC is thorough. The mobile UX (bottom nav, PWA) is already well-built — far ahead of `MyTally/frontend-nextjs`.

3. **No local DB** — Unlike `MyTally` (SQLite + local FastAPI), `tally-web` hits a cloud Neon Postgres directly from Next.js server actions.

4. **PDF generation is complete** — `lib/pdf-generator.ts` (25KB) generates professional ledger statements, stock reports, and voucher PDFs.

5. **KGOC mapping** — `lib/kgoc-mapping.ts` (12KB) contains Sneh Distributors–specific product name aliases, suggesting business-specific logic is already embedded.

---

## To Start the Dev Server

```bash
cd /Users/akashkansal/Documents/Github/tally-web
npm run dev
```

> App will be available at `http://localhost:3000` (or next available port since 3000 may be occupied by MyTally).
