# MyTally → Livekeeping parity plan

_Written 5 Oct 2026. Replaces the older [livekeeping.md](livekeeping.md), most of which has since been built (P&L, balance sheet, ageing, dashboard charts, inactive customers, backup, audit log)._

## Goal

1. **Track A: use it ourselves.** Bring MyTally up to everything Livekeeping does, for our own business, and run on it daily until every feature is proven on real data.
2. **Track B: sell it.** Only after Track A meets its exit criteria (below), turn MyTally into a product other Tally users can sign up for and pay for.

Livekeeping for reference (Oct 2026): "India's No.1 Business Accounting on Mobile App", 1 lakh+ businesses, IndiaMART-owned. Plans (3-year billing, per year, excl. GST): Growth (read-only) ₹2,400 · Pro (create vouchers, invoice templates) ₹3,750 · Pro Plus (e-way bill + e-invoice) ₹5,250 · extra user ₹5,625/yr.

## Where we stand

MyTally already matches or beats Livekeeping on: Tally connector and two-way sync, web + Android, dashboard and comparisons, ~35 reports, outstanding and ageing (with credit days, chase list, days to get paid), voucher entry pushed to Tally, multi-company and role-based access, GPS tracking, attendance, notifications, inactive customers.

Features Livekeeping doesn't have: bank reconciliation, GST returns workspace, expenses, sales target / watchlists / city reports, field-staff management (beat plans, shop check-ins, customer profiles).

**Gaps found in the code:**

| # | Gap | Severity |
|---|---|---|
| G1 | e-Invoice is simulated: IRN is a SHA-256 hash and ack number is random, even with the setting on "production" (`backend/app/routers/gst.py`, `generate_einvoice_irn`) | Critical |
| G2 | e-Way bill is simulated: random 12-digit number for bills ≥ ₹50,000 (same function) | Critical |
| G3 | GSTR-2B "Request OTP" says an OTP was sent, but no request is made (`gst.py`, `request_gstr2b_otp`) | High |
| G4 | Payment links are broken: `pay.mytally.in/...` is not a live site; Razorpay/Stripe link addresses are made up and the gateway API is never called (`payments.py`, `payment_gateway.py`) | High |
| G5 | Reminders are WhatsApp click-to-send only. "Bulk" only writes the messages. No SMS, no email, no scheduling, no auto-stop on payment | High |
| G6 | Invoice PDF has one fixed layout: no logo, UPI QR, bank details, terms or signature. `components/InvoicePDF.tsx` is unused | Medium |
| G7 | Voucher entry lacks batch selection, alternate units and physical stock voucher | Medium |
| G8 | No maker-checker queue: vouchers can be draft/optional/confirmed, but there's no approve-before-Tally step | Medium |
| G9 | Backups are on-demand only: no schedule, no emailed copy | Low |
| G10 | Missing reports: cash/bank book, cost-centre report, godown-wise and batch-wise stock; no one-tap report sharing | Low |
| G11 | No customer greetings (festival/birthday/thank-you templates with branding) | Low |
| G12 | Ledger statements and invoices can't be emailed | Low (solved by Phase 2 email channel) |
| G13 | iOS project exists but hasn't been built or tested | Low (own use) / High (selling) |

Checked on the real database (read-only, 5 Oct): **no simulated IRNs, e-way bill numbers or payment links have been saved**, and the one company is set to "mock". So Phase 1 needs no data clean-up.

## Ground rules for every phase

- A short design note in this file before code; tests for every backend change; verify on the throwaway demo (SQLite API + frontend clone), then read-only checks on real data.
- Nothing pretends to work: a feature without its real integration is hidden or clearly labelled "Demo".
- Secrets (API keys, GSP credentials, WhatsApp tokens) live only in `backend/.env` or the host's environment, never in git or chat. The repo is public.
- Commits only when asked.

---

# Track A: for our own business

## Phase 1: Make the simulated features honest

**Why first:** a made-up IRN or e-way bill number on a real invoice is a GST compliance risk, and a customer tapping a payment link that leads nowhere hurts trust. No provider accounts are needed. **Size: S (1–2 days).**

- **e-Invoice / e-Way bill (G1, G2):**
  - Remove the "sandbox" and "production" choices from e-invoice settings until Phase 4 makes them real; the only option is "Demo".
  - In demo mode, every IRN, ack number and e-way bill number is shown with a "DEMO – not valid" label, and is never printed on an invoice PDF or pushed to Tally.
  - Backend refuses to save simulated values under any environment other than "mock".
- **GSTR-2B (G3):** hide "Request OTP / Verify OTP"; keep the JSON upload, which is real.
- **Payment links (G4):** reminders and the voucher page send only the UPI link (`upi://pay?...`, which works). Remove the `pay.mytally.in` address. Hide "create Razorpay/Stripe link" until a real gateway integration is built (moved to Phase 2b).
- **Tests:** demo IRN can't be produced in other environments; reminders contain no dead links.
- **Done when:** nothing in the app shows a made-up compliance number or link as if it were real.

## Phase 2: Automatic payment reminders (G5, G12)

Livekeeping's main selling point for collections. **Size: L (5–8 days), plus provider sign-ups.**

- **Channels**, behind one provider interface so a provider can be swapped:
  - **WhatsApp:** Meta's WhatsApp Business API (directly, or through a provider such as Interakt, Wati or Gupshup). Needs Meta business verification and pre-approved message templates ("utility" category for payment reminders).
  - **Email:** a transactional email service (e.g. Amazon SES, Resend) or SMTP from our own domain, with SPF/DKIM set up so mail isn't marked spam.
  - **SMS (optional):** Indian SMS needs DLT registration (business, sender header, every template) through a telecom DLT portal, then a provider such as MSG91. Recommend leaving SMS until WhatsApp and email are running.
- **New data:** `reminder_schedules` (party or ageing bucket, channels, daily / weekly / monthly / on due date, time of day, template, active) and `reminder_log` (when, channel, message, provider message id, delivered/read/failed).
- **Worker:** a background loop like the existing daily-cleanup worker, running every few minutes in IST. It sends what's due, skips parties who have paid, and stops a schedule automatically once the balance is cleared.
- **Safety:** quiet hours (no messages before 9 am or after 8 pm), at most one reminder per party per day, opt-out, and a dry-run mode that logs instead of sending.
- **Screens:** on Outstanding, add "Schedule reminder" for a customer or a whole ageing bucket, with a preview of the exact message, a per-customer reminder history, and failed sends shown in Notifications.
- **Also uses the email channel:** email ledger statements and invoices.
- **Phase 2b (optional): real payment links.** Razorpay payment links API plus the existing webhook to mark bills paid. Only if UPI links aren't enough.
- **Done when:** a reminder set for a real overdue customer goes out on schedule by WhatsApp and email, shows "delivered", and stops by itself after the payment lands in Tally.

## Phase 3: Branded invoices and sharing (G6)

**Size: M (3–4 days).**

- **Company branding settings:** logo, address, GSTIN, bank details, UPI ID (printed as a scannable UPI QR code with the bill amount), terms, signature image, and a choice of 2–3 layouts.
- **Where it's used:** the voucher/invoice PDF (`lib/pdf-generator.ts`) and the ledger statement PDF (`lib/ledger-export.ts`). Remove or reuse the unused `components/InvoicePDF.tsx`.
- **Sharing:** the phone's share sheet on Android (Capacitor Share) and the Web Share API on the web, so the PDF goes straight to WhatsApp. Email uses the Phase 2 channel.
- **Done when:** a real sales invoice PDF with our logo and UPI QR can be shared to a customer's WhatsApp in two taps.

## Phase 4: Real e-Way bill and e-Invoice (G1, G2)

**Size: L (6–10 days), plus GSP onboarding.**

- **Do we need it for ourselves?**
  - **e-Invoice** is mandatory only once aggregate turnover crosses ₹5 crore in any financial year. At our ₹20 lakh/month target (~₹2.4 crore/year) we're probably below that. **Confirm with our CA.**
  - **e-Way bill** is needed for most goods movements over ₹50,000, whatever the turnover (state rules vary; confirm with the CA).
  - So for our own use, build **e-way bill first**. Build e-invoice too, but it can stay in sandbox until we sell the product or cross ₹5 crore.
- **Provider:** a licensed GST Suvidha Provider (GSP) with e-way bill and e-invoice APIs. Get quotes from 2–3 (e.g. Masters India, ClearTax, IRIS, TaxPro) on cost per call and sandbox access. Direct NIC API access is another option if we're eligible.
- **Build:**
  1. Token/session handling.
  2. e-Way bill from a sales voucher (Part A from the voucher, Part B vehicle details); update vehicle; cancel within 24 hours; print the EWB number and its QR on the PDF.
  3. e-Invoice: IRN from a sales voucher using the government's INV-01 JSON schema; signed QR; ack number and date; cancel within 24 hours; e-way bill from the IRN.
  4. Write IRN / EWB numbers back to Tally through the sync agent so Tally's records match.
  5. Validation before sending (GSTINs, HSN codes, pincodes, state codes) with plain-language errors.
- **Testing:** everything in the GSP sandbox first, then one real e-way bill, checked on the government portal.
- **Not planned:** Livekeeping's "track the vehicle on a live map". It needs vehicle GPS/FASTag data we don't have.
- **Done when:** a real e-way bill is generated from the app, matches the government portal, and its number appears on the invoice and in Tally.

## Phase 5: Remaining parity items

**Size: M–L (5–8 days), can be split up.**

- **Voucher entry (G7):** batch selection, alternate units, physical stock voucher.
- **Maker-checker (G8):** a new "approve vouchers" permission. Vouchers entered by a "maker" stay as drafts and are not pushed to Tally until a "checker" approves; rejected ones go back with a note. Approval queue screen; notifications to both sides.
- **Backups (G9):** a daily scheduled backup with a log, keeping the last N copies, plus "email me a copy".
- **Reports (G10):** cash/bank book, cost-centre report, godown-wise and batch-wise stock; a share button on every report (PDF to WhatsApp or email).
- **Customer greetings (G11):** a small library of festival, birthday and thank-you templates with our logo and contact details, sent by WhatsApp to inactive customers (from Watchlists).
- **iOS (G13):** build and test on the simulator and an iPhone. Only needed internally if someone uses an iPhone.

## Track A exit criteria (before starting Track B)

- Used daily for at least **6 weeks** by the owner and field staff, with no blocking bugs.
- Automatic reminders have run for at least a month, with delivery logs, and collections can be compared before and after.
- At least **10 real e-way bills** generated with no portal mismatches (and e-invoice passing in sandbox).
- Every voucher entered from mobile reached Tally correctly. The sync conflict list is empty or explained.
- Backups have run on schedule for a month, and one restore has been tested.

---

# Track B: selling it (after Track A)

Outline only. Each item gets its own detailed plan when we get here.

1. **Remove our own business from the code.** 39 files mention "Sneh"/"SnehDistribuors", or a fallback GSTIN (`09GAHPK5367P1ZR` in `gst.py`), across the backend, the desktop connector and the frontend. Move all of it to per-company settings. Rename the connector and app.
2. **Keep each customer's data separate.** Audit every query for company/account scoping, add an "account" level that owns companies and users, and add automated tests that one account can never read another's data.
3. **Scale beyond one server process.** Today it runs a single worker with an in-memory report cache and background loops inside the web process. Move to a shared cache (e.g. Redis), a proper job queue for reminders, e-way bills and backups, and several workers.
4. **Self-serve onboarding.** Sign-up, 7-day trial, connect-your-Tally wizard, signed Windows installer for the connector, help videos.
5. **Plans and billing.**
   - Plans like Livekeeping's: read-only / create entries / compliance.
   - Charge for extra users and message credits (WhatsApp/SMS).
   - Razorpay subscriptions, with GST invoices for our own sales.
   - Plan limits enforced in the app.
6. **Message credits.** Track WhatsApp/SMS/e-way bill/e-invoice usage per account against what's paid for.
7. **Legal and trust.**
   - Privacy policy, terms, refund policy, and compliance with the Digital Personal Data Protection Act 2023.
   - A "not affiliated with Tally Solutions" disclaimer.
   - Security review; ISO 27001 later.
8. **Operations.** Monitoring and alerts, per-account backups, rate limits, support channel, status page, iOS App Store and Play Store listings.
9. **Positioning against Livekeeping.** Lead with what they don't have: field staff (attendance, routes, beat plans, check-ins), GST returns workspace, bank reconciliation, sales targets and watchlists.

---

## Decisions needed before each phase

| # | Decision | Needed by | Recommendation |
|---|---|---|---|
| D1 | WhatsApp: Meta API directly, or through a provider (Interakt / Wati / Gupshup)? | Phase 2 | A provider is quicker to set up (they handle verification and templates). Meta directly is cheaper long-term. For own use, start with a provider. |
| D2 | Email: which service and which sending domain? | Phase 2 | A transactional service on our own domain (e.g. `billing@ourdomain`) with SPF/DKIM. |
| D3 | SMS now or later? | Phase 2 | Later. DLT registration takes time, and WhatsApp + email cover most customers. |
| D4 | Real Razorpay payment links, or UPI links only? | Phase 2b | UPI only for now. It's free and already works. |
| D5 | Invoice layout: what must appear (logo, bank details, UPI QR, terms, signature)? | Phase 3 | All five, with 2 layouts to choose from. |
| D6 | Is e-invoicing mandatory for us (turnover ≥ ₹5 crore in any year)? | Phase 4 | Ask our CA. If not, e-way bill only in production; e-invoice stays in sandbox. |
| D7 | Which GSP? | Phase 4 | Get 2–3 quotes; pick on per-call price, sandbox quality and support. |
| D8 | Who are the makers and checkers? | Phase 5 | Field staff and accountant = makers; owner = checker. |

## Order and rough sizes

| Phase | What | Size | Blocked by |
|---|---|---|---|
| 1 | Make simulated features honest | S | nothing |
| 2 | Automatic reminders (WhatsApp + email) | L | D1, D2 (provider accounts) |
| 3 | Branded invoices and sharing | M | D5 |
| 4 | Real e-way bill (then e-invoice) | L | D6, D7 (GSP account) |
| 5 | Voucher entry extras, maker-checker, scheduled backups, reports, greetings, iOS | M–L | D8 |
| B | Selling | XL | Track A exit criteria |

Phases 2–4 need outside accounts, so start those sign-ups while Phase 1 is being built. Phase 3 can be built while waiting for Phase 2/4 approvals.
