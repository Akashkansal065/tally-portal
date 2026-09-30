I completed the review using the confirmed domain lens: **wholesale trading and field-sales distribution**. The full standalone review is available in the [wholesale ERP architecture review canvas](/Users/akashkansal/.cursor/projects/Users-akashkansal-Documents-Github-tally-web/canvases/wholesale-erp-review.canvas.tsx), which you can open beside the chat. I used a canvas because the deliverable is a structured architecture/product audit with multiple categorized findings and roadmap items.

## Executive assessment

MyTally already covers a substantial distributor operating model:

- Tally Prime bidirectional synchronization
- Ledgers, vouchers, inventory, godowns, batches, BOMs, price levels
- GST, e-invoice metadata, payments, collections, and bank reconciliation
- Field GPS check-ins, attendance, image proof, offline IndexedDB queueing, and PWA support
- Company switching, RBAC, approval rules, audit snapshots, backup/restore, and sync retries

The main issue is not lack of breadth. It is **operational reliability and maintainability as tenant volume grows**. The highest risks are automatic schema mutation during startup, insecure database TLS fallback, oversized workflow modules, fixed-limit list queries, inconsistent browser authentication handling, and the absence of a normal CI build/test/migration gate.

## 1. Code and architecture improvements

### P0 — Fix database TLS behavior

`backend/app/core/database.py` creates an SSL context with:

- `check_hostname = False`
- `verify_mode = CERT_NONE`

when `ca.pem` is unavailable.

That is unsafe for production or cloud-hosted databases because the application can accept an impersonated database endpoint. Recommended change:

1. Require CA verification in production.
2. Fail startup if `DB_SSL=true` but no trusted CA is configured.
3. Make hostname verification mandatory.
4. Use separate development behavior explicitly rather than silently weakening verification.
5. Add a configuration test that rejects insecure production settings.

### P0 — Replace startup schema mutation with migrations

The application currently:

- Creates databases at startup.
- Runs `Base.metadata.create_all`.
- Dynamically inspects tables.
- Executes `ALTER TABLE ADD COLUMN` and `MODIFY COLUMN`.
- Seeds data during application lifespan initialization.

This is convenient for development but unsafe for production deployments. Multiple replicas can race, DDL can partially complete, and schema changes cannot be reviewed or rolled back cleanly.

Move to:

- Alembic migrations committed to source control.
- A migration job executed before application rollout.
- A startup check that validates the migration revision instead of altering the schema.
- Separate seed commands for immutable reference data and tenant-specific defaults.

### P1 — Split oversized modules by bounded capability

The largest files are concentrated workflow hubs:

- `backend/app/routers/sync.py` — approximately 4,511 lines
- `backend/app/routers/customers.py` — approximately 2,632 lines
- `backend/app/routers/reports.py` — approximately 2,295 lines
- `backend/app/services/tally_xml_importer.py` — approximately 2,498 lines
- `frontend-nextjs/src/app/reports/page.tsx` — approximately 5,817 lines
- `frontend-nextjs/src/app/customers/[id]/page.tsx` — approximately 4,054 lines

Recommended backend structure:

```text
backend/app/
  domains/
    sync/
      router.py
      orchestration.py
      inbound.py
      outbound.py
      retry_policy.py
      schemas.py
    customers/
      router.py
      service.py
      read_models.py
    reporting/
      router.py
      queries/
      exports/
  integrations/
    tally/
      client.py
      xml_builder.py
      xml_importer.py
      schema_registry.py
    payments/
    imagekit/
  platform/
    auth/
    database/
    observability/
    pagination/
```

Recommended frontend structure:

```text
frontend-nextjs/src/
  features/
    customers/
    reports/
    vouchers/
    inventory/
    sync/
  shared/
    api/
    auth/
    components/
    formatting/
    offline/
```

Keep App Router pages thin and move API calls, query state, form logic, and domain components into feature modules.

### P1 — Centralize frontend API and authentication handling

The frontend has a shared `API_BASE` and `authHeaders`, but some pages directly access legacy token keys such as:

- `localStorage.getItem('token')`
- `localStorage.getItem('mytally_token')`

This creates inconsistent behavior and increases the impact of an XSS vulnerability because bearer tokens are stored in localStorage.

Recommended target:

- Prefer secure, HttpOnly, SameSite cookies.
- Add refresh-token rotation and server-side revocation.
- Expose authentication only through `AuthContext` or a single API client.
- Remove direct localStorage token reads.
- Add a consistent handling path for `401`, `403`, timeout, malformed JSON, and network-offline states.

### P1 — Standardize pagination and query projections

Several routers use fixed limits such as 100, 200, and 500 records. This creates two risks:

- Users may not realize that records are silently omitted.
- Large tenants cause unnecessary memory usage and slow serialization.

The repository already has `backend/app/core/pagination.py`, so extend that consistently:

- Use cursor pagination for high-volume vouchers, sync logs, traffic logs, payments, and audit records.
- Use projection queries instead of loading full SQLAlchemy models.
- Add composite indexes beginning with `company_id` and followed by the primary filter/sort fields.
- Use asynchronous export jobs for CSV/PDF/report downloads.
- Add explicit total-count controls because exact counts can become expensive.

### P1 — Make sync an explicit durable event system

The existing `SyncQueue`, `SyncTrafficLog`, retry endpoints, snapshots, and offline queue are good foundations. The next step should be a durable inbox/outbox design:

- Outbox event created in the same transaction as the business record.
- Sync worker claims events with leases, not only status changes.
- Idempotency key on every outbound event.
- Monotonic event version or sequence per company/entity.
- Explicit states: pending, claimed, sent, acknowledged, conflict, dead-lettered.
- Exponential backoff with jitter.
- Dead-letter queue and operator resolution workflow.
- Payload schema versioning.
- Conflict detail exposed to users instead of generic failure status.

This is particularly important because Tally is an external system with its own ordering and mutation semantics.

### P1 — Improve tenant isolation guarantees

Most queries visibly filter by `company_id`, but this is a critical security invariant and should not depend solely on individual router authors remembering it.

Recommended controls:

- Company-scoped repository/service functions rather than raw model queries from routers.
- Automated tests that attempt cross-company access for every major resource.
- A request-scoped tenant context.
- Database-level safeguards where practical.
- Static review rules preventing unscoped reads on tenant tables.
- Composite unique constraints that include `company_id` where business identity is tenant-specific.

### P2 — Replace broad exception handling and `print`

Many services and routers still use broad `except Exception`, `print`, or silent fallbacks. This is especially prevalent in sync, Tally import, notifications, ImageKit, and database setup code.

Recommended error taxonomy:

- `ValidationError`
- `AuthorizationError`
- `ExternalServiceError`
- `SyncConflictError`
- `RetryableSyncError`
- `PermanentSyncError`
- `DataIntegrityError`

Each should map to:

- A stable API response.
- A structured log event.
- A correlation/request ID.
- A retry or non-retry classification.
- A user-facing message that does not expose sensitive internals.

### P2 — Improve cache architecture

`backend/app/core/cache.py` uses a process-local in-memory cache. That is acceptable for a single worker but becomes inconsistent across multiple replicas and is lost on restart.

Use Redis or another shared cache for:

- Report responses
- Master data
- Permission snapshots
- VAPID/configuration data
- Sync health aggregates

Also add cache invalidation on relevant mutation events rather than relying only on TTL.

## Testing, CI/CD, and operations gaps

The repository has valuable voucher E2E harnesses, but the only GitHub workflow found is Scorecard. There is no normal automated gate for:

- Backend unit/integration tests
- Frontend lint
- Type checking
- Next.js production build
- Migration validation
- API contract compatibility
- Dependency installation and lockfile consistency
- Container smoke testing
- Secret scanning or vulnerability scanning in the normal pipeline

Recommended CI sequence:

1. Install Python and Node dependencies using locked versions.
2. Run Python formatting, linting, type checks, and unit tests.
3. Start a disposable MySQL service.
4. Apply migrations from an empty database.
5. Run API integration and tenant-isolation tests.
6. Run frontend lint, TypeScript checks, and production build.
7. Run a minimal Tally sync contract test with fixtures.
8. Run dependency and secret scans.
9. Publish migration, test, and build artifacts.

Add observability around:

- Sync queue age
- Failed events by company and entity type
- Tally round-trip latency
- Import rows per second
- Conflict rate
- Offline queue age
- Payment webhook lag
- Report query latency
- Database pool exhaustion
- Background worker restarts

## 2. High-impact missing business features

### 1. Distributor pricing and promotion engine — P1

The application has price levels, but a field-sales distributor generally needs more than a static price list:

- Customer-specific prices
- Channel/customer-group prices
- Quantity slabs
- Date-effective rates
- Promotional schemes
- Buy-X-get-Y/free-item rules
- Salesperson override permissions
- Margin floor checks
- Offline price snapshots

This should integrate with temporary orders, vouchers, customer groups, inventory, and approvals. It would directly reduce margin leakage and order-entry friction.

### 2. Van sales and route settlement — P1

The current system has route planning, GPS check-ins, orders, payments, and stock entities, but not a complete van-sales lifecycle.

MVP capabilities:

- Van or salesperson stock loading
- Route manifest
- Opening cash and opening stock
- Invoice/receipt capture during visits
- Cash and UPI collection
- Returns, damages, and unsold stock
- End-of-day settlement
- Variance approval
- Manager sign-off

This is one of the highest-value distributor features because it joins inventory accountability, field execution, and collections into one operational workflow.

### 3. Lot, batch, expiry, and recall traceability — P1

Batch and godown models provide a foundation, but distributor-grade traceability requires:

- FEFO allocation
- Expiry and near-expiry alerts
- Blocked/held lots
- Purchase-to-sale lot genealogy
- Customer trace-back
- Recall campaigns
- Notification and acknowledgement audit
- Expiry write-off workflow

This is particularly important for products with shelf life, regulated goods, or manufacturer recall obligations.

### 4. Customer credit and collections cockpit — P2

Outstanding balances, payments, reminders, and customer health appear as separate capabilities. A field team needs one prioritized collection workspace:

- Credit limit and available credit
- Aging bands
- Risk score
- Promise-to-pay tracking
- Dispute reason
- Collection route
- Payment link
- Escalation rules
- Hold-order policy

The first release could be a read model and work queue rather than a new accounting subsystem.

### 5. Procurement replenishment and supplier performance — P2

The system has stock and purchase concepts but lacks a clear demand-driven procurement layer.

Useful capabilities:

- Min/max and safety stock
- Lead-time-aware reorder points
- Suggested purchase orders
- Supplier fill rate
- Purchase price variance
- Landed-cost tracking
- Supplier scorecards
- Slow-moving and dead-stock analysis

## Recommended integrations

### Barcode and mobile scanning

Integrate camera or Bluetooth scanner support for:

- Stock lookup
- Van loading
- Goods receipt
- Batch capture
- Order entry
- Returns
- Cycle counts

The existing stock item, batch, godown, and offline queue contracts make this a natural extension. Scan resolution should work offline first, with synchronization when connectivity returns.

### Payment and messaging rails

Connect payment links and messaging to existing outstanding, payments, reminders, notifications, and customer workflows:

- UPI/payment-link provider
- WhatsApp Business or SMS provider
- Webhook-based payment confirmation
- Provider transaction ID
- Reconciliation state
- Expiry and retry handling
- Customer-facing receipt/status message

A redirect or client-side success response must not be treated as payment confirmation; only a verified webhook or provider reconciliation should finalize the transaction.

## 3. Quick wins

### Unified API client and error surface

Create one frontend API client that handles:

- Base URL
- Authorization
- Timeouts
- Request IDs
- JSON parsing
- `401` and `403`
- Offline/network errors
- Consistent toast-safe messages

This is relatively small and eliminates duplicated behavior across pages.

### Sync health dashboard

Expose:

- Pending count
- Failed count
- Oldest queue age
- Last successful inbound sync
- Last successful outbound push
- Retry rate
- Conflict count
- Per-company health
- Dead-letter items

The backend already has sync queue and traffic log entities, so this mostly requires an aggregate endpoint and a focused UI.

### Saved field-sales workspace

Create a customer card optimized for reps with:

- Next route stop
- Last order
- Current outstanding
- Customer-specific price list
- Recent payment
- Last check-in
- Next action
- Offline-ready cached details

This would make the existing offline and field-sales investment visible in the daily user workflow.

## Recommended sequence

### First 30 days — stabilize the platform

- Enforce secure database TLS.
- Introduce CI build/test/migration gates.
- Centralize frontend auth/API handling.
- Add structured sync error taxonomy.
- Add queue age, retry, and failure metrics.
- Begin migration away from startup schema mutation.

### Days 31–90 — make field sales dependable

- Implement cursor pagination and query projections.
- Launch distributor pricing/promotion MVP.
- Build customer credit and collections cockpit.
- Improve offline conflict and retry UX.
- Start van route settlement MVP.

### Days 91–180 — deepen distributor economics

- Add FEFO and expiry traceability.
- Add replenishment suggestions and supplier scorecards.
- Add barcode/mobile scanning.
- Add payment-link and messaging integrations.
- Add route, margin, inventory, and collections analytics.

**Bottom line:** prioritize platform reliability first, then differentiate around distributor economics. Pricing/promotion, route settlement, and credit collections are more strategically valuable for this product than adding another broad ERP module.