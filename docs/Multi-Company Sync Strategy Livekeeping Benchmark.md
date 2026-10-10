# Multi-Company Sync Strategy: Livekeeping Benchmark

Oct 10, 2026 · @Akash Kansal

## Summary

MyTally is closer to multi-company than the brief assumes: the backend and web app already scope data by company and let a user switch. The work is in the sync agent, which follows one pinned company, and in the sync API, which infers the company from the signed-in user instead of from the request.

The recommended approach has four parts:

1. **Make the Tally company GUID the key on every agent call.** The agent names the company it is syncing; the backend refuses anything it cannot match to a company linked to that agent.
2. **One agent, many companies, one at a time.** The agent loops over every linked company that is open in Tally and runs each company's cycle to completion before starting the next. Tally's port never sees two of our requests at once.
3. **A per-company sync record.** One row per company holds last successful sync, last attempt, state and the agent that reported it. The switcher and header read "Last synced" from it.
4. **Isolation enforced in the database and in tests,** not only in query filters: company-scoped unique keys, a single scoping helper, and a cross-company test suite.

One finding needs attention before any new feature: the agent's outbound queue and its incremental watermark follow the agent user's *active* company, which the web switcher can change. Section 2 explains the failure and Phase 0 of the roadmap closes it.

## 1. Livekeeping benchmark

Livekeeping's public material confirms the model (one connector on the Tally PC, many companies, automatic sync) but does not show how its company switcher or last-synced display look. The video is a two-minute connector setup tutorial, and its transcript would not load, so I read its title, description and chapter list only. I did not see its screens.

| What Livekeeping does | Evidence | Source |
| --- | --- | --- |
| A desktop "Data Connector" is installed on the same computer as Tally | Setup step 1; video description warns to use "the exact same computer" | [site](https://www.livekeeping.com/), [video](https://www.youtube.com/watch?v=vxHrjts289E) |
| Connector sign-in is by mobile OTP, not a password | Chapter 00:29 "Secure Login via OTP" | [video](https://www.youtube.com/watch?v=vxHrjts289E) |
| The user picks which company to connect, then syncs it | Setup step 2 "Connect your accounting company & sync"; chapters 00:45 and 01:05 | [site](https://www.livekeeping.com/), [video](https://www.youtube.com/watch?v=vxHrjts289E) |
| Tally's port is a visible setup and troubleshooting step | Chapter 01:22 "Checking System & Port Settings" | [video](https://www.youtube.com/watch?v=vxHrjts289E) |
| Sync is automatic and covers multiple companies on every plan | "Auto Sync Companies" is listed in the base Growth plan | [site](https://www.livekeeping.com/) |
| Many companies sit under one login | A published customer review cites checking "unlimited companies" with a single click | [site](https://www.livekeeping.com/) |
| A backup is taken per company when it syncs, and each backup is logged | Data Backup feature text | [site](https://www.livekeeping.com/) |
| Pricing is per account with user add-ons, not per company | Pricing table | [site](https://www.livekeeping.com/) |

Three product lessons follow from this, and they shape the rest of the plan:

- **Linking a company is an explicit, one-time act in the connector.** The user chooses companies; the connector does not silently sync whatever happens to be open.
- **After linking, sync needs no attention.** "Auto Sync Companies" is a base-plan promise, so per-company freshness has to be visible without opening the desktop tool.
- **Company count is not a paywall.** Users expect to add every company they keep in Tally.

The switcher and last-synced designs in section 3 are therefore my recommendation, not a copy of Livekeeping's screens. If you want a true like-for-like, a 15-minute walk through their trial app with two companies linked would settle it.

## 2. Where MyTally stands today

The backend is already a shared-schema multi-tenant system and the web app already has a company switcher; the agent is single-company by design. This is from reading the working tree on `master`, not from running it.

| Layer | Already in place | Gap |
| --- | --- | --- |
| Database | `company_id` foreign key on the master, voucher and sync tables; `companies.tally_guid`; `user_company_access` grants | `tally_guid` is indexed but not unique, per company or globally. Several child tables carry a `guid` and no `company_id`. No per-company sync-state record. |
| Auth | `X-Company-ID` re-targets one request and is checked against the user's allowed set; `POST /auth/me/active-company` persists the choice | The persisted choice is account-wide, so it also moves every other session of that user, including the agent. |
| Sync API | Inbound import resolves the company by GUID first, then by name, and refuses unknown companies for non-admins | `/sync/outbound-queue`, `/sync/acknowledge`, `/sync/voucher-identities` and `/sync/last-alter-id` take the company from `user.company_id`. Inbound falls back to name, then to the user's first company. |
| Agent | Pins one company by GUID, survives a rename, pauses when that company is closed, lists open companies with GUIDs | One `company_name` / `company_guid` in config. Retry floors are keyed by company name. No per-company loop. |
| Web app | Company sheet in `GlobalHeader`; `switchCompany()` in `AuthContext`; sync-health badge per company | No last-synced time anywhere. Health shows queue and error counts only. |
| Tally reach-back | Realtime push from the backend to Tally | `get_active_tally_sync_for_company()` returns one global `TALLY_URL` for every company. |

### The defect to fix first

The agent does not send `X-Company-ID`, so the backend serves it the queue and watermark of whatever company its user account currently has active. Switching company in the web app with the same account changes that.

Two things can then go wrong:

- **Wrong watermark.** `/sync/last-alter-id` returns company B's highest AlterID while the agent exports company A from Tally. If B's number is higher, A's changes below it are skipped without an error.
- **Wrong queue.** The agent receives B's pending pushes while pinned to A. Each payload names its own company in `SVCURRENTCOMPANY`, so it lands in B if B is open, by name and with no GUID check.

I have not reproduced either; both follow from the code paths in `backend/app/routers/sync.py` and `desktop-sync-agent/cloud_client.py`. A dedicated agent login that never uses the web app would avoid it, but the agent currently shares its login with a web user (confirmed 10 Oct 2026). The exposure is live, so Phase 0 ships before anything else. As a stopgap today, give the agent its own account with access to its one company only, and never switch company on that account.

## 3. UI/UX workflow

The user should always know three things without looking for them: which company they are in, how fresh its data is, and how to move to another. Every screen stays inside one company; there is no blended view across companies, now or later.

### Company switching

- **A persistent company chip in the header.** It shows the company name and a freshness dot. It is the only entry point to switching, on web and mobile, so the habit forms once.
- **A switcher sheet, not a dropdown.** Tapping the chip opens a searchable list (bottom sheet on mobile, popover on web). Each row shows name, GSTIN or city to tell look-alikes apart, financial year, and last synced. The existing `showCompanySheet` in `GlobalHeader` is the place to build this.
- **Switching is per device, not per account.** The chosen company is stored on the device and sent as `X-Company-ID` on every request. Choosing Company B on the phone must not move the laptop or the agent.
- **A hard reset on switch.** Clear every cached list, close open forms, and return to the dashboard. If a voucher form has unsaved input, ask before switching. The cheapest correct implementation is to key the app's data layer on `company_id` so nothing from the previous company can render.
- **Company identity on anything that writes.** Voucher forms, delete confirmations and share sheets repeat the company name. People with two similar companies make their mistakes here.
- **Deep links carry the company.** A notification for Company B opens B, after a one-line toast saying the company changed. `notifications.ts` already sends a company id; routes should carry it too.
- **A home for all companies.** A "My companies" page lists every linked company as a card with last synced, pending pushes and open issues. This is where linking, unlinking and access live.

### Last synced, per company

"Last synced" must mean one specific thing: the time the agent last completed a full cycle for that company with no errors. A heartbeat or a partial cycle does not move it.

| State | Rule | What the user sees |
| --- | --- | --- |
| Live | Last success under 5 minutes ago | Green dot, "Synced just now" or "Synced 3 min ago" |
| Syncing | A cycle is running | Spinner, "Syncing vouchers…" |
| Behind | Last success older than 15 minutes, agent online | Amber dot, "Synced 42 min ago" |
| Company closed | Agent online, company not open in Tally | Grey dot, "Open this company in Tally to sync. Last synced today 11:20" |
| Agent offline | No agent heartbeat for 3 minutes | Grey dot, "Sync agent offline since 10:05" |
| Needs attention | Last cycle ended with errors | Red dot, "3 items failed to sync" linking to the sync log |

The thresholds are starting values to tune against the agent's real intervals (5 seconds outbound, 60 seconds inbound today).

Show it in three places:

1. **Header chip:** the dot only, with the sentence on hover or tap.
2. **Switcher rows and company cards:** the full sentence for every company, so a stale company is visible before the user enters it.
3. **Reports and ledgers:** a quiet "Data as of 11:20" line when the state is anything but Live, because a balance read from stale books is the costly mistake.

Two details matter more than they look. Use relative time under an hour and clock time after it. And separate *data freshness* from *pending pushes*: "Synced 2 min ago · 4 entries waiting to reach Tally" is two facts, and merging them hides one.

## 4. Sync agent architecture

One agent process owns Tally's port and works through the linked companies one at a time, identifying each by GUID. Names are used only at the last step, because Tally's `SVCURRENTCOMPANY` accepts nothing else.

&#91;embedded content: agent sync cycle · 4 steps between Tally and the MyTally API\]

Steps 2 and 3 each finish one company before starting the next; a closed company is skipped for Tally work but still reported in step 4.

### Identify by GUID, address by name

- **GUID is the identity.** The agent stores a list of linked companies, each with its Tally GUID, the cloud `company_id` it maps to, the last name seen and its own retry floors. This replaces the single `company_name` / `company_guid` pair in `config.py`.
- **Name is resolved fresh each cycle.** One cheap request (`get_open_companies()`, which already returns name and GUID) opens every cycle. The agent maps each linked GUID to the name Tally shows right now, so renames keep working.
- **Every Tally request sets `SVCURRENTCOMPANY`.** A request without it goes to whichever company the operator has in front of them. The agent should refuse to send one, rather than patch it in as it does today.
- **Every cloud request names the company.** The agent sends the GUID in a header on queue, acknowledge, watermark and inbound calls. The backend maps it to a `company_id` and rejects a mismatch with a 409 instead of guessing.
- **Verify before writing.** Just before a push, the agent confirms the target name still maps to the expected GUID in this cycle's open-company list. If two open companies share a name, it pauses both and says so; it never picks one.
- **State is per GUID.** Watermarks, retry floors, last success and last error are held per company. A failure in Company A never moves Company B's floor. Tally's AlterID counters are per company, so a shared watermark is always wrong.

### Sequential, with a time budget

Process companies sequentially. Tally serves its HTTP port one request at a time and a large export stalls the Tally window for the person using it, so parallel requests only queue up inside Tally and time out. Sequential also keeps `SVCURRENTCOMPANY` reasoning simple: one company in flight, always.

Sequential does not mean one company can hold the others up:

1. **Pushes first, for every company.** Drain each company's outbound queue in a bounded batch before any export. A person is waiting on those; nobody is waiting on an export.
2. **Then incremental pulls, round-robin.** Each company gets one incremental export per cycle by its own AlterID watermark.
3. **A budget per company.** A first-time full sync is cut into voucher date ranges and resumes where it stopped. After its time slice the agent moves on and returns next cycle, so a new company with 5 years of vouchers does not freeze the others for an hour.
4. **Skip, don't stall.** A timeout or error marks that company and the loop continues. The existing pause-when-closed behaviour becomes a per-company state, not an agent-wide one.
5. **Parallelise the cloud side only.** Uploading Company A's export can overlap with exporting Company B, because the upload does not touch Tally. One Tally worker, one uploader.
6. **One lock on the port.** The GUI's "Test connection" and "Detect company" buttons go through the same lock as the sync loop.

Both standing rules for this project carry over unchanged. Every push and every import stays repeat-safe, with the company GUID inside the idempotency key. Deletes still confirm the target by content and address it by master id or stored REMOTEID, now inside a GUID-verified company.

## 5. Data isolation and security

Keep the shared schema with a `company_id` on every row, and make isolation something the database and the test suite enforce. Moving to a database or schema per company would mean rewriting a working system for a guarantee that constraints and tests can give at this scale.

| Model | Isolation | Cost here | Verdict |
| --- | --- | --- | --- |
| Shared tables, `company_id` column | Depends on every query filtering | Already built | Keep, and harden |
| Schema per company | Strong | Migrations run once per company; cross-schema keys to `companies` break | Not worth it now |
| Database per company | Strongest | Connection pools, backups and migrations per company | Only if a customer contract demands it |

### Hardening the shared model

1. **Company-scoped unique keys.** Add a unique constraint on (`company_id`, `tally_guid`) to every master and voucher table. Tally GUIDs are unique inside a company, not across MyTally, so a bare GUID lookup can match another company's row. The importer already filters by both; the constraint makes it a rule.
2. **A unique Tally GUID per account on `companies`.** Today a second company row can claim the same GUID. Linking should fail loudly when the GUID is already linked.
3. **`company_id` on every table.** The child tables that carry only a `guid` should gain a `company_id`, so no row's owner is known only through a join.
4. **One way to scope a query.** A single helper or session-level filter adds the `company_id` predicate, and a lint rule or test fails any tenant-table query that bypasses it. Hand-written `where company_id == user.company_id` in 30 routers is where a leak will eventually come from.
5. **Lookups by id always include the company.** `get(voucher_id)` alone is an IDOR; the pattern already used in `retry_voucher_push` (id and company together, 404 otherwise) should be universal.
6. **Caches and jobs keyed by company.** The in-memory cache already keys on `company_id`. Background workers, reminders, backups and push notifications need the same check: each job carries a `company_id` and loads nothing outside it.
7. **Composite indexes.** Lead the hot indexes with `company_id` so tenant filters stay fast as company count grows.

### Hosted for many customers: same-name companies

Decided 10 Oct 2026: shared tables stay, separated by company. Two customers with the same company name do not merge today, but a hosted service needs one more level, the customer account, before it is safe.

| Case | What happens today | What should happen |
| --- | --- | --- |
| Customer X and customer Y each have "Sharma Traders" | Two rows in `companies` with different `company_id`. Import matches a name only among companies that user is granted, so each sync lands in its own company. | Same, but matched by GUID inside the customer's account; name never decides. |
| One customer has two Tally companies with the same name | Import by name picks the older row, so the second company's data can land in the first. | Each is linked by its own GUID; the switcher tells them apart by GSTIN and financial year. |
| An Admin-role user at customer X | `accessible_company_ids()` and `/auth/me/companies` give the Admin role every active company on the server, including customer Y's. | Admin means admin of one account. Only a separate platform-operator role sees across accounts. |
| Two unrelated customers sync a company with the same GUID (a shared backup, an accountant's copy) | Not prevented. | Allowed, as two separate companies in two accounts; GUID is unique per account, not globally. |

The third row is the one that matters. There is no entity above a company today, so "Admin" is server-wide. That is fine for one business running its own server and wrong the day a second customer signs up.

The change:

1. Add an `accounts` table, one row per customer, and an `account_id` on `companies` and `users`.
2. Scope the Admin role to companies where `account_id` matches the user's. Registration creates an account with its first company.
3. Make (`account_id`, `tally_guid`) unique on `companies`. Company names stay free text and need no uniqueness.
4. Agent linking matches a GUID only inside the agent's account and never offers a company from another one.
5. Add customer X's admin requesting customer Y's company to the cross-company test suite.

Access rules, agreed 10 Oct 2026:

- **An admin sees only their own account's companies.** No role, including Admin, widens access beyond the account. The three places that grant server-wide access today are `accessible_company_ids()` in `core/permissions.py`, and `/auth/me/companies` and `/auth/me/active-company` in `routers/auth.py`.
- **One admin, many companies.** An account can hold any number of companies; the admin switches between them with the header switcher.
- **Companies are created only from the desktop sync agent.** Linking a Tally company in the agent is the single way a company comes into existence, so every company has a GUID and an owning account from its first moment. The web "new company" page and `POST /companies` are removed (confirmed 10 Oct 2026).
- **Staff access is granted inside the account.** An admin can give a user access to companies of their own account only; `user_company_access` rows are rejected when the user and the company belong to different accounts.
- **Every access check has two parts:** the company is in the caller's account, and the caller is the account's admin or has a grant for it. Failing either returns 404, so one admin cannot learn that another admin's company exists.
- **The platform operator is a separate role,** held by MyTally staff, audited, and never assigned to a customer.

Confirmed 10 Oct 2026: several customers will share one server to keep hosting cost down, so the accounts table is required, not optional.

### Agent trust

- **A device credential, not a user login.** The agent gets its own token, issued when a company is linked, bound to that device and to an explicit list of company ids. It cannot be used to browse the app, and the web switcher cannot affect it.
- **Explicit company on every sync call.** The server derives nothing from "current user". GUID in, `company_id` resolved, membership in the token's list checked, otherwise 403.
- **No name fallback on import.** Inbound data without a GUID that matches a linked company is rejected. The current fall-through to name, then to the user's first company, is convenient for first setup and unsafe after it.
- **Linking is the only way a company appears.** Auto-create on import stays off except inside the explicit link flow.
- **Revocation per company.** Unlinking removes that company from the token's list at once and is written to the audit log.

### Proving it

A two-company test fixture runs against every router: sign in with access to A only, request each endpoint with B's ids and with `X-Company-ID: B`, and require 403 or 404 every time. Run the same for the agent token. This suite is the acceptance gate for each roadmap phase.

## 6. Actionable roadmap

Five phases, each shippable on its own and each ending in a gate. Phases 0 and 1 change no user-facing behaviour; they make the later phases safe. I have not estimated durations.

### Phase 0: Make the company explicit

Closes the defect in section 2 with the current single-company agent.

| Component | Change | Where |
| --- | --- | --- |
| Agent | Send the pinned company's GUID as a header on every cloud call | `cloud_client.py` `_get_headers()`, `push_inbound_xml()` |
| Agent | Refuse to send any Tally request without `SVCURRENTCOMPANY`; drop payloads whose company is not the pinned one | `agent.py` outbound loop |
| Backend | A `sync_company` dependency resolves the GUID header to a `company_id` the caller may access; use it in place of `user.company_id` | `routers/sync.py`: `/outbound-queue`, `/acknowledge`, `/voucher-identities`, `/last-alter-id`, `/inbound` |
| Backend | Old agents without the header keep working for one release, with a logged warning | same |
| Frontend | Send `X-Company-ID` from one shared fetch wrapper on every request, not only in `GlobalHeader` and `notifications.ts` | `src/lib` API helper, `AuthContext.tsx` |

**Gate:** switching company in the web app while the agent runs changes nothing the agent receives.

Because several customers will share one server, Phase 0 also adds the `accounts` table and the account-scoped Admin role from section 5. It is an access fix, not a feature, and it must be live before a second customer is onboarded.

### Phase 1: Data model

| Component | Change | Where |
| --- | --- | --- |
| Backend | New `company_sync_state` table: `company_id`, `agent_device_id`, `state`, `last_success_at`, `last_attempt_at`, `last_error`, master and voucher watermarks, pending count | `models/portal_core.py`, migration |
| Backend | New `agent_devices` and `agent_company_links` tables: which device may sync which company | same |
| Backend | Unique (`company_id`, `tally_guid`) on master and voucher tables, after a script reports and resolves existing duplicates | `models/tally_core.py`, migration |
| Backend | Unique Tally GUID per account on `companies`; `company_id` added to GUID-only child tables | both model files |
| Backend | `POST /sync/state` for the agent to report; `GET /companies` returns each company with its sync state | `routers/sync.py`, `routers/companies.py` |

**Gate:** migrations run clean on a copy of production data; the duplicate report is empty.

### Phase 2: Multi-company agent

| Component | Change | Where |
| --- | --- | --- |
| Agent | Replace `company_name` / `company_guid` with a `companies` list; migrate the existing pin into it on first start | `config.py` |
| Agent | Key retry floors and watermarks by GUID, not name | `config.py`, `agent.py` `_update_inbound_retry_floor()` |
| Agent | Turn `check_and_handle_company_switch()` into a per-cycle resolver returning each linked company as open, closed or ambiguous | `agent.py` |
| Agent | Cycle becomes: discover, drain pushes for each open company, incremental pull for each, report state. One lock around all Tally calls | `agent.py` `run_daemon()`, `tally_client.py` |
| Agent | Chunk full sync by voucher date range with a resumable cursor and a per-company time slice | `tally_client.py` `export_full_collections()` |
| Agent | "Companies" screen: open companies from Tally with a Link / Unlink toggle and a per-company status line | `gui_app.py` |
| Backend | `POST /sync/companies/link`: create or match the company by GUID, grant the device, return `company_id` | `routers/sync.py` |

**Gate:** two companies open in Tally sync for a day with independent watermarks; closing one pauses only that one; a voucher pushed for A never appears in B.

Once agent linking is live, remove the web "new company" page (`frontend-nextjs/src/app/companies/new/`) and `POST /companies` in the same release, not before, so there is never a moment with no way to add a company.

### Phase 3: App experience

| Component | Change | Where |
| --- | --- | --- |
| Frontend | Header chip with freshness dot; switcher sheet with search and per-company last synced | `GlobalHeader.tsx` |
| Frontend | Active company stored per device; data layer keyed by `company_id`; unsaved-form guard on switch | `AuthContext.tsx` `switchCompany()` |
| Frontend | "My companies" page with a card per company | `src/app/companies/` |
| Frontend | "Data as of" line on reports and ledgers when not Live; company name on write and delete confirmations | `reports/`, `ledgers/`, `VoucherFormModal.tsx` |
| Backend | `/auth/me/active-company` becomes the default for a new device, not a live switch for all sessions | `routers/auth.py` |
| Backend | `/sync/health` adds `state`, `last_success_at`, `agent_online` from `company_sync_state` | `routers/sync.py` |

**Gate:** a tester with three companies can say which one they are in and how fresh it is from any screen, and switching never shows the previous company's data.

### Phase 4: Hardening

| Component | Change | Where |
| --- | --- | --- |
| Backend | Device token for the agent, scoped to its linked companies; user-login path for sync retired | `routers/auth.py`, `core/permissions.py` |
| Backend | Remove the name and first-company fallbacks from import | `services/tally_xml_importer.py` |
| Backend | Single scoping helper adopted across routers; cross-company test suite in CI | `core/`, `backend/tests/` |
| Backend | Per-company realtime push target replaces the global `TALLY_URL` | `get_active_tally_sync_for_company()` |
| Agent | Tests for two open companies, same-name companies, close mid-cycle, and timeout in one company | `desktop-sync-agent/tests/` |
| All | Alert when a linked company has not synced for a set time while its agent is online | notifications service |

**Gate:** the cross-company suite passes for user and agent tokens; an agent on the previous version is refused with a clear upgrade message.

## 7. Risks and open questions

| Risk | Effect | Mitigation |
| --- | --- | --- |
| A copied or restored company can carry the same GUID as its original | Two data sets merge into one cloud company | On link, record a second fingerprint (books-from date, company number) and pause on mismatch. Needs a test against a real restored copy. |
| A company must be open in Tally to sync | Companies the operator rarely opens go stale | The "Company closed" state says exactly this; do not try to open companies remotely in the first release. |
| Existing rows violate the new unique keys | Phase 1 migration fails | Run the duplicate report first; resolve by content, not by blind delete. |
| A full sync of a large company monopolises Tally | Operator's Tally freezes; other companies wait | Date-range chunks and time slices in Phase 2; schedule first sync outside working hours. |
| Old agents in the field | They keep using the implicit company | One release of compatibility with a warning, then refuse with an upgrade message. |
| Two PCs link the same company | Competing watermarks and double pushes | `agent_company_links` allows one active device per company; a second link asks to take over. |

Open questions:

- [x] Does Livekeeping's app show last synced per company in its switcher? Yes, as confirmed by you on 10 Oct 2026; the site and the video description do not show it. The per-row last synced in section 3 matches that behaviour.
- [x] Should one agent support Tally instances on several ports or PCs for one account, or is one PC per agent enough for the first release? Decided 10 Oct 2026: one agent per PC talking to one Tally port, and several PCs per account. Each company is synced by exactly one PC at a time. Store the Tally address on each company link so a second port on the same PC can be added later without a schema change.
- [x] Is a combined view across companies (group outstanding, consolidated cash) wanted later? No, decided 10 Oct 2026: every company's data stays separate, with no combined or consolidated view.
- [x] Does the mobile app share the Next.js front end's data layer, or does the per-device company setting need a separate implementation there? Answered from the code: the Android and iOS apps are the Next.js app wrapped with Capacitor, so the header chip and switcher sheet in section 3 serve mobile and web from one implementation. Switching only changes which company that device is viewing.

## Sources

- [Livekeeping website](https://www.livekeeping.com/), home page, read 10 Oct 2026
- [How to Set Up LiveKeeping Data Connector for Tally on mobile](https://www.youtube.com/watch?v=vxHrjts289E), title, description and chapters only
- MyTally working tree on `master`: `backend/app/routers/sync.py`, `backend/app/core/permissions.py`, `backend/app/services/tally_xml_importer.py`, `backend/app/models/`, `desktop-sync-agent/`, `frontend-nextjs/src/`
