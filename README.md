# MyTally — Tally Prime Cloud Portal

[![CI](https://github.com/Akashkansal065/tally-portal/actions/workflows/ci.yml/badge.svg)](https://github.com/Akashkansal065/tally-portal/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Akashkansal065/tally-portal/badge)](https://scorecard.dev/viewer/?uri=github.com/Akashkansal065/tally-portal)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Good first issues](https://img.shields.io/github/issues/Akashkansal065/tally-portal/good%20first%20issue?label=good%20first%20issues)](https://github.com/Akashkansal065/tally-portal/labels/good%20first%20issue)

MyTally (repo: `tally-portal`, mobile app: **SnehDist.**) puts a business's **Tally Prime** books in front of people who aren't sitting at the Tally desktop. It mirrors Tally's ledgers, inventory and vouchers into a cloud database, gives field staff and managers a web and mobile app on top of that data, and writes the changes they make back into Tally.

> **New here?** Read this file top to bottom, then [`architecture.md`](architecture.md) for how the parts fit together. Deep-dive references live in [`docs/`](docs/).

---

## Table of contents

1. [What problem does it solve?](#what-problem-does-it-solve)
2. [Core features](#core-features)
3. [Repository layout](#repository-layout)
4. [Prerequisites](#prerequisites)
5. [Setup from scratch](#setup-from-scratch)
6. [Usage and scripts](#usage-and-scripts)
7. [Environment variables](#environment-variables)
8. [Troubleshooting](#troubleshooting)
9. [Further documentation](#further-documentation)
10. [Contributing](#contributing)

---

## What problem does it solve?

Tally Prime is a desktop accounting package. Its data lives on one Windows PC, so everyone outside the office (salespeople, collection agents, owners on the move) has to phone the accountant for a balance, a stock count or an order status.

MyTally fixes this in three parts:

| Part | Runs on | Job |
|---|---|---|
| **Desktop Sync Agent** (`desktop-sync-agent/`) | The Windows PC running Tally | Talks to Tally's local XML server (`:9000`). It pushes Tally changes up to the cloud and pulls cloud-created records down into Tally. |
| **Backend API** (`backend/`) | A server or cloud VM | FastAPI + MySQL. Stores the Tally mirror plus portal-only data (attendance, orders, payments, RBAC), and serves the REST API. |
| **Web and mobile app** (`frontend-nextjs/`) | Vercel, plus Android/iOS via Capacitor | Next.js UI for accountants (desktop tables) and field staff (mobile cards, GPS, camera). |

## Core features

- **Two-way Tally sync.** Incremental (AlterID-based) inbound import of masters and vouchers. Large companies do their full sync in date ranges, a part each cycle, and resume after a restart. Cloud-created ledgers, vouchers, stock items and so on go through an outbound queue and are acknowledged once Tally accepts them. Every write carries an idempotency key, so a repeated request or a retried push never creates a second record. Traffic logs, retry, conflict compare and deleted-record audits.
- **Accounts and companies.** Each business is an account with its own companies, users, roles and settings, isolated from every other account on the server. One Sync Agent can sync several Tally companies, each bound to its Tally GUID, so data from the wrong company or a restored copy of the books is refused. The header shows each company's sync freshness, and each device remembers its own current company.
- **Onboarding.** A new business creates its account from the Sync Agent with an emailed verification code. Everyone else joins by email invitation (Admin → Sync agent & team). The Tally PC signs in as a device with its own token and stores no password.
- **Accounting.** Ledgers and groups, all voucher types (sales, purchase, receipt, payment, contra, journal, debit/credit notes, inventory vouchers), bill-wise outstanding and ageing, bank reconciliation, cost centres, per-company currencies, TDS and payroll masters.
- **Inventory.** Stock groups, categories, items, units, godowns, price lists and BOM.
- **Reports.** Dashboard KPIs, P&L and balance-sheet style summaries, trial balance, sales trends, debtors and creditors, dead-stock analysis, reporting periods, and PDF/Excel exports.
- **GST.** GSTR summaries, HSN summary, 2B reconciliation, and a pluggable GST provider adapter.
- **Field force.** GPS attendance with geofencing and a background location trail (native Android foreground service), shop check-ins that start attendance automatically, order capture with partial dispatch and a daily dispatch summary, payment collection with photo proof, expenses, and a visit planner.
- **Admin.** Role-based permissions with per-user overrides and data scopes (ledger, stock and voucher-type restrictions), maker-checker approval rules, web push notifications, and alerts when a company stops syncing or a request from outside the account is refused.
- **Device sessions.** Every login records the device it came from (phone app, browser, Sync Agent). Admins see each user's devices and every signed-in device in the company (Admin → Active Devices), sign any of them out, block a device from signing in again, and cap devices per role. Every user can review and sign out their own devices (menu → My Devices).
- **Payments.** Razorpay payment links with webhook auto-receipting, and UPI.
- **Backup.** Tally master and voucher backup/restore module (`backend/backup_module/`).

## Repository layout

```text
tally-portal/
├── backend/                    FastAPI service (Python)
│   ├── app/
│   │   ├── main.py             App factory: lifespan, middleware, router registration
│   │   ├── core/               Config, DB engine, auth/RBAC, tenancy, idempotency, cache, rate limiter, seed data
│   │   ├── models/             SQLAlchemy models: portal_core.py (portal schema), tally_core.py (tally schema)
│   │   ├── routers/            One module per domain (auth, agent, team, ledgers, vouchers, sync, attendance, gst, ...)
│   │   ├── schemas/            Pydantic request/response models + Tally object definitions (JSON)
│   │   └── services/           Tally XML importer/builder, GST, geo, ImageKit, alerts, sync status, attendance worker
│   ├── backup_module/          Tally backup & restore (mounted at /backup)
│   ├── scripts/                Rollout scripts (migrate_to_account.py: move existing data into an account)
│   ├── scratch/                One-off admin/maintenance scripts (reset, wipe, compare, daemon)
│   ├── tests/                  pytest suite (SQLite); e2e_vouchers/ holds round-trip scripts that need a running stack
│   └── requirements.txt
├── frontend-nextjs/            Next.js 16 + React 19 + Tailwind 4 app
│   ├── src/app/                App Router pages (one folder per screen)
│   ├── src/components/         Feature components + ui/ primitives (shadcn/Radix)
│   ├── src/context/            AuthContext (session, permissions), PeriodContext (FY range)
│   ├── src/lib/                API base, Capacitor bridges, PDF, offline storage, exports
│   ├── android/ ios/           Capacitor native shells (Android has a custom tracking service)
│   └── capacitor.config.ts
├── desktop-sync-agent/         Windows Tally connector (GUI + headless CLI, .exe builder)
├── docs/                       Tally API references, sync design notes, DB docs
├── docker-compose.yml          Local MySQL 8.0
└── architecture.md             System architecture (start here after this README)
```

---

## Prerequisites

| Tool | Version | Check | Needed for |
|---|---|---|---|
| Git | any recent | `git --version` | Cloning |
| Python | **3.12+** (3.14 is used in development) | `python3 --version` | Backend, sync agent |
| Node.js | **20.9+** (Next.js 16 requirement) | `node -v` | Frontend |
| npm | 10+ | `npm -v` | Frontend |
| Docker Desktop | any recent | `docker --version` | Local MySQL (or install MySQL 8 natively) |
| MySQL | **8.0** | `mysql --version` | Only if not using Docker |
| Tally Prime | 3.0+ with the XML server on port 9000 | open `http://127.0.0.1:9000` on the Tally PC | Creating the first account, and live sync |
| An SMTP login | Gmail app password | — | Sign-up codes and invitation emails |
| JDK 17/21 + Android SDK | API 34+ | `javac -version`, `echo $ANDROID_HOME` | Building the Android APK (optional) |
| Xcode | 16+ | `xcodebuild -version` | Building iOS (optional, macOS only) |

**To enable the Tally XML server**, open Tally Prime and go to **F1 Help → Settings → Connectivity → Client/Server configuration**. Set *TallyPrime acts as* = **Both** and *Port* = **9000**, then restart Tally.

Environment variables are listed in [Environment variables](#environment-variables). The minimum to boot the backend is `DATABASE_URL` and `JWT_SECRET`. Creating an account also needs `SMTP_USER` and `SMTP_PASS`.

---

## Setup from scratch

Every block below can be pasted as-is. Commands assume macOS/Linux with a bash/zsh shell. Windows equivalents are noted where they differ.

### 1. Clone

```bash
git clone https://github.com/Akashkansal065/tally-portal.git
cd tally-portal
```

### 2. Start MySQL

```bash
docker compose up -d db
```

This starts MySQL 8.0 on `localhost:3306` with root password `rootpassword` (see `docker-compose.yml`). You **don't** need to create the databases yourself. On first boot the backend creates both `mytally_db` and `tally_sync`.

<details>
<summary>Using a native MySQL instead</summary>

```sql
CREATE DATABASE IF NOT EXISTS mytally_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS tally_sync CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The user in `DATABASE_URL` needs full privileges on **both** schemas, because the backend joins across them.
</details>

### 3. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Generate a JWT secret and paste it into `backend/.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Start the API. On startup it creates both schemas, creates or extends every table, and seeds the default roles, modules and permissions:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check that it's up:

```bash
curl http://127.0.0.1:8000/health
```

- Swagger UI: <http://127.0.0.1:8000/docs>. Click **Authorize** and log in with your email and password.
- Binding to `0.0.0.0` lets phones on your Wi-Fi reach the API for mobile testing.

### 4. Frontend

In a second terminal:

```bash
cd frontend-nextjs
npm install
cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000>. There is nobody to sign in as yet: the next step creates the first account.

### 5. Create your account from the Sync Agent

The system has no default user, and there is no web registration (`POST /auth/register-company` answers 410). An account is created from the Desktop Sync Agent, together with its first company, which comes from the company open in Tally. Sign-up emails a verification code, so set `SMTP_USER` and `SMTP_PASS` in `backend/.env` first.

On the Windows PC running Tally, with the company open:

```bash
cd desktop-sync-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python gui_app.py
```

On the Setup screen, enter the backend URL (e.g. `http://192.168.1.20:8000`) and the Tally host (`http://127.0.0.1:9000`), then:

- **New business:** press **New here? Create an account for your business**, fill in the details and enter the code emailed to you. This creates the account, its **Admin** user, this PC's device and the first company in one step.
- **Existing account:** enter the email and password of someone who holds the **Manage sync agent** permission (admins do by default) and press **Connect & Start Sync**.

Either way the PC is then signed in as a device with its own token and keeps no password. The agent syncs Tally → cloud every 60 s and cloud → Tally every 5 s. Sign in to the web app with the same email and password.

The company's name in Tally must match its name in the app when an existing company is linked for the first time, otherwise a second company is added.

Headless runs, once the PC is signed in:

```bash
python agent.py --discover
```

```bash
python agent.py --sync-all
```

```bash
python agent.py
```

To build a standalone `.exe` (no Python needed on the client), run `installer\build_windows_exe.bat`. The output is `desktop-sync-agent/dist/SnehDistribuorsSync.exe`. The build needs a 64-bit Intel/AMD Python with tkinter (not the ARM64 one); the script checks for it and offers to install it.

### 6. Add people and more companies

- **People.** Invite them from Admin → Sync agent & team. The email links to the app's **Accept invite** page, where they set a password. Set `APP_PUBLIC_URL` so the email carries a link; without it the email carries a code to paste. The same tab lists the PCs signed in to the agent and who may use it.
- **A second Tally company.** Open it in TallyPrime on the agent's PC, press **Companies** in the agent and then **Link**. It appears in the app's company switcher for admins; give other users access from Admin → Users. **Unlink** stops syncing it from that PC and leaves its data in the app.
- **Direct backend → Tally (optional).** If the backend can reach Tally's port (same LAN or a tunnel), set `TALLY_URL=http://<tally-pc-ip>:9000` in `backend/.env` and restart the API. Creates and edits are then pushed to Tally in real time, and **Sync → Run once** in the UI pulls data. On a server holding more than one account, also set `TALLY_URL_COMPANY_GUID` so pushes go to that Tally for its own company only.

Upgrading a server that was set up before accounts existed is a manual, ordered procedure: follow [`docs/Multi-Tenant Rollout Runbook.md`](docs/Multi-Tenant%20Rollout%20Runbook.md).

### 7. Android app (optional)

The native shell loads the web app from `CAPACITOR_SERVER_URL`, or the production Vercel URL if that is unset. To test against your local machine, set `CAPACITOR_SERVER_URL=http://<your-LAN-IP>:3000` in `.env.local`, then:

```bash
cd frontend-nextjs
npm run build:apk
```

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

Plain-HTTP dev servers only work in **debug** builds. Release builds block cleartext traffic and WebView debugging, and only navigate within the production host. So build releases with `CAPACITOR_SERVER_URL` unset, or set to an `https://` URL.

For a signed release build, copy `android/key.properties.example` to `android/key.properties`, point it at your keystore, and run `npm run build:apk-release`. Never commit the keystore or `key.properties`.

For iOS (macOS only):

```bash
cd frontend-nextjs
npx cap sync ios
npx cap open ios
```

---

## Usage and scripts

### Frontend (`frontend-nextjs/`)

| Command | What it does |
|---|---|
| `npm run dev` | Next.js dev server on :3000 with hot reload |
| `npm run build` | Production build (`.next/`) |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (Next.js config) |
| `npx tsc --noEmit` | Type-check. Run this before pushing, because `next.config.ts` currently skips type errors at build time |
| `npm run cap:sync` | Copy web assets and plugins into the native projects |
| `npm run build:apk` | Debug Android APK |
| `npm run build:apk-release` | Signed release APK (needs `android/key.properties`) |

### Backend (`backend/`, with venv active)

| Command | What it does |
|---|---|
| `uvicorn app.main:app --reload --port 8000` | Dev server |
| `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` | Production-style run (see the single-worker note below) |
| `python -m app.core.seed` | Re-seed global roles, modules and permissions (idempotent; also runs on every startup) |
| `pip install -r requirements.txt` then `pytest` | Automated tests (account isolation, agent sign-up and company binding, idempotency, Tally identity, voucher sync, device sessions, caching, alerts, cleanup and more). Use throwaway SQLite databases and never touch the database in `.env` |
| `python scripts/migrate_to_account.py` | Rollout only: show what moving existing data into one account would change. `--apply` saves it; `--enforce` and `--merge-duplicates` are the later steps. Repeat-safe. Follow the [rollout runbook](docs/Multi-Tenant%20Rollout%20Runbook.md) |
| `python tests/e2e_vouchers/run_all_vouchers_e2e.py` | End-to-end voucher round trips. **Needs the API running and Tally reachable.** Writes `e2e_voucher_trace_report.json` |
| `python scratch/check_sync_counts.py` | Compare row counts between Tally and the mirror |
| `python scratch/reset_sync.py` | ⚠️ Truncate synced vouchers and reset AlterIDs so the next sync is a full re-import |
| `python scratch/wipe_all.py` | ⚠️ Delete **all** data. Dev only |

> **Run the backend with one worker.** The response cache, auth/permission cache, sync lock, rate limiter location-ping guard and background workers (DB keep-alive, attendance auto-punch-out, daily cleanup) all live in process memory. More workers means stale permissions, duplicate notifications and imports of different companies running at the same time. One thing does hold across processes: a company's import from the Sync Agent takes a MySQL named lock, so a second import of the same company is refused (HTTP 409, `sync_in_progress`) instead of running alongside the first. See `architecture.md` → *Scaling constraints*.

### Desktop Sync Agent (`desktop-sync-agent/`)

| Command | What it does |
|---|---|
| `python gui_app.py` | GUI with tray icon |
| `python agent.py` | Headless daemon |
| `python agent.py --test-once` | One discovery + sync pass, then exit |
| `python agent.py --discover` | Detect the Tally host and open companies only |
| `python agent.py --sync-all` (or `--full-sync`) | Force a full (non-incremental) inbound sync |
| `python agent.py --config <path>` | Use a config file other than `agent_config.json` next to the agent |
| `python agent.py --install-startup` / `--uninstall-startup` | Toggle auto-start on Windows boot |
| `pip install -r requirements.txt` then `pytest tests` | Agent tests (company binding, multi-company sync, date-range full sync, safe Tally writes, sign-out handling, inbound retry) against a fake backend |

### Tests and CI

Automated suites: `backend/tests/` (run `pytest` from `backend/`) and `desktop-sync-agent/tests/` (run `pytest tests` from `desktop-sync-agent/`). `backend/tests/e2e_vouchers/` holds older integration scripts that need a live backend and Tally. GitHub Actions runs both suites, a frontend type-check, and ESLint on the lines each pull request changes (`.github/workflows/ci.yml`), plus OpenSSF Scorecard weekly. See [`CONTRIBUTING.md`](CONTRIBUTING.md#run-the-checks) for running the same checks locally.

---

## Environment variables

### `backend/.env` (template: `backend/.env.example`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | `mysql+aiomysql://user:pass@host:3306/<portal_db>`. The DB name becomes the portal schema |
| `JWT_SECRET` | ✅ | — | HMAC key for access tokens |
| `TALLY_DATABASE_NAME` | | `tally_sync` | Schema holding the Tally mirror (same server) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | `43200` (30 d) | Session lifetime |
| `DB_SSL` | | `false` | TLS to MySQL. Put the CA at `backend/ca.pem` to verify it |
| `TALLY_URL` | | — | Enables direct backend → Tally push |
| `TALLY_URL_COMPANY_GUID` | | — | Tally GUID of the company `TALLY_URL` belongs to. Set it on a server holding more than one account, so direct pushes are made for that company only |
| `IMAGEKIT_PUBLIC_KEY` / `IMAGEKIT_PRIVATE_KEY` / `IMAGEKIT_URL_ENDPOINT` | | — | Photo uploads |
| `SMTP_USER` / `SMTP_PASS` | | — | Email, including sign-up codes and invitations. For Gmail, `SMTP_PASS` must be an app password |
| `APP_PUBLIC_URL` | | — | Address people open the app at. Used for the link in invitation emails; without it the email carries a code to paste |
| `ACCOUNTS_ENFORCED` | | `false` | Rollout switch. Turn on after `scripts/migrate_to_account.py --enforce --apply`: a row with no account then belongs to nobody |
| `REQUIRE_AGENT_DEVICE_SIGNIN` | | `false` | Rollout switch. Turn on once every agent PC has signed in as a device: an agent still using a person's email and password is refused |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL` | | — | Web push |
| `RAZORPAY_WEBHOOK_SECRET` | | — | Webhook signature verification. **Set this in any environment that exposes the webhook** |
| `DEFAULT_UPI_VPA` | | — | UPI QR payee |
| `GST_PROVIDER_URL` / `GST_PROVIDER_API_KEY` | | — | GST API adapter |
| `RATE_LIMIT_ENABLED`, `LOGIN_RATE_LIMIT`, `REGISTER_RATE_LIMIT` | | `true`, `5/minute`, `5/minute; 20/hour` | slowapi limits |
| `LOG_LEVEL`, `LOG_FORMAT` | | `INFO`, `text` | `json` for structured logs |
| `DEVICE_LIMIT_POLICY` | | `evict_oldest` | When a role's device limit is reached: `evict_oldest` signs out the least recently used device, `refuse` rejects the new login |
| `SESSION_PURGE_EXPIRED_AFTER_DAYS`, `SESSION_PURGE_REVOKED_AFTER_DAYS` | | `30`, `90` | Daily cleanup of old login sessions |
| `SYNC_LOG_PURGE_SUCCESS_AFTER_DAYS` | | `30` | Daily cleanup of successful sync traffic logs (failed ones stay until cleared) |

### `frontend-nextjs/.env.local` (template: `frontend-nextjs/.env.example`)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE` | Backend URL. A `localhost` value is swapped for the page's hostname at runtime, so LAN devices work |
| `NEXT_PUBLIC_IMAGEKIT_PUBLIC_KEY`, `NEXT_PUBLIC_IMAGEKIT_URL_ENDPOINT` | Client-side image URLs |
| `CAPACITOR_SERVER_URL` / `NEXT_PUBLIC_APP_URL` | URL the native shell loads |

### `desktop-sync-agent/agent_config.json`

This file is written by the GUI. Passwords and tokens go into the OS credential vault (Windows Credential Manager) and the file only stores references to them. **Don't commit it.** `.gitignore` covers `agent_config.json` at any depth. See `desktop-sync-agent/agent_config.example.json` for the shape.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Access denied for user` on backend start | `DATABASE_URL` credentials don't match `docker-compose.yml` (`root` / `rootpassword`) |
| `Can't connect to MySQL server` | `docker compose ps`, and wait about 20 s after first `up` for MySQL to initialize |
| Frontend shows network errors | Backend not on :8000, or `NEXT_PUBLIC_API_BASE` is wrong. Restart `npm run dev` after editing `.env.local` |
| CORS error from a new domain | Add the origin to `CORSMiddleware` in `backend/app/main.py` |
| Phone can't reach dev server | Run uvicorn with `--host 0.0.0.0`, use your LAN IP, and allow ports 3000/8000 through the OS firewall |
| "Accounts are created from the Desktop Sync Agent" when registering | Web registration is removed on purpose. See [step 5](#5-create-your-account-from-the-sync-agent) |
| "The verification email could not be sent", or an invitation never arrives | `SMTP_USER` / `SMTP_PASS` are missing or `SMTP_PASS` isn't a Gmail app password. The backend log line "could not be emailed" gives the reason |
| Agent says "You are not allowed to use the sync agent" | That person lacks **Manage sync agent**. An admin grants it in Admin → Sync agent & team |
| Agent says "This PC is signed out of the sync agent" | It was signed out in Admin → Sync agent & team, or the person who signed it in was deactivated. Sign in again from Setup |
| Agent says a company is "a different copy of the books" | The company open in Tally is a copy or restored backup of the synced one. Open the right one, or Unlink then Link if the move was deliberate |
| Header dot stays grey for a company | No agent has synced it recently: the agent is stopped, outdated, or the company isn't open in Tally |
| Agent log says "the server is still importing this company's previous sync" | Not an error. The server refuses a second import of a company while one is running; the agent sends it again next cycle. If it never clears, another backend is running against the same database |
| "Another SnehDistribuors Sync Agent is already running on this PC" | One agent per PC, window or command line. Quit the other one from the system tray |
| Agent says "Tally Offline" | Tally isn't running, the XML server isn't enabled, or the port isn't 9000 |
| Sync imported nothing | Normal when nothing changed (AlterID unchanged). Use **Sync All** to force a full import |
| Location trail stops on Android | Set battery optimization to **Unrestricted** for the app (Xiaomi, Vivo, Oppo and Samsung kill background services) |

---

## Further documentation

| Doc | Topic |
|---|---|
| [`architecture.md`](architecture.md) | Components, interactions, data flow, tech stack, scaling constraints |
| [`docs/TALLY_SYNC_FLOW.md`](docs/TALLY_SYNC_FLOW.md) | Sync engine internals |
| [`docs/TALLY_DISTRIBUTED_SYNC.md`](docs/TALLY_DISTRIBUTED_SYNC.md) | Agent ↔ cloud protocol |
| [`docs/DATABASE_DOCUMENTATION.md`](docs/DATABASE_DOCUMENTATION.md) | Table-by-table schema reference |
| [`docs/ERP_FEATURES_DOCUMENTATION.md`](docs/ERP_FEATURES_DOCUMENTATION.md) | Feature-level walkthrough |
| [`docs/Multi-Tenant Rollout Runbook.md`](docs/Multi-Tenant%20Rollout%20Runbook.md) | Manual steps, in order, for moving an existing server to accounts |
| [`docs/Multi-Tenant Working Plan.md`](docs/Multi-Tenant%20Working%20Plan.md) | Design and reasons behind accounts, agent devices and company binding |
| [`docs/Device Session Control.md`](docs/Device%20Session%20Control.md) | Device sessions, blocking and per-role device limits |
| [`docs/TALLY_CRASH_PREVENTION_GUIDE.md`](docs/TALLY_CRASH_PREVENTION_GUIDE.md) | Safe XML request patterns for Tally |
| [`docs/TallyPrime_API_Explorer_Reference.md`](docs/TallyPrime_API_Explorer_Reference.md) | Tally XML/JSON API reference |
| [`desktop-sync-agent/README.md`](desktop-sync-agent/README.md) | Agent features and packaging |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Setting up, running checks, opening a pull request |
| [`SECURITY.md`](SECURITY.md) | Reporting vulnerabilities |

## Contributing

Contributions are welcome, and most of them don't need Tally Prime or MySQL: the backend tests run on SQLite. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md), then pick an issue labelled [good first issue](https://github.com/Akashkansal065/tally-portal/labels/good%20first%20issue). Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT. See [`LICENSE`](LICENSE).
