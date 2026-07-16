# Open Tally-Clone — Schema Design (Phase 1)

An open-source, web-based accounting system inspired by Tally, built with
**Python (FastAPI) + MySQL**.

## Files in this drop
- `db/schema.sql` — full core MySQL schema (DDL)
- `db/seed_defaults.sql` — default account groups, voucher types, roles (run after creating a company)
- `db/schema_orders_payments.sql` — Sales/Purchase Orders + bill-wise payment allocation (AR/AP tracking)
- `db/schema_payment_gateway.sql` — Razorpay/Stripe integration: payment links, gateway transactions, webhook handling
- `db/schema_admin_permissions.sql` — Admin panel backing: per-user permission overrides, data scoping, maker-checker approval workflows, session control, company settings
- `db/schema_payroll.sql` — Employees, salary structures, payroll processing, payslips
- `db/schema_currency_tds.sql` — Multi-currency ledgers/vouchers with forex gain-loss, plus TDS/TCS deduction, certificates, and challan tracking
- `db/schema_batch_serial.sql` — Batch/lot tracking with expiry (FEFO), individual serial-number tracking with warranty
- `db/schema_gst_returns.sql` — GSTR-1 (outward supplies + HSN summary) and GSTR-3B (summary return with ITC set-off), snapshot-based for filed-return immutability

## Design decisions & why

**1. Multi-company from day one**
Every table hangs off `company_id`. Tally is fundamentally multi-company —
retrofitting this later is painful, so it's baked into the schema now.

**2. Groups → Ledgers hierarchy (self-referencing tree)**
`account_groups` mirrors Tally's ~28 default primary groups (Capital Account,
Sundry Debtors, Duties & Taxes, etc.) but lets users nest custom sub-groups.
`nature` (Asset/Liability/Income/Expense) and `affects_gross_profit` drive
automatic P&L vs Balance Sheet classification — this is what makes reports
"just work" without hardcoding logic per ledger.

**3. Vouchers = header + entries (true double-entry)**
`vouchers` is the header (type, date, number, narration).
`voucher_entries` holds the actual debit/credit lines against ledgers.
A `CHECK` constraint prevents a line from being both debit and credit.
**Balance validation (sum(debit) == sum(credit))** is enforced in the FastAPI
service layer, not the DB — MySQL CHECK constraints can't easily do
cross-row aggregate validation, and you'll want a clean error message
in the API anyway.

**4. Inventory is fully decoupled from accounting**
`stock_items`, `stock_entries`, `godowns` exist independently, and a Sales/
Purchase voucher links to both `voucher_entries` (accounting impact) and
`stock_entries` (quantity impact) — same pattern Tally uses internally.

**5. GST-ready**
`hsn_code` + `gst_rate_percent` on stock items, `gstin` on ledgers/company,
and a `tax_rates` table for CGST/SGST/IGST splits — enough to generate
GST-compliant invoices and GSTR-1/3B style reports later.

**6. Audit log as JSON diff**
`audit_logs` stores old/new value as JSON rather than a rigid per-field
table — flexible for any entity type, and cheap to query with MySQL's JSON
functions when needed for compliance/audit trail features.

**7. Roles + granular permissions, not just role names**
`permissions` is a separate table per (role, module) rather than hardcoded
in code — lets you add new roles/modules without a schema migration.

**8. Orders are separate from Vouchers — on purpose**
`orders` / `order_items` hold *commitments* (a customer's PO, your PO to a
vendor). They carry zero accounting or stock weight by themselves.
`order_fulfillments` links an order line to the real Sales/Purchase voucher
that eventually invoices it — so a single order can be fulfilled across
multiple partial shipments/invoices, and you can report on "open orders"
without them polluting your books.

**9. Payments are tracked bill-wise, not just as ledger balances**
This is the piece most simple accounting schemas skip, and it's the
difference between "the customer owes ₹50,000 in total" and "the customer
owes ₹20,000 from Invoice #114 (30 days overdue) and ₹30,000 from Invoice
#118 (due next week)". Every Sales/Purchase voucher auto-creates a `bills`
row; every Payment/Receipt entry allocates against one or more bills via
`bill_allocations` (or gets parked as Advance/On Account if unmatched yet).
This is what powers outstanding reports, ageing analysis, and payment
reminders — all real Tally features that don't work without this layer.

**10. Payment gateway secrets never live in the database**
`payment_gateway_configs.secret_key_ref` and `webhook_secret_ref` are
*pointers* (e.g. an env var name or secrets-manager key), not the actual
key values. The FastAPI app resolves them at runtime. Only the
publishable/public key is safe to store directly in MySQL.

**11. Webhooks are idempotent by design**
Razorpay and Stripe both retry webhook delivery on timeout, which means
your endpoint *will* receive the same event more than once eventually.
`webhook_events` has a unique constraint on `(gateway_config_id,
gateway_event_id)` specifically so a duplicate delivery gets rejected at
the DB level instead of creating two Receipt vouchers for one payment.

**12. A successful payment auto-creates a Receipt voucher, not a new table**
Rather than inventing a parallel "online payment" concept, a captured
gateway transaction becomes a normal Receipt voucher (same `vouchers` /
`voucher_entries` tables from Phase 1) with a `bill_allocations` row
settling the right invoice. This means your Trial Balance, P&L, and
outstanding reports don't need special-casing for "was this paid online
or by cash" — it's all one ledger.

**13. Permissions resolve in a strict override order**
`role`-level permissions from Phase 1 (`permissions` table) are the
default, but a real admin panel needs one-off exceptions without
inventing a new role for every edge case. Resolution order at request
time: (1) `user_permission_overrides` for that exact user+module wins if
present → (2) fall back to the user's role permission → (3) fail safe to
read-only if neither exists. This is implemented as a single function in
the FastAPI dependency layer, not duplicated per-route.

**14. Data scoping is separate from CRUD permissions**
"Can this user edit vouchers" (CRUD) and "which godown/cost-center can
they see" (data scope) are different questions and shouldn't be conflated
into more roles. `user_data_scopes` lets the admin panel restrict, say, a
warehouse clerk to one godown without touching their role.

**15. Maker-checker approval, not just permission gates**
Some actions shouldn't be blocked outright — they should require a
second person's sign-off. `approval_rules` lets an admin set a threshold
(e.g. "Payment vouchers over ₹50,000 need Admin approval") and
`approval_requests` becomes each user's pending queue. The voucher exists
in `vouchers` immediately but is held from finalizing until approved —
this is a standard control in real accounting systems, not just Tally.

**16. Sessions are revocable, not just expirable**
`user_sessions` stores a hash of each active token so the admin panel can
show "active logins" per user and force a logout (e.g. offboarding an
employee) without waiting for token expiry.

**17. Payroll posts one voucher per period, not per employee**
Processing payroll for 200 employees doesn't create 200 Journal vouchers —
it creates ONE, with a line per salary component aggregated across
employees, crediting a single "Salaries Payable" ledger. Individual
`payslips` still exist for employee-facing payslip generation; they just
don't each need their own ledger posting. Keeps the general ledger
readable instead of drowning in payroll noise.

**18. Multi-currency stores base-currency amounts as the source of truth**
`voucher_entries.debit_amount`/`credit_amount` always stay in base
currency (so every existing report — Trial Balance, P&L — keeps working
unmodified). `forex_amount` + `exchange_rate_used` are additional columns
for display/audit. Forex gain/loss only gets posted (via
`forex_adjustments`) when a foreign-currency bill is actually settled at a
different rate than it was raised at — not on every rate fluctuation.

**19. TDS/TCS deduction happens on the same voucher, not a separate one**
When a Purchase/Payment voucher triggers TDS, the deducted amount posts
as an extra `voucher_entries` line on that same voucher (crediting a "TDS
Payable" ledger) rather than a disconnected side-transaction — this keeps
the voucher's debit/credit sum consistent and the audit trail obvious:
one voucher, one event, all its consequences visible together.

**20. Batch/serial tracking is opt-in per item**
Most stock items need neither. `stock_items.tracking_type` defaults to
'None' so the UI doesn't force batch/serial fields on every item — only
pharma/food (`Batch`) or electronics/appliances (`Serial`) items need to
set it, and `stock_entries` gained optional `batch_id`/`serial_id`
columns to record which specific batch or unit moved.

**21. Filed GST returns are immutable snapshots, not live queries**
`gstr1_line_items` and `gstr3b_summary` are populated once at "Generate
Return" time and frozen once `status = 'Filed'`. This matters because
ledger data (a voucher gets corrected, a credit note gets added later)
can change *after* a return was actually filed with the government — the
filed return must stay exactly as submitted, while a fresh generation for
the next period reflects current data. Re-deriving GSTR-1 live from
`vouchers` every time would silently rewrite history.

## Modules covered so far
Core accounting → Inventory/GST → Orders → Bill-wise AR/AP → Payment
gateway → Admin/permissions → Payroll → Multi-currency/TDS/TCS →
Batch/serial tracking → GST returns. This is now a genuinely comprehensive
schema. Remaining stretch modules if you want to keep going: e-way bill
generation, bank statement auto-import/reconciliation, budgeting vs
actuals variance reports, and a document management layer (attach PDFs/
images to vouchers).

## Suggested FastAPI project layout (Phase 2 — once you're ready for the API)
```
app/
  core/           # config, security (JWT), db session
  models/         # SQLAlchemy models (1:1 with tables above)
  schemas/        # Pydantic request/response schemas
  routers/
    companies.py
    ledgers.py
    vouchers.py
    inventory.py
    reports.py    # Trial Balance, P&L, Balance Sheet, Day Book
  services/
    voucher_service.py   # balance validation, stock impact, numbering
    report_service.py     # aggregation queries
  main.py
alembic/          # migrations (recommended over raw schema.sql going forward)
```

## Next step
Once you confirm this schema looks right, I'll scaffold the FastAPI project
(SQLAlchemy models + Alembic migration from this schema + first working
endpoint set: create ledger, post voucher, Trial Balance report).
