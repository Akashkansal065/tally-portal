# Open Tally-Clone — Architecture & Workflow

Visual map of how the FastAPI service layer, MySQL tables, and external
systems (payment gateway, GST portal) interconnect across every module
built so far.

---

## 1. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        WEB[Web App - React/Vue]
        ADMIN[Admin Panel]
    end

    subgraph API["FastAPI Service Layer"]
        AUTH[Auth Service<br/>JWT + Sessions]
        PERM[Permission Resolver<br/>override to role to fail-safe]
        VOUCH[Voucher Service<br/>balance validation, numbering]
        INV[Inventory Service<br/>batch/serial, FEFO]
        PAY[Payroll Service]
        GST[GST Service<br/>returns generation]
        GATE[Gateway Service<br/>payment links, webhooks]
        REPORT[Report Service<br/>Trial Balance, P&L, GSTR]
    end

    subgraph External["External Systems"]
        RAZOR[Razorpay / Stripe]
        GSTPORTAL[GST Portal<br/>manual filing]
    end

    subgraph DB["MySQL Database"]
        CORE[(Core: companies, ledgers,<br/>account_groups, vouchers,<br/>voucher_entries)]
        INVDB[(Inventory: stock_items,<br/>batches, serial_numbers,<br/>stock_entries)]
        ORDPAY[(Orders/Payments: orders,<br/>bills, bill_allocations)]
        ADMDB[(Admin: roles, permissions,<br/>user_permission_overrides,<br/>approval_requests, sessions)]
        PAYDB[(Payroll: employees,<br/>salary_structures, payslips)]
        GSTDB[(GST: gstr1_line_items,<br/>gstr3b_summary, itc_entries)]
        GATEDB[(Gateway: payment_links,<br/>gateway_transactions,<br/>webhook_events)]
    end

    WEB --> AUTH
    ADMIN --> AUTH
    AUTH --> PERM
    PERM --> ADMDB
    WEB --> VOUCH --> CORE
    VOUCH --> ORDPAY
    WEB --> INV --> INVDB
    ADMIN --> PAY --> PAYDB
    PAY --> VOUCH
    ADMIN --> GST --> GSTDB
    GST --> CORE
    WEB --> GATE
    GATE <--> RAZOR
    GATE --> GATEDB
    GATE --> VOUCH
    GST -.manual filing.-> GSTPORTAL
    REPORT --> CORE
    REPORT --> ORDPAY
    REPORT --> GSTDB
    WEB --> REPORT
```

**Reading this:** every write path that touches money ultimately flows
through the **Voucher Service** — payroll, gateway payments, and GST all
*create* vouchers rather than bypassing the ledger. This is deliberate:
it means Trial Balance/P&L never need special-casing per module.

---

## 2. Core Flow: Posting Any Voucher

```mermaid
sequenceDiagram
    participant U as User
    participant API as Voucher Service
    participant DB as MySQL

    U->>API: POST /vouchers (type, date, entries[])
    API->>API: Check permission (module=vouchers)
    API->>DB: Read approval_rules for this voucher_type
    alt Amount exceeds threshold
        API->>DB: INSERT approval_requests (status=Pending)
        API-->>U: 202 Accepted - Pending Approval
    else No approval needed
        API->>API: Validate sum(debit) == sum(credit)
        API->>DB: INSERT vouchers + voucher_entries
        alt Voucher type = Sales/Purchase
            API->>DB: INSERT bills (from schema_orders_payments.sql)
            API->>DB: INSERT stock_entries (if inventory items present)
        end
        API->>DB: INSERT audit_logs (action=CREATE)
        API-->>U: 201 Created
    end
```

**Tables touched:** `vouchers`, `voucher_entries`, `approval_rules`,
`approval_requests`, `bills`, `stock_entries`, `audit_logs`.

---

## 3. Order-to-Cash Flow (Sales Order → Payment)

```mermaid
flowchart LR
    A[Sales Order created] -->|orders + order_items| B[Order: Open]
    B -->|Sales Voucher raised| C[order_fulfillments linked]
    C --> D[Sales Voucher posted]
    D -->|auto-creates| E[bills row<br/>status: Open]
    D -->|auto-creates| F[voucher_entries<br/>Dr Debtor / Cr Sales]
    D -->|if inventory item| G[stock_entries<br/>+ batches/serial_numbers]
    E --> H{Payment method?}
    H -->|Manual| I[Receipt Voucher entered]
    H -->|Online| J[payment_links generated]
    J --> K[Customer pays via Razorpay/Stripe]
    K --> L[Webhook received]
    L --> M[webhook_events INSERT<br/>idempotency check]
    M --> N[gateway_transactions<br/>status: Captured]
    N --> O[Auto-create Receipt Voucher]
    I --> P[bill_allocations<br/>type: Against Ref]
    O --> P
    P --> Q[bills.settled_amount updated]
    Q --> R{Fully settled?}
    R -->|Yes| S[bills.status = Settled]
    R -->|No| T[bills.status = Partially Settled]
```

**Tables touched (in order):** `orders` → `order_items` →
`order_fulfillments` → `vouchers`/`voucher_entries` → `bills` →
`stock_entries`/`batches`/`serial_numbers` → `payment_links` →
`webhook_events` → `gateway_transactions` → new `vouchers` (Receipt) →
`bill_allocations` → `bills` (updated).

---

## 4. Permission Resolution (every protected request)

```mermaid
flowchart TD
    A[Request: user X wants action Y on module Z] --> B{user_permission_overrides<br/>row exists for X+Z?}
    B -->|Yes, field non-NULL| C[Use override value]
    B -->|No / NULL fields| D{permissions row for<br/>role of X + module Z?}
    D -->|Yes| E[Use role permission]
    D -->|No| F[Fail-safe: read-only]
    C --> G{Data scope check}
    E --> G
    F --> G
    G --> H{user_data_scopes row<br/>exists for X?}
    H -->|Yes| I[Filter results to<br/>allowed godown/cost-center IDs]
    H -->|No| J[No filtering - full access<br/>within module permission]
    I --> K[Execute request]
    J --> K
```

**Tables touched:** `user_permission_overrides`, `permissions`, `roles`,
`user_data_scopes`, `modules`.

---

## 5. Payroll Processing Flow

```mermaid
flowchart LR
    A[Admin: Process Payroll<br/>for period] --> B[Fetch active employees<br/>from employees table]
    B --> C[Resolve active salary_structure<br/>as of period date]
    C --> D[Apply attendance<br/>days_present / days_in_period]
    D --> E[INSERT payslips<br/>+ payslip_components]
    E --> F[Aggregate ALL employees'<br/>components into ONE Journal voucher]
    F --> G[vouchers + voucher_entries<br/>Dr Salary Expense / Cr Salaries Payable]
    G --> H[payroll_periods.status = Processed]
    H --> I[Admin: Disburse salaries]
    I --> J[Payment voucher per bank batch<br/>Dr Salaries Payable / Cr Bank]
    J --> K[payslips.payment_voucher_id set]
    K --> L[payroll_periods.status = Paid]
```

**Tables touched:** `employees`, `salary_structures`,
`salary_structure_components`, `payroll_periods`, `payslips`,
`payslip_components`, `vouchers`, `voucher_entries`.

---

## 6. GST Return Generation Flow

```mermaid
flowchart TD
    A[Admin: Generate GSTR-1<br/>for month] --> B[Query all Sales vouchers<br/>in that period]
    B --> C[Classify each: B2B/B2CL/B2CS/Export<br/>by party GSTIN + invoice value]
    C --> D[SNAPSHOT into<br/>gstr1_line_items]
    C --> E[SNAPSHOT into<br/>gstr1_hsn_summary]
    D --> F[gst_return_periods.status = Draft]
    E --> F
    F --> G{Admin reviews,<br/>regenerates if needed}
    G -->|Filed on GST portal| H[Enter ARN]
    H --> I[gst_return_periods.status = Filed<br/>rows become immutable]

    J[Generate GSTR-3B] --> K[Pull outward figures<br/>from same-period GSTR-1]
    J --> L[Pull ITC from itc_entries<br/>WHERE claimed_return_period_id matches]
    K --> M[Apply GST set-off rules<br/>IGST/CGST/SGST]
    L --> M
    M --> N[INSERT gstr3b_summary<br/>net payable per tax head]
```

**Tables touched:** `gst_return_periods`, `gstr1_line_items`,
`gstr1_hsn_summary`, `itc_entries`, `gstr3b_summary`, `vouchers`
(read-only source).

---

## 7. Module → Table Ownership Map

```mermaid
flowchart TB
    subgraph M1["Core Accounting"]
        T1[companies]
        T2[financial_years]
        T3[account_groups]
        T4[ledgers]
        T5[cost_centers]
        T6[voucher_types]
        T7[vouchers]
        T8[voucher_entries]
    end

    subgraph M2["Inventory + Batch/Serial"]
        T9[units_of_measure]
        T10[stock_groups]
        T11[godowns]
        T12[stock_items]
        T13[stock_entries]
        T14[batches]
        T15[serial_numbers]
    end

    subgraph M3["Orders + Bill-wise AR/AP"]
        T16[orders / order_items]
        T17[order_fulfillments]
        T18[bills]
        T19[bill_allocations]
    end

    subgraph M4["Payment Gateway"]
        T20[payment_gateway_configs]
        T21[payment_links]
        T22[gateway_transactions]
        T23[webhook_events]
    end

    subgraph M5["Admin / Permissions"]
        T24[roles / permissions]
        T25[modules]
        T26[user_permission_overrides]
        T27[user_data_scopes]
        T28[approval_rules / requests]
        T29[user_sessions]
        T30[company_settings]
    end

    subgraph M6["Payroll"]
        T31[employees]
        T32[salary_components / structures]
        T33[payroll_periods]
        T34[payslips]
    end

    subgraph M7["Multi-currency + TDS/TCS"]
        T35[currencies / exchange_rates]
        T36[forex_adjustments]
        T37[tds_sections / tcs_sections]
        T38[tds_tcs_entries]
        T39[tax_challans]
    end

    subgraph M8["GST Returns"]
        T40[gst_return_periods]
        T41[gstr1_line_items / hsn_summary]
        T42[gstr3b_summary]
        T43[itc_entries]
    end

    M2 -.stock impact.-> M1
    M3 -.accounting impact.-> M1
    M4 -.settles.-> M3
    M6 -.posts to.-> M1
    M7 -.adjusts.-> M1
    M7 -.adjusts.-> M3
    M8 -.reads.-> M1
    M8 -.reads.-> M3
    M5 -.gates access to.-> M1
    M5 -.gates access to.-> M2
    M5 -.gates access to.-> M3
    M5 -.gates access to.-> M4
    M5 -.gates access to.-> M6
    M5 -.gates access to.-> M8
```

**The one rule that holds everywhere:** every module either *posts to*
`vouchers`/`voucher_entries` (Core) or *reads from* it for reporting.
Nothing maintains a parallel balance. That's what keeps Trial Balance,
P&L, and Balance Sheet accurate regardless of which module generated
the underlying transaction.

---

## Next step
This diagram set maps cleanly onto the FastAPI `routers/` and `services/`
folders proposed earlier — each subgraph in section 7 becomes one router
+ one service module. Ready to scaffold that whenever you are.
