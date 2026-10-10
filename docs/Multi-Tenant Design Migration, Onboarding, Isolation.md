# Multi-Tenant Design: Migration, Onboarding, Isolation

Oct 10, 2026 · @Akash Kansal

## Summary

The tenant is the **account**: one customer, created by one root admin signing up in the Desktop Sync Agent. Everything else hangs off it, and four rules carry the whole design.

1. **Every row has an owner chain.** Data belongs to a company, a company belongs to an account, a user belongs to an account. No row is reachable without passing through an account check.
2. **A company is identified by account plus Tally GUID, never by name.** Two customers can both sync "ABC Corp"; they are two rows with different ids, and no lookup crosses accounts.
3. **The agent creates accounts; the app creates people.** Sign-up exists only in the agent and always creates a new account with exactly one root admin. Every other user is invited from the web or mobile app into an existing account.
4. **Migration is expand, backfill, verify, then enforce.** Legacy rows get an account while the old behaviour still works, and constraints are switched on only after the verification queries come back clean.

This builds on Phase 0, which is implemented on the `phase0-explicit-sync-company` branch and not yet merged: the `accounts` table, `account_id` on companies and users, account-scoped Admin access, and the agent naming its company by GUID on every call. This document covers what comes after it.

## 1. Database schema

Keep the shared tables and add one level above the company. Isolation comes from two things the database enforces: every tenant row carries its owner's id, and every uniqueness rule is scoped by that id.

&#91;embedded content: ownership chain · account, users, companies, devices, data\]

Arrows run from owner to owned. The two join tables at the bottom corners each sit under two parents, and both parents must be in the same account.

### Tables

| Table | Status | Key columns | Constraints |
| --- | --- | --- | --- |
| `accounts` | Exists after Phase 0; extend | `account_id`, `name`, `owner_user_id`, `status`, `created_at` | `owner_user_id` unique and not null once backfilled: one root admin per account |
| `users` | Extend | `account_id`, `email`, `phone`, `email_verified_at`, `phone_verified_at`, `role_id`, `company_id` (last active) | `account_id` not null; `email` unique across the service; `phone` unique when present |
| `companies` | Extend | `account_id`, `tally_guid`, `name`, `tally_fingerprint` | `account_id` not null; unique (`account_id`, `tally_guid`); no uniqueness on `name` |
| `user_company_access` | Extend | `user_id`, `company_id` | Unique (`user_id`, `company_id`); user and company must share an account |
| `agent_devices` | New | `device_id`, `account_id`, `registered_by_user_id`, `machine_id`, `name`, `token_hash`, `last_seen_at`, `revoked_at` | Unique (`account_id`, `machine_id`); token stored hashed only |
| `agent_company_links` | New | `link_id`, `device_id`, `company_id`, `linked_at`, `unlinked_at` | One active link per company: a company is synced by one PC at a time |
| `company_sync_state` | New | `company_id`, `device_id`, `state`, `last_success_at`, `last_attempt_at`, `last_error`, master and voucher watermarks | One row per company |
| `user_invites` | New | `invite_id`, `account_id`, `email`, `phone`, `role_id`, `company_ids`, `token_hash`, `expires_at`, `accepted_at`, `invited_by_user_id` | Unique open invite per (`account_id`, `email`) |
| Tally data tables (ledgers, groups, stock items, vouchers and their children) | Extend | `company_id`, `tally_guid`, `tally_alter_id` | `company_id` not null on every table, including child tables; unique (`company_id`, `tally_guid`) |
| `sync_queue`, `sync_traffic_log`, `deleted_record_audit` | Keep | `company_id` | Already scoped by company |

### Rules the schema encodes

- **`account_id` is denormalised onto users and companies only.** Data tables carry `company_id`; the account is one join away and never copied further, so there is one place it can be wrong.
- **The root admin is a pointer, not a role name.** `accounts.owner_user_id` names exactly one user. Roles stay what they are today (permissions); ownership is separate, so a second "Admin" in the account is a normal invited user with wide permissions, not a second root.
- **Cross-account grants are impossible, not just unchecked.** On MySQL this is a composite foreign key: `user_company_access` carries `account_id`, and both (`user_id`, `account_id`) and (`company_id`, `account_id`) reference their parent tables. If that is too invasive, a service-level check plus a nightly audit query is the fallback.
- **Composite indexes lead with the tenant key.** (`company_id`, `tally_guid`), (`company_id`, `tally_alter_id`), (`account_id`, `tally_guid`). Tenant filters stay cheap as the service grows.
- **Deletion cascades downward only.** Closing an account soft-deletes it first (`status = closed`), and a separate, audited job removes its companies and data later.

## 2. Multi-tenancy and name collisions

A company name is a label and nothing more. The system finds a company by (`account_id`, `tally_guid`) and refers to it afterwards by `company_id`; the name is never part of a lookup, a key or a URL.

### User A and User B both sync "ABC Corp"

| Step | User A | User B |
| --- | --- | --- |
| Signs up in the agent | Account 101 created | Account 102 created |
| Links "ABC Corp" | Tally GUID `g-a1`; lookup (101, `g-a1`) finds nothing; company 5001 created in account 101 | Tally GUID `g-b7`; lookup (102, `g-b7`) finds nothing; company 5002 created in account 102 |
| Agent syncs | Sends `g-a1`; server resolves inside account 101 only, to 5001 | Sends `g-b7`; server resolves inside account 102 only, to 5002 |
| Opens the app | Sees one "ABC Corp", id 5001 | Sees one "ABC Corp", id 5002 |

The two never meet because the lookup starts from the caller's account. User B's token cannot name account 101, so there is no query in which the two companies are candidates together.

### The cases that look like collisions

| Case | Outcome |
| --- | --- |
| Same name, different accounts | Two companies. No interaction. |
| Same name, same account, different GUIDs (two real Tally companies) | Two companies. The switcher tells them apart by GSTIN, financial year and city. |
| Same GUID, same account, linked again | The existing company; linking is repeat-safe and returns the same `company_id`. |
| Same GUID, different accounts (an accountant's copy, a shared backup) | Two separate companies, one per account. Neither account can detect the other. |
| Same name, same account, GUID changed (company restored or re-created in Tally) | Not matched by name. The agent shows "this looks like a different company with the same name" and the admin chooses: link as new, or re-point the existing company after a fingerprint check. |
| Company renamed in Tally | Same GUID, so same company; the stored name updates on the next sync. |

### Why not make the Tally GUID globally unique

It is tempting, because it would make "one root admin per Tally company" a database constraint. I recommend against it for three reasons.

- **Copies share GUIDs.** A backup handed to an accountant or restored on another PC keeps the original GUID. A global rule would lock the second party out for something that is not their error.
- **It leaks existence.** "This company is already registered" tells a stranger that a specific business uses the service.
- **It invites squatting.** Whoever links a GUID first would own it, with no proof they own the business.

The one-root-admin rule is enforced where it can be proven: one owner per account, and one account per company row. Section 3 covers how that meets the requirement.

### Defence in depth

1. **Token scope.** A user token carries `account_id`; an agent device token carries `account_id` and its linked company ids. The server never reads an account or company id from a request body without checking it against the token.
2. **One scoping helper.** Every tenant query goes through one function that adds the `company_id` predicate and verifies the company's account. A test fails any router that queries a tenant table without it.
3. **Ids are not capabilities.** Fetching by id always includes the company; a wrong-tenant id returns 404, the same as a missing one.
4. **Scoped side channels.** Cache keys, background jobs, push notifications, backups and exports each carry a `company_id` and load nothing outside it.
5. **A cross-tenant test suite.** Two accounts, each with a company named "ABC Corp"; every endpoint is called with the other account's ids and must return 403 or 404. The Phase 0 tests are the start of this.

## 3. Agent-first admin onboarding

Sign-up lives in one place, the Desktop Sync Agent, and does one thing: create a new account with its root admin. The web and mobile apps have sign-in and "accept invite", and no sign-up.

### What sign-up captures

| Field | Required | Why |
| --- | --- | --- |
| Full name | Yes | Shown to invited users and on audit entries |
| Email | Yes (a username also works for sign-in) | Sign-in id; unique across the service |
| Mobile number | Yes, stored unverified for now | Recovery, and the usual identity for Indian SMEs |
| Password | Yes | Minimum length and breach check; stored hashed |
| Business name | Yes | Names the account; prefilled from the first Tally company |
| Acceptance of terms | Yes | Timestamp and version stored |
| Device name and machine id | Automatic | Registers this PC as an agent device |
| Tally serial number, GSTIN | Optional, read from Tally | Fingerprint for support and for the restored-company check |

### Sign-up flow

1. The agent starts with no stored credential and shows **Create account** and **Sign in**.
2. Create account posts name, email or username, phone and password to `POST /agent/signup`. No code is sent in the first release (see section 6).
3. The server runs one transaction: create the account, create the user with that account, set `accounts.owner_user_id`, register the device, issue a device token.
4. The agent stores the device token in the OS credential store and discards the password.
5. The agent lists the companies open in Tally. The admin ticks the ones to link; each becomes a company in the account by GUID.
6. First sync runs. The agent shows a QR code and link to the app, where the admin signs in with the same email and password.

The sign-up call is repeat-safe: sent twice from the same PC with the same details, it returns the same account and device, not a second one. OTP slots in later as a step between 2 and 3 without changing anything else.

### Enforcing "one root admin, everyone else through the app"

| Attempt | Result | Enforced by |
| --- | --- | --- |
| Sign up in the agent with a new email | New account, this user is its root admin | `/agent/signup` only ever creates an account; it has no "join" path |
| Sign up with an email or phone that already exists | Refused: "You already have an account. Sign in." | Unique `users.email`, unique `users.phone` |
| Second root admin for an account | Not possible | `accounts.owner_user_id` is a single unique column; no endpoint sets it after creation except ownership transfer |
| Employee tries to sign up in the agent to join their company | They get a separate, empty account, and cannot see the employer's data | Accounts are isolated; the sign-up screen says "Joining an existing business? Ask your admin for an invite." |
| Invited user signs in to the agent | Refused, unless the root admin has granted them "Manage sync agent" | Agent sign-in checks owner or that permission |
| Admin adds an employee | Invite created in the app; the employee sets a password from the invite link | `user_invites`; the user is created with the inviter's `account_id` |
| Anyone calls the old `/auth/register` | Removed | Endpoint deleted once agent sign-up ships |
| Admin creates a company in the web app | Removed | Companies come only from agent linking |

On the requirement's wording, "one root admin per company": a company row belongs to exactly one account and an account has exactly one owner, so every company has exactly one root admin. The rule holds per company without being a per-company table.

### Details worth deciding early

- **Ownership transfer.** The root admin can hand ownership to another user of the same account from the app, confirmed by their password. Without this, a departed owner strands the business.
- **Second PC.** The root admin signs in (not up) on another PC. That registers a second device in the same account, which can link other companies. A company already linked elsewhere asks "move sync to this PC?".
- **Lost PC.** Devices are listed in the app; revoking one invalidates its token at once and frees its companies to be linked elsewhere.
- **Recovery.** Password reset goes through a link sent to the account's email, from the app or the agent.
- **Invites.** Single use, expire after 7 days, bound to the invited email or phone, and carry the role and the companies the user will see.

## 4. Agent authentication and sync flow

The agent authenticates as a device, not as a person. A person proves who they are once, at sign-up or sign-in; after that the PC holds a device token that can sync its linked companies and do nothing else.

&#91;embedded content: agent authentication · 1 decision, 5 steps\]

The lower row happens once per PC. Sign-up creates the account and its root admin; sign-in adds this PC to an existing account.

### Every sync call

1. The agent sends the device token and the Tally company GUID it is working on.
2. The server loads the device by token hash and rejects a revoked or unknown one with 401.
3. It resolves the GUID inside the device's account to a `company_id`.
4. It checks an active `agent_company_links` row ties this device to that company. No link returns 403; an unknown GUID returns 409 "not linked".
5. The handler runs with that `company_id`. Nothing in the request body can change it.

### One cycle

1. **Discover.** Ask Tally for its open companies with name and GUID. One request.
2. **Match.** For each linked company: open, closed, or ambiguous (two open companies share its name).
3. **Push.** For each open company in turn, fetch its queue, verify each payload's GUID, address it to the name Tally shows now, send, read back, acknowledge. Repeat-safe by REMOTEID and master id, as today.
4. **Pull.** For each open company in turn, export changes above that company's own master and voucher watermarks, and upload them tagged with its GUID.
5. **Report.** Post state and last-success time for every linked company, closed ones included, to `company_sync_state`.

Companies are processed one at a time because Tally serves one request at a time. A slow or failing company is marked and skipped; it does not hold up the others.

### Endpoints

| Endpoint | Caller | Purpose |
| --- | --- | --- |
| `POST /agent/signup`, `/agent/signup/verify` (later, with OTP) | Agent, no token | Create account, root admin and device |
| `POST /agent/signin` | Agent, no token | Root admin registers this PC as a device of an existing account |
| `POST /agent/token/refresh` | Agent, device token | Rotate the device token |
| `GET /agent/companies` | Device | Companies of the account and which device each is linked to |
| `POST /agent/companies/link`, `/unlink` | Device | Link or unlink a Tally company by GUID |
| `GET /sync/outbound-queue`, `POST /sync/acknowledge`, `/voucher-identities`, `GET /sync/last-alter-id`, `POST /sync/inbound` | Device | Existing sync calls, now authorised by device and link |
| `POST /sync/state` | Device | Per-company state for the app's "Last synced" |

### Failure behaviour

| Situation | Agent does | User sees |
| --- | --- | --- |
| Device revoked | Stops, clears the token | "This PC was signed out by your admin. Sign in again." |
| Company unlinked in the app | Stops syncing that company only | "ABC Corp is no longer synced from this PC." |
| Company closed in Tally | Skips it, reports "closed" | App shows "Open this company in Tally to sync" |
| Two open companies share a linked name | Pauses both | "Two companies named ABC Corp are open. Close one." |
| Server unreachable | Keeps retrying with backoff; never writes to Tally without a fetched queue | "Cloud offline" |
| Tally timeout on a push | Looks the record up by REMOTEID before resending | Nothing, unless it keeps failing |

## 5. Data migration plan

Migrate in four stages, expand, backfill, verify, enforce, so that the application works at every point and each stage can be stopped or rolled back on its own. Legacy rows today have no account (NULL) and behave as one shared group; the goal is that no NULL remains and the shared-group rule is deleted.

### Stage A: Expand (no behaviour change)

1. **Back up** both databases and record row counts per table. Keep the backup until Stage D has run for two weeks.
2. **Deploy Phase 0.** It creates `accounts` and adds nullable `account_id` to `companies` and `users`. The startup schema sync adds these as plain columns, so add the foreign keys and indexes with an explicit script.
3. **Add the remaining nullable columns and new tables:** `accounts.owner_user_id`, `users.phone` and the verification timestamps, `companies.tally_fingerprint`, `company_id` on the child tables that lack it, and `agent_devices`, `agent_company_links`, `company_sync_state`, `user_invites`.

### Stage B: Backfill

4. **Inventory.** A read-only script reports every company (id, name, GUID, row counts), every user (role, home company, grants), companies with no GUID, and duplicate (`company_id`, `tally_guid`) rows per data table. Nothing is changed.
5. **Propose accounts.** Group companies and users into connected sets: a user and a company are connected when the user's home company is that company or a `user_company_access` row links them. Ignore the Admin role's implicit access to everything, or every legacy row collapses into one set. Each set is a proposed account.
6. **Review the proposal by hand.** This is the one step that needs a person: confirm each set is one real customer, split any that an over-broad grant merged, and name the root admin of each. Default owner: the earliest-created Admin user whose home company is in the set.
7. **Apply.** In one transaction per account: insert the account, set `account_id` on its companies and users, set `owner_user_id`. The script is repeat-safe: it skips rows that already carry the intended account and stops on any row that carries a different one.
8. **Remove cross-account grants.** Delete `user_company_access` rows whose user and company ended up in different accounts, after listing them in the review.
9. **Fill child `company_id`.** Set it from each child row's parent. Rows whose parent is missing are orphans: export them to a file, then delete.
10. **Resolve duplicates.** For each duplicate (`company_id`, `tally_guid`) group, compare content. Keep the row with the highest `tally_alter_id`, re-point children to it, and delete the others only after the comparison is logged. Never delete on GUID match alone.
11. **Link GUIDs.** Companies with no `tally_guid` get one on their agent's next full sync. Until then they are flagged "not linked" and excluded from the unique constraint by being NULL.
12. **Create devices and links.** For each agent that has synced recently, create an `agent_devices` row and a link to its company, so the upgrade to device tokens does not need every customer to re-link.

### Stage C: Verify

13. **Run the checks.** All must return zero rows:
    - companies or users with `account_id` NULL
    - accounts with no owner, or an owner belonging to another account
    - `user_company_access` rows crossing accounts
    - data rows with `company_id` NULL
    - duplicate (`company_id`, `tally_guid`) in any data table, or duplicate (`account_id`, `tally_guid`) in `companies`
14. **Compare counts** per company against the Stage A record. Only orphans and logged duplicates may differ.
15. **Run the cross-tenant test suite** against a restored copy of the migrated database.

### Stage D: Enforce

16. **Add the constraints:** `account_id` not null, the unique keys from section 1, the foreign keys.
17. **Delete the shared-group rule.** Remove the "NULL matches NULL" branch in `same_account_as_user()`. From here an Admin with no account sees nothing, which is the safe failure.
18. **Switch agents to device tokens.** Ship the agent with sign-in; for one release accept both the old user login (with the Phase 0 GUID header) and device tokens, then refuse the old login with an upgrade message.
19. **Remove the old entry points:** `/auth/register`, `POST /companies` and the web "new company" page.
20. **Watch for two weeks.** Alert on any 409 "not linked", any refused cross-account request, and any company whose last sync is older than a day while its agent is online.

### Rollback

| Stage | How to undo |
| --- | --- |
| A | Nothing to undo: nullable columns and empty tables are ignored by the old code |
| B | Set `account_id` and `owner_user_id` back to NULL and empty the new tables. Steps 8 to 10 delete rows, so they restore from the exported files |
| D | Drop the constraints and restore the shared-group branch. Device tokens and user logins both work during the overlap release |

Production holds one company with several users today (confirmed 10 Oct 2026). Step 5 therefore yields one account, step 6 is naming its root admin, and step 8 should find no cross-account grants. The plan is the same; it is just short.

## 6. Open decisions

- [x] **How many customers are on the production server today?** Answered 10 Oct 2026: several users, all belonging to a single company. That is one customer, so the migration creates one account holding that company and all its users, and the only choice left in step 6 is which user becomes the root admin.
- [x] **Same Tally GUID in two accounts: allow or block?** Decided 10 Oct 2026: allow, as two separate, isolated companies, one per account (section 2). The GUID is unique inside an account, not across the service.
- [x] **Phone OTP provider and cost.** Decided 10 Oct 2026: launch with email or username and password, no OTP. I found no free SMS OTP service for production use in India, only trials. Twilio's trial sends to a handful of pre-verified numbers; Fast2SMS gives a small sign-up credit and needs DLT registration; Firebase reportedly allows about 10 free SMS a day on a billing account and has free fixed test numbers for development. Paid Indian providers run roughly ₹0.13 to ₹0.25 per OTP. These figures are from search summaries of third-party pages ([Authgear comparison](https://www.authgear.com/post/best-otp-service-providers/), [Fast2SMS](https://www.fast2sms.com/otp), [Twilio trial](https://www.twilio.com/docs/usage/trials)), not checked against each provider's own rate card. Build sign-up so a verification step can be added later behind one provider interface.
- [x] **Who may operate the agent besides the root admin?** Decided 10 Oct 2026: the root admin, plus any user the root admin grants a "Manage sync agent" permission. Nobody else can sign in to the agent.
- [x] **Platform operator access.** Support staff need a way to see an account when asked. Decided 10 Oct 2026: a separate operator role with time-limited, audited access granted per account, never a standing super-admin.
- [x] **Per-account limits.** Whether plans cap companies, users or devices. The schema supports any of these; none is enforced yet. Suggested: add `plan`, `max_users` and `max_devices` to `accounts`, check them when an invite is accepted or a PC signs in, and leave companies uncapped. That matches Livekeeping, which prices by plan and extra users, not by company. Decided 10 Oct 2026: keep every pricing option open (per user, per company, flat). So `accounts` also gets `max_companies`, checked when a company is linked, and each limit is empty by default, meaning unlimited. A flat plan leaves all three empty; pricing can change later without a schema change.
