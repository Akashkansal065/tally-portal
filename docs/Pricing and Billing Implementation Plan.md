# MyTally Pricing, Subscriptions and Payment Gateways: Implementation Plan

## 1. Context

The uncommitted billing work (`backend/app/routers/billing.py`, `/pricing`, `PlanCheckoutModal`, `SubscriptionBillingPanel`) gives a good pricing UI, but the backend is a mock:

- Any signed-in user can get any plan for free (`verify-payment` checks nothing, and the frontend always takes the "demo" path).
- Nothing about a purchase is stored: no order, payment, subscription or invoice. Expiry is invented.
- Plans, prices and coupons are hardcoded in three places.
- Limits shown on screen disagree with what the server enforces, and feature gating does not exist.

The goal is a real billing system: plans in the database, custom plans per customer, Razorpay and Cashfree behind one interface, prepaid and autopay billing, GST invoices, and enforcement of limits, features and expiry.

### Decisions already made

| Topic | Decision |
|---|---|
| Billing model | Prepaid 1/2/3-year terms, monthly plans, and autopay (UPI Autopay / e-mandate), all in scope |
| On expiry | 7-day grace, then **full lock**: only the billing page works and Tally sync stops until payment |
| Existing accounts | Grandfathered on a hidden unlimited `legacy` plan until an operator assigns a plan or end date |
| Gateway choice | The customer picks Razorpay or Cashfree at checkout |

### Inputs needed from you before go-live (not blocking development)

- Seller legal name, GSTIN, registered state, SAC code, invoice number prefix.
- Monthly prices for Silver, Gold, Diamond (seeded inactive until set).
- The real sales phone / WhatsApp number (the code has `83838 38383`).
- Razorpay and Cashfree live keys and webhook secrets.

### Two corrections to my earlier review

- New columns are added automatically at startup by `auto_sync_all_model_schemas` ([database.py:164](backend/app/core/database.py:164)), so no manual `ALTER TABLE` is needed.
- The `Idempotency-Key` header is added by a fetch wrapper in [AuthContext.tsx:60](frontend-nextjs/src/context/AuthContext.tsx:60), not per call. Confirm in Phase 0 that the billing calls go through it.

---

## 2. What must be fixed in the current code

| # | File | Fix |
|---|---|---|
| F1 | [billing.py:444](backend/app/routers/billing.py:444) | Delete `verify-payment`. Replace with `POST /billing/orders/{ref}/confirm`, which verifies with the gateway server-side and calls `fulfil_order`. |
| F2 | [PlanCheckoutModal.tsx:244](frontend-nextjs/src/components/pricing/PlanCheckoutModal.tsx:244) | Remove the `DEMO_PAY_` simulation branch entirely. |
| F3 | [billing.py:424](backend/app/routers/billing.py:424) | Remove `except Exception: pass`, the mock fallback and the fake `rzp_test_MyTallyPortalKey`. A gateway failure returns 502 with a clear message. |
| F4 | [billing.py:224](backend/app/routers/billing.py:224) | Validate inputs: `extra_users`/`extra_companies` with `Field(ge=0, le=500)`, plan and term checked against the database. |
| F5 | [billing.py:271](backend/app/routers/billing.py:271) | Rewrite `current-subscription` to read the real subscription row. Remove the invented expiry, the substring tier detection and the hardcoded feature list. |
| F6 | billing endpoints | Require an account admin (`is_admin_user`) for anything that buys or changes a plan. Refuse users with no `account_id`. |
| F7 | [admin/page.tsx:2118](frontend-nextjs/src/app/admin/page.tsx:2118) | `SubscriptionBillingPanel` is passed `token` but takes no props. Remove the prop. |
| F8 | [pricing/page.tsx](frontend-nextjs/src/app/pricing/page.tsx), modal, panel | Delete the hardcoded plan arrays, the `999`/`1499` constants and the client-side coupon logic. All numbers come from the API. |
| F9 | quote maths | Use integer paise and `Decimal`. One server-side quote function; the frontend only displays it. |
| F10 | GST | Split CGST+SGST or IGST by place of supply. Validate and store the GSTIN. |
| F11 | [billing.py:475](backend/app/routers/billing.py:475) | Store inquiries in `billing_leads`, rate-limit the endpoint, notify the operator. |
| F12 | UI claims | Remove or make true: "automated prorated billing", "7-Day Money-Back Guarantee", "Renews on 12 Oct 2027", "256-bit Razorpay" (now two gateways). |
| F13 | [navigation.ts:153](frontend-nextjs/src/lib/navigation.ts:153), billing.py comment | Remove the competitor name from shipped code. |
| F14 | panel fallbacks | Show a loading or error state instead of fake defaults (`'Gold Plan'`, `5` slots). Handle unlimited (`null`) limits without dividing by zero. |
| F15 | "Add company slot" buttons | Open an add-on purchase flow, not a Diamond/Gold checkout. |

Unrelated to billing but in the same diff: [companies.py](backend/app/routers/companies.py) no longer queues `run_once_sync_background` after a company update, yet still imports it. Confirm that removal was intended.

---

## 3. Data model

New module `backend/app/models/billing.py` (portal schema). Register it where models are imported: `main.py`, `auto_sync_all_model_schemas` in `database.py`, and `tests/conftest.py`. All money is integer paise.

### Catalog

| Table | Key columns | Notes |
|---|---|---|
| `billing_plans` | `code` (unique), `name`, `tagline`, `badge`, `max_users`, `max_companies`, `max_devices`, `features` (JSON list), `display` (JSON), `trial_days`, `is_public`, `is_active`, `account_id` (nullable), `sort_order` | `NULL` limit = unlimited, matching the existing convention. `account_id` set = **custom plan** visible only to that account. |
| `billing_plan_prices` | `plan_id`, `interval` (`month`/`year`), `interval_count`, `amount_paise`, `compare_at_paise`, `autopay_allowed`, `gateway_plan_refs` (JSON), `is_active` | Unique on (plan, interval, interval_count). `gateway_plan_refs` holds the Razorpay/Cashfree plan ids for autopay. |
| `billing_addons` | `code`, `kind` (`seat_user`/`seat_company`/`credit_pack`), `yearly_paise`, `monthly_paise`, `credit_type`, `credit_qty` | Replaces `ADDONS_DATA`. |
| `billing_coupons` | `code`, `kind` (`percent`/`flat`), `value`, `max_discount_paise`, `valid_from`, `valid_until`, `max_redemptions`, `per_account_limit`, `plan_codes`, `first_purchase_only`, `partner_id` | |
| `billing_coupon_redemptions` | `coupon_id`, `account_id`, `order_id` (unique) | |

The comparison table on the pricing page is derived from `features` plus a small feature registry (`services/billing/features.py`: key, label, category, info), so it cannot drift from what is enforced.

### Per account

| Table | Key columns | Notes |
|---|---|---|
| `account_subscriptions` | `account_id` (unique), `plan_id`, `price_id`, `status`, `trial_ends_at`, `current_period_start`, `current_period_end`, `grace_ends_at`, `extra_users`, `extra_companies`, `overrides` (JSON), `autopay`, `gateway`, `gateway_subscription_id`, `gateway_customer_id`, `cancel_at_period_end`, `pending_plan_id`, `pending_price_id` | `status`: `legacy`, `trialing`, `active`, `grace`, `locked`, `cancelled`. `overrides` lets an operator adjust limits or features for one account. |
| `billing_subscription_events` | `account_id`, `type`, `from_state`, `to_state`, `order_id`, `actor_user_id`, `detail` (JSON) | Append-only history. |
| `account_billing_profiles` | `account_id` (PK), `legal_name`, `gstin`, `address`, `state_code`, `email`, `phone` | Prefilled from the account's first company (`Company.gstin`, `state`). |
| `billing_credit_ledger` | `account_id`, `credit_type`, `delta`, `reason`, `reference` | Unique on (account, type, reference). Balance is the sum. Used for e-invoice and WhatsApp packs. |

### Money movement

| Table | Key columns | Uniqueness (the idempotency guarantees) |
|---|---|---|
| `billing_orders` | `order_ref`, `account_id`, `purpose` (`new`/`renewal`/`upgrade`/`addon`/`credit_pack`/`autopay_charge`), frozen `quote` JSON, amount columns, `status`, `gateway`, `gateway_order_id`, `client_request_key`, buyer snapshot, `paid_at`, `fulfilled_at`, `expires_at` | `order_ref`; (`gateway`, `gateway_order_id`); (`account_id`, `client_request_key`) |
| `billing_payments` | `order_id`, `gateway`, `gateway_payment_id`, `amount_paise`, `status`, `method`, `raw` | (`gateway`, `gateway_payment_id`) |
| `billing_refunds` | `payment_id`, `gateway_refund_id`, `amount_paise`, `status`, `reason`, `actor_user_id` | `gateway_refund_id` |
| `billing_webhook_events` | `gateway`, `event_id`, `event_type`, `payload`, `signature_verified`, `processed`, `processing_error` | (`gateway`, `event_id`) |
| `billing_invoices` | `invoice_number`, `kind` (`invoice`/`credit_note`), `order_id`, buyer and seller snapshots, `place_of_supply`, `sac`, lines, tax split, `pdf_path` | `invoice_number`; (`order_id`, `kind`) |
| `billing_invoice_counters` | `fy`, `kind`, `last_number` | Row-locked when numbering. |
| `billing_leads` | name, phone, email, company, plan, message, `status` | |

`Account.plan`, `max_users`, `max_companies`, `max_devices` stay in place but stop being read (see section 6).

### Configuration

- **Secrets in env** ([config.py](backend/app/core/config.py)): `BILLING_RAZORPAY_KEY_ID`, `BILLING_RAZORPAY_KEY_SECRET`, `BILLING_RAZORPAY_WEBHOOK_SECRET`, `BILLING_CASHFREE_APP_ID`, `BILLING_CASHFREE_SECRET`, `BILLING_CASHFREE_ENV`. These are separate from `RAZORPAY_WEBHOOK_SECRET`, which belongs to the tenant payment-link webhook.
- **Operator settings** in the existing `AppSetting` table (`services/app_settings.py`): enabled gateways, grace days, seller details, invoice prefix, sales contact.

---

## 4. Backend services

New package `backend/app/services/billing/`.

| Module | Responsibility |
|---|---|
| `catalog.py` | Load plans, prices, add-ons (cached). Idempotent seed of Silver/Gold/Diamond, `legacy`, add-ons from today's `PLANS_DATA`. |
| `features.py` | Feature registry: key, label, category. |
| `quote.py` | Pure function: plan + term + add-ons + coupon + buyer state + current subscription → itemised quote in paise. Handles proration. |
| `entitlements.py` | `get_entitlements(db, account_id)` → state, limits, features, period end. Cached, invalidated on every subscription change. |
| `orders.py` | `create_order`, `fulfil_order`, `expire_stale_orders`. |
| `subscriptions.py` | State machine, `start_trial`, `apply_purchase`, `schedule_downgrade`, lifecycle worker. |
| `invoices.py` | Numbering, tax split, PDF, credit notes. |
| `credits.py` | Grant and consume pack credits. |
| `gateways/base.py`, `razorpay.py`, `cashfree.py`, `registry.py` | Provider interface and adapters. |

### Quote rules

- Base price comes from `billing_plan_prices`. Add-on price = unit price × quantity × term.
- **Upgrade:** credit the unused share of the current term's taxable amount (days left ÷ days in term) against the new price. The new term starts today.
- **Add-on mid-term:** charged pro rata to the current period end, so everything renews together.
- **Renewal:** extends from `current_period_end`, or from today if already lapsed.
- **Downgrade:** refused if current usage exceeds the new limits (the response lists what to remove). Otherwise stored as `pending_plan_id` and applied at period end.
- **Tax:** 18% GST on the taxable amount. Buyer state equals seller state → CGST + SGST; otherwise IGST. Rounded once, to the paisa.

### `fulfil_order(order_id)`: the single activation path

Called by the confirm endpoint, both webhooks, the reconciliation worker and the operator's offline-payment action.

1. Lock the order row (`SELECT … FOR UPDATE`). If `fulfilled_at` is set, return the existing result.
2. Fetch the payment from the gateway server-side. Require captured status, amount equal to the order total, currency INR.
3. Upsert `billing_payments` (unique key makes a repeat a no-op).
4. Apply the subscription change, redeem the coupon, grant credits, issue the invoice.
5. Write a `billing_subscription_events` row and set `fulfilled_at`. Commit.
6. After commit: invalidate the entitlements cache, notify account admins (`notify_admins` in [notifications.py:323](backend/app/services/notifications.py:323)), email the invoice (`send_email` in [messaging.py:89](backend/app/services/messaging.py:89)).

The database unique constraints carry the idempotency, because the request-level middleware ([idempotency.py](backend/app/core/idempotency.py)) is per process.

---

## 5. Payment gateways

Both adapters use `httpx` (already in `requirements.txt`); no SDK dependency.

### Provider interface (`gateways/base.py`)

```python
class BillingGateway(Protocol):
    code: str
    def checkout_config(self, order) -> dict          # what the frontend SDK needs
    async def create_order(self, order) -> GatewayOrder
    async def confirm(self, order, client_payload) -> GatewayPayment   # server-side verification
    def verify_webhook(self, headers, raw_body) -> bool
    def parse_webhook(self, payload) -> NormalisedEvent
    async def fetch_order_payments(self, gateway_order_id) -> list[GatewayPayment]
    async def refund(self, payment, amount_paise, reference) -> GatewayRefund
    async def ensure_plan(self, price) -> str          # autopay
    async def create_subscription(self, account, price, order) -> GatewaySubscription
    async def cancel_subscription(self, gateway_subscription_id) -> None
```

`NormalisedEvent` types: `payment.captured`, `payment.failed`, `refund.processed`, `subscription.activated`, `subscription.charged`, `subscription.payment_failed`, `subscription.cancelled`.

### Razorpay

- **Order:** `POST /v1/orders`, amount in paise, `receipt = order_ref`, `notes.account_id`.
- **Checkout confirm:** HMAC-SHA256 of `order_id|payment_id` with the key secret, compared with `hmac.compare_digest`. Then fetch the payment to confirm captured status and amount.
- **Webhook:** HMAC-SHA256 of the raw body with the webhook secret (`X-Razorpay-Signature`). Event id from `X-Razorpay-Event-Id`. Reuse the approach of `_razorpay_signature_valid` in [payment_gateway.py:104](backend/app/routers/payment_gateway.py:104).
- **Autopay:** Plans and Subscriptions APIs; checkout opens with `subscription_id`.

### Cashfree

- **Order:** `POST /pg/orders` with `x-client-id`, `x-client-secret`, `x-api-version`. Returns `payment_session_id`.
- **Checkout confirm:** there is no client signature. Confirm by fetching the order and its payments server-side.
- **Webhook:** base64 of HMAC-SHA256 over `timestamp + raw body` (`x-webhook-signature`, `x-webhook-timestamp`). Reject stale timestamps.
- **Autopay:** Cashfree Subscriptions API.
- Check header names, API version and subscription endpoints against the current Cashfree docs when building the adapter.

### Rules for both

- Fail closed: no secret configured means the webhook returns 503 and the gateway is not offered at checkout.
- Webhook handler order: verify signature → insert `billing_webhook_events` (duplicate = return 200) → map to order → `fulfil_order` → mark processed. A processing failure returns non-2xx so the gateway retries.
- **Reconciliation worker:** every 5 minutes, poll the gateway for orders stuck in `pending` for over 2 minutes; expire unpaid orders after 30 minutes.
- **Autopay limits:** mark `autopay_allowed` only on prices under the UPI Autopay per-debit limit (check the current RBI figure). 2- and 3-year terms stay prepaid.

---

## 6. Entitlements and enforcement

### Limits

Effective limit = plan limit + purchased extras + operator override; `NULL` stays unlimited. Replace the direct reads:

- [team.py:67](backend/app/routers/team.py:67) `_check_user_limit` → entitlements `max_users`.
- [agent.py:119](backend/app/routers/agent.py:119) device limit and [agent.py:180](backend/app/routers/agent.py:180) company limit → entitlements.

### Features

`require_feature("einvoice_eway_bill")` dependency, modelled on `require_integration` ([integrations.py:197](backend/app/services/integrations.py:197)). Apply it router by router: e-invoicing, bank reconciliation, approvals, visits/orders, reminders, payment links, custom roles. Refusal is a 403 with `X-Billing-Reason: feature` so the UI can show an upgrade prompt.

### Lifecycle

```
signup → trialing ──pay──► active ──period end──► grace ──7 days──► locked
                              ▲                      │                 │
                              └──────────pay─────────┴─────────────────┘
legacy: unlimited, no end date, until an operator assigns a plan
```

- **Trial start:** call `start_trial` in the same transaction as account creation at [phone_auth.py:178](backend/app/routers/phone_auth.py:178) and [agent.py:314](backend/app/routers/agent.py:314). [tenant_migration.py:69](backend/app/services/tenant_migration.py:69) creates `legacy`.
- **Backfill:** an idempotent startup step gives every account without a subscription row a `legacy` row. Nothing changes for existing customers on deploy.
- **Lifecycle worker:** a new loop beside `reminder_worker` in [main.py](backend/app/main.py). It moves subscriptions between states, applies pending downgrades, and sends reminders at 15, 7, 3 and 1 days before expiry and during grace. Each reminder is keyed (account, period end, offset) so it is sent once.

### Full lock

- Checked inside `get_current_user` ([permissions.py:161](backend/app/core/permissions.py:161)) after the user is resolved, using the cached entitlement state, so it also covers sync-agent device tokens.
- When `locked`, every path returns **402** with `X-Billing-State: locked`, except an allowlist: `/auth/*`, `/billing/*`, `/health`, and the notification count.
- Platform admins and `legacy` accounts are never locked.
- **Sync agent:** [agent.py](desktop-sync-agent/agent.py) treats 402 as "subscription expired": it stops the sync loop, shows the message, and rechecks every 15 minutes. Tally data is untouched. Once payment lands, the next check resumes sync through the existing resume flow.
- Queued Tally pushes are kept, not dropped, while locked.

---

## 7. API

### Public
- `GET /billing/plans`: public plans, prices, add-ons, feature comparison, enabled gateways, trial days, sales contact. With a token, also the caller's custom plans.
- `POST /billing/quote`
- `POST /billing/leads` (rate limited with the existing limiter)

### Account admin
- `GET /billing/subscription`: state, plan, period, usage against limits, features, credit balances.
- `GET|PUT /billing/profile`
- `POST /billing/orders`: body carries plan, term, add-ons, coupon, gateway, `autopay`, `client_request_key`. Returns the checkout config for the chosen gateway.
- `POST /billing/orders/{ref}/confirm`, `GET /billing/orders/{ref}`
- `GET /billing/invoices`, `GET /billing/invoices/{id}/pdf`
- `POST /billing/subscription/autopay/cancel`

### Webhooks
- `POST /billing/webhooks/razorpay`, `POST /billing/webhooks/cashfree`

### Operator (`require_platform_admin`, [permissions.py:285](backend/app/core/permissions.py:285))
New router `backend/app/routers/platform_billing.py`, prefix `/platform/billing`:
- Plans, prices, add-ons, coupons: create, edit, activate, retire.
- Accounts: list with state and expiry; assign plan; **create a custom plan for an account**; extend or set end date; set overrides; lock or unlock.
- Record an offline payment (NEFT/cheque/UPI with UTR), which runs `fulfil_order` with `gateway = offline`.
- Refunds (issues a credit note), leads, webhook event log with replay, settings.
- Metrics: MRR/ARR, trials ending, expiring in 30 days, failed payments, conversion.

---

## 8. Frontend

Read the relevant guide in `frontend-nextjs/node_modules/next/dist/docs/` before writing code (per `AGENTS.md`).

| File | Change |
|---|---|
| `src/lib/billing.ts` (new) | Types and API calls. The only place billing endpoints are called. |
| `src/lib/loadScript.ts` (new) | Loads Razorpay `checkout.js` or Cashfree `cashfree.js` on demand. |
| [pricing/page.tsx](frontend-nextjs/src/app/pricing/page.tsx) | Render from `GET /billing/plans`. Month/year toggle. Add-on steppers priced by `POST /billing/quote`. Anonymous visitors are sent to signup, then back to checkout. |
| [PlanCheckoutModal.tsx](frontend-nextjs/src/components/pricing/PlanCheckoutModal.tsx) | Server quote (debounced), coupon applied by the server, billing profile with GSTIN, **gateway picker**, autopay toggle where allowed, then confirm and poll order status. Success is shown only after the server says `paid`. |
| [SubscriptionBillingPanel.tsx](frontend-nextjs/src/components/admin/SubscriptionBillingPanel.tsx) | Real state, usage, invoices list with PDF download, add-on purchase, autopay management. |
| `src/app/billing/locked/page.tsx` (new) | The only screen a locked account sees: what expired, pay now, contact sales. |
| [AuthContext.tsx](frontend-nextjs/src/context/AuthContext.tsx) | On 402 with `X-Billing-State: locked`, route to the locked page (same pattern as the expired-session handling). |
| [GlobalHeader.tsx](frontend-nextjs/src/components/GlobalHeader.tsx) | Banner for trial days left, expiring soon, and grace. |
| `src/components/UpgradePrompt.tsx` (new) | Shown when a 403 carries `X-Billing-Reason: feature`. |
| `src/app/platform/billing/` (new) | Operator console, visible only to platform admins. |
| [navigation.ts](frontend-nextjs/src/lib/navigation.ts) | Hide modules the plan does not include, or show them with an upgrade badge. |

**Mobile apps:** Apple and Google restrict selling digital subscriptions inside apps outside their own billing. Hide purchase buttons inside the native wrappers and point to the web until the store rules for this B2B case are confirmed.

---

## 9. Further features (after the core)

1. Partner and reseller codes for CAs and Tally partners, with commission reports.
2. Referral credits.
3. Metered usage for e-invoice and WhatsApp credits, with low-balance alerts and auto top-up.
4. TDS handling: record a short payment when a customer deducts TDS, with the certificate reference.
5. Dunning for failed autopay charges: retry schedule and reminders.
6. Self-serve cancellation with a reason, and win-back offers.
7. Posting MyTally's own subscription invoices into its own Tally.
8. Revenue analytics: churn, cohort retention, plan mix.

---

## 10. Phases

| Phase | Scope | Result |
|---|---|---|
| **0. Stop the leak** | F1–F7, F12–F14. Checkout disabled behind a flag; the pricing page stays up with "Contact sales". | Nobody can self-upgrade for free. |
| **1. Catalog** | Models, seed, `catalog.py`, `quote.py`, public endpoints, pricing page reading the API (F8, F9, F11). | One source of truth for prices. |
| **2. Subscriptions and entitlements** | Subscription rows, backfill to `legacy`, trial at signup, `entitlements.py`, limit checks moved over. | Limits are real; existing customers unaffected. |
| **3. Prepaid checkout** | Orders, both gateway adapters, confirm, webhooks, `fulfil_order`, reconciliation worker, new checkout modal. | Customers can pay with either gateway. |
| **4. Invoices and tax** | Billing profile, GST split, numbering, PDF, email (F10). | Compliant invoice for every payment. |
| **5. Lifecycle and lock** | Worker, reminders, grace, 402 lock, locked page, sync-agent handling, banners. | Expiry is enforced. |
| **6. Operator console** | Platform router and UI: custom plans, assignments, offline payments, refunds, leads, metrics. | Sales and support can run billing without code. |
| **7. Feature gating** | `require_feature` on routers, navigation gating, upgrade prompts. | Plans differ in what they unlock. |
| **8. Monthly and autopay** | Monthly prices, gateway plans and subscriptions, mandate events, dunning. | Recurring billing. |
| **9. Upgrades, add-ons, credits** | Proration, mid-term add-ons, scheduled downgrades, credit packs (F15). | Full plan changes. |

Each phase ends with its tests green and a runbook update.

---

## 11. Tests and verification

**Automated** (`backend/tests/`, using the existing SQLite harness in `conftest.py`):

- `test_billing_quote.py`: prices, add-ons, coupon caps, proration, CGST/SGST against IGST, paisa rounding, negative and oversize inputs refused.
- `test_billing_orders.py`: confirm with a bad signature fails; amount mismatch fails; `fulfil_order` twice activates once; the same webhook delivered twice yields one payment and one invoice; a webhook arriving before confirm works.
- `test_billing_gateways.py`: Razorpay and Cashfree signature checks with known vectors; adapters tested against mocked `httpx`.
- `test_billing_entitlements.py`: user, company and device limits; `legacy` unlimited; feature refusal.
- `test_billing_lifecycle.py`: trial → grace → locked; 402 on normal routes and 200 on the allowlist; payment unlocks; reminders sent once.
- `test_billing_isolation.py`: one account cannot read another's orders, invoices or custom plans; non-admins cannot buy; operator routes refuse account admins.

Run from `backend/`:

```bash
pytest tests -k billing
```

```bash
pytest tests
```

**Manual, end to end:**

1. Razorpay test mode and Cashfree sandbox keys in `.env`; expose the local server with a tunnel and register both webhook URLs.
2. Start the frontend with the preview tools; buy Gold for 1 year through each gateway with test cards and test UPI.
3. Confirm: order `paid`, subscription `active` with the right period end, invoice PDF with the correct tax split, limits changed in the admin panel.
4. Close the browser mid-payment and confirm the webhook alone activates the plan.
5. Replay a webhook from the gateway dashboard and confirm nothing is duplicated.
6. Set a subscription's period end in the past, run the lifecycle worker, and confirm grace, then the locked page, then the sync agent's "subscription expired" state; pay and confirm sync resumes.
7. As operator: create a custom plan for one account, record an offline payment, issue a refund and check the credit note.

---

## 12. Rollout

Add each manual step to `docs/Multi-Tenant Rollout Runbook.md` as it is introduced:

- New env vars per environment; webhook URLs and secrets registered in both gateway dashboards.
- Seed run and catalog check; seller details and invoice prefix entered in operator settings.
- Confirmation that every existing account received a `legacy` subscription row.
- Checkout feature flag turned on only after Phase 4.
- Sync agent release with 402 handling shipped **before** the lock is switched on in Phase 5.

**First step on approval:** save this plan to `docs/Pricing and Billing Implementation Plan.md` in the repo, then start Phase 0.
