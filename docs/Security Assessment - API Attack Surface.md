# MyTally Backend: Security Assessment

**Target:** FastAPI service at `http://localhost:8000` (`backend/app`, `backend/backup_module`)
**Method:** source audit of all 415 routes (an automated scan of every id-taking and admin-only handler, then manual review of each flagged one), plus harmless live checks on localhost. Nothing was written, deleted or sent to Tally.
**Date:** 2026-10-10 · **Last updated:** 2026-10-10 (C1–C3 and M1–M5 fixed)

---

## Status at a glance

| ID | Finding | Severity | Status |
|---|---|---|---|
| C1 | Cross-tenant backup access (list, download, delete, restore) | Critical | **Fixed** |
| C2 | Backup schedule hijack (backups emailed to the attacker) | Critical | **Fixed** |
| C3 | Cross-account role tampering via `/admin/permissions` | Critical | **Fixed** |
| H1 | Login rate limit bypassed with a spoofed `X-Forwarded-For` | High | Open (confirmed live) |
| H2 | Your Gmail used as a phishing relay; shared email quota exhausted | High | Open |
| M1 | IDOR on POS payment splits | Medium | **Fixed** |
| M2 | Revoked token works up to 5 min; 30-day tokens | Medium | **Fixed** (5 min → 30 s); token lifetime is your decision |
| M3 | Unbounded upload reads; parser errors leaked | Medium | **Fixed** |
| M4 | Any account's changes reach the server's direct Tally; `/sync/run-once` open to any admin | ~~Medium~~ **High** on this server | **Fixed** |
| M5 | Up to 50,000 rows per request | ~~Medium~~ not a finding | **Corrected**; setting aligned to 500 |
| L1 | Broad CORS origins with credentials | Low | Open |
| L2 | Signup reveals registered emails | Low | Open |
| L3 | Pincode→city table shared by every account | Low | Open |
| L4 | SQL built by string interpolation (not exploitable today) | Low | Open |
| L5 | API docs public; no production switch | Low | Open |

**Before deploying:** add `PLATFORM_ADMIN_EMAILS=` and `TALLY_URL_COMPANY_ID=` to `backend/.env` (see "Deployment steps" below). Without the first, nobody can use Backup & Restore. Without the second, only the server's first account uses the direct Tally.

---

## The root cause behind the worst findings

Since accounts arrived, **anyone can create an account** from the Desktop Sync Agent (`POST /agent/signup`: an email code is the only check), and the first user of every account gets the role **Admin**. `require_admin` only checks the role *name*:

```python
# app/routers/admin.py:143
if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
```

So "admin" now means **admin of your own account**. But several features still act on the **whole server** and are protected by nothing more than `require_admin`: the backup module, the backup schedule, the role-permission editor, and the pincode→city table. Each of those is open to a stranger who signs up. The C-level findings below are all this one pattern.

**Where this pattern stands now:** the backup module, the backup schedule, the role editor (C1–C3) and `/sync/run-once` (M4) are fixed. Two places still follow the same pattern and are open: the "email" integration switch (H2) and the pincode→city table (L3).

**Attack chain (no insider access needed):** sign up from the agent with any email you control and any made-up Tally GUID → you are Admin of a new, empty account → call the server-wide admin endpoints below.

---

## Findings

### C1. Cross-tenant backup access: list, download, delete and restore every customer's books

> **Status: Fixed (2026-10-10).**
> * **New setting** `PLATFORM_ADMIN_EMAILS` (`backend/app/core/config.py:62`): comma-separated emails of the people who run the server. Matching ignores case and surrounding spaces. Empty means nobody.
> * **New check** `require_platform_admin` / `is_platform_admin` (`backend/app/core/permissions.py:277-290`). It refuses with `403 "Only the people who run this server can do this."` and never looks at role names.
> * **Every `/backup/*` route** is now mounted with `Depends(require_platform_admin)` instead of `require_admin` (`backend/app/main.py:212-215`).
> * **Web app:** the backup page now shows the server's reason on a 403 instead of "Cannot reach backup service" (`frontend-nextjs/src/app/backup/page.tsx:149`).
> * **Tests** (`backend/tests/test_backup_auth.py`): an account Admin gets 403 on **every** backup route (taken from the OpenAPI schema, so new routes are covered automatically); a listed operator can list and download; an empty list lets nobody in. The old test that asserted "any admin can download" was replaced, because it asserted the hole.

* **Vulnerability:** Broken Access Control / IDOR (OWASP A01)
* **Severity:** Critical
* **Location (before the fix):** `backend/backup_module/router.py` (all routes); mounted in `backend/app/main.py` with only `Depends(require_admin)`
* **Description & Impact:** The backup module has no idea of accounts or companies. `GET /backup/list` returns every backup on the server; `GET /backup/{id}/download` streams the ZIP (a company's full Tally data); `DELETE /backup/{id}` deletes any backup; `POST /backup/restore` restores any backup **into Tally** under any `company_name` the caller picks; `GET /backup/tally/status` reveals `TALLY_URL` and the companies open in it. Any self-signed-up "admin" can steal every customer's books, wipe their backups, or write one customer's data into another's Tally. Live check: `GET /backup/list` → `401` without a token, which confirms the module is mounted and only needs a login.
* **Remediation (as implemented):** The backup module works on the server's own Tally, so it is a *server operator* feature, not an account feature:

```python
# app/core/config.py
PLATFORM_ADMIN_EMAILS: str = ""

# app/core/permissions.py
def is_platform_admin(user: User) -> bool:
    allowed = {email.strip().lower() for email in settings.PLATFORM_ADMIN_EMAILS.split(",") if email.strip()}
    return bool(user.email) and user.email.strip().lower() in allowed


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the people who run this server can do this.")
    return user

# app/main.py
from app.core.permissions import require_platform_admin
app.include_router(backup_router, prefix="/backup", tags=["Backup & Restore"],
                   dependencies=[Depends(require_platform_admin)])
```

  This is secure because access depends on an allow-list held in server config, which no API call can change, not on a role name every new account is given. It fails closed: an empty list means nobody gets in. The list is meant for a handful of operators, not for customer admins; see "Open design question" below.

---

### C2. Backup schedule hijack: the server emails every company's backup to the attacker

> **Status: Fixed (2026-10-10).**
> * `GET /backup-schedule`, `PUT /backup-schedule` and `POST /backup-schedule/run-now` now use `require_platform_admin` (`backend/app/routers/backup_schedule.py:14, 33, 38, 51`).
> * **Web app:** no change needed. The Daily backup card already hides itself when loading fails, so account admins simply don't see it.
> * **The scheduled run itself** (the background worker) is unaffected and keeps using the saved settings.
> * **Test** (`backend/tests/test_backup_schedule.py:90`): an account Admin who is not an operator gets 403 on view, save (with `email_to` set to an outside address) and run-now; no backup is started, and the saved `email_to` stays empty. The operator's existing schedule tests still pass.
> * **Not done (defence in depth):** refusing an `email_to` that isn't a platform admin's address. See "What is still left".

* **Vulnerability:** Broken Access Control on a global setting → data exfiltration (OWASP A01)
* **Severity:** Critical
* **Location (before the fix):** `backend/app/routers/backup_schedule.py:30-60` (`GET/PUT /backup-schedule`, `POST /backup-schedule/run-now`); `backend/app/services/backup_schedule.py:25` (`KEY = "backup_schedule"`, one row for the whole server)
* **Description & Impact:** There is one schedule for the server. Any account admin can `PUT` it with `email_to` set to their own address and then call `run-now`. The server backs up **every active company** open in Tally and emails each ZIP to the attacker (for companies with the email switch on). Setting `keep: 1` also prunes everyone's older backups.
* **Remediation (as implemented):** Same check as C1 on all three routes:

```python
@router.get("")
async def get_schedule(user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)): ...

@router.put("")
async def save_schedule(req: ScheduleIn, user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)): ...

@router.post("/run-now")
async def run_now(user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)): ...
```

  This is secure because only the server operator can now set where backups go.

---

### C3. Cross-account role tampering through `POST /admin/permissions`

> **Status: Fixed (2026-10-10).** Does not depend on `PLATFORM_ADMIN_EMAILS`.
> * `POST /admin/permissions` (`backend/app/routers/admin.py:818`): every `role_id` in the request must be one of the caller's account's roles (`role_in_account`). If **any** is not, the answer is `404 "Role not found."` and **nothing** is written: the whole request is all-or-nothing. A missing `role_id` gets `400` (it used to crash with a 500). Overrides are cleared only for users of the caller's account.
> * `GET /admin/permissions` (`admin.py:807`) returns only the caller's account's roles.
> * `GET /admin/users/{user_id}/permissions` (`admin.py:996`) gives 404 for a user outside the admin's company, using the existing `_company_user` helper.
> * **Web app:** no change needed. The Roles screen only sends the role selected on screen, which is always one of the account's own.
> * **Tests** (`backend/tests/test_account_isolation.py:223-266`): another account's role is refused, including when it's mixed into a request with your own roles (nothing at all is written); your own roles can still be changed; a missing role is refused; the listings show only your own account.

* **Vulnerability:** Broken Access Control / IDOR on authorization data (OWASP A01)
* **Severity:** Critical
* **Location (before the fix):** `backend/app/routers/admin.py` (`update_permissions`, `get_permissions`, `get_user_permissions`)
* **Description & Impact:** `update_permissions` writes `Permission` rows for whatever `role_id` the body names, with no check that the role belongs to the caller's account. It also deletes `UserPermissionOverride` rows for every user holding those roles. A stranger can:
  * strip every permission from your Admin/Sales roles, locking your business out (denial of service);
  * give a low-level salesperson role in your account full create/update/delete on vouchers or ledgers (privilege escalation for an insider);
  * send `role_id: null` to create permission rows that belong to no role.

  Role ids are small sequential integers, so they are easy to guess. Both `GET` routes leak other accounts' rows too: `GET /admin/permissions` returns every account's permission rows, and `GET /admin/users/{id}/permissions` returns any user's overrides.
* **Remediation (as implemented; the code in `admin.py` matches this):**

```python
@router.get("/permissions", response_model=List[PermissionItem])
async def get_permissions(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    query = await db.execute(
        select(Permission).join(Role, Role.role_id == Permission.role_id).where(role_in_account(admin.account_id)))
    return query.scalars().all()


@router.post("/permissions")
async def update_permissions(payload: List[PermissionUpdateItem], db: AsyncSession = Depends(get_db),
                             admin: User = Depends(require_admin)):
    wanted = {item.role_id for item in payload}
    if None in wanted:
        raise HTTPException(status_code=400, detail="Every permission must name a role.")
    own = set((await db.execute(
        select(Role.role_id).where(Role.role_id.in_(wanted), role_in_account(admin.account_id)))).scalars().all())
    if own != wanted:
        # Another account's role and a role that does not exist get the same answer
        raise HTTPException(status_code=404, detail="Role not found.")
    ...  # existing loop unchanged
    # and when clearing overrides, limit the users to this account too:
    user_ids_q = await db.execute(select(User.user_id).where(
        User.role_id.in_(role_ids),
        User.account_id.is_(None) if admin.account_id is None else User.account_id == admin.account_id))


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    target = await _company_user(db, admin, user_id)   # 404 for a user outside the admin's company
    query = await db.execute(select(UserPermissionOverride).where(UserPermissionOverride.user_id == target.user_id))
    return query.scalars().all()
```

  This is secure because every role id is checked against the caller's account before anything is written. The 404 doesn't reveal whether the role exists elsewhere, and `role_in_account` is the helper `team.py` already uses for invitations.

---

### H1. Login brute-force protection bypassed with a spoofed `X-Forwarded-For` (confirmed live)

* **Vulnerability:** Security Misconfiguration → Identification & Authentication Failures (OWASP A05/A07)
* **Severity:** High
* **Location:** `backend/app/core/rate_limiter.py:9` (`get_client_ip`)
* **Description & Impact:** The limiter's key is taken from `cf-connecting-ip`, `x-real-ip` or `x-forwarded-for`, whichever the client sends, with no check that the request came through your proxy. Live result on localhost with a made-up email:

  ```
  same IP:                      400 400 400 400 400 429 429
  rotating X-Forwarded-For:     400 400 400 400 400 400 400
  ```

  An attacker gets unlimited password guesses on `/auth/login`, `/auth/swagger-login` and `/agent/signin`, and unlimited signup-code emails (`/agent/signup`), which can also be used to spam.
* **Remediation:** Trust forwarding headers only from your own proxy:

```python
# app/core/config.py
TRUSTED_PROXY_CIDRS: str = "127.0.0.1/32,::1/128"   # add your load balancer / Cloudflare ranges in production

# app/core/rate_limiter.py
import ipaddress

_TRUSTED = [ipaddress.ip_network(c.strip()) for c in settings.TRUSTED_PROXY_CIDRS.split(",") if c.strip()]

def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client and request.client.host else "127.0.0.1"
    try:
        from_proxy = any(ipaddress.ip_address(peer) in net for net in _TRUSTED)
    except ValueError:
        from_proxy = False
    if not from_proxy:
        return peer                      # a direct caller cannot choose its own key
    for header in ("cf-connecting-ip", "x-real-ip"):
        if request.headers.get(header):
            return request.headers[header].strip()
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[-1].strip() if forwarded else peer   # the hop your proxy appended, not the client's
```

  This is secure because a client that isn't your proxy can no longer pick its own rate-limit key. Also add a per-account lockout (for example, 10 failures per email in 15 minutes), so guessing is limited even across many real IPs.

---

### H2. Your Gmail used as an open phishing relay, and the server-wide email quota exhausted

* **Vulnerability:** Business Logic Flaw / Insecure Design (OWASP A04)
* **Severity:** High
* **Location:** `backend/app/routers/reminders.py:288` (`POST /reminders/email-document`), `backend/app/services/reminders.py:232` (`emails_sent_today`), `backend/app/routers/integrations.py:39` (switch gated only by `require_admin`)
* **Description & Impact:** The Gmail account (`SMTP_USER`) is the server's, shared by everyone. A stranger who signs up is Admin of their own company, turns on its "email" switch, and calls `email-document` with any `to`, any `subject`, any `message` and any PDF. The server sends it from **your** Gmail: ready-made phishing that carries your reputation. The daily limit (450) is also counted across **every company**, so the same attacker can use it up and stop all your real customers' payment reminders.
* **Remediation:** Send only to an address on that customer's ledger, and count the quota per company:

```python
# app/services/reminders.py, inside email_document()
ledger = (await db.execute(select(MstLedger).where(
    MstLedger.ledger_id == ledger_id, MstLedger.company_id == company.company_id))).scalars().first()
on_file = {messaging.clean_email(e) for e in ((ledger.email if ledger else None), (ledger.email_cc if ledger else None)) if e}
recipient = messaging.clean_email(to)
if not recipient or recipient not in on_file:
    raise HTTPException(status_code=422, detail="Documents can only be emailed to the customer's address on file.")

async def emails_sent_today(db: AsyncSession, now: datetime, company_id: Optional[int] = None) -> int:
    q = select(func.count(ReminderLog.id)).where(
        ReminderLog.channel == "email", ReminderLog.status == "sent", ReminderLog.created_at >= day_start(now))
    if company_id is not None:
        q = q.where(ReminderLog.company_id == company_id)
    return (await db.execute(q)).scalar() or 0
# check a per-company share (e.g. EMAIL_DAILY_LIMIT_PER_COMPANY = 50) as well as the server-wide limit
```

  This is secure because the recipient comes from data already in the books, not from the request, and one company can no longer use up everyone's quota. Also consider making the "email" integration a server-operator switch until each account brings its own sender.

---

### M1. IDOR: POS payment splits of any company's voucher

> **Status: Fixed (2026-10-10).**
> * `GET /pos/payments/{voucher_id}` (`backend/app/routers/advanced.py:433`) joins the voucher and requires `TrnVoucher.company_id == user.company_id`. Another company's voucher gets the same 404 as one that doesn't exist. Creating POS splits was already scoped; only this read was open.
> * **Test:** `backend/tests/test_security_hardening.py:41`: your own voucher's splits → 200; another company's → 404.

* **Vulnerability:** Insecure Direct Object Reference (OWASP A01)
* **Severity:** Medium
* **Location:** `backend/app/routers/advanced.py:433` (`GET /pos/payments/{voucher_id}`)
* **Description & Impact:** The handler loads `PosPayment` by `voucher_id` alone. Voucher ids are sequential integers, so any user with `vouchers:read` in any account can step through ids and read other businesses' POS payment splits (cash/card/UPI amounts).
* **Remediation:**

```python
@router.get("/pos/payments/{voucher_id}", response_model=PosPaymentResponse)
async def get_pos_payment(voucher_id: int, user: User = Depends(require_permission("vouchers", "read")),
                          db: AsyncSession = Depends(get_db)):
    stmt = (select(PosPayment)
            .join(TrnVoucher, TrnVoucher.voucher_id == PosPayment.voucher_id)
            .where(PosPayment.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))
    pos = (await db.execute(stmt)).scalars().first()
    if not pos:
        raise HTTPException(status_code=404, detail="POS Payment splits not found.")
    return pos
```

  This is secure because the voucher must belong to the caller's company. Another company's voucher returns the same 404 as one that doesn't exist.

---

### M2. A revoked or stolen token keeps working for up to 5 minutes, and lasts 30 days

> **Status: Fixed for revocation (2026-10-10). Token lifetime left unchanged on purpose.**
> * `AUTH_CACHE_TTL_SECONDS` and `PERMISSIONS_CACHE_TTL_SECONDS` went from 300 to **30** (`backend/app/core/permissions.py:93-94`). A sign-out, deactivation or removed permission already took effect at once in the worker that made it. In other workers it now takes at most 30 seconds instead of 5 minutes, at the cost of one session lookup per signed-in device per 30 seconds.
> * **Not changed: the 30-day token lifetime.** Sessions **don't renew while in use**: the expiry is fixed at sign-in. A 7-day lifetime would sign every field user out every week. Shortening it safely first needs sliding renewal (a fresh token issued while the app is in use), which is a product decision. See "What is still left".
> * **Chosen over the snippet below:** re-reading `revoked_at` on every request would mean one database query on every call, including on screens that call the API many times a second. 30 seconds bounds the risk without that cost.

* **Vulnerability:** Identification & Authentication Failures (OWASP A07)
* **Severity:** Medium
* **Location:** `backend/app/core/permissions.py:91` (`AUTH_CACHE_TTL_SECONDS = 300`), `:192` (cache hit skips the DB session check); `backend/app/core/config.py:9` (`ACCESS_TOKEN_EXPIRE_MINUTES = 43200`)
* **Description & Impact:** On a cache hit, `revoked_at` isn't re-read. Revocation only takes effect when the revoking code also clears the cache (`forget_tokens`) **in the same worker process**. With several uvicorn workers, a "sign out this device" handled by one worker leaves the token valid in the others for up to 5 minutes. Tokens otherwise live 30 days.
* **Remediation:** Keep the cache, but make revocation visible to every worker cheaply, using a revocation counter that is checked on each hit:

```python
# on a cache hit, re-check only the session row's revoked flag (one indexed primary-key read):
revoked = (await db.execute(select(UserSession.revoked_at)
                            .where(UserSession.session_id == cached_entry["session_id"]))).scalar()
if revoked is not None:
    _auth_cache.pop(token_hash, None)
    raise HTTPException(status_code=401, detail="Session expired or revoked",
                        headers={"WWW-Authenticate": "Bearer", "X-Auth-Reason": "admin_revoke"})
```

  Also lower `ACCESS_TOKEN_EXPIRE_MINUTES` (for example, 7 days with sliding renewal). This is secure because a revoked session is refused on its very next request, in every worker.

---

### M3. Unbounded upload reads (memory DoS) and leaked parser errors

> **Status: Fixed (2026-10-10).**
> * **Bank statements** (`backend/app/routers/bank_recon.py`):
>   * Uploads are read up to 10 MB (`MAX_STATEMENT_BYTES`, line 26); larger ones get 413.
>   * An Excel file's **unpacked** size is checked from its zip directory before it is opened (`_unpacked_size`, line 142): over 100 MB gets 413. This stops a "zip bomb" (a small `.xlsx` that unpacks to gigabytes), which an upload size cap alone does not.
>   * The Excel reader's own error goes to the log; the person sees a plain message.
> * **GSTR-2B** (`backend/app/routers/gst.py:797`): read up to 20 MB, else 413. Invalid JSON, and JSON that isn't an object (which used to crash with a 500), get a plain 400 instead of the parser's text.
> * **Tests:** `backend/tests/test_security_hardening.py:59-100` cover oversize statement, zip bomb, unreadable workbook, oversize GSTR-2B, and broken or non-object JSON.
> * **Still worth adding at the proxy:** a request-body limit (`client_max_body_size` in nginx), so oversized requests are refused before they reach Python.

* **Vulnerability:** Uncontrolled Resource Consumption / Information Exposure (OWASP A04/A05)
* **Severity:** Medium
* **Location:** `backend/app/routers/bank_recon.py:470` (`content_bytes = await file.read()`), `backend/app/routers/gst.py:797` (`contents = await file.read()`, and `detail=f"Failed to parse JSON file: {str(e)}"`)
* **Description & Impact:** Both read the entire upload into memory with no cap. A few large uploads (or an `.xlsx` zip bomb sent to the bank parser) can exhaust the server's memory. The GST error echoes the raw exception text back to the client.
* **Remediation:** Copy the pattern `reminders.py` already uses:

```python
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

content_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
if len(content_bytes) > MAX_UPLOAD_BYTES:
    raise HTTPException(status_code=413, detail="The file is larger than 10 MB.")

# gst.py
except Exception:
    logger.warning("GSTR-2B upload could not be parsed", exc_info=True)
    raise HTTPException(status_code=400, detail="That file is not a valid GSTR-2B JSON download.")
```

  Also set a request-body limit at the proxy (`client_max_body_size` in nginx). This is secure because memory use per request is bounded and internal error details stay in the server log.

---

### M4. The server's direct Tally reachable by any account (unpinned) or by a copied GUID

> **Status: Fixed (2026-10-10).** **Rated higher than first written:** on this server `TALLY_URL` is set and nothing pinned it to a company. Before the fix, any company, including one made by a stranger who just signed up, had its ledgers and vouchers pushed **straight into your Tally** as they were created.
> * **One company owns the direct Tally** (`backend/app/core/tally_target.py:62`, `_is_direct_company`), in this order:
>   1. `TALLY_URL_COMPANY_ID` (new, `backend/app/core/config.py:56`). An id can't be copied, so this is the recommended setting. A blank value counts as not set, so a copied `.env.example` line can't stop the server from starting.
>   2. `TALLY_URL_COMPANY_GUID`: now the **earliest** company with that GUID, so a later account that reuses the GUID never gets it.
>   3. Neither set: the server's **first** account plus companies from before accounts (until `ACCOUNTS_ENFORCED`). A later sign-up never gets it, and the backend log warns (at most once an hour) when a second account exists and nothing is pinned.
> * **No company recorded** (a background job outside a request): no direct Tally.
> * **The background sync run** (`backend/app/routers/sync.py:3909`) now checks the company of **each queued change** and skips other companies' changes; those wait for their own sync agent. Before, it sent every company the person could open to the one Tally. The same run is also started when a company profile is saved (`companies.py:258`), and that path is covered by this fix.
> * `POST /sync/run-once` (`sync.py:4519`) now requires `require_platform_admin`.
> * **Tests:** `backend/tests/test_account_isolation.py:177` (first account vs. later account, enforced accounts, GUID pin, a copied GUID, id pin), `:222` (no company recorded); `backend/tests/test_security_hardening.py:104` (`run-once` refused to an account admin) and `:115` (the sync run sends only the direct company's change; this test fails if the per-item check is removed).
> * **Your action:** set `TALLY_URL_COMPANY_ID` in `backend/.env` (see "Deployment steps").

* **Vulnerability:** Insecure Design (OWASP A04)
* **Severity:** High on this server (`TALLY_URL` set, nothing pinned); Medium where `TALLY_URL_COMPANY_GUID` was set (then it needs the victim's GUID)
* **Location:** `backend/app/core/tally_target.py:29` (`current_tally_url`), `backend/app/routers/agent.py:140` (GUIDs are unique only *per account*)
* **Description & Impact:** When `TALLY_URL_COMPANY_GUID` is set, a request may use the server's direct Tally whenever its company's `tally_guid` matches. A new account can register a company with the same GUID, and its requests then reach the server's Tally: direct pushes write into that customer's books, and `/sync/run-once` (any admin) pulls from it. With `TALLY_URL` set and `TALLY_URL_COMPANY_GUID` *unset*, **every** account's admin can trigger `/sync/run-once` against the server's Tally.
* **Remediation:** Pin the direct Tally to a company **id**, which can't be duplicated:

```python
# config.py
TALLY_URL_COMPANY_ID: Optional[int] = None

# tally_target.py
def current_tally_url() -> Optional[str]:
    url = settings.TALLY_URL
    if not url:
        return None
    only = settings.TALLY_URL_COMPANY_ID
    if only is None:
        return None                       # fail closed on a multi-account server
    return url if _request_company_id.get() == only else None
```

  Also gate `/sync/run-once` with `require_platform_admin`. This is secure because a database id belongs to exactly one company and can't be chosen at signup.

---

### M5. Results of up to 50,000 rows per request

> **Status: Corrected (2026-10-10): not a vulnerability.** The original finding was wrong. The `page_size` and `limit` parameters are already declared with `le=500` (`backend/app/core/pagination.py:20-22`), so a request asking for more is refused before `MAX_PAGE_SIZE` is consulted; 50,000 could never be reached. No route allows a large row limit of its own (the only parameters above 1,000 are day counts and a distance). What remains is by design: a list requested **without** paging parameters returns all of the caller's own company's rows, kept for older app versions.
> * **Changed anyway:** `MAX_PAGE_SIZE` is now 500 (`backend/app/core/config.py:117`), matching what the parameters enforce, so the setting no longer suggests 50,000.

* **Vulnerability:** Uncontrolled Resource Consumption (OWASP A04)
* **Severity:** ~~Medium~~ none (see status)
* **Location:** `backend/app/core/config.py` (`MAX_PAGE_SIZE`)
* **Description & Impact:** One authenticated request can make the server load and serialise 50k rows; a few in parallel slow the service for everyone.
* **Remediation:** `MAX_PAGE_SIZE: int = 1000` for list endpoints, plus a separate, admin-only export endpoint that streams. This is secure because the cost of any single request is bounded.

---

### L1. CORS trusts every LAN host and every matching Vercel preview, with credentials

* **Vulnerability:** Security Misconfiguration (OWASP A05)
* **Severity:** Low (auth is a Bearer header, not a cookie, so there is no ambient credential to ride)
* **Location:** `backend/app/main.py:152`
* **Remediation:** Pick origins per environment:

```python
# config.py
CORS_ORIGINS: str = "http://localhost:3000"      # production: "https://tally-portal-one.vercel.app"
CORS_ORIGIN_REGEX: Optional[str] = None          # set only in development

# main.py
app.add_middleware(CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Auth-Reason"])
```

### L2. Signup reveals which emails have accounts

* **Vulnerability:** User enumeration (OWASP A07)
* **Severity:** Low
* **Location:** `backend/app/routers/agent.py:224` (`409 "You already have an account. Sign in."`)
* **Remediation:** Return the same `{"status": "code_sent"}` either way. For an existing email, send a "someone tried to sign up with your address; sign in instead" message rather than a code. `signup_verify` already re-checks before creating anything.

### L3. One pincode→city table shared by every account

* **Vulnerability:** Broken Access Control on shared data (OWASP A01)
* **Severity:** Low
* **Location:** `backend/app/routers/report_insights.py:433` (`PUT /city-mapping/{pincode}`)
* **Description & Impact:** Any account admin can rename or delete the city for any pincode, which changes every other business's area reports.
* **Remediation:** Add `account_id` to `PincodeCity`, with the global row as a read-only fallback, or gate writes with `require_platform_admin`.

### L4. SQL built by interpolating values and identifiers

* **Vulnerability:** Injection-prone pattern (OWASP A03); **not exploitable today**
* **Severity:** Low
* **Location:** `backend/app/routers/vouchers.py:880-885` (`WHERE voucher_id = {vid}`), `backend/app/core/database.py:221` (DDL)
* **Remediation:** Bind the value: `text(f"DELETE FROM `{tally_db}`.stock_entries WHERE voucher_id = :vid"), {"vid": vid}`. Keep identifier interpolation limited to names taken from model metadata.

### L5. API docs public; no production hardening switch

* **Severity:** Low
* **Location:** `backend/app/main.py:136`
* **Remediation:** `FastAPI(..., docs_url=None if settings.ENV == "production" else "/docs", redoc_url=None, openapi_url=None if settings.ENV == "production" else "/openapi.json")`. Run production through the process manager, never `python main.py` (`reload=True`).

---

## What was checked and is secure

| Area | Why it holds | Where |
|---|---|---|
| SQL injection in reports | `f"..."` only adds fixed SQL fragments; every value is a bound parameter | `reports.py:485` |
| Password storage | bcrypt with a per-hash salt; minimum length 8 | `security.py:16`, `agent.py:59` |
| JWT forgery and replay | Signature, expiry and a live DB session (revocation) are all required | `security.py:30`, `permissions.py:200` |
| Razorpay webhook | HMAC-SHA256, `hmac.compare_digest`, event-id idempotency | `payment_gateway.py:104` |
| WhatsApp webhook | `X-Hub-Signature-256` checked with the app secret, constant-time | `messaging.py:126` |
| Signup code | Hashed, constant-time compare, attempts lockout, expiry, row lock against races | `agent.py:262` |
| Invitations | 256-bit random token stored hashed, row-locked, expiring; role and companies checked against the inviting account | `team.py:111`, `team.py:146` |
| Company switching (`X-Company-ID`) | Honoured only for companies the caller may open; refusals from another business raise an alert | `permissions.py:301` |
| Sync agent device tokens | Hashed; usable only on sync paths; only for companies linked to that PC | `agent_auth.py:40`, `permissions.py:322` |
| Company linking | GUID and legacy-name lookups are both scoped to the caller's account; no takeover of another account's company | `agent.py:121-160` |
| Tenant scoping on id routes | All other ~150 id-taking handlers check ownership (`_own_period`, `_company_user`, `_get_mine`, `_group_for_delete`, account checks) | scan of `app/routers/*.py` |
| Login responses | One generic "Incorrect email or password"; no enumeration | `auth.py:62` |
| Secrets | `.env` is git-ignored; only placeholders are committed | `.gitignore:12` |
| PDF emailing input checks | 5 MB cap, `%PDF` magic check, filename sanitised | `reminders.py:300` |

---

## How the fixes were verified

* **The new tests catch each hole.** With each fix temporarily removed, its tests fail:
  * C1–C3: 6 tests.
  * M1, M3 and the `run-once` gate (M4): 7 tests.
  * The per-company check in the sync run (M4): 1 test, which sends another account's change to the server's Tally without the check.

  With the fixes in place, all of them pass.
* **Nothing else broke.** The full backend suite passes: **289 tests** (`e2e_vouchers` excluded as usual; it needs a live Tally). Two payroll tests that replay "made while Tally was away" changes were updated to record each change's company first, as the real sync run now does.
* **Test isolation:** the suite now also blanks `PLATFORM_ADMIN_EMAILS` and `TALLY_URL_COMPANY_GUID` (`backend/tests/conftest.py`), so values in your real `.env` can't change test results, and it clears the direct-company cache between tests.
* **Web app:** `tsc --noEmit` is clean.
* **Not yet done live:** the fixes are proven by tests, not by signing up a real second account from the agent against a running server. Do that once after deploying (see "Follow-ups").

## Deployment steps

Add to `backend/.env`, then restart the backend:

```
PLATFORM_ADMIN_EMAILS=you@example.com
TALLY_URL_COMPANY_ID=<id of the company your server's Tally belongs to>
```

* **`PLATFORM_ADMIN_EMAILS`:** the sign-in email of each person who runs the server, comma-separated. Without it, nobody can use Backup & Restore, the backup schedule or `/sync/run-once` (the scheduled backup itself keeps running).
* **`TALLY_URL_COMPANY_ID`:** the MyTally id of the company your server's `TALLY_URL` Tally belongs to. `scripts/migrate_to_account.py` (runbook section 4) lists companies as `#<id> 'name'`. Without it, the server's first account and companies from before accounts keep using the direct Tally. That is very likely your own company, but pin it so you don't depend on that guess.
* Both steps are in `docs/Multi-Tenant Rollout Runbook.md` (section 3), with a check in section 6; `backend/.env.example` documents both settings.

## Open design question: backups for customer admins

`PLATFORM_ADMIN_EMAILS` is for the few people who run the server. **Customer admins must never be added to it:** every listed email can reach every customer's backups, so listing them would reopen C1.

* **If customers need to back up their own books:** this is a new feature. The backup module only reaches the server's own Tally (`TALLY_URL`), while each customer's Tally sits on their own PC behind their sync agent. Per-customer backup should run through the agent (export locally, upload tagged with the company id). It should be listed, downloaded and restored only for the caller's own companies, using the normal Admin role, so there's no list to maintain.
* **If your own operations staff grows past a handful of people:** move the list into the database: an `is_platform_admin` flag that only an existing platform admin can grant (gated by `require_platform_admin`) and that is audit-logged. Keep the env list as a short emergency list so you can't lock yourself out. Never derive it from a role name.

## What is still left

In order:

1. **H1: trusted-proxy check in `get_client_ip`**, plus a per-email login lockout. Brute force on `/auth/login` is still possible today (confirmed live).
2. **H2: email relay.** Send documents only to the customer's address on file, and count the daily quota per company.
3. **M2 (remaining part): token lifetime.** Decide whether to add sliding renewal (a fresh token issued while the app is in use) and then shorten the 30-day lifetime. Don't shorten it without renewal, or field users are signed out every week.
4. **L1–L5:** CORS per environment, neutral signup response, per-account pincode table (or `require_platform_admin` on writes), bound parameters in `vouchers.py`, docs off in production.

**Follow-ups:**

* **Defence in depth on the schedule (C2):** refuse an `email_to` that isn't the address of someone in `PLATFORM_ADMIN_EMAILS`, so even a stolen operator token can't redirect backups to an outside address without also changing server config.
* **Request-body limit at the proxy (M3):** `client_max_body_size` (nginx) or the equivalent, so oversized uploads are refused before they reach Python.
* **Live re-test after deploy:** create a second account from the agent and confirm that:
  * `/backup/list`, `PUT /backup-schedule` and `POST /sync/run-once` answer 403;
  * `POST /admin/permissions` with a role id from the first account answers 404 and changes nothing;
  * a ledger created in the second account is **not** sent to your Tally (it stays queued for that account's own agent).
* **Decide the customer-backup question** above before customers ask for backups. Until then, they don't have any.
