# Platform Admin Panel: Architecture and Implementation Plan

Written for MyTally (FastAPI, SQLAlchemy async, MySQL 8, Next.js). The schemas are MySQL 8, because that is the
database this project runs on; the notes say where PostgreSQL differs. The patterns themselves do not depend on
the stack.

## 0. Where MyTally is today, and what this changes

| Today | Problem | This plan |
|---|---|---|
| An operator is an ordinary tenant user whose email is listed in `PLATFORM_ADMIN_EMAILS` (`is_platform_admin`, [permissions.py:279](../backend/app/core/permissions.py)) | Operator access rides on a customer login. A leaked tenant password is a leaked operator. | Operators become their own identity, in their own table, with their own login. |
| One bearer token, valid 30 days (`ACCESS_TOKEN_EXPIRE_MINUTES = 43200`), held by the browser's JavaScript | Too long-lived and too exposed for an operator | Short access token in an HTTP-only cookie, rotating refresh token, a passkey as the second step (can be switched off) |
| Every operator can do everything under `/platform/*` | No least privilege, no separation of duties | Roles and permissions per operator |
| `audit_logs` is per company and has no IP, user agent or operator | Operator actions across accounts are not traceable | A separate, append-only operator audit log |
| Tenant "Admin" page lives at `/admin`, and the tenant API router already uses the `/admin` prefix | The names in the brief (`/admin/auth/*`) would collide | The operator API lives under `/platform/*`, next to the existing `/platform/billing` |

Two words are used strictly below. An **operator** is a person who runs MyTally. A **user** is a customer's
person, in the existing `users` table. Tenant Admins keep managing their own team from the existing Admin page;
nothing here changes that.

---

## 1. Architecture and isolation

### 1.1 Identity: separate tables

Operators get their own tables (`platform_admins`, …). They are not rows in `users` with a special role.

- A bug in tenant role handling can never produce an operator.
- Operators belong to no account, so tenant isolation (`same_account_as_user`) never has to carve out an exception for them.
- Password policy, lockout, passkeys and session length can differ without touching customer logins.
- The cost is a second login flow. That cost is the point.

**Only operators can sign in to the console.** Its login checks email and password against `platform_admins`
and nothing else. A customer's user, whatever their role in their own business (Admin, Sales, Owner or any
other), has no row there, so their email and password are refused with the same "wrong email or password"
message as any unknown login. There is no setting, role or permission on the customer side that grants console
access, and customer role names mean nothing to the console. The reverse also holds: an operator's login does
not work on the customer app.

`PLATFORM_ADMIN_EMAILS` stays only as a one-time bootstrap: on first start with an empty `platform_admins`
table it names who may claim the first super-admin. After that it is ignored, and `require_platform_admin` is
replaced by `require_platform_permission(...)`.

The initial operator password must be provided explicitly through the deployment secret store as
`PLATFORM_ADMIN_INITIAL_PASSWORD`; the application has no built-in default credential. The emergency
break-glass script requires an explicit email and prompts for a password without echoing it or accepting it
as a command-line argument.

### 1.2 Surface: inside the customer app for now, built to move out

**Decided (13 Oct 2026):** the console ships inside the customer app, at the same address, and is built so it
can move to its own `admin.` host later with configuration only.

```
Now     app host/console/*       → operator console pages
        app host/console-api/*   → proxied by Next.js to the API's /platform/*   (operator cookies live here)
        app host/*               → customer app → API directly, bearer token as today

Later   admin host/*             → the same console pages
        admin host/console-api/* → the same proxy
```

What this costs, so it is a known trade and not a surprise: while the console shares the customer app's
address, a script-injection bug anywhere in the customer app runs with the same origin as the console and could
make console requests in a signed-in operator's browser. Section 5.2 lists what limits that. Moving to a
separate host removes it.

#### Rules that keep the move cheap

Each rule exists so that moving out is a deployment change, not a rewrite.

1. **One folder, one boundary.** Console pages live in their own Next.js route group, `src/app/(console)/console/...`, with their own root layout, and console code in `src/console/`. A lint rule forbids imports between `src/console/` and the customer app in both directions. Only the design-system primitives (`src/components/ui`) are shared.
2. **Its own session, not `AuthContext`.** The console has its own provider and never reads the customer token, the customer's local storage or the customer's company header. The customer app's global `fetch` wrapper in `AuthContext.tsx` must skip `/console-api/` requests.
3. **One API client, one base path.** Every console request goes through `src/console/api.ts` to a relative path, `/console-api/...`. No console code names the API host. Next.js rewrites `/console-api/:path*` to the API's `/platform/:path*`. The browser therefore sees the cookies as first-party, and the same rewrite works unchanged on a future admin host.
4. **Cookies scoped by path.** Operator cookies are set with `Path=/console-api`, so they are never sent with customer-app requests. (The `__Host-` prefix needs `Path=/`, so the cookies use the `__Secure-` prefix until the console has its own host.)
5. **Everything host-specific is a setting.** `PLATFORM_CONSOLE_ORIGIN` (allowed origin for console requests), `PLATFORM_WEBAUTHN_RP_ID`, `PLATFORM_COOKIE_PATH`, `PLATFORM_COOKIE_PREFIX`. The backend never assumes the console and the customer app share an address.
6. **The service worker stays out.** `public/sw.js` must not cache or intercept `/console` or `/console-api`.
7. **Passkeys are tied to the address, so the move includes re-registering them.** The app is on `tally-portal-one.vercel.app` only (confirmed 13 Oct 2026). A passkey registered there works on that exact address and nowhere else: `vercel.app` cannot act as a shared parent domain. So:
   - `PLATFORM_WEBAUTHN_RP_ID=tally-portal-one.vercel.app` for now, as a setting.
   - Each stored passkey records the address it was registered for (`rp_id` column on `platform_admin_webauthn_credentials`), so passkeys for the old and the new address can exist side by side during a move.
   - The move has a planned hand-over (below) so nobody is locked out.
   - Passkeys do not work on Vercel preview addresses. The console is usable on the production address only, which is the intended behaviour.
   - If the app goes onto your own domain **before** the console is built, register passkeys against that parent domain instead and this whole step disappears. That is the cheaper order if a domain is coming anyway.

#### Moving out later

1. Create a second Vercel project from the same repository whose build includes only the `(console)` group (a build flag), on `admin.<your domain>`.
2. Set `PLATFORM_CONSOLE_ORIGIN` to the new address and `PLATFORM_COOKIE_PATH=/`, `PLATFORM_COOKIE_PREFIX=__Host-`.
3. In the customer project, turn the same build flag the other way so `/console` is no longer built, and redirect it to the new address.
4. Hand over the passkeys. While both addresses are live, each operator signs in on the old address and requests a one-time enrolment link (15 minutes, single use, audited). They open it on the new address and register their devices there. When every operator has done so, the old address's passkeys are deleted and the old console is switched off. (With `PLATFORM_PASSKEY_REQUIRED=false` during the move, this step is simply signing in with the password on the new address and registering there.)
5. Optionally restrict the admin host to office or VPN addresses.

**API**: one FastAPI service; the operator routers are mounted under `/platform` with their own dependency
chain. Tenant tokens are refused there and operator sessions are refused everywhere else. Signing keys, cookie
names, rate-limit buckets and session tables are never shared with the customer side.

### 1.3 Sessions and tokens

| Item | Choice |
|---|---|
| Access token | JWT, 10 minutes, signed with `PLATFORM_JWT_SECRET` (not `JWT_SECRET`). Carries `sub` (admin id), `sid` (session id), `pv` (permission version), `amr` (how they signed in). |
| Refresh token | Opaque 256-bit random value, stored hashed (SHA-256), **rotated on every use**. |
| Transport | Cookies: `__Secure-pa_at` (path `/console-api`) and `__Secure-pa_rt` (path `/console-api/auth`), both `HttpOnly; Secure; SameSite=Strict`. Nothing in JavaScript storage. On a separate host later they become `__Host-` cookies (section 1.2). |
| CSRF | `SameSite=Strict`, plus a double-submit token: `X-CSRF-Token` header must equal the value in a readable `pa_csrf` cookie on every write. |
| Lifetimes | Idle timeout 30 minutes, absolute lifetime 8 hours, then a full sign-in again. |
| Reuse detection | A refresh token used twice means theft: revoke the whole token family and alert. |
| Second step | A **passkey**: the fingerprint, face or PIN unlock of the operator's own laptop or phone (a USB security key also works; it is the same mechanism). Required for every operator after the password, and each operator should register two (for example laptop and phone) so losing one device does not lock them out. **`PLATFORM_PASSKEY_REQUIRED` (default `true`) switches it off:** when `false`, sign-in is email and password only, for super-admins too. There are no SMS codes, authenticator-app codes or recovery codes. |
| Step-up | Dangerous actions (hard delete, impersonate, role changes, export) need a fresh check if the last one is older than 5 minutes: the passkey again, or the password again when passkeys are switched off. |
| Revocation | Every request checks the session row (cached for a few seconds) and compares `pv` with the admin's current `permission_version`. |

```
Login            POST /platform/auth/login {email, password}
                   → passkeys off: Set-Cookie pa_at, pa_rt, pa_csrf   (session created; signed in)
                   → passkeys on:  200 {passkey_required, mfa_token}  (5-minute, single-purpose token; no session yet)
                 POST /platform/auth/passkey/login/verify {mfa_token, assertion}
                   → Set-Cookie pa_at, pa_rt, pa_csrf       (session row created here)

Every request    cookie pa_at → verify signature and expiry → load session (not revoked, not idle-expired)
                   → pv matches? → permission check → handler → audit

Refresh          POST /platform/auth/refresh   (cookie pa_rt)
                   → token unused?  yes: mark used, issue new pair
                                    no:  revoke family, 401, alert
```

The existing device-session code ([sessions.py](../backend/app/core/sessions.py)) is the model for the session
row and its revocation; it is not reused directly, so the two session stores stay apart.

---

## 2. Permissions and access control

### 2.1 Model

RBAC as the base, with a small number of attribute rules on top.

- A **permission** is a string, `resource.action`: `users.read`, `users.update`, `users.hard_delete`, `page.billing`.
- The catalogue of permissions lives **in code** and is synced to the table at startup. Operators assign permissions; they cannot invent them. A permission that no code checks would be meaningless.
- A **role** is a named set of permissions with a **rank**. An operator may hold several roles; the effective set is the union.
- **Attribute rules** (the ABAC part) are evaluated after the role check:
  1. **Rank**: you may only act on operators and roles ranked strictly below your own highest rank.
  2. **Self**: you may never change your own roles or status, or reset your own passkeys, through the admin APIs.
  3. **Scope** (optional per role assignment): limit an operator to certain accounts, for example a support agent for one reseller's customers.
  4. **Field level**: `users.read_pii` decides whether email and phone are returned whole or masked.
  5. **Protected targets**: the last active super-admin can be neither disabled, demoted nor deleted.

Page visibility is just another permission (`page.users`, `page.audit`, …). A page's permission never grants the
data: the API checks the data permission separately.

### 2.2 Permission catalogue for users

| Permission | Allows |
|---|---|
| `users.read` | List and open user records, PII masked |
| `users.read_pii` | See email and phone unmasked |
| `users.create` | Create a user in an account |
| `users.update` | Edit profile fields, role within the account, company access |
| `users.suspend` | Suspend and reinstate, lock and unlock |
| `users.reset_password` | Force a reset, issue a temporary password |
| `users.revoke_sessions` | Sign a user out everywhere |
| `users.soft_delete` | Mark deleted, and restore within the retention period |
| `users.hard_delete` | Erase personal data permanently (step-up, second approver) |
| `users.impersonate` | Open the tenant app as the user (step-up, reason required) |
| `users.export` | Download a list (step-up, rate limited) |

### 2.3 Schema

```sql
CREATE TABLE platform_admins (
  admin_id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email               VARCHAR(190) NOT NULL,
  full_name           VARCHAR(120) NOT NULL,
  password_hash       VARCHAR(255) NOT NULL,              -- argon2id (bcrypt as today is acceptable)
  status              ENUM('invited','active','suspended','disabled') NOT NULL DEFAULT 'invited',
  failed_logins       INT NOT NULL DEFAULT 0,
  locked_until        DATETIME NULL,
  password_changed_at DATETIME NULL,
  permission_version  INT NOT NULL DEFAULT 1,             -- bumped on any role or permission change
  allowed_ip_cidrs    JSON NULL,                          -- optional per-admin allowlist
  last_login_at       DATETIME NULL,
  last_login_ip       VARCHAR(45) NULL,
  created_by          BIGINT UNSIGNED NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  version             INT NOT NULL DEFAULT 1,             -- optimistic lock
  UNIQUE KEY uq_platform_admins_email (email)
);

CREATE TABLE platform_roles (
  role_id     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code        VARCHAR(50)  NOT NULL,                      -- super_admin, support, billing, auditor
  name        VARCHAR(80)  NOT NULL,
  description VARCHAR(255) NULL,
  `rank`      SMALLINT NOT NULL,                          -- higher outranks lower; super_admin = 1000
  is_system   BOOLEAN NOT NULL DEFAULT FALSE,             -- system roles cannot be edited or deleted
  version     INT NOT NULL DEFAULT 1,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_platform_roles_code (code)
);

CREATE TABLE platform_permissions (
  permission_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code          VARCHAR(80)  NOT NULL,                    -- users.hard_delete
  resource      VARCHAR(40)  NOT NULL,                    -- users
  action        VARCHAR(40)  NOT NULL,                    -- hard_delete
  description   VARCHAR(255) NOT NULL,
  is_sensitive  BOOLEAN NOT NULL DEFAULT FALSE,           -- needs step-up
  UNIQUE KEY uq_platform_permissions_code (code)
);

CREATE TABLE platform_role_permissions (
  role_id       INT UNSIGNED NOT NULL,
  permission_id INT UNSIGNED NOT NULL,
  granted_by    BIGINT UNSIGNED NULL,
  granted_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id, permission_id),
  FOREIGN KEY (role_id)       REFERENCES platform_roles(role_id) ON DELETE CASCADE,
  FOREIGN KEY (permission_id) REFERENCES platform_permissions(permission_id) ON DELETE CASCADE
);

CREATE TABLE platform_admin_roles (
  admin_id          BIGINT UNSIGNED NOT NULL,
  role_id           INT UNSIGNED NOT NULL,
  scope_account_ids JSON NULL,                            -- NULL = every account
  assigned_by       BIGINT UNSIGNED NULL,
  assigned_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at        DATETIME NULL,                        -- temporary elevation
  PRIMARY KEY (admin_id, role_id),
  FOREIGN KEY (admin_id) REFERENCES platform_admins(admin_id) ON DELETE CASCADE,
  FOREIGN KEY (role_id)  REFERENCES platform_roles(role_id) ON DELETE RESTRICT
);

CREATE TABLE platform_admin_sessions (
  session_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id       BIGINT UNSIGNED NOT NULL,
  family_id      CHAR(36) NOT NULL,                       -- one per sign-in; rotation stays in the family
  refresh_hash   CHAR(64) NOT NULL,
  refresh_used   BOOLEAN NOT NULL DEFAULT FALSE,
  mfa_at         DATETIME NOT NULL,                       -- last passkey (or password) check, for step-up
  ip_address     VARCHAR(45) NULL,
  user_agent     VARCHAR(500) NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at     DATETIME NOT NULL,                       -- absolute
  revoked_at     DATETIME NULL,
  revoked_reason VARCHAR(60) NULL,
  UNIQUE KEY uq_pas_refresh (refresh_hash),
  KEY ix_pas_admin (admin_id, revoked_at),
  KEY ix_pas_family (family_id),
  FOREIGN KEY (admin_id) REFERENCES platform_admins(admin_id) ON DELETE CASCADE
);

CREATE TABLE platform_login_attempts (
  attempt_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email_hash   CHAR(64) NOT NULL,                         -- SHA-256 of the lower-cased email, known or not
  ip_address   VARCHAR(45) NOT NULL,
  succeeded    BOOLEAN NOT NULL,
  attempted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_pla_ip (ip_address, attempted_at),
  KEY ix_pla_email (email_hash, attempted_at)
);                                                        -- rows older than 7 days are purged nightly

CREATE TABLE platform_admin_webauthn_credentials (
  credential_pk BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id      BIGINT UNSIGNED NOT NULL,
  credential_id VARBINARY(255) NOT NULL,                  -- from the authenticator
  public_key    BLOB NOT NULL,                            -- COSE key
  sign_count    BIGINT UNSIGNED NOT NULL DEFAULT 0,       -- a count that goes backwards means a cloned key
  aaguid        CHAR(36) NULL,                            -- make and model of the key
  transports    JSON NULL,
  rp_id         VARCHAR(190) NOT NULL,                    -- the address the key was registered for
  nickname      VARCHAR(60) NOT NULL,                     -- "Office laptop", "My phone"
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at  DATETIME NULL,
  UNIQUE KEY uq_pawc_credential (credential_id),
  FOREIGN KEY (admin_id) REFERENCES platform_admins(admin_id) ON DELETE CASCADE
);


PostgreSQL differences: `BIGINT GENERATED ALWAYS AS IDENTITY` for the keys, `JSONB` for `JSON`, `TIMESTAMPTZ`
for `DATETIME`, `CHECK` constraints or native enums for `ENUM`, `INET`/`CIDR[]` for the IP columns, and a
trigger for `updated_at`.

```
platform_admins ──< platform_admin_roles >── platform_roles ──< platform_role_permissions >── platform_permissions
       │
       ├──< platform_admin_sessions
       ├──< platform_admin_webauthn_credentials
       └──< platform_audit_log   (section 3.5)
```

Starting roles: `super_admin` (rank 1000, everything), `admin` (800, all but operator and role management),
`support` (400, read users, suspend, reset password, revoke sessions), `billing` (400, billing console),
`auditor` (300, read-only plus the audit log).

### 2.4 Enforcement in the API

One dependency chain, the same shape as the existing `require_permission` and `require_feature`:

```python
async def current_admin(request, db) -> AdminContext:
    claims  = verify_jwt(request.cookies["__Host-pa_at"], PLATFORM_JWT_SECRET)
    session = await load_session(db, claims.sid)                 # cached a few seconds
    if session.revoked_at or session.expired or session.idle_expired: raise 401
    admin = await load_admin(db, claims.sub)
    if admin.status != "active" or claims.pv != admin.permission_version: raise 401
    if not ip_allowed(request.client_ip, admin.allowed_ip_cidrs): raise 403
    if request.method not in SAFE and not csrf_ok(request): raise 403
    return AdminContext(admin, session, permissions=await effective_permissions(db, admin), rank=...)

def require_platform_permission(code: str, *, step_up: bool = False):
    async def dep(ctx = Depends(current_admin)):
        if code not in ctx.permissions: raise 403
        if (step_up or SENSITIVE[code]) and ctx.session.mfa_at < now() - 5min:
            raise 401 with header  X-Step-Up: required
        return ctx
    return dep

@router.delete("/users/{user_id}/purge")
async def purge_user(user_id: int, body: PurgeIn,
                     ctx = Depends(require_platform_permission("users.hard_delete"))):
    ...
```

Rules that keep this honest:

- **Deny by default.** A startup check walks every route under `/platform` and fails the boot if one has no `require_platform_permission` (the auth routes are the listed exceptions).
- **Object-level rules live in the service layer**, not the route: rank, self, scope and protected-target checks run where the target row has been loaded.
- **Out-of-scope targets answer 404**, not 403, so an operator cannot probe for what exists outside their scope.

### 2.5 Enforcement in the UI

The UI guard is for usability only. The API is the security boundary.

- `GET /platform/auth/me` returns the operator, the permission codes and the list of pages they may see.
- One navigation registry maps each page to its permission, the way [navigation.ts](../frontend-nextjs/src/lib/navigation.ts) does for the tenant app. The sidebar, the route guard and the command palette all read from it.
- A `<Can permission="users.suspend">` component hides or disables actions.
- A route guard in the layout redirects to a "not allowed" page; a 401 anywhere returns to login; a 401 with `X-Step-Up` opens the passkey (or password) prompt and retries the request.
- Where Next.js middleware is used for an early redirect, it only checks that a session cookie exists. It never decides permissions.

---

## 3. User data management

The engine operates on the existing `users` table. Columns to add (the startup schema synchroniser adds them):

```sql
ALTER TABLE users
  ADD COLUMN status                ENUM('active','suspended','locked') NOT NULL DEFAULT 'active',
  ADD COLUMN suspended_at          DATETIME NULL,
  ADD COLUMN suspended_reason      VARCHAR(255) NULL,
  ADD COLUMN must_change_password  BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN temp_password_expires DATETIME NULL,
  ADD COLUMN deleted_at            DATETIME NULL,
  ADD COLUMN deleted_by_admin_id   BIGINT UNSIGNED NULL,
  ADD COLUMN purge_after           DATETIME NULL,
  ADD COLUMN purged_at             DATETIME NULL,
  ADD COLUMN version               INT NOT NULL DEFAULT 1,
  ADD KEY ix_users_deleted (deleted_at),
  ADD KEY ix_users_account_status (account_id, status, deleted_at),
  ADD KEY ix_users_created (created_at, user_id),
  ADD KEY ix_users_last_login (last_login, user_id);
```

`is_active` stays as it is for the tenant app; `status` and `deleted_at` are the operator's view on top of it,
and sign-in refuses a user who is suspended, locked or deleted.

### 3.1 Create

1. Operator picks the account, role (one of that account's roles) and companies.
2. Server checks: email or phone is unique, the account's plan has a free seat (`get_entitlements`), the role belongs to that account.
3. **Preferred:** send an invitation through the existing `user_invites` flow. No password ever passes through an operator's hands.
4. **Fallback (`users.reset_password` also required):** generate a temporary password on the server (16 or more random characters), show it **once**, store only the hash, set `must_change_password` and `temp_password_expires` (24 hours). The audit entry records that one was issued, never its value.
5. `email_verified_at` stays empty unless the operator ticks "verified by us", which is its own audited field.

The request carries an `Idempotency-Key`, and the unique keys on email and phone are the final guard, in line
with the project's rule that every write is repeat-safe.

### 3.2 Read

- **Pagination by key, not offset.** `WHERE (created_at, user_id) < (:c, :id) ORDER BY created_at DESC, user_id DESC LIMIT 50`, with an opaque cursor. Offsets get slow and skip rows on a table that is being written to. No total count by default; an approximate count is available on request.
- **Sorting** only on an allowlist of indexed columns (`created_at`, `last_login`, `username`), each paired with `user_id` as the tie-breaker.
- **Filters** on indexed columns: account, status, role, verified, created and last-login ranges, deleted or not.
- **Search**: exact match on email and phone (indexed), prefix match on name. For "contains" search add a `FULLTEXT` index on `(username, email)` (PostgreSQL: `pg_trgm` with a GIN index). Never an unanchored `LIKE '%x%'` over the whole table.
- **Masking** happens in the serialiser, driven by `users.read_pii`: `a•••••@gmail.com`, `••••••4321`. `password_hash`, tokens and passkey data are never serialised under any permission. Opening an unmasked record writes an audit entry (`users.pii_viewed`).
- **Export** runs as a background job, is capped in rows, masked unless `users.read_pii` is held, produces a link that expires, and is audited with the filter that was used.

### 3.3 Update

- Strict schemas per operation; unknown fields are rejected, so nothing is mass-assigned.
- Every update carries the `version` it read (section 5.3).
- **Role change**: the new role must belong to the user's own account. Making someone a tenant Admin, or removing the last Admin of an account, needs `users.update` plus a reason, and the last-Admin case is refused.
- **Password reset**: default is a reset link to the user. A temporary password follows the rules in 3.1. Either way every session of the user is revoked.
- **Suspend / reinstate**: sets status and reason, revokes sessions and device tokens, clears the auth cache (`invalidate_auth_cache`). The account's own data is untouched.
- **Lock / unlock** is the automatic brute-force state; an operator may clear it.
- Email or phone changes re-check uniqueness and reset the verified flag.

### 3.4 Delete

**Soft delete** (`users.soft_delete`): set `deleted_at`, `deleted_by_admin_id`, `purge_after = now + 30 days`,
`is_active = false`; revoke sessions. The row stays, so every voucher, order and audit entry the person created
still resolves. Restore within the period clears those fields. Refused when the user is the last Admin of the
account, with a message saying to assign another first.

**Hard delete** (`users.hard_delete`, step-up, second approver): implemented as **anonymisation, not row
removal**. Many tables point at `users.user_id` (`created_by`, `granted_by`, audit rows, vouchers), and those
records are business and tax records of the customer that must survive the person.

- Overwrite: email → `deleted-<id>@invalid`, username → `Deleted user`, phone, designation, employee code → `NULL`, password hash → a value that can never match.
- Delete outright: sessions, device registrations, push tokens, phone-login rows, open invitations, permission overrides, location pings.
- Keep: the row id, and everything accounting-related that references it.
- Set `purged_at`. A nightly job (beside `daily_cleanup_worker`) does the same for soft-deleted rows past `purge_after`.
- **Nothing is sent to Tally.** Deleting a person in the app must not delete or alter any master or voucher in Tally; the job touches portal tables only.

**Retention and compliance**: a retention table states, per kind of data, how long it is kept and why (tax
records: the statutory period; operator audit log: at least as long). An erasure request is fulfilled by the
anonymisation above, with a record of what was erased and what was retained under which obligation. Backups
age out on their normal schedule; that is stated in the response to the request. Have the periods confirmed by
your legal adviser before they are fixed.

### 3.5 Audit trail

```sql
CREATE TABLE platform_audit_log (
  audit_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  occurred_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  admin_id          BIGINT UNSIGNED NULL,                -- NULL for a failed login by an unknown email
  admin_email       VARCHAR(190) NOT NULL,               -- kept even if the admin row is later removed
  session_id        BIGINT UNSIGNED NULL,
  action_type       VARCHAR(60) NOT NULL,                -- users.update, users.suspend, auth.login_failed
  target_type       VARCHAR(40) NULL,                    -- user, admin, role, account
  target_id         BIGINT NULL,
  target_account_id INT NULL,
  target_user_id    INT NULL,
  old_values        JSON NULL,                           -- changed fields only
  new_values        JSON NULL,
  reason            VARCHAR(500) NULL,
  outcome           ENUM('success','denied','failed') NOT NULL,
  request_id        CHAR(36) NOT NULL,
  ip_address        VARCHAR(45) NULL,
  user_agent        VARCHAR(500) NULL,
  prev_hash         CHAR(64) NULL,
  row_hash          CHAR(64) NOT NULL,                   -- SHA-256(prev_hash || canonical row)
  KEY ix_pal_time (occurred_at),
  KEY ix_pal_admin (admin_id, occurred_at),
  KEY ix_pal_target_user (target_user_id, occurred_at),
  KEY ix_pal_account (target_account_id, occurred_at),
  KEY ix_pal_action (action_type, occurred_at)
);
```

How entries get written:

1. A small middleware puts `request_id`, IP and user agent into a context variable for the request.
2. Each service function that writes calls `audit(ctx, action, target, before, after, reason)` **in the same transaction as the change**. If the audit insert fails, the change rolls back. There is no unaudited write.
3. A SQLAlchemy `before_flush` listener is the safety net: a change to a watched table (`users`, `platform_*`) made while an operator context is active, with no audit entry queued, raises. This catches a write someone forgot to audit.
4. `before` and `after` are diffed to the changed fields. A deny-list (`password_hash`, tokens, secrets, temporary passwords) is redacted to `"[redacted]"` before storing.
5. Denied attempts and failed logins are logged too, with `outcome`.

Integrity: the application's database user has `INSERT` and `SELECT` only on this table; each row carries a hash
of the previous one, verified by a scheduled job; and rows are shipped to external storage for the long term.
The existing per-company `audit_logs` table stays what it is: the customer's own record of their staff's
actions.

---

## 4. API

REST, JSON, under `/platform`. Writes take `Idempotency-Key` and, for updates, `If-Match: <version>`. Errors use
one shape: `{"detail": "...", "code": "..."}`. The brief's `/admin/...` paths map to these.

### Authentication: `/platform/auth`

| Method and path | Purpose | Needs |
|---|---|---|
| `POST /login` | Email and password, checked against `platform_admins` only. With passkeys off it creates the session; with passkeys on it returns `mfa_token`. | public, rate limited |
| `POST /passkey/login/options`, `POST /passkey/login/verify` | Confirm with a passkey. Creates the session. | `mfa_token` |
| `POST /passkey/register/options`, `POST /passkey/register/verify` | Add a passkey (first-time setup from the invitation, or another device later). | invitation token, or session + step-up |
| `GET /passkey/credentials`, `DELETE /passkey/credentials/{id}` | My passkeys. The last one cannot be removed while passkeys are required. | session + step-up |
| `POST /step-up` | Fresh passkey check (or password, when passkeys are off) for sensitive actions. | session |
| `POST /refresh` | Rotate tokens. | refresh cookie |
| `POST /logout`, `POST /logout-all` | End this session, or all of mine. | session |
| `GET /me` | Profile, permissions, visible pages. | session |
| `GET /sessions`, `DELETE /sessions/{id}` | My sessions. | session |
| `POST /password` | Change my password; ends my other sessions. | session + step-up |

### Operators, roles and permissions

| Method and path | Permission |
|---|---|
| `GET /platform/admins`, `GET /platform/admins/{id}` | `admins.read` |
| `POST /platform/admins` (invite) | `admins.create` |
| `PATCH /platform/admins/{id}` (name, status, IP allowlist) | `admins.update` |
| `PUT /platform/admins/{id}/roles` | `admins.assign_roles` + step-up |
| `POST /platform/admins/{id}/reset-passkeys` | `admins.reset_mfa` + step-up |
| `DELETE /platform/admins/{id}/sessions` | `admins.revoke_sessions` |
| `GET /platform/permissions` (the catalogue) | `roles.read` |
| `GET /platform/roles`, `GET /platform/roles/{id}` | `roles.read` |
| `POST /platform/roles`, `PATCH /platform/roles/{id}`, `DELETE /platform/roles/{id}` | `roles.manage` + step-up |
| `PUT /platform/roles/{id}/permissions` | `roles.manage` + step-up |

### Users: `/platform/users`

| Method and path | Permission |
|---|---|
| `GET /` `?cursor&limit&sort&q&account_id&status&role&verified&created_from&created_to&include_deleted` | `users.read` |
| `GET /{id}` | `users.read` (+ `users.read_pii` to unmask) |
| `POST /` | `users.create` |
| `PATCH /{id}` | `users.update` |
| `POST /{id}/suspend`, `POST /{id}/reinstate`, `POST /{id}/unlock` | `users.suspend` |
| `POST /{id}/password-reset` `{mode: "link" \| "temporary"}` | `users.reset_password` (+ step-up for temporary) |
| `DELETE /{id}/sessions` | `users.revoke_sessions` |
| `DELETE /{id}` (soft), `POST /{id}/restore` | `users.soft_delete` |
| `POST /{id}/purge-requests`, `POST /purge-requests/{rid}/approve` | `users.hard_delete` + step-up; approver must be someone else |
| `POST /{id}/impersonate` `{reason, minutes}`, `DELETE /impersonations/{sid}` | `users.impersonate` + step-up |
| `POST /exports`, `GET /exports/{id}` | `users.export` + step-up |

### Audit: `/platform/audit-logs`

| Method and path | Permission |
|---|---|
| `GET /` `?cursor&admin_id&action_type&target_user_id&target_account_id&outcome&from&to` | `audit.read` |
| `GET /{id}` | `audit.read` |
| `POST /exports` | `audit.export` + step-up |
| `GET /integrity` (result of the last chain check) | `audit.read` |

There is no update or delete endpoint for audit entries.

---

## 5. Security hardening and edge cases

### 5.1 Privilege escalation

- **You cannot give what you do not have.** Assigning a role is refused unless every permission in it is one the assigner already holds.
- **Rank is strict.** Create, edit, suspend, reset or delete only operators and roles ranked below your own. Equal rank is refused, so two admins cannot lock each other out and super-admins are untouchable by anyone but super-admins.
- **No self-service elevation.** Your own roles, status and passkey reset are not editable by you.
- **System roles are fixed.** `super_admin` cannot be edited or deleted, and the last active one cannot be disabled or demoted. Enforced in the service and backed by a check inside the same transaction with the rows locked.
- **Two people for the irreversible.** Hard delete and granting `super_admin` need a second operator's approval.
- **Break-glass**: one offline, documented procedure (a script run on the server) to restore a super-admin, itself writing an audit entry and an alert.

### 5.2 Abuse and sessions

- **Lockout and rate limits are mandatory.** They are part of the console login itself: there is no setting that switches them off, in any environment, with passkeys on or off. In particular the app-wide `RATE_LIMIT_ENABLED` switch, which can turn the customer app's limiter off, has no effect on the console.

  | Guard | Rule | Kept in |
  |---|---|---|
  | Per operator lockout | 5 wrong passwords in a row locks the account for 15 minutes; each further lock doubles, up to 24 hours. A correct sign-in resets the count. | `platform_admins.failed_logins`, `locked_until` |
  | Per address limit | 10 sign-in attempts per IP per 15 minutes across all emails, then refused for the rest of the window. | `platform_login_attempts` table |
  | Per email limit | 10 attempts per email per hour from any address, whether or not the email exists. | `platform_login_attempts` table |
  | Passkey and step-up | 5 failed checks per session token, then the token is void and sign-in starts again. | the `mfa_token` / session row |
  | Refresh | 30 per session per hour. | session row |

  - The counters live in the database, not in the server's memory, so a restart or a second worker does not reset them and an attacker cannot get more tries by spreading requests.
  - A locked account answers exactly like a wrong password, with the same text and the same timing, and so does an email that does not exist. Nothing tells an attacker which emails are real or which are locked.
  - The lock applies even to a correct password while it lasts.
  - On a lock the operator gets an email, every super-admin gets an alert, and it is written to the audit log with the address it came from.
  - A higher-ranked operator with `admins.update` can lift a lock early; nobody can lift their own.
  - Every failed attempt is written to the audit log (`auth.login_failed`).
- **Passkeys switched off** (`PLATFORM_PASSKEY_REQUIRED=false`) leaves the console protected by a password alone. A phished, reused or guessed operator password is then full access to every customer's data. If it is run that way: keep the per-operator IP allowlist on and use long unique passwords. Lockout and rate limits stay on regardless; they cannot be switched off. The backend logs a warning at every start while it is off, the audit log records each sign-in as password-only, and the console shows a banner to super-admins.
- **Passwords**: argon2id, minimum 14 characters, checked against a breached-password list, no forced periodic rotation.
- **IP allowlisting** per operator (`allowed_ip_cidrs`), checked by the API on every console request. Restricting the whole console address becomes possible once it has its own host. Trust `X-Forwarded-For` only from your own proxy.
- **While the console shares the customer app's address**, a script-injection bug in the customer app could issue console requests in an operator's browser. What limits it: cookies scoped to `/console-api`; every sensitive action needs a fresh passkey check, which is a fingerprint, face or PIN prompt from the device that a script cannot answer (this protection is lost while passkeys are switched off); a strict Content-Security-Policy on `/console` pages; 10-minute access tokens and 30-minute idle expiry; and operators using a separate browser profile for the console. Treat any cross-site-scripting finding in the customer app as an operator-level finding until the console moves out.
- **Revocation on change**: any change to an operator's roles, to a role's permissions, to status or password bumps `permission_version` and revokes that operator's sessions. Because access tokens last 10 minutes and the version is checked on every request, the change takes effect at once.
- **Impersonation** issues a separate, marked tenant session: 15 minutes by default, read-only unless `users.impersonate_write` is held, a banner in the tenant app, every request logged with both identities, password, billing and delete actions refused, and the account's Admins notified afterwards.
- **Headers**: strict Content-Security-Policy with no inline script, `frame-ancestors 'none'`, HSTS, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` on every operator API response.
- **Alerts** to a channel a human watches: new super-admin, refresh-token reuse, passkey reset, the passkey flag switched off, purge, export, login from a new country, a broken audit chain.

### 5.3 Concurrent edits

Optimistic locking with a `version` column (a counter is safer than comparing `updated_at`, which can collide
within the timestamp's resolution).

```sql
UPDATE users
   SET designation = :d, version = version + 1
 WHERE user_id = :id AND version = :expected;      -- 0 rows changed → someone else got there first
```

- `GET` returns `version` (also as an `ETag`); writes send it back in `If-Match`.
- A mismatch answers `409` with the current record, and the UI shows what changed and offers to reapply.
- A missing `If-Match` on an update answers `428`, so no client can skip the check by accident.
- For rules that span rows (last Admin of an account, last super-admin), lock the rows with `SELECT … FOR UPDATE` inside the transaction; a version check alone does not protect a count.

### 5.4 Other edge cases

- An operator deleted or disabled mid-session: the next request fails on the session check.
- Passkeys switched off and on again: registered passkeys are kept while the flag is off, so turning it back on needs no re-registration. An operator invited while it was off is made to register one at their next sign-in.
- Lost device: the operator signs in with their second passkey and removes the lost one. With none left, a higher-ranked operator with `admins.reset_mfa` clears their passkeys and they register again from a fresh invitation link.
- The only super-admin has lost every passkey: someone with access to the server sets `PLATFORM_PASSKEY_REQUIRED=false`, the super-admin signs in with the password and registers a new passkey, and the flag goes back to `true`. Each change of the flag is logged at startup and raises an alert.
- A passkey is bound to the console's address. Moving the console to another address later means registering passkeys again (section 1.2, rule 7).
- A user restored after their email was taken by a new signup: restore is refused with a clear message, and the operator must change the email first.
- A suspended user's sync agent: device tokens are revoked with the sessions, so the PC stops syncing until someone else in the account signs it in.

---

## 6. Roadmap

| Phase | Scope | Done when |
|---|---|---|
| **1. Schema and authentication** | `platform_*` tables and seed of roles and permissions. Bootstrap of the first super-admin. Login with email and password, passkey registration and check, the `PLATFORM_PASSKEY_REQUIRED` flag, cookies, refresh rotation with reuse detection, logout, CSRF, and the mandatory lockout and rate limits (section 5.2). Console route group inside the customer app with its own layout, session provider, API client and the `/console-api` proxy; the import boundary lint rule; the service worker exclusion. | An operator signs in with password and passkey; with the flag off, with password alone; a customer's Admin or Sales login is refused at the console login; a tenant token is refused under `/platform`; reusing a refresh token kills the family. |
| **2. User CRUD and middleware** | `current_admin` and `require_platform_permission`. The `users` columns. List with key pagination, filters, search, masking. Create, update, suspend, reset password, revoke sessions, soft delete and restore, with `version` checks and idempotency keys. Audit writer in the same transaction. Move `/platform/billing` onto the new dependency. | Every route under `/platform` has a permission (boot check passes); the support role can do support tasks and nothing else. |
| **3. Dynamic permissions and UI guards** | Operator and role management with the rank, self and "cannot grant what you lack" rules. `permission_version` revocation. Step-up. Navigation registry, `<Can>`, route guard, step-up prompt, conflict dialog for 409. Account scoping. | Changing a role takes effect on the operator's next request; hidden pages also answer 403 from the API. |
| **4. Audit, deletion and security testing** | Audit viewer and export, hash-chain check, safety-net listener. Purge requests with a second approver, the anonymisation job, retention table. Impersonation. Exports. Alerts. IP allowlists. Then testing. | The test list below passes, and an outside review has no open high findings. |

Retire `PLATFORM_ADMIN_EMAILS` as an access rule at the end of phase 2, once every operator has a
`platform_admins` row.

### Tests that must exist before go-live

- **Isolation**: a tenant token on `/platform/*` and an operator cookie on tenant routes are both refused. A customer user's correct email and password (tenant Admin, Sales, and an email listed in the old `PLATFORM_ADMIN_EMAILS`) are refused at the console login with the same message as a wrong password.
- **Passkey flag**: with it on, a correct password alone creates no session; with it off, it does, and step-up asks for the password.
- **Deny by default**: a route without a permission fails the boot.
- **Escalation**: self role change, granting an unheld permission, acting on an equal or higher rank, removing the last super-admin: all refused.
- **Sessions**: refresh reuse, idle and absolute expiry, revocation after a role change, step-up required and honoured.
- **CSRF**: a write without the header is refused.
- **Scope**: an out-of-scope user answers 404.
- **Masking**: no PII without `users.read_pii`; secrets never appear in any response or audit row.
- **Concurrency**: two updates with the same version, one wins and one gets 409; two simultaneous removals of the last two Admins leave one.
- **Deletion**: after a purge the person's vouchers still load, and nothing was queued for Tally.
- **Audit**: every write endpoint produces exactly one entry; a forced audit failure rolls the change back; a tampered row is caught by the chain check.
- **Lockout and rate limits**: the sixth wrong password is refused and so is the correct one until the lock ends; the per-address and per-email limits hold across a restart; identical response and timing for a wrong password, a locked account and an unknown email; the limits still apply with `RATE_LIMIT_ENABLED=false` and with passkeys off.

### Decisions

| Question | Decided (13 Oct 2026) |
|---|---|
| Second step | Passkey (device fingerprint, face or PIN; a USB key also works) for every operator. `PLATFORM_PASSKEY_REQUIRED=false` switches it off, and sign-in is then email and password only, super-admins included. No authenticator-app codes. |
| Hard delete | Anonymisation with a second approver. A soft-deleted user is purged after 30 days. The retention periods still need confirming with a legal adviser. |
| Impersonation | In scope, with the limits in section 5.2 (time-boxed, read-only by default, banner, both identities logged, account's Admins notified). |
| Scope | Kept. An ordinary operator sees every account (`scope_account_ids` empty). Scoping is used only for a partner or reseller login, which sees its own customers. |
| Host | Inside the customer app for now, built to move to its own `admin.` host by configuration (section 1.2). The app is on `tally-portal-one.vercel.app` only, so passkeys are registered for that address and re-registered through a planned hand-over when the console moves. |
