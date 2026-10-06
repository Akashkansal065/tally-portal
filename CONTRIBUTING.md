# Contributing to MyTally

Thanks for wanting to help. MyTally puts Tally Prime accounting data in front of people who aren't sitting at the Tally PC: a FastAPI backend, a Next.js web and mobile app, and a Windows sync agent. Contributions of every size are welcome, from fixing a typo to building a feature.

**You don't need Tally Prime, MySQL or a Windows PC for most work.** The backend test suite runs on throwaway SQLite databases, and the web app runs against a local backend.

## Table of contents

1. [Find something to work on](#find-something-to-work-on)
2. [Set up your environment](#set-up-your-environment)
3. [Make your change](#make-your-change)
4. [Run the checks](#run-the-checks)
5. [Open a pull request](#open-a-pull-request)
6. [Working with Tally](#working-with-tally)
7. [Reporting bugs and security issues](#reporting-bugs-and-security-issues)

---

## Find something to work on

- [**good first issue**](https://github.com/Akashkansal065/tally-portal/labels/good%20first%20issue): small, well-scoped tasks with the files to touch listed in the issue.
- [**help wanted**](https://github.com/Akashkansal065/tally-portal/labels/help%20wanted): bigger tasks where outside help is especially welcome.
- Found a bug or have an idea? [Open an issue](https://github.com/Akashkansal065/tally-portal/issues/new/choose) first, so we can agree on the approach before you write code.

**Claim an issue** by commenting "I'd like to work on this". If there's been no activity for two weeks, it's fair game for someone else.

## Set up your environment

The full setup (MySQL, mobile builds, Tally connection) is in the [README](README.md#setup-from-scratch). Pick the smallest setup that covers your change:

| You're changing | You need |
|---|---|
| Backend logic, with tests | Python 3.14 (what CI and development use). No database, see below |
| Web UI | Node.js 20.9+, plus a running backend (README steps 2–5) |
| Desktop Sync Agent logic | Python 3.14. Its tests use a fake backend and a fake Tally |
| Android/iOS shell | README step 7 |
| Docs only | Nothing, just edit the Markdown |

### Fork and clone

```bash
git clone https://github.com/<your-username>/tally-portal.git
```

```bash
cd tally-portal
git remote add upstream https://github.com/Akashkansal065/tally-portal.git
```

### Backend (tests only, no MySQL)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest
```

The test harness (`backend/tests/conftest.py`) forces `DATABASE_URL` to an unreachable dummy and runs the real models and routers on SQLite. Tests never touch the database in your `.env`.

### Frontend

```bash
cd frontend-nextjs
npm install
cp .env.example .env.local
npm run dev
```

> **Next.js 16 note:** this project uses Next.js 16 and React 19, which have breaking changes compared to older versions. If an API looks unfamiliar, check `node_modules/next/dist/docs/` before guessing.

## Make your change

1. Sync with upstream and create a branch:

   ```bash
   git fetch upstream && git checkout -b fix/short-description upstream/master
   ```

2. Keep the pull request focused. One bug fix or one feature per PR is much quicker to review than a bundle.
3. Write code that reads like the code around it: same naming, same structure, same comment density.
4. **Add or update tests** for backend and sync agent changes. Look at an existing file in `backend/tests/` for the pattern; `conftest.py` provides a `harness` fixture (fresh SQLite databases plus helpers for creating companies and users) and the `login()` / `bearer()` helpers for authenticated requests.
5. Update docs (README, `architecture.md`, `docs/`) if you change setup steps, environment variables or behaviour users see.

### Things to know before you start

- **The backend runs as a single worker.** Caches, the sync lock, the rate limiter and background jobs live in process memory. Read `architecture.md` → *Scaling constraints* before touching any of them.
- **Two database schemas.** Portal data (`app/models/portal_core.py`) and the Tally mirror (`app/models/tally_core.py`) live in separate schemas on the same server, and queries join across them.
- **Permissions are enforced on the server.** A new endpoint needs a permission check, not just a hidden button in the UI. See how existing routers use `app/core/permissions.py`.
- **Never commit secrets or real business data**: no `.env`, `agent_config.json`, keystores, Firebase keys, or Tally exports from a real company. Use made-up names like "Demo Traders" in tests and screenshots.

### Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```text
fix(attendance): stop auto punch-out running twice after restart
feat(gst): add HSN-wise summary export
docs: explain how to run backend tests without MySQL
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`. The scope is optional but helpful (`backend`, `frontend`, `agent`, `sync`, `gst`, …).

## Run the checks

CI runs these on every pull request. Running them locally first saves a round trip.

| Area | Command (from the folder shown) |
|---|---|
| Backend tests | `backend/`: `pytest` |
| Sync agent tests | `desktop-sync-agent/`: `pytest tests` |
| Frontend type-check | `frontend-nextjs/`: `npx tsc --noEmit` |
| Frontend lint | `frontend-nextjs/`: `python3 ../.github/scripts/lint_changed_lines.py upstream/master` |

**About lint:** the codebase still has older ESLint errors (mostly `no-explicit-any`) that are being cleaned up gradually. So CI only fails on errors in **lines your PR adds or edits**, and the existing errors in a file you touch won't block you. Fixing a few of them while you're there is always appreciated, and doing that cleanup on its own is a good first contribution (see the issues labelled `good first issue`).

For UI changes, also click through the screens you touched, on a narrow (phone-width) window as well as a desktop one.

## Open a pull request

1. Push your branch to your fork and open a PR against `master`.
2. Fill in the PR template: what changed, why, how you tested it, and screenshots for UI changes.
3. Link the issue with `Fixes #123` so it closes automatically.
4. CI must be green. If it fails for a reason unrelated to your change, say so in the PR.
5. A maintainer will review, usually within a week. Expect some back-and-forth, which is normal and not a sign the PR is unwelcome.

Draft PRs are welcome if you want early feedback.

## Working with Tally

If your change builds or sends XML to Tally Prime (`backend/app/services/`, `desktop-sync-agent/tally_client.py`), read [`.agents/rules/tally-safety-rules.md`](.agents/rules/tally-safety-rules.md) first. Some requests make Tally open a modal error dialog, and **Tally's XML server then freezes until someone clicks OK on the Tally PC**. In short:

- Export data with `<TYPE>Collection</TYPE>` requests, never UI reports such as *Day Book* with `<TYPE>Data</TYPE>`.
- Never send `<SYSTEM TYPE="Formulae">`.
- Filter and aggregate in Python, not in TDL.

[`docs/TALLY_CRASH_PREVENTION_GUIDE.md`](docs/TALLY_CRASH_PREVENTION_GUIDE.md) and [`docs/TallyPrime_API_Reference.md`](docs/TallyPrime_API_Reference.md) have the details. If you don't have Tally, say so in your PR and a maintainer will test the change against a real instance.

## Reporting bugs and security issues

- **Bugs and feature ideas:** use the [issue templates](https://github.com/Akashkansal065/tally-portal/issues/new/choose).
- **Security vulnerabilities:** don't open a public issue. Follow [`SECURITY.md`](SECURITY.md).

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).
