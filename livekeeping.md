# Make MyTally Similar to TallyDekho / LiveKeeping

## Background

**TallyDekho** and **LiveKeeping** are commercial cloud/mobile products that sync with Tally Prime / Tally ERP 9, giving business owners remote access to their accounting data via web and mobile apps. They share a common feature set:

| Feature | TallyDekho | LiveKeeping | MyTally (Current) |
|:---|:---:|:---:|:---:|
| **Real-time dashboard** (Sales, Purchases, Cash/Bank, Receivables, Payables) | ✅ | ✅ | ✅ Partial (4 tiles) |
| **Charts & graphs** (trend lines, bar charts, pie charts) | ✅ | ✅ | ❌ |
| **Sales/Purchase comparison** (vs. previous week/month/year) | ✅ | ✅ | ❌ |
| **20+ Business Reports** (Day Book, Ledger, Trial Balance, P&L, Balance Sheet, Cash Flow) | ✅ | ✅ | ✅ Partial (some reports) |
| **Invoicing from web/mobile** (GST-compliant, branded invoices) | ✅ | ✅ | ❌ |
| **Voucher creation** (Sales, Purchase, Receipt, Payment, Debit/Credit Note, Contra, Journal) | ✅ | ✅ | ✅ Partial (limited types) |
| **Payment Reminders** (automated SMS/Email/WhatsApp) | ✅ | ✅ | ❌ |
| **Outstanding Ageing Analysis** (party-wise receivables/payables aging) | ✅ | ✅ | ❌ |
| **Inactive Customers/Items Report** | ❌ | ✅ | ❌ |
| **Top Customers / Top Items Report** | ✅ | ✅ | ❌ |
| **Stock Summary & Stock Ageing** | ✅ | ✅ | ✅ Partial |
| **Profit & Loss Statement** | ✅ | ✅ | ❌ |
| **Balance Sheet** | ✅ | ✅ | ❌ |
| **Cash Flow / Fund Flow** | ✅ | ✅ | ❌ |
| **Ratio Analysis** | ✅ | ❌ | ❌ |
| **GST Reports (GSTR-1, GSTR-3B)** | ✅ | ✅ | ✅ |
| **E-Way Bill / E-Invoice** | ❌ | ✅ (Add-on) | ❌ |
| **Tally Data Backup/Restore** | ✅ | ✅ | ❌ |
| **Multi-company support** | ✅ | ✅ | ✅ |
| **Role-based access (RBAC)** | ✅ | ✅ | ✅ |
| **PDF Export & Share (WhatsApp, Email)** | ✅ | ✅ | ✅ Partial |
| **GPS Tracking / Check-in** | ❌ | ✅ | ✅ |
| **Attendance / Punch-in** | ❌ | ✅ | ✅ |
| **Activity Logs / Audit Trail** | ❌ | ✅ | ❌ |

---

## User Review Required

> [!IMPORTANT]
> This is a **massive undertaking** spanning multiple modules. I recommend we prioritize and tackle it in **phases** rather than all at once. Please review the proposed phasing below and let me know:
> 1. Which phase to start with
> 2. Any features you want to skip or reprioritize
> 3. Whether you want to do all phases or just specific ones

> [!WARNING]
> Some features (like Payment Reminders via SMS/WhatsApp, E-Way Bill generation) require **third-party API integrations** (e.g., Twilio, MSG91, or GST e-Invoice portal credentials). These will need separate setup.

---

## Open Questions

> [!IMPORTANT]
> 1. **Invoice Template Branding**: Do you want a customizable invoice template (with logo, colors, terms) or a fixed template?
> 2. **Payment Reminder Channels**: Which channels do you want? SMS only? Email only? WhatsApp? All three?
> 3. **Chart Library Preference**: Should I use Chart.js, Recharts, or another charting library for the dashboard graphs?
> 4. **Financial Statements Source**: Should P&L, Balance Sheet, Trial Balance be pulled **live from Tally** via XML, or computed from the synced database records?

---

## Proposed Changes (Phased)

### Phase 1: Enhanced Dashboard with Charts & Comparison Analytics
**Goal**: Match the TallyDekho/LiveKeeping dashboard experience — rich visual analytics with charts, trend comparisons, and at-a-glance business health.

---

#### [MODIFY] [page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/page.tsx)
- Add **Sales vs. Purchase trend chart** (bar/line chart, last 7 days or monthly)
- Add **Cash & Bank Balance** summary tile
- Add **Sales Order / Purchase Order** count tiles
- Add **Top 5 Customers** and **Top 5 Items** quick widgets
- Add a **period selector** (This Week / This Month / This Quarter / This Year)

#### [NEW] [components/charts/SalesPurchaseChart.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/components/charts/SalesPurchaseChart.tsx)
- Reusable bar/line chart component using Recharts
- Accepts data for sales vs. purchases over time

#### [NEW] [components/charts/OutstandingPieChart.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/components/charts/OutstandingPieChart.tsx)
- Pie/donut chart for receivables vs. payables breakdown

#### [MODIFY] [reports.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/reports.py)
- Add `GET /reports/dashboard-charts` endpoint returning:
  - Daily/weekly/monthly sales & purchase aggregates
  - Cash & bank balances
  - Top 5 customers by sales volume
  - Top 5 stock items by quantity sold

---

### Phase 2: Financial Reports (P&L, Balance Sheet, Trial Balance, Cash Flow)
**Goal**: Add the core accounting reports that TallyDekho/LiveKeeping highlight as their key value.

#### [NEW] [app/reports/profit-loss/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/profit-loss/page.tsx)
- Profit & Loss statement with expandable groups and drill-down to ledgers

#### [NEW] [app/reports/balance-sheet/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/balance-sheet/page.tsx)
- Balance Sheet with Assets, Liabilities, Capital hierarchy

#### [NEW] [app/reports/trial-balance/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/trial-balance/page.tsx)
- Trial Balance with Dr/Cr columns

#### [NEW] [app/reports/cash-flow/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/cash-flow/page.tsx)
- Cash Flow statement (Operating, Investing, Financing activities)

#### [MODIFY] [reports.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/reports.py)
- Add endpoints:
  - `GET /reports/profit-loss`
  - `GET /reports/balance-sheet`
  - `GET /reports/trial-balance`
  - `GET /reports/cash-flow`
- Each endpoint queries Tally via XML `Export Data` requests using the proper `REPORTNAME`

---

### Phase 3: Outstanding Ageing, Inactive Customers/Items, Top Analytics
**Goal**: Business intelligence reports that LiveKeeping uses as differentiators.

#### [NEW] [app/reports/ageing/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/ageing/page.tsx)
- Ageing analysis: 0-30, 31-60, 61-90, 90+ day buckets for receivables and payables

#### [NEW] [app/reports/inactive/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/inactive/page.tsx)
- Inactive Customers: parties with zero transactions in last N days
- Inactive Items: stock items with zero movement in last N days

#### [NEW] [app/reports/top-analytics/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reports/top-analytics/page.tsx)
- Top Customers by revenue
- Top Items by quantity/value
- Configurable date range

#### [MODIFY] [reports.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/reports.py)
- Add endpoints:
  - `GET /reports/ageing-analysis`
  - `GET /reports/inactive-parties`
  - `GET /reports/inactive-items`
  - `GET /reports/top-customers`
  - `GET /reports/top-items`

---

### Phase 4: Invoice Creation & Sharing
**Goal**: Allow creating GST-compliant invoices from the web portal, syncing to Tally, and sharing via WhatsApp/Email.

#### [NEW] [app/vouchers/create/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/vouchers/create/page.tsx)
- Full invoice creation form: Party selection, item rows, tax calculation, narration
- Support for: Sales, Purchase, Receipt, Payment, Debit Note, Credit Note, Contra, Journal

#### [NEW] [components/InvoicePDF.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/components/InvoicePDF.tsx)
- Client-side PDF generation using `@react-pdf/renderer` or `html2canvas + jspdf`
- Branded template with company logo, address, GSTIN, terms

#### [MODIFY] [vouchers.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/vouchers.py)
- Add `POST /vouchers/create` for creating new vouchers that sync to Tally
- Add `GET /vouchers/{id}/pdf` for server-side PDF generation

#### [MODIFY] [sync.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/sync.py)
- Extend outbound sync to handle new voucher types (Sales, Purchase, Receipt, Payment, Debit/Credit Note, Contra, Journal)

---

### Phase 5: Payment Reminders & Automation
**Goal**: Automated payment reminders via SMS/Email/WhatsApp for outstanding dues.

#### [NEW] [app/reminders/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/reminders/page.tsx)
- UI to configure reminder rules: frequency (daily/weekly/monthly), channels, templates
- View history of sent reminders

#### [NEW] [routers/reminders.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/reminders.py)
- `POST /reminders/send` — trigger manual reminders to specific parties
- `GET /reminders/history` — past reminder logs
- `PUT /reminders/settings` — configure automation rules

#### [NEW] [services/notification.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/services/notification.py)
- Abstraction layer for SMS (MSG91/Twilio), Email (SMTP), and WhatsApp (WhatsApp Business API)

---

### Phase 6: Activity Logs & Audit Trail
**Goal**: Track who did what and when — a legal requirement in many jurisdictions.

#### [NEW] [app/admin/activity-log/page.tsx](file:///Users/akashkansal/Documents/Github/MyTally/frontend-nextjs/src/app/admin/activity-log/page.tsx)
- Searchable, filterable activity log table

#### [NEW] [routers/audit.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/routers/audit.py)
- `GET /audit/logs` with filters (user, action, date range, module)

#### [NEW] [middleware/audit_middleware.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/app/middleware/audit_middleware.py)
- Middleware to automatically log all write operations (POST, PUT, DELETE)

---

## Verification Plan

### Automated Tests
- `pytest backend/tests/` for all new API endpoints
- Verify XML payloads sent to Tally match expected schemas from [tally_integration_guide.md](file:///Users/akashkansal/Documents/Github/MyTally/docs/tally_integration_guide.md)

### Manual Verification
- Visual inspection of dashboard charts and reports in browser at `localhost:3000`
- Test invoice PDF generation and sharing
- Verify Tally sync for newly created vouchers
- Test ageing analysis accuracy against Tally data
