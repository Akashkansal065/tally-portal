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

## Feature flags for paid or keyed providers

**Rule:** any feature that needs another company's API keys or a paid subscription sits behind an on/off flag. **Free features have no flag.**

**How the flags work:**
- Flags are per company, **off by default**, and only an admin can change them (Admin → Integrations).
- A flag that's off hides the feature everywhere, and the API refuses it with a message saying it's switched off.
- Turning a flag on doesn't make a feature work by itself. Each integration also shows whether the real connection is built yet and whether its keys are set.
- Keys are kept on the server only: never sent back to the browser, never in git or chat. Today the e-invoice GSP keys are columns on the company record; Phase 4 decides whether they move to the server's environment settings or become encrypted.

| Status shown | Meaning |
|---|---|
| Off | Hidden everywhere (default) |
| Demo | On, but the real connection isn't built yet. Any numbers it makes are labelled "DEMO – not valid" and never printed or sent to Tally |
| Not available yet | On, but there's no safe demo. The feature stays hidden until its phase is built |
| Needs setup | Real connection built, but keys are missing |
| Connected | Real connection built and keys present |

**Flagged** (needs keys or a paid subscription):

| Flag | Provider | Phase |
|---|---|---|
| `einvoice` (e-invoice: IRN + QR) | GSP (MasterGST) | Built (Phase 4): Demo or Live |
| `eway_bill` (e-way bill) | GSP (MasterGST) | Built (Phase 4): Demo or Live |
| `gst_portal` (fetch GSTR-2B with OTP) | GSP | 1 (hidden, no safe demo), later |
| `gst_filing` (submit a GST return through a GSP) | GSP | 1 (Demo), later |
| `payment_gateway` (Razorpay/Stripe payment links) | Razorpay / Stripe | 1 (hidden), 2b |
| `whatsapp_api` (automatic WhatsApp messages) | Meta / WhatsApp provider | 2 |
| `email` (sending email) | Email service or SMTP | 2 |
| `sms` (SMS) | SMS provider + DLT | 2 (optional) |

**Not flagged** (free): UPI payment links and QR codes, WhatsApp click-to-send (`wa.me`), PDFs and branding, phone share sheet, backups, all reports, greetings shared through `wa.me`, manual GSTR-2B upload, manually recorded IRN / e-way numbers.

---

# Track A: for our own business

## Phase 1: Make the simulated features honest ✅ Done 5 Oct 2026

**Why first:** a made-up IRN or e-way bill number on a real invoice is a GST compliance risk, and a customer tapping a payment link that leads nowhere hurts trust. No provider accounts are needed. **Size: S (1–2 days).**

- **Flag system:**
  - New table `company_integrations` (company, flag, on/off, who changed it, when) and a registry in `backend/app/services/integrations.py` listing each flag's label, provider, cost note, whether the real connection is built, and how to tell if its keys are set.
  - `GET /integrations` returns the status of every flag for the current company. `PUT /integrations/{key}` turns a flag on or off (admin only).
  - A `require_integration(key)` check guards every flagged API route.
  - New "Integrations" tab in Admin.
- **e-Invoice / e-Way bill (G1, G2), behind `einvoice` / `eway_bill`:**
  - Off by default: the e-invoice tab, voucher e-invoice panel and admin e-invoice settings are all hidden.
  - When on, only "Demo" is allowed: the backend rejects "sandbox" and "production" until Phase 4.
  - Demo IRNs and e-way numbers are labelled "DEMO – not valid" wherever they're shown.
  - A demo e-way number is only made when `eway_bill` is also on.
- **GSTR-2B portal fetch (G3), behind `gst_portal`:**
  - Today's "Verify OTP" deletes any saved GSTR-2B rows for the period and replaces them with copies of our own purchase vouchers, so reconciliation always "matches". It's removed, not demoed.
  - Both OTP routes now answer "not available yet" (and are refused while the flag is off). The OTP buttons are hidden.
  - The manual JSON upload stays, with no flag.
- **Payment links (G4):**
  - UPI link and QR stay, with no flag. The made-up `pay.mytally.in` address is removed, so "copy link" buttons become "copy UPI ID".
  - The card is renamed from "Tally 7.0 Connected Paylink" to "UPI payment QR", since it isn't connected to Tally.
  - Razorpay/Stripe link creation (`/gateways/...`) goes behind `payment_gateway` and answers "not available yet" until Phase 2b. No screen uses it today.
- **Small fix found on the way:** `GET /einvoice/metadata/{voucher_id}` doesn't check the voucher belongs to the user's company. Add that check.
- **Tests:**
  - Flags default off and the routes refuse.
  - Only admins can switch flags.
  - Demo works only in "mock" mode.
  - GSTR-2B rows are never touched by the OTP routes.
  - Payment links contain no dead address.
  - Metadata is company-scoped.
- **Done when:** nothing in the app shows a made-up compliance number or link as if it were real, and every keyed or paid feature has a flag that's off by default.

**What was built (5 Oct 2026):**
- Switches: `company_integrations` table, `backend/app/services/integrations.py`, `GET`/`PUT /integrations`, Admin → Integrations tab (replaces the old Admin → E-Invoices tab), and `useIntegrations()` in `frontend-nextjs/src/lib/integrations.ts` for screens.
- **Found while building, also fixed:**
  - GST return "Submit (Mock)" (`/gst/periods/{id}/submit`) quietly used a mock for "sandbox" too. It's now behind a new `gst_filing` switch, demo only, with results labelled demo.
  - The voucher screen never got the customer's GSTIN from the API, so its e-invoice panel always said "not required". The voucher API now returns `party_gstin`.
  - It also never got e-invoice details, so it now loads them from `/einvoice/metadata/{voucher_id}`.
  - Hand-recorded IRNs were saved as "mock"; they're now saved as "manual" and aren't labelled demo.
- **Removed:** the fake GSTR-2B OTP walkthrough and "live GST portal log" on the GST screen, the e-invoice "Configure" modal (only Demo is allowed until Phase 4), and the fake portal-log helper.
- **Checks:**
  - 8 new backend tests (94 pass in total).
  - TypeScript passes. The new files lint clean, and every edited screen has the same or fewer lint problems than before.
  - Clicked through on a throwaway demo: everything hidden with switches off; demo labels shown with them on; UPI QR has no dead link.
- **Real database (read-only check):** `company_integrations` was created and is empty, so every switch is off. Nothing simulated had been saved before this change.

## Phase 2: Automatic payment reminders (G5, G12) ✅ Built 5 Oct 2026, waiting on WhatsApp sign-up

Livekeeping's main selling point for collections. **Size: L (5–8 days), plus the WhatsApp sign-up.**

**Decided (5 Oct 2026):** WhatsApp through **Meta's WhatsApp Cloud API directly** (we sign up). Email through **a personal Gmail account** (SMTP with an app password, about 500 emails a day). SMS later.

**Found on real data (read-only, 5 Oct):**
- 90 customers owe money.
- **None has an email** in Tally or MyTally.
- 43 have a mobile number.
- So email reaches nobody until emails are added. The reminder screen lets us add a customer's email or WhatsApp number on the spot, saved to their MyTally profile (Tally isn't changed).

### Design

**Switches** (both need credentials, so both are flagged; the real connection is built in this phase):

| Switch | Provider | Keys (in `backend/.env` only) | Status when on |
|---|---|---|---|
| `email` | Gmail SMTP (`smtp.gmail.com:587`, STARTTLS) | `SMTP_USER` (the Gmail address), `SMTP_PASS` (a 16-character **app password**, which needs 2-Step Verification on that account). Optional `SMTP_FROM_NAME`, `EMAIL_DAILY_LIMIT` (default 450) | Connected / Needs setup |
| `whatsapp_api` | Meta WhatsApp Cloud API | `WHATSAPP_ACCESS_TOKEN` (permanent system-user token), `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE` (approved template name), `WHATSAPP_TEMPLATE_LANG` (default `en`), `WHATSAPP_APP_SECRET` and `WHATSAPP_VERIFY_TOKEN` (for delivery receipts), `WHATSAPP_API_VERSION` | Connected / Needs setup |

**Where reminders go:**
- **WhatsApp number:** the customer's MyTally profile WhatsApp number first, then the Tally ledger mobile, then the ledger phone. 10-digit numbers get the 91 prefix.
- **Email:** the MyTally profile email, then the Tally ledger email.

**The WhatsApp message template** (to be created in Meta's WhatsApp Manager, category *Utility*, language English, name `payment_reminder`). Meta only allows business-started messages from approved templates:

> Hello {{1}}, this is a reminder from {{2}}. Your outstanding balance is ₹{{3}}, of which ₹{{4}} is overdue. You can pay by UPI to {{5}}. Please ignore this if you have already paid. Thank you.

Parameters: {{1}} customer name · {{2}} our company name · {{3}} outstanding · {{4}} overdue · {{5}} UPI ID.

**The email:**
- Subject: "Payment reminder from {company}: ₹{outstanding} outstanding".
- Body (plain text and simple HTML): the amounts, a table of open bills (bill no, date, due date, amount, days overdue), and the UPI ID.
- Sent from the Gmail address, with the company name as the display name.

**New data:**
- `reminder_schedules`: one active schedule per customer. Fields: channels, frequency (once / daily / weekly on a weekday / monthly on a date), time of day (IST, 9 am–8 pm), "only while something is overdue" (default yes), next run, active, why it stopped (paid / stopped by user / no contact), who created it.
- `reminder_log`: every attempt. Fields: channel, recipient, amounts at the time, status (sent / delivered / read / failed / skipped / dry-run), provider message id, error, who sent it (for "send now").

**Worker:**
- Every 5 minutes (in the web process, like the attendance worker). It picks schedules that are due and recomputes that customer's balance with the shared receivables service.
- **Paid in full:** the schedule stops ("paid").
- **Nothing overdue** (and "only while overdue" is on): no message; the schedule moves to its next run.
- **Otherwise:** sends on each chosen channel whose switch is on and keys are set. A channel that's off or not set up is logged as skipped with the reason.
- **Rules:**
  - Quiet hours: nothing before 9 am or after 8 pm IST.
  - At most one reminder per customer per day per channel.
  - The email daily limit is respected: anything over it waits until tomorrow.
- **Dry run:** `REMINDERS_DRY_RUN=true` logs what would be sent without sending. Use it for the first days on real data.

**Delivery receipts:** Meta calls `POST /reminders/whatsapp/webhook`, which checks the signature with `WHATSAPP_APP_SECRET`, and the log moves to delivered / read / failed. A failed WhatsApp or email send notifies admins (new "Collections" notification category). Gmail SMTP gives no delivery receipts, so email is "sent", or "failed" if Gmail refuses it.

**API (`/reminders`, needs the payments permission):**
- `GET /channels`: each channel's switch status and today's email count.
- `GET /preview/{ledger_id}`: the exact email and WhatsApp text, plus where they'd go.
- `POST /send-now`: one customer, chosen channels.
- `GET`/`POST /schedules`: one customer or many at once.
- `PUT`/`DELETE /schedules/{id}`: pause, resume, change or stop.
- `GET /log`: history, per customer or all.
- `PUT /contact/{ledger_id}`: save email / WhatsApp number to the MyTally profile.

**Screens (Outstanding):**
- A "Reminders" sheet per customer, opened from the "Chase first" list and the customer rows. It has:
  - where it will go (with add/edit email and WhatsApp number)
  - channel choices (greyed out with the reason when a switch is off)
  - "Send now"
  - a schedule form
  - a preview
  - the reminder history
- Bulk: "Schedule reminders for everyone in this ageing bucket".
- A small "Automatic reminders" summary: active schedules, sent today, failures.

**Not in this phase:**
- Email ledger statements and invoices: moves to Phase 3, where the PDFs are branded and built.
- "On the due date" schedules: later.
- SMS: later.

**Done when:** a reminder set for a real overdue customer goes out on schedule by WhatsApp and email, the WhatsApp one shows "delivered", and the schedule stops by itself after the payment lands in Tally.

**Your setup steps:** see [Appendix A: Setup guide](#appendix-a-setup-guide), sections A1–A5.

**What was built (5 Oct 2026):**
- **Backend:**
  - `reminder_schedules` and `reminder_log` tables.
  - `app/services/messaging.py` (Gmail SMTP, Meta template sender, webhook signature check).
  - `app/services/reminders.py` (contacts, message content, sending rules, schedules, worker, delivery receipts).
  - `app/routers/reminders.py`.
  - `email` and `whatsapp_api` switches; "Collections" notification category for failed sends.
  - The worker starts with the backend and checks every 5 minutes.
- **Screens (Outstanding):**
  - "Automatic reminders" strip, with today's counts, History, and "Schedule a group".
  - "Auto" button on each customer row and in "Chase first", opening the customer's reminder sheet (send to / channels / send now / schedule / preview / history).
- **Checks:**
  - 7 new backend tests (101 pass in total).
  - TypeScript passes; new files lint clean; Outstanding page lint unchanged (16).
  - Clicked through on a throwaway demo with fake senders and dry run: add email, send now, schedule, group schedule, phone width.
- **Real database (read-only check):** the three new tables exist and are empty; every switch is off.
- **Still to prove on real data:** the "Done when" above, once Email is switched on (dry run first) and WhatsApp is approved by Meta.

- **Phase 2b (optional): real payment links.** Razorpay payment links API plus the existing webhook to mark bills paid. Only if UPI links aren't enough.

## Phase 3: Branded invoices and sharing (G6) ✅ Built 5 Oct 2026

**Size: M (3–4 days).** Free: no switch, except emailing a PDF, which uses the Phase 2 `email` switch.

**Found before starting (5 Oct 2026):**
- **The invoice PDF has the business hard-coded in the code** (`lib/pdf-generator.ts`): name, address, GSTIN, phone, email, the **bank account number and IFSC**, and "for Sneh Distributors". The repository is public, so these are visible to anyone, and every company in MyTally gets this one business's details on its invoices.
- **The buyer block is always empty:** the voucher API never sent the party's address, GSTIN, state or mobile, so invoices print the buyer's name only.
- **On the Android app, "Download PDF" doesn't open the share sheet:** it calls `doc.save()` instead of the existing `saveOrSharePdf()`.
- **Real company profile (read-only check):** address, state, pincode, mobile and email are filled. **GSTIN, PAN and the UPI ID are not**, and Tally hasn't synced a GSTIN either. So the GSTIN must be entered in Company profile, or tax invoices would print without it (see Appendix A7).

### Design

**Where invoice details come from:**
- **Company profile** (existing fields, edited via the company name → Company profile): name, address, state, pincode, phone, email, GSTIN, PAN, UPI ID.
- **New `company_branding` table** (one row per company, edited in **Admin → Invoice design**):
  - logo and signature images (stored in the database as small PNG/JPEG data, resized in the browser: logo up to 600 px wide, about 300 KB at most; signature about 150 KB at most)
  - bank account name, bank, account number, IFSC, branch
  - declaration / terms text (defaults to today's wording)
  - "Print UPI QR code on sales invoices" (on by default)
- `GET /branding` returns all of it for the user's current company; anyone signed in can read it, because every invoice PDF needs it. `PUT /branding` is admin only.

**Invoice PDF** (one layout: the current Tally-style "Tax Invoice", now branded):
- **Header:** logo at top left, with company name, address, GSTIN, state and code, contact and email next to it. Lines with nothing set are left out.
- **Buyer block:** filled from the party ledger (address, GSTIN, state and code, mobile), which the voucher API now returns.
- **Bottom block:**
  - On sales invoices with a UPI ID: a **UPI QR code for the invoice amount**, with "Scan to pay ₹X".
  - The bank details that are set.
  - The declaration.
  - "for {company}", with the signature image above "Authorised Signatory".
- **Missing details:** if the company GSTIN is missing, downloading warns, rather than silently printing a tax invoice without it.
- **Plan change:** one layout instead of 2–3. The Tally-style one matches what customers already get. A second layout can be added later if wanted.

**Sharing** (voucher page and ledger statement):
- **Share:** on Android, the native share sheet (WhatsApp, Drive, print). In mobile browsers, the Web Share API with the PDF file. Elsewhere it downloads.
- **Download:** downloads on the web; on Android it goes through the share sheet, so the file can be saved.
- **Email** (only when the `email` switch is Connected): a sheet with the address (the customer's email from Phase 2, editable), subject and message. `POST /reminders/email-document` sends the PDF through Gmail.
  - It's logged in the customer's reminder history and counts toward the daily Gmail limit.
  - It follows the switch, dry run and daily limit, but not sending hours or the once-a-day rule, because someone asked for it to go now.

**Also:**
- The ledger statement PDF gets the logo.
- The unused `components/InvoicePDF.tsx` is removed.

**Done when:** a real sales invoice PDF with the logo, the company's details from the database, the buyer's details and a UPI QR code for the bill amount can be shared to a customer's WhatsApp in two taps, and emailed when email is on.

**What was built (5 Oct 2026):**
- **Backend:**
  - `company_branding` table and `GET`/`PUT /branding` (`app/routers/branding.py`).
  - Voucher detail now returns `party_details` (cache key bumped to `voucher_detail_v2_`).
  - `POST /reminders/email-document`; PDF attachments in `messaging.send_email`.
- **Frontend:**
  - `lib/branding.ts` (branding fetch/cache, image shrinking, UPI link, QR as PNG from `qrcode.react` with no new package).
  - `lib/pdf-generator.ts` branded: no business details left in the code.
  - `sharePdf()` in `lib/capacitor-pdf.ts`; `components/EmailPdfSheet.tsx`.
  - **Admin → Invoice design** (`components/admin/InvoiceDesignPanel.tsx`, with a checklist and "Preview a sample invoice").
  - Share/Email on the voucher page and the ledger statement; statement logo.
  - The voucher action buttons now wrap on phones (Download was already cut off).
  - Unused `components/InvoicePDF.tsx` removed.
- **Checks:**
  - 4 new backend tests (105 pass in total).
  - TypeScript passes; new files lint clean; edited files no worse than before.
  - On a throwaway demo, rendered the real invoice and statement PDFs and checked them by eye: logo, company and buyer details, bank details, QR.
  - Decoded the invoice QR with macOS's QR detector: `upi://pay?pa=…&pn=…&am=11800.00&cu=INR&tn=Invoice S-101`.
  - PDFs are about 27 KB (images compressed).
  - Emailed an invoice through a fake sender, with the PDF attached.
- **Real database (read-only):** `company_branding` exists and is empty.
- **Before deploying, enter the company GSTIN, UPI ID and bank details** (Appendix A7). The bank account that used to be hard-coded no longer prints until it's entered in Invoice design.
- Noticed for Phase 4: the `vouchers` table already has Tally's own `irn`, `irn_ack_no`, `irn_qr_code`, `eway_bill_no` and `vehicle_no` fields, synced from Tally. Phase 4 can print these on invoices and write real numbers back there.

## Phase 4: Real e-Way bill and e-Invoice (G1, G2) ✅ Built 6 Oct 2026, waiting on MasterGST keys

**Size: L (6–10 days), plus GSP onboarding.**

- **Do we need it for ourselves?**
  - **e-Invoice** is mandatory only once aggregate turnover crosses ₹5 crore in any financial year. At our ₹20 lakh/month target (~₹2.4 crore/year) we're probably below that. **Confirm with our CA.**
  - **e-Way bill** is needed for most goods movements over ₹50,000, whatever the turnover (state rules vary; confirm with the CA).
  - So for our own use, build **e-way bill first**. Build e-invoice too, but it can stay in sandbox until we sell the product or cross ₹5 crore.
- **Decided (5 Oct 2026):** build **both** e-way bill and e-invoice, each behind its own switch (`eway_bill`, `einvoice`), and turn them on only when needed.
- **Provider research (5 Oct 2026, from providers' own pages; prices change, so confirm in the quote):**
  - **Direct from the government (free, but not for us now):**
    - e-Invoice API access straight from NIC's invoice portal is for taxpayers above ₹5 crore turnover (₹5–10 crore since Jan 2023, above ₹10 crore before that).
    - e-Way bill direct API access needs registering the server with the e-way bill system, testing in their pre-production system, and **IP whitelisting**. That means a fixed server address, which most cloud hosts don't give.
  - **IRIS IRP** (one of the government-authorised e-invoice portals) says its core e-invoice APIs are **free** after sandbox testing; extra services are paid per use. It's aimed at software providers, and e-way bills come via the e-invoice (IRN).
  - **GST Suvidha Providers (paid per call, no fixed server address needed):** Masters India, MasterGST, ClearTax, Adaequare, IRIS GSP, Cygnet and others.
    - **MasterGST** offers self sign-up with a **free sandbox**, both e-invoice and e-way bill APIs, and sells to small businesses.
    - One published price list (an accounting-software vendor's) shows **₹0.25 per IRN, ₹0.40 per IRN + e-way bill, ₹1.50 per full bundle**. Treat it as a ballpark.
  - **Warning:** the domain `taxprogsp.co.in` (listed as TaxPro GSP's site) now serves a gambling site. Don't use it or anything it links to.
  - **e-Invoicing below ₹5 crore:** some providers say businesses under the limit can switch it on voluntarily on the e-invoice portal. Confirm with the CA before relying on that (decision D6).
- **Recommendation:**
  - Ask **MasterGST** and **Masters India** (and optionally ClearTax) for quotes using the checklist in Appendix A8.
  - Meanwhile, sign up for the **free sandbox** of the front-runner. Phase 4 can be built and tested end to end against it at no cost.
  - The code talks to the provider through one adapter, so changing provider later only touches that adapter.

**Decided (6 Oct 2026):**
- Build it now against **MasterGST**, so nothing needs building later.
- Turnover today is under ₹2.5 crore, so e-invoicing isn't mandatory yet. It stays in Demo (or off) until it's needed; switching to Live is configuration only (Appendix A8).

**What was built (6 Oct 2026):**
- `app/services/gst_documents.py`:
  - Turns a sales voucher into the government's e-invoice request (INV-01 v1.1) and e-way bill request (NIC API v1.03).
  - Includes state codes, unit codes, and CGST/SGST vs IGST by state.
  - Round-off, other charges and discount are worked out from the party total.
  - Plain-language checks: company and buyer GSTIN, pincode, address, state; HSN on every item; vehicle number format; distance.
- `app/services/gsp.py`, the provider adapter:
  - Sign-in, with the token renewed once if it has expired.
  - Generate, cancel and get IRN; e-way bill from IRN; e-way bill directly; update vehicle (Part B); cancel e-way bill.
  - **All MasterGST-specific details are in this one file.** They follow MasterGST's public API conventions; its full API reference PDF is only available after sign-up. **Check them on the first sandbox run;** any mismatch is fixed in this file alone.
- `app/services/einvoicing.py`:
  - Saves live numbers to `einvoice_metadata` (environment `live`) and copies them onto the voucher's own IRN fields (`irn`, `irn_ack_no`, `irn_ack_date`, `irn_qr_code`, `irn_source = "MyTally"`), `eway_bill_no`, `vehicle_no` and `trn_eway_bills`. The Tally sync already reads these.
  - 24-hour cancel windows; an e-invoice can't be cancelled while its e-way bill is active.
  - An e-way bill is made from the IRN when there is one, otherwise directly (unregistered buyers are "URP").
  - Every action is audited.
- **Routes:**
  - `POST /gst/einvoice/{id}/generate` (Live or Demo)
  - `GET /gst/edocs/{id}`
  - `POST /gst/einvoice/{id}/cancel`
  - `POST /gst/ewaybill/{id}/generate`
  - `POST /gst/ewaybill/{id}/vehicle`
  - `POST /gst/ewaybill/{id}/cancel`
  - `GET`/`PUT /gst/einvoice/settings` (Demo/Live mode and portal API users; admin only; passwords never returned).
- **Screens:**
  - Voucher page "e-Invoice & e-Way bill" panel: what's missing, generate, vehicle update, cancel, Demo/Live badge.
  - The invoice PDF prints the live IRN, Ack no/date, e-invoice QR and e-way bill number; demo numbers are never printed.
  - Admin → Integrations "e-Invoice & e-way bill set-up" (checklist, mode, portal API users).
- **Checks:**
  - 7 new backend tests with a fake provider (112 pass in total).
  - TypeScript passes; new files lint clean; the voucher page has fewer lint problems than before.
  - Clicked through on a demo with a fake provider: IRN, then an e-way bill from it, both shown.
  - The invoice PDF was rendered and both QR codes decoded: the e-invoice signed QR, and UPI for ₹59,000.
- **Real database (read-only):** the new columns (`companies.eway_username/eway_password`, `einvoice_metadata.signed_qr/irn_status/ewb_status`…) were added on reload; nothing else changed.
- **Not automatic yet:** pushing the IRN / e-way bill into Tally. They're stored on the voucher record the sync uses, but the voucher isn't re-sent to Tally on its own. Test that with your Tally on the first live invoice.
- **Build:**
  1. Token/session handling.
  2. e-Way bill from a sales voucher (Part A from the voucher, Part B vehicle details); update vehicle; cancel within 24 hours; print the EWB number and its QR on the PDF.
  3. e-Invoice: IRN from a sales voucher using the government's INV-01 JSON schema; signed QR; ack number and date; cancel within 24 hours; e-way bill from the IRN.
  4. Write IRN / EWB numbers back to Tally through the sync agent so Tally's records match.
  5. Validation before sending (GSTINs, HSN codes, pincodes, state codes) with plain-language errors.
- **Testing:** everything in the GSP sandbox first, then one real e-way bill, checked on the government portal.
- **Not planned:** Livekeeping's "track the vehicle on a live map". It needs vehicle GPS/FASTag data we don't have.
- **Done when:** a real e-way bill is generated from the app, matches the government portal, and its number appears on the invoice and in Tally.

## Phase 5: Remaining parity items ✅ Built 6 Oct 2026

**Size: M–L (5–8 days).** All free: no switches, except emailing a backup, which uses the `email` switch.

**Found on real data (read-only, 6 Oct 2026):**
- 0 batches, 0 items with alternate units, 0 cost centres, 1 godown.
- No vouchers entered in MyTally yet; all come from Tally.
- 2 admins and 2 sales users.
- A half-built maker-checker exists: amount rules (`approval_rules`) hold a voucher back from Tally (status "optional") and create an `approval_requests` row. But there are **no screens or routes** to set rules, approve or reject, so held vouchers would be stuck.
- Backups read **directly from Tally** (`TALLY_URL`), so they only work where the backend can reach the Tally PC.

**Order** (most useful to us first; everything is still built, for selling later):

1. **Voucher approval (G8)**, finishing the existing maker-checker:
   - **Rules** (Admin → Approvals): voucher type (or all), "amount over ₹X" (0 = every voucher), and who approves (a role). Admins and the approving role are never held back.
   - **Held vouchers** stay out of Tally and show "Waiting for approval".
   - **Checkers** get an approval queue on the Vouchers page, with approve / reject and a note.
     - Approve: the voucher is confirmed and pushed to Tally the usual way.
     - Reject: it goes back to the maker as a draft with the note. Editing it re-checks the rules.
   - **Notifications:** checkers hear about new requests; the maker hears the decision ("Approvals" category, which can't be turned off).
2. **Customer greetings (G11):**
   - About 12 ready-made cards: Diwali, Holi, Eid, Christmas, New Year, Independence Day, Raksha Bandhan, birthday, anniversary, thank you, "we miss you", new stock.
   - Each is drawn in the browser with our logo, name, phone and address from Invoice design.
   - **Who:** inactive customers (no sale in 30 / 60 / 90 / 120 days, or a custom date) from the existing inactive-customers data, or any customer.
   - **How:** share the image through the phone's share sheet, or open WhatsApp with the message (wa.me can't attach images, so on a computer the image is downloaded to attach). Free, no switch.
3. **Reports (G10):**
   - **Cash & bank book:** each cash / bank ledger's opening, money in, money out and closing for the period, opening the ledger statement.
   - **Godown-wise and batch-wise stock.**
   - **Cost-centre report:** totals per cost centre.
   - **Share** on report PDFs, using the Phase 3 share sheet.
   - With our data, godown / batch / cost-centre show a single row or "none set up in Tally".
4. **Scheduled backups (G9):**
   - Admin → Backups: daily at a chosen time, keep the last N (default 7), and optionally email the backup file (Gmail switch; files over 20 MB are only mentioned in the email).
   - A worker in the backend runs it.
   - If Tally isn't reachable from the server, the run is skipped and admins are notified (new "System" notification category).
5. **Voucher entry extras (G7):**
   - **Batch picker:** only for items with batches.
   - **Alternate unit:** shows the conversion and lets you enter in either unit, only for items with one.
   - **Physical Stock voucher:** counted quantities per item and godown.
   - Hidden when not used, so nothing changes for us today.
6. **iOS (G13):** not now. There are no iPhone users; it's needed for selling (Track B).

**What was built (6 Oct 2026):**
- **Voucher approval:**
  - `app/services/approvals.py`, `app/routers/approvals.py`: rules; queue (`to_me` / `mine`); approve, which confirms the voucher, applies stock and pushes it to Tally as a new voucher; send back with a note; send again; notifications.
  - Screens: Admin → Approvals (rules); Vouchers page "Approvals" box (also opened from notifications via `/vouchers?tab=approvals`); voucher page banner.
  - The old inline rule check in `create_voucher` now uses the service. Admins and the approving role are never held.
- **Greetings:**
  - `GET /greetings/customers?days=` lists customers (Sundry Debtors tree) by days since their last sale, with the WhatsApp number.
  - `/greetings` page with 12 cards drawn in the browser (`lib/greetings.ts`, 1080×1350 PNG) with the Invoice design logo and details.
  - Sending shares the image through the share sheet. On a computer it downloads the card and opens WhatsApp with the text.
- **Reports:**
  - `app/routers/books.py`: cash & bank book, cost centres (Tally's allocations), stock by godown (movement in the period), stock by batch.
  - Reports → **Books & Stock** tab with "Share CSV".
  - Every existing report's CSV export now opens the share sheet on phones, and quote marks inside values are escaped properly.
- **Scheduled backups:**
  - `app/services/backup_schedule.py` (settings in `app_settings` under `backup_schedule`; no new table) with a worker every 10 minutes; `app/routers/backup_schedule.py`.
  - Daily time, keep the last N, email a copy, "Back up now".
  - Skips and notifies (new "System" category) when Tally isn't reachable or a company isn't open in Tally. Nothing is written while it's off.
- **Voucher entry:**
  - Under each item: batch picker (items with batches), godown choice (more than one godown), and the alternate-unit equivalent ("= 2 BOX (1 BOX = 12 PCS)").
  - Godown and batch are now sent with each item; before, the form tracked the godown but never sent it. The backend checks they belong to the company and the item.
  - The stock-item list now returns `alt_unit_id` / `alt_unit_conversion`.
- **Not built:** the **Physical Stock voucher**. The Tally push sends every inventory voucher in invoice format with sales/purchase ledger lines, which is wrong for Physical Stock. Getting it right needs testing against a real Tally, and nobody uses it today.
- **Existing bugs fixed along the way:**
  - Creating or changing a voucher from MyTally failed while building the response (cost-centre allocations weren't loaded), so the screen showed an error after saving.
  - The stock-item list never returned alternate units.
- **Checks:**
  - 9 new backend tests (119 pass in total).
  - TypeScript passes. New files lint clean; edited pages have the same or fewer lint problems than before.
  - Clicked through on a demo: approval queue → send back → banner → maker notified; greetings card (personalised, branded) and recipient list; cash & bank book; batch report; voucher-form batch / godown / alternate unit.
- **Real database:** no new tables in this phase.

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
| D1 | WhatsApp: Meta API directly, or through a provider (Interakt / Wati / Gupshup)? | Phase 2 | **Decided: Meta directly.** |
| D2 | Email: which service and which sending domain? | Phase 2 | **Decided: personal Gmail (SMTP + app password).** |
| D3 | SMS now or later? | Phase 2 | **Decided: later.** |
| D4 | Real Razorpay payment links, or UPI links only? | Phase 2b | UPI only for now. It's free and already works. |
| D5 | Invoice layout: what must appear (logo, bank details, UPI QR, terms, signature)? | Phase 3 | **All five, one Tally-style layout** (a second layout later if wanted). |
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

---

# Appendix A: Setup guide

Everything you need to do outside the code to switch features on, in order. Keys and passwords are put in the server's settings only. Never commit them to git or paste them in chat: the repository is public.

## A1. Where settings go, and restarting

- **On your computer (local backend):** the file `backend/.env`, one `NAME=value` per line.
- **On the deployed backend (the one the live app and the Android app use):** the same names, added as environment variables in your hosting provider's dashboard (or its `.env` file on the server).
- **After changing settings, restart the backend.** The local `uvicorn --reload` only reloads when Python files change, not `.env`, so stop and start it.
- **Switches:** a feature that needs keys also needs its switch on: **Admin → Integrations** in the app (admins only). The status next to each switch tells you what's missing:
  - Off: hidden everywhere.
  - Needs setup: the keys aren't set on the server yet.
  - Connected: working.
  - Demo: only a labelled demo is available.
  - Not available yet: the real connection isn't built yet.

## A2. Company details used in messages and invoices

1. In the app, tap the **company name** at the top, then **Company profile**, then **Edit Profile Details**.
2. Fill in:
   - address, state, pincode
   - phone, email
   - GSTIN, PAN
   - **Direct Merchant UPI ID / VPA** (for example `yourshop@okhdfcbank`)
3. Save.

**Why the UPI ID matters:**
- It's printed in email reminders.
- It's required for WhatsApp reminders: the message template includes it.
- It becomes the UPI QR code on invoices (Phase 3).

## A3. Email reminders through Gmail (free)

1. **Choose the Gmail account** that reminders come from (for example `yourshop.accounts@gmail.com`). Customers see this address and can reply to it.
2. **Turn on 2-Step Verification** for that account: [myaccount.google.com](https://myaccount.google.com) → **Security** → **2-Step Verification** → follow the steps.
3. **Create an app password:**
   1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (or search "App passwords" in your Google Account).
   2. Name it `MyTally` and click **Create**.
   3. Google shows a 16-letter password once. Copy it **without spaces**.
   - If you later change the Google password, Google cancels app passwords; create a new one.
4. **Add to the settings (A1):**
   ```
   SMTP_USER=yourshop.accounts@gmail.com
   SMTP_PASS=abcdefghijklmnop
   SMTP_FROM_NAME=Your Company Name        # optional; defaults to the company name
   EMAIL_DAILY_LIMIT=450                   # optional; personal Gmail allows about 500 a day
   REMINDERS_DRY_RUN=true                  # first few days: log reminders without sending
   ```
   (`SMTP_USER` / `SMTP_PASS` are already in `backend/.env`. Check they're this account and that the password is an **app password**.)
5. **Restart the backend**, then turn on **Email (Gmail)** in Admin → Integrations. It should show **Connected**.
6. **Add customer emails:**
   - None of the customers who owe money has an email yet.
   - On **Outstanding**, tap **Auto** on a customer, then **Email → Add**.
   - It's saved in MyTally only; Tally isn't changed. Adding the email to the ledger in Tally also works: it syncs across.
7. **Try it in dry run:**
   1. Pick one customer and press **Send reminder now**. History shows **Dry run**.
   2. Open **Preview the message** to read exactly what will go out.
8. **Go live:**
   1. Remove `REMINDERS_DRY_RUN=true` (or set it to `false`) and restart.
   2. Send one real reminder to an address of your own first.
   3. Check it arrives (and not in spam).
   4. Then set schedules (A5).

## A4. WhatsApp reminders through Meta (paid per message)

Meta's own steps and screens change from time to time. If a screen looks different, the names below are what to look for.

1. **Business account and verification**
   1. Go to [business.facebook.com](https://business.facebook.com) and create a **business portfolio** for the company (or use the existing one).
   2. In **Business settings → Business info** (or **Security Centre**), start **Business verification**. You need the legal name, address and documents such as the GST certificate. It usually takes a few days.
2. **Create the app**
   1. Go to [developers.facebook.com](https://developers.facebook.com) → **My Apps** → **Create app**.
   2. Choose the use case **Connect with customers through WhatsApp** (type *Business*) and link the business portfolio.
3. **Add the phone number that sends reminders**
   1. In the app: **WhatsApp → API Setup → Add phone number**.
   2. Use a number that's **not** currently on the WhatsApp or WhatsApp Business app. To reuse one, delete its WhatsApp account on the phone first.
   3. Verify it by SMS or call.
   4. Set the **display name** (your company name). Meta reviews it.
   5. Copy the **Phone number ID** shown on API Setup.
4. **Add a payment method:** in **WhatsApp Manager → Payment settings**, add a card. Business-started messages (templates) are charged per message by Meta; utility messages in India cost little. Check Meta's current pricing page.
5. **Create a permanent access token** (the temporary one on API Setup expires in a day):
   1. **Business settings → Users → System users → Add**, with the role **Admin**.
   2. **Assign assets:** the app (full control) and the WhatsApp account (full control).
   3. **Generate new token:**
      - Choose the app.
      - Expiry: **Never**.
      - Permissions: `whatsapp_business_messaging` and `whatsapp_business_management`.
   4. Copy the token; Meta shows it once.
6. **Copy the app secret:** in the app, **App settings → Basic → App secret → Show**.
7. **Create the message template**
   1. **WhatsApp Manager → Message templates → Create template**.
   2. Set:
      - Category: **Utility**
      - Name: `payment_reminder`
      - Language: **English**
   3. Body (exactly, including the numbered placeholders):
      > Hello {{1}}, this is a reminder from {{2}}. Your outstanding balance is ₹{{3}}, of which ₹{{4}} is overdue. You can pay by UPI to {{5}}. Please ignore this if you have already paid. Thank you.
   4. Sample values for review: `Gupta Electricals`, `Your Company`, `70,800`, `47,200`, `yourshop@okhdfcbank`.
   5. Submit. Approval usually takes minutes to a day.
   - If you pick **English (US)** instead of **English**, set `WHATSAPP_TEMPLATE_LANG=en_US` below.
8. **Choose a verify token:** any random word you make up (for example `mytally-7f3k2`). It's used once, in the next step.
9. **Delivery receipts (webhook)**
   1. Needs the **deployed** backend on a public `https://` address; a backend only on your computer can't receive them.
   2. In the app: **WhatsApp → Configuration → Webhook → Edit**.
      - **Callback URL:** `https://<your deployed backend>/reminders/whatsapp/webhook`
      - **Verify token:** the word from step 8
   3. Click **Verify and save**. This only succeeds once step 10 is done and the backend has restarted.
   4. Under **Webhook fields**, **Subscribe** to `messages`.
   5. Switch the app to **Live** mode (top of the app dashboard) so real receipts are sent.
10. **Add to the settings (A1)**, on the deployed backend (and locally if you test there):
    ```
    WHATSAPP_ACCESS_TOKEN=<permanent token from step 5>
    WHATSAPP_PHONE_NUMBER_ID=<from step 3>
    WHATSAPP_TEMPLATE=payment_reminder
    WHATSAPP_TEMPLATE_LANG=en
    WHATSAPP_APP_SECRET=<from step 6>
    WHATSAPP_VERIFY_TOKEN=<your word from step 8>
    ```
    `WHATSAPP_API_VERSION` defaults to `v23.0`. Only change it if Meta retires that version.
11. **Restart**, then turn on **WhatsApp messages (automatic)** in Admin → Integrations (it should show **Connected**). Make sure the company UPI ID is set (A2).
12. **Try it:**
    1. Keep `REMINDERS_DRY_RUN=true` for a first look.
    2. Then go live and send one reminder to your own mobile.
    3. Its History entry should change from **Sent** to **Delivered** and **Read** within a minute or two; that proves the webhook works.
    4. If it says **Failed**, the reason shown comes from Meta. Common ones:
       - Template not approved yet.
       - Wrong language code.
       - Number not on WhatsApp.
       - No payment method.

## A5. Using reminders day to day

1. **One customer:** Outstanding → **Auto** on the customer:
   - choose channels
   - **Send reminder now**, or set **Automatic reminders** (once / daily / weekly / monthly, at a time between 09:00 and 20:00)
   - **Start automatic reminders**
2. **Many customers:** Outstanding → **Schedule a group** → pick *Anyone overdue* or an ageing bucket → channels and timing → **Start automatic reminders**. A customer's existing schedule is replaced.
3. **Rules the app follows:**
   - Nothing before 9 am or after 8 pm IST.
   - At most one reminder per customer per channel per day.
   - Gmail is held to the daily limit.
   - A schedule stops by itself once the customer has paid in full in Tally.
   - "Only while something is overdue" skips customers whose bills aren't due yet.
4. **Watching it:**
   - The **Automatic reminders** strip shows how many customers are on, and today's sent, dry-run and failed counts. **History** lists the last 100.
   - Failed sends appear in the bell under **Collections**, for the other admins.
5. **Stopping:**
   - **Auto** on the customer → **Stop**.
   - Or switch the channel off in Admin → Integrations. Everything on that channel pauses; schedules stay and resume when it's back on.

## A6. Features that aren't real yet

- **e-Invoice, e-Way bill, GST return submission:** the switches give a labelled **Demo** only. Real ones need a GST Suvidha Provider (Phase 4).
- **GSTR-2B fetch from the portal and card / net-banking payment links:** **Not available yet**. Use the GSTR-2B JSON upload and UPI links instead; both are free.

## A6b. Phase 5 features: where they are

- **Voucher approval:**
  - Admin → **Approvals**: add a rule (voucher type or all, "amount at or over ₹X" with 0 = every voucher, and the approving role).
  - Vouchers that sales staff enter in MyTally then wait on the Vouchers page under **Approvals** until someone in that role approves them, and only then go to Tally.
  - Sent-back vouchers show the reason. Fix the voucher with Alter / Edit, then press **Send again**.
- **Greetings:** More → **Greetings**.
  1. Pick a card and edit the message.
  2. Choose "No sale 60+ days" (or any filter).
  3. Press **Send** next to a customer.
  - On a phone this opens the share sheet. On a computer the card is downloaded and WhatsApp opens with the text; attach the card there.
  - Add your logo first (A7).
- **Reports:** Reports → **Books & Stock** (cash & bank book, cost centres, stock by godown, stock by batch). Every report's CSV can be shared from a phone.
- **Daily backup:**
  - **Backup** page → **Daily backup**: turn it on, set the time, choose how many to keep, and optionally an email address (needs Email (Gmail) on).
  - It works only on a server that can reach your Tally PC (`TALLY_URL`). Otherwise each run is skipped and admins get a "System" notification.
- **Voucher entry:** batch, godown and alternate-unit details appear under an item automatically when the item or company uses them.

## A7. Invoice design (logo, bank details, UPI QR)

Do this **before** deploying Phase 3. The company's details and bank account used to be written into the code; now they come from settings, so invoices print without them until they're entered.

1. **Company profile** (A2): make sure the **GSTIN** and **UPI ID** are filled in, along with the address, phone and email. Today the GSTIN and UPI ID are empty for your company. Without the GSTIN, tax invoices print without it, and downloading one shows a warning.
2. **Admin → Invoice design:**
   1. The checklist at the top shows what's still missing from Company profile.
   2. **Logo:** upload a PNG or JPEG. It's shrunk automatically and printed at the top left of invoices and the top right of statements.
   3. **Signature** (optional): a scan of the authorised signature on a white or transparent background, printed above "Authorised Signatory".
   4. **Bank details:** account holder's name (leave blank for the company name), bank name, account number, IFSC, branch.
   5. **Declaration / terms:** the text printed at the bottom left. It starts with the usual declaration.
   6. **Print a UPI QR code** (on by default): sales invoices get a QR code for the exact bill amount, paying your UPI ID.
   7. **Preview a sample invoice** to check, then **Save**.
3. **Using it:** on any voucher:
   - **Download PDF:** on the Android app this opens the share sheet, where you can save it.
   - **Share:** WhatsApp, email apps, Drive.
   - **Email:** shown when Email (Gmail) is on (A3). It sends the PDF to the customer's email.
   - The ledger statement has the same Share and Email buttons.

## A8. e-Way bill and e-Invoice provider (Phase 4)

Everything is built. Going live is configuration only. Turnover is under ₹2.5 crore today, so e-invoicing isn't mandatory; it becomes mandatory once aggregate turnover crosses ₹5 crore in any year. Until then keep the switches off, or on in **Demo** mode to try the screens.

**The keys MasterGST gives you, and where each goes:**

| What | Where you get it | Where it goes |
|---|---|---|
| Registered email | Your MasterGST sign-up email | Server setting `GSP_EMAIL` |
| Client ID | MasterGST dashboard → credentials | Server setting `GSP_CLIENT_ID` |
| Client secret | MasterGST dashboard → credentials | Server setting `GSP_CLIENT_SECRET` |
| Server IP (only if they ask) | Your backend host's public IP | Server setting `GSP_IP_ADDRESS` (default 127.0.0.1) |
| e-Invoice API username / password | Created on the e-invoice portal (or MasterGST's sandbox credentials) | Admin → Integrations → e-Invoice & e-way bill set-up |
| e-Way bill API username / password | Created on ewaybillgst.gov.in (or MasterGST's sandbox credentials) | Admin → Integrations → e-Invoice & e-way bill set-up |

`GSP_PROVIDER=mastergst` and `GSP_BASE_URL=https://api.mastergst.com` are the defaults; change them only if MasterGST gives a different sandbox address.

**Steps:**
1. **Sign up at mastergst.com.**
   1. In the dashboard, create e-invoice and e-way bill credentials.
   2. Ask sales@mastergst.com for **sandbox** credentials.
   3. Download their e-invoice and e-way bill API reference PDFs. The MasterGST details in `backend/app/services/gsp.py` should be checked against them on the first run.
2. **Make sure the company profile is complete** (A2): **GSTIN**, address, state, pincode. Every stock item needs an **HSN code** in Tally, and customers need a pincode and state. The voucher panel lists anything missing.
3. **Server settings** (A1): add `GSP_EMAIL`, `GSP_CLIENT_ID`, `GSP_CLIENT_SECRET` (sandbox values first), then restart the backend. Never put them in git or chat.
4. **Admin → Integrations:**
   1. Turn on **e-Invoice** and/or **e-Way bill**.
   2. In **e-Invoice & e-way bill set-up**, enter the sandbox API usernames and passwords, choose **Live** and save.
   3. The checklist should be all green, and the switches should show **Connected**.
5. **Try it in the sandbox:**
   1. Open a B2B sales voucher and press **Generate e-invoice (IRN)**.
   2. Then add a vehicle number and press **Generate e-way bill**.
   3. Download the PDF: it should show the IRN, Ack no, e-way bill number and e-invoice QR.
   4. Try **Cancel** too (within 24 hours).
   5. If anything is refused, the message from the portal is shown. Send it to me with MasterGST's PDF and I'll adjust the adapter.
6. **Going to production:**
   1. Create the production API users on the government portals:
      - e-Way bill: ewaybillgst.gov.in → **Registration → For API** → choose MasterGST.
      - e-Invoice: the e-invoice portal's API registration, choosing MasterGST.
   2. Replace the sandbox values with production ones (server settings + Admin → Integrations).
   3. Restart.
   4. Turn on e-invoicing on the e-invoice portal if it isn't already enabled for your GSTIN.
7. **Day to day:** voucher → **e-Invoice & e-Way bill** panel.
   - **Generate**, then use **Update vehicle** if the truck changes.
   - **Cancel** within 24 hours if needed: cancel the e-way bill before the e-invoice. After 24 hours, issue a credit note instead.
   - The invoice PDF prints everything.
