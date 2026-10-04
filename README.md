# MyTally — Tally Prime Cloud Portal

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

- **Two-way Tally sync.** Incremental (AlterID-based) inbound import of masters and vouchers. Cloud-created ledgers, vouchers, stock items and so on go through an outbound queue and are acknowledged once Tally accepts them. Traffic logs, retry, conflict compare and deleted-record audits.
- **Accounting.** Ledgers and groups, all voucher types (sales, purchase, receipt, payment, contra, journal, debit/credit notes, inventory vouchers), bill-wise outstanding and ageing, bank reconciliation, cost centres, currencies and TDS.
- **Inventory.** Stock groups, categories, items, units, godowns, price lists and BOM.
- **Reports.** Dashboard KPIs, P&L and balance-sheet style summaries, sales trends, debtors and creditors, dead-stock analysis, and PDF/Excel exports.
- **GST.** GSTR summaries, HSN summary, 2B reconciliation, and a pluggable GST provider adapter.
- **Field force.** GPS attendance with geofencing and a background location trail (native Android foreground service), shop check-ins, order capture, payment collection with photo proof, expenses, and a visit planner.
- **Admin.** Multi-company tenancy, role-based permissions with per-user overrides and data scopes (ledger, stock and voucher-type restrictions), maker-checker approval rules, and web push notifications.
- **Payments.** Razorpay payment links with webhook auto-receipting, and UPI.
- **Backup.** Tally master and voucher backup/restore module (`backend/backup_module/`).

## Repository layout

```text
tally-portal/
├── backend/                    FastAPI service (Python)
│   ├── app/
│   │   ├── main.py             App factory: lifespan, middleware, router registration
│   │   ├── core/               Config, DB engine, auth/RBAC, cache, rate limiter, seed data
│   │   ├── models/             SQLAlchemy models: portal_core.py (portal schema), tally_core.py (tally schema)
│   │   ├── routers/            One module per domain (auth, ledgers, vouchers, sync, attendance, gst, ...)
│   │   ├── schemas/            Pydantic request/response models + Tally object definitions (JSON)
│   │   └── services/           Tally XML importer/builder, GST, geo, ImageKit, attendance worker
│   ├── backup_module/          Tally backup & restore (mounted at /backup)
│   ├── scratch/                One-off admin/maintenance scripts (reset, wipe, compare, daemon)
│   ├── tests/e2e_vouchers/     End-to-end voucher round-trip scripts (need a running stack)
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
| Tally Prime | 3.0+ with the XML server on port 9000 | open `http://127.0.0.1:9000` on the Tally PC | Live sync (optional for UI work) |
| JDK 17/21 + Android SDK | API 34+ | `javac -version`, `echo $ANDROID_HOME` | Building the Android APK (optional) |
| Xcode | 16+ | `xcodebuild -version` | Building iOS (optional, macOS only) |

**To enable the Tally XML server**, open Tally Prime and go to **F1 Help → Settings → Connectivity → Client/Server configuration**. Set *TallyPrime acts as* = **Both** and *Port* = **9000**, then restart Tally.

Environment variables are listed in [Environment variables](#environment-variables). The minimum to boot the backend is `DATABASE_URL` and `JWT_SECRET`.

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

Open <http://localhost:3000>.

### 5. Create the first admin and company

The system has no default user. On a fresh database the **login page detects bootstrap mode** (`GET /auth/bootstrap-status`) and shows a "Register company" form. The first registration creates:

- the company (with its default Tally groups and voucher types seeded),
- an **Admin** user,
- that user's access to the company.

After the first admin exists, public registration is locked. Only admins can add companies (Admin → Companies) or users (Admin → Users).

You can also bootstrap from the terminal:

```bash
curl -X POST http://127.0.0.1:8000/auth/register-company \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"Demo Traders","books_begin_date":"2026-04-01","financial_year_start":"2026-04-01","username":"admin","email":"admin@example.com","password":"change-me-now"}'
```

### 6. Connect Tally (optional)

Pick **one** of these:

**A. Desktop Sync Agent (recommended, works when the backend is in the cloud).** On the Windows PC running Tally:

```bash
cd desktop-sync-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python gui_app.py
```

In the GUI, enter the backend URL (e.g. `http://192.168.1.20:8000`), your MyTally email and password, and the Tally host (`http://127.0.0.1:9000`). Click **Auto-Detect Company**, then **Save**. The agent syncs Tally → cloud every 60 s and cloud → Tally every 5 s.

Headless alternatives:

```bash
python agent.py --discover
```

```bash
python agent.py --sync-all
```

```bash
python agent.py
```

To build a standalone `.exe` (no Python needed on the client), run `installer\build_windows_exe.bat`. The output is `desktop-sync-agent/dist/`.

**B. Direct backend → Tally.** Only works if the backend can reach Tally's port (same LAN or a tunnel). Set `TALLY_URL=http://<tally-pc-ip>:9000` in `backend/.env` and restart the API. Creates and edits are then pushed to Tally in real time, and **Sync → Run once** in the UI pulls data.

### 7. Android app (optional)

The native shell loads the web app from `CAPACITOR_SERVER_URL`, or the production Vercel URL if that is unset. To test against your local machine, set `CAPACITOR_SERVER_URL=http://<your-LAN-IP>:3000` in `.env.local`, then:

```bash
cd frontend-nextjs
npm run build:apk
```

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

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
| `python tests/e2e_vouchers/run_all_vouchers_e2e.py` | End-to-end voucher round trips. **Needs the API running and Tally reachable.** Writes `e2e_voucher_trace_report.json` |
| `python scratch/check_sync_counts.py` | Compare row counts between Tally and the mirror |
| `python scratch/reset_sync.py` | ⚠️ Truncate synced vouchers and reset AlterIDs so the next sync is a full re-import |
| `python scratch/wipe_all.py` | ⚠️ Delete **all** data. Dev only |

> **Run the backend with one worker.** The response cache, auth/permission cache, sync lock, rate limiter and background workers (DB keep-alive, attendance auto-punch-out) all live in process memory. More workers means stale permissions, duplicate notifications and a sync lock that no longer serializes imports. See `architecture.md` → *Scaling constraints*.

### Desktop Sync Agent (`desktop-sync-agent/`)

| Command | What it does |
|---|---|
| `python gui_app.py` | GUI with tray icon |
| `python agent.py` | Headless daemon |
| `python agent.py --test-once` | One discovery + sync pass, then exit |
| `python agent.py --discover` | Detect the Tally host and open companies only |
| `python agent.py --sync-all` | Force a full (non-incremental) inbound sync |
| `python agent.py --install-startup` / `--uninstall-startup` | Toggle auto-start on Windows boot |

### Tests and CI

There's no unit-test suite yet. `backend/tests/e2e_vouchers/` holds integration scripts that need a live backend and Tally. GitHub Actions currently runs only OpenSSF Scorecard (`.github/workflows/scorecard.yml`). Before opening a PR, run at least `npm run lint`, `npx tsc --noEmit` and a manual smoke test of the screens you touched.

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
| `IMAGEKIT_PUBLIC_KEY` / `IMAGEKIT_PRIVATE_KEY` / `IMAGEKIT_URL_ENDPOINT` | | — | Photo uploads |
| `SMTP_USER` / `SMTP_PASS` | | — | Email |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL` | | — | Web push |
| `RAZORPAY_WEBHOOK_SECRET` | | — | Webhook signature verification. **Set this in any environment that exposes the webhook** |
| `DEFAULT_UPI_VPA` | | — | UPI QR payee |
| `GST_PROVIDER_URL` / `GST_PROVIDER_API_KEY` | | — | GST API adapter |
| `RATE_LIMIT_ENABLED`, `LOGIN_RATE_LIMIT`, `REGISTER_RATE_LIMIT` | | `true`, `5/minute`, `5/minute; 20/hour` | slowapi limits |
| `LOG_LEVEL`, `LOG_FORMAT` | | `INFO`, `text` | `json` for structured logs |

### `frontend-nextjs/.env.local` (template: `frontend-nextjs/.env.example`)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE` | Backend URL. A `localhost` value is swapped for the page's hostname at runtime, so LAN devices work |
| `NEXT_PUBLIC_IMAGEKIT_PUBLIC_KEY`, `NEXT_PUBLIC_IMAGEKIT_URL_ENDPOINT` | Client-side image URLs |
| `CAPACITOR_SERVER_URL` / `NEXT_PUBLIC_APP_URL` | URL the native shell loads |

### `desktop-sync-agent/agent_config.json`

This file is written by the GUI. Passwords and tokens are encrypted with a machine-bound key. **Don't commit it.** It's listed in `.gitignore`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Access denied for user` on backend start | `DATABASE_URL` credentials don't match `docker-compose.yml` (`root` / `rootpassword`) |
| `Can't connect to MySQL server` | `docker compose ps`, and wait about 20 s after first `up` for MySQL to initialize |
| Frontend shows network errors | Backend not on :8000, or `NEXT_PUBLIC_API_BASE` is wrong. Restart `npm run dev` after editing `.env.local` |
| CORS error from a new domain | Add the origin to `CORSMiddleware` in `backend/app/main.py` |
| Phone can't reach dev server | Run uvicorn with `--host 0.0.0.0`, use your LAN IP, and allow ports 3000/8000 through the OS firewall |
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
| [`docs/TALLY_CRASH_PREVENTION_GUIDE.md`](docs/TALLY_CRASH_PREVENTION_GUIDE.md) | Safe XML request patterns for Tally |
| [`docs/TallyPrime_API_Reference.md`](docs/TallyPrime_API_Reference.md) | Tally XML/JSON API reference |
| [`desktop-sync-agent/README.md`](desktop-sync-agent/README.md) | Agent features and packaging |
| [`SECURITY.md`](SECURITY.md) | Reporting vulnerabilities |

## License

MIT. See [`LICENSE`](LICENSE).
