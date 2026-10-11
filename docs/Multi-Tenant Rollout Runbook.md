# Multi-Tenant Rollout Runbook

Last updated: 10 Oct 2026 (covers Phase 0 and Steps 1 to 6, and the test round of 10 Oct)

The steps to run by hand, in order, once development is complete. The design and the reasons are in `Multi-Tenant Working Plan.md`; this file is only what to do. Each development step that adds a manual action adds it here.

Status of each part:

| Part | Needs a manual step? | In this runbook |
| --- | --- | --- |
| Phase 0: explicit sync company, accounts | Deploy, in a set order | Sections 2 to 5 |
| Step 1: schema expansion | No: startup creates it | Section 3 |
| Step 2: move existing data into one account | Yes: one script | Section 4 |
| Step 3: agent sign-up and device tokens | Yes: two settings, and signing the PC in | Sections 3, 5 and 6 |
| Step 4: multi-company agent | Only when you add a second company | Section 7 |
| Step 5: app switcher and last synced | Deploy the web app; checks only | Sections 3 and 6 |
| Step 6: enforce and harden | Yes: one setting now, three later | Sections 3 and 8 |

## 1. Before you start

- [ ] Until the new backend is live, do not switch company in the web app on the login the sync agent uses.
- [ ] Pick a quiet time: nobody entering vouchers, agent idle.
- [ ] Back up both databases. The names come from `backend/.env`: the portal database is the one in `DATABASE_URL` (`tally_portal` on this machine) and the Tally mirror is `TALLY_DATABASE_NAME` (`tally_sync`).

```bash
mysqldump -u <user> -p --single-transaction --routines tally_portal > tally_portal_before_accounts.sql
```

```bash
mysqldump -u <user> -p --single-transaction --routines tally_sync > tally_sync_before_accounts.sql
```

- [ ] Keep both files until two weeks after the last step in this runbook.

## 2. Merge

- [ ] Review and merge the pull request: https://github.com/Akashkansal065/tally-portal/pull/67

## 3. Deploy the backend (before the agent)

- [ ] In `backend/.env`, check the email settings are there: `SMTP_USER` and `SMTP_PASS` (a Gmail app password: 16 letters, made at myaccount.google.com/apppasswords; the normal Gmail password is refused). Sign-up codes and invitations are sent with them. Without them, creating an account fails with "The verification email could not be sent".
- [ ] In `backend/.env`, add `APP_PUBLIC_URL=` with the address people open the app at (for example `https://app.yourdomain.com`). Invitation emails link to it. Without it the email carries a code to paste instead.
- [ ] If `TALLY_URL` is set in `backend/.env` (the server reaches Tally directly, for example through a tunnel), pin it to the company it belongs to: add `TALLY_URL_COMPANY_ID=` with that company's MyTally id. The migration script in section 4 lists each company as `#<id> 'name'`; use the number after `#`. Only that company's changes are then sent to this Tally; every other company's wait for its own sync agent. Prefer the id over `TALLY_URL_COMPANY_GUID`: anyone who signs up can give a company of theirs the same GUID, but not the same id. (A GUID pin still works, and only the earliest company with that GUID uses the Tally.) Without either, only the server's first account and the companies from before accounts use it, and the backend log warns once a second account exists.
- [ ] In `backend/.env`, add `PLATFORM_ADMIN_EMAILS=` with the sign-in email of each person who runs this server, comma-separated (for example `PLATFORM_ADMIN_EMAILS=you@example.com`). Only they can open Backup & Restore and the daily backup schedule, because those act on every customer's books. Being an Admin of an account is no longer enough, since anyone who signs up from the sync agent is the Admin of their own account. Without this line nobody can use backups: the backup page answers "Only the people who run this server can do this", and the Daily backup card does not appear. The scheduled backup itself keeps running with the settings it already has.
- [ ] In the startup log, look for lines beginning `Auto Schema Synchronizer:`. They list each column and index it adds. New tables (`accounts`, `agent_devices`, `agent_company_links`, `company_sync_state`, `user_invites`, `signup_verifications`) are created silently.
- [ ] Confirm there is no line beginning `Warning during auto schema sync`.
- [ ] The first start on this version also prints `Device-session times moved from UTC to IST.` once. It moves the stored sign-in times so they match the rest of the app; nobody is signed out. It must not appear on later starts.
- [ ] The same first start prints `N shared currencies given to each company as its own.` once. Currencies were one list for the whole server; each company now gets its own copy, and its exchange rates, ledgers and voucher entries follow it. Nothing to run by hand. To confirm: `SELECT company_id, COUNT(*) FROM currencies GROUP BY company_id;` shows the same count for every company and no row with a NULL company. If it stops halfway, start the server again; it finishes without making second copies.
- [ ] Sign in to the web app and open a ledger and a voucher. Nothing should look different.

- [ ] Deploy the web app (the Vercel project). The Android and iOS apps load the web app from there, so they pick up the change without a new app build.

The old agent keeps working against the new backend. The backend log will show a warning that the agent "names no Tally company"; that is expected until section 5.

## 4. Move the existing data into one account

Run from the `backend` folder on the machine the backend runs on, with the same `.env` the backend uses. The script creates no user and deletes nothing. It must be this machine: the same script run elsewhere migrates whatever database that machine's `.env` points to.

- [ ] Look first. This saves nothing:

```bash
./venv/bin/python scripts/migrate_to_account.py
```

- [ ] Read the output:
  - "What is there now" should list your one company and all your users.
  - "What would change" should show every company, user and role being given the account, and every admin under "admins".
  - No line starting with `!`.
- [ ] Do it:

```bash
./venv/bin/python scripts/migrate_to_account.py --apply
```

- [ ] It must print `Saved.` and then one `added` line per foreign key (nine in all). A `STOP` line means that key was not added; send me the line.
- [ ] It then prints two `done` lines for roles: role names become unique inside an account instead of across the server. A second customer cannot sign up until this has run.
- [ ] "Still to deal with" will list your company as having no Tally GUID. That is expected: signing the PC in (section 5) gives it the GUID.
- [ ] If it lists duplicate Tally GUIDs, leave them. They are handled in Step 6 and block nothing before it.

To give the account a different name than the company's: add `--name "Your Business Name"`. Running the script again later is safe; it changes nothing the second time.

## 5. Deploy the agent (after the backend)

- [ ] Get the agent's `.exe`. Either download it from GitHub (Actions, "Sync agent exe", the latest run's Artifacts; or the Release, if an `agent-v...` tag was pushed), or build it: on a Windows PC, in `desktop-sync-agent\installer\`, run `build_windows_exe.bat`. The result is `desktop-sync-agent\dist\SnehDistribuorsSync.exe` (the file keeps this name; a build that includes the redesigned window opens as "MyTally Bridge"). The script also installs `pywebview` for the new window; if that fails it says so and the build opens the older-style window, with the same sync. The script needs a 64-bit Intel/AMD Python with tkinter (not the ARM64 one, even on an ARM PC); if there is none it says so and offers to install it. Its failure cases are listed in `desktop-sync-agent/README.md`.
- [ ] The new window needs Microsoft's Edge WebView2 Runtime on the Tally PC. Windows 11 has it; on Windows 10 look for "Microsoft Edge WebView2 Runtime" under Installed apps and, if it is missing, install the Evergreen one from Microsoft. Without it the agent still runs, in the older-style window.
- [ ] Close the running agent on the Tally PC, replace the `.exe`, start it again. The existing `agent_config.json` is kept, and the agent keeps syncing on the old login for now.
- [ ] Sign the PC in. With the company open in Tally, open the agent's sign-in screen (Settings, then "Sign in as someone else"), enter an admin's email and password, and press "Sign in and start syncing" ("Connect & Start Sync" in a build with the old window). The agent signs in as this PC, links the company and returns to the dashboard. From then on it stores no password.
- [ ] The company name in Tally must match the company's name in the app (capitals and spaces at the ends do not matter). That is how the first sign-in finds your existing company and gives it its Tally GUID. If the names differ, rename the company in the app first (Company profile), or the sign-in adds a second company.
- [ ] If it says "This server's data has not been moved into an account yet", section 4 has not been run on the backend's machine.
- [ ] If it says "You are not allowed to use the sync agent", that person is not an admin, or an admin removed their permission.
- [ ] If it asks "Move sync to this PC?", another PC is syncing the company. Answer Yes only if this PC should take over.
- [ ] In the agent log, the next cycle should sync as before.
- [ ] A full sync now sends vouchers in date ranges of about 50 each ("Vouchers sent per request in a full re-sync" under Advanced in the agent's Settings; "Vouchers per Full Sync Range" in an older build), a few each cycle: the log shows `Full sync of N vouchers planned in M date ranges` and the status line `Full sync 3 of 12`. It finishes over several cycles and survives a restart. If the log says `This Tally does not return vouchers by date range`, it has gone back to one export, as before; send me that line.

## 6. Check it worked

- [ ] With the agent running, switch company in the web app (if you have more than one) or sign in on a second device. The agent's log should show no change of company and no errors.
- [ ] Create a test voucher in the app and confirm it reaches Tally in the right company.
- [ ] Change something in Tally and confirm it appears in the app within a minute or two.
- [ ] In the backend log, the "names no Tally company" warning should have stopped.
- [ ] Run the script from section 4 once more without `--apply`. It must list one company (not two with the same name), and that company must now show a GUID.
- [ ] In the web app, open Admin → Sync agent & team. The PC should be listed as signed in, syncing your company, and every admin should be ticked under "Who may use the sync agent".
- [ ] Untick any admin who should not be able to use the sync agent.
- [ ] Admins now get three kinds of alert in the bell: a company no PC syncs any more, a company not synced for a day, and a request from outside the business that was refused. Each comes at most once a day per company. Sync alerts can be turned off under Notifications → System; the refused-request one cannot.
- [ ] Invite a test user from that tab, open the link in a private browser window, set a password and sign in. Then try that user's email in the agent's Setup screen: it must be refused.
- [ ] Signed in as a person listed in `PLATFORM_ADMIN_EMAILS`, open Backup: the list of backups and the Daily backup card appear. Signed in as an Admin who is not listed: the backup page refuses and there is no Daily backup card.
- [ ] If `TALLY_URL` is set: create a test ledger in the company named by `TALLY_URL_COMPANY_ID` and confirm it reaches the server's Tally. If you have a second account (for example the test account from the invitation check), create a ledger there too: it must **not** appear in the server's Tally, and it stays queued for that account's own sync agent. In the backend log there must be no warning beginning `TALLY_URL is set but not pinned to a company`.

- [ ] The company name in the header should have a green dot within a couple of minutes of the agent syncing. Tap the name: the list shows each company with "Synced … ago".
- [ ] Stop the agent for four minutes: the dot turns grey and the list says "Sync agent offline since …". Start it again.
- [ ] Close the company in Tally with the agent running: within a couple of minutes the list says "Open this company in Tally to sync", and Reports shows a "Data as of …" line.
- [ ] Open Companies from the menu: one card per company with the same status.
- [ ] If you have two companies: switch from the phone, and confirm the laptop stays in the company it was in.

For a new customer later, nothing here is needed. Sign-up is no longer in the agent: once mobile number sign-in is switched on (section 10), they create their account in the app with their mobile number, then install the agent and choose "Connect with a code from the app". Until section 10 is done there is no way for a new customer to sign up by themselves.

## 7. Adding a second company (any time after section 6)

Nothing needs doing until you want a second Tally company in the app.

- [ ] Make sure section 4 has been run: field-sales rows (orders, visits, payments, expenses) need their company filled in before a second company exists, or old rows will appear under whichever company their owner has open.
- [ ] Open both companies in TallyPrime on the PC running the agent.
- [ ] In the agent, press Companies. The new company is listed as "Open in Tally · not synced". Press Link.
- [ ] The first sync of the new company starts at once. For a large company this can take a while and holds up the other company until it finishes; do it outside working hours.
- [ ] In the web app, the new company appears in the company switcher for admins. Give other users access from Admin → Users.
- [ ] If two companies with the same name are open in Tally, the agent syncs neither and says so. Close the one that should not be synced.

To stop syncing a company from this PC, press Unlink beside it in the same window. Its data in the app stays.

## 8. Switching enforcement on (a week or more after section 6)

Do this only when sections 1 to 6 are done and everything has run normally for a while. It makes the database itself refuse rows with no owner and duplicate Tally records. Pick a quiet time: making a key unique on the vouchers table can take minutes and holds the table while it runs.

- [ ] Back up both databases again (section 1).
- [ ] Look first. This changes nothing:

```bash
./venv/bin/python scripts/migrate_to_account.py --enforce
```

- [ ] If it says "Not ready to enforce", run the script without `--enforce` first (section 4), then try again.
- [ ] Read the plan. Lines starting `would` are what it will do. A line starting `STOP` names a key that still has duplicate rows: it will be skipped, and everything else still goes ahead.
- [ ] If there are `STOP` lines for Tally records, merge the duplicates. Look first, then apply, then run the `--enforce` look again:

```bash
./venv/bin/python scripts/migrate_to_account.py --merge-duplicates
```

```bash
./venv/bin/python scripts/migrate_to_account.py --merge-duplicates --apply
```

  It keeps the copy Tally changed last, points everything at it and removes the other from the app's database only. Nothing is sent to Tally. A `STOP` line here means that pair could not be merged and was left alone; send it to me.
- [ ] Do it:

```bash
./venv/bin/python scripts/migrate_to_account.py --enforce --apply
```

- [ ] In `backend/.env`, add `ACCOUNTS_ENFORCED=true` and restart the backend. Sign in and check you still see your company.
- [ ] When every sync agent PC has been updated and signed in (section 5), add `REQUIRE_AGENT_DEVICE_SIGNIN=true` and restart. An agent still on the old login is then refused and told to update.
- [ ] Run the script once more with `--enforce`: every line should now start with `ok`.

## 9. If something goes wrong

| Problem | What to do |
| --- | --- |
| Backend will not start after deploying | Redeploy the previous version. The new columns and tables are ignored by the old code. |
| The migration script prints `Refused` | Nothing was changed. Send me the message. |
| The migration script stops with `Unknown column '….companies.account_id'` | Nothing was changed. The database in `backend/.env` has not had the new backend started on it yet, so the new columns are missing. Do section 3 against that database (start the backend once and check the `Auto Schema Synchronizer:` lines), then run the script again. Also check `DATABASE_URL` names the database you mean to migrate. |
| The migration script fails on Windows with "No time zone found with key Asia/Kolkata" | Run `python -m pip install -r requirements.txt` in `backend`: Windows needs the `tzdata` package. And check you are on the backend's machine (section 4). |
| After signing the PC in there are two companies with the same name | The name in Tally did not match the name in the app, so a second company was added. Stop the agent and send me the output of the section 4 script; the two have to be joined by hand. |
| The migration script prints `NOT saved` | Nothing was changed. The lines starting with `!` say why. |
| Users cannot see their company after section 4 | Run the script again without `--apply` and check every user shows the same account as the company. |
| Agent log says a range `could not be pushed (HTTP 524 …)` or timed out during a full sync | The server did not finish importing that range before the proxy in front of it gave up (Cloudflare waits 100 seconds). An agent built before the evening of 10 Oct 2026 sends 500 vouchers a range and repeats the failed one forever: rebuild the `.exe` (section 5) and replace it. The new one sends about 50 a range, and plans the rest of a half-done full sync again by itself. If it still times out, lower "Vouchers sent per request in a full re-sync" (Settings, Advanced). Nothing needs doing on the server; a range that arrives twice is stored once. |
| Agent log says `the server is still importing this company's previous sync` | Not a fault. The server takes one import per company at a time and refuses a second while the first runs (usually the range a 524 was returned for, still being stored). The agent sends it again next cycle; nothing is lost and nothing is stored twice. If it goes on for more than a few minutes, a second backend is running on the same database (a local `uvicorn` with `.env` pointing at production, for one): stop it. |
| Agent started from the command line says `Another SnehDistribuors Sync Agent is already running on this PC` | The window version is running (system tray). One agent per PC; quit one of them. |
| Agent stops syncing after section 5 | Put the previous `.exe` back. The new backend still accepts the old agent. |
| Agent says "This PC is signed out of the sync agent" | Someone signed it out in Admin → Sync agent & team, or the person who signed it in was deactivated. Sign in again from Setup. |
| Agent or app says a company is "a different copy of the books" | The company open in Tally has the same identity as the synced one but a different Tally company number or books-from date: a copy or a restored backup. Open the right one. If the company really was moved or restored on purpose, press Unlink beside it in the agent's Companies window, then Link. |
| Agent says a company "is not open in Tally" | Open it in TallyPrime. The other linked companies keep syncing meanwhile. |
| Agent says "Two companies named ... are open" | Close the copy that should not be synced. |
| The header dot stays grey "No sync agent has connected this company yet" | The agent on that PC is older than Step 4, or has not finished a cycle yet. Update it and wait one minute. |
| After switching company the app shows the old company | The device was not allowed to open the one chosen (access was removed). It falls back to the person's own company. |
| After `ACCOUNTS_ENFORCED=true` someone cannot see a company | That person or company has no account. Remove the setting, restart, run the script in section 4 again, then put it back. |
| An agent says "This sync agent must be updated and signed in again" | `REQUIRE_AGENT_DEVICE_SIGNIN` is on and that PC is still on the old login. Update it and sign in from Setup, or remove the setting for now. |
| "Create your account in the MyTally app with your mobile number" when registering | The old web registration is removed on purpose. New businesses sign up on the login screen with a mobile number (section 10); people join by invitation. |
| Sign-up or invitation email never arrives | Look for the backend log line "could not be emailed". "Gmail rejected the login" or "Connection unexpectedly closed" means `SMTP_PASS` is not an app password: make one at myaccount.google.com/apppasswords for the `SMTP_USER` account (2-Step Verification must be on), put its 16 letters in `backend/.env` without spaces, and restart. The admin can copy the invitation link from the screen meanwhile. |
| You need to undo section 4 completely | Restore `tally_portal` from the backup taken in section 1. |

## 10. Mobile number sign-in with an OTP (off until you switch it on)

People can sign in, and a new business can sign up, with a mobile number and an SMS code, next to email and password. Firebase Authentication sends and checks the code; the server only checks the proof Firebase hands back. It stays off, and the login screen shows email and password only, until both the server flag and the web app's Firebase settings below are in place. Sign-up has been removed from the sync agent, so this is how a new business gets an account.

Firebase console (project `mytally-b8ef2`, the one already used for push):

- [ ] Authentication → Sign-in method → enable **Phone**.
- [ ] Authentication → Settings → Authorized domains: add the domain people open the app on (`tally-portal-one.vercel.app`, and any custom domain). `localhost` is there already. The Android and iOS apps load that same website, so they need nothing more.
- [ ] For testing without SMS: Authentication → Sign-in method → Phone → "Phone numbers for testing". Add a number and a fixed 6-digit code (for example `+91 99999 00001` / `123456`). These never send an SMS and cost nothing. Do not use a real person's number.
- [ ] Real SMS: check Usage and billing in the Firebase console before relying on it. Depending on the project's plan, Firebase may refuse to send real SMS until billing is set up, and the app then says "SMS codes are not switched on for this app yet". Test numbers work either way.
- [ ] Project settings → General → Your apps: if there is no Web app, add one. Copy `apiKey`, `projectId` and `appId` from its config.

Backend (`backend/.env`, then restart):

- [ ] `PHONE_SIGNIN_ENABLED=true`
- [ ] `FIREBASE_PROJECT_ID=mytally-b8ef2`. Not needed if `FCM_SERVICE_ACCOUNT_JSON` is already set for that project.
- [ ] New tables `user_phones` and `agent_pairings` are created silently at startup, and the startup log shows `Auto Schema Synchronizer: Adding missing column 'awaiting_tally'` for `companies`. Nothing to run by hand.
- [ ] `GET /auth/phone/status` should answer `{"enabled": true}`.

Web app (Vercel → Project → Settings → Environment Variables, then redeploy; for local work, `frontend-nextjs/.env.local`):

- [ ] `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID` from the Web app config above. These are public values, not secrets. They are read when the site is built, so a redeploy is needed after setting them.

Sync agent:

- [ ] Rebuild and replace the `.exe` (section 5). The new one has no "Create an account"; its first screen offers "Connect with a code from the app" and "Sign in with email and password". PCs already signed in are not affected.

Check it worked:

- [ ] Open the login screen: it now starts on "Mobile number", with "Sign in with email and password" underneath. An existing email login must still work.
- [ ] Enter a test number, press Send code, enter its fixed code. A new number is asked for name, business name, pin code and optional email, then lands on **Connect Tally**.
- [ ] On the Tally PC, open the agent, choose "Connect with a code from the app" and press "Get a code". Enter that code on Connect Tally, confirm the PC name, press "Connect this PC". Within a few seconds the agent opens its Companies page with the company open in Tally linked.
- [ ] In the app, the business now shows the Tally company's name: the empty company the account started with has become it, not a second one.
- [ ] Sign out and sign in again with the same number: no details are asked, and it goes straight to the app.
- [ ] A new business cannot leave Connect Tally until a PC is connected: opening any other page brings it back, and the only other choice is "Sign in with a different account".
- [ ] Invite a second test number: Admin → Sync agent & team → Invite someone, fill in only "Mobile number". No link is produced. Sign in with that number in a private window: after the code it says "You have been invited to join ..." and asks only for a name. That person is not held at Connect Tally.
- [ ] Invite an email: open the link in a private window. It offers "Confirm your mobile number" first and "Use a password instead" underneath. An invitation with both an email and a mobile number can only be accepted by confirming that number.

To switch it off again: set `PHONE_SIGNIN_ENABLED=false` and restart. The login screen goes back to email and password only. People who signed up with only a mobile number cannot sign in while it is off (they have no password); their data is untouched.

| What you see | What to do |
|---|---|
| Login screen still shows only email and password | Either the server flag is off (`/auth/phone/status` says `false`) or the three `NEXT_PUBLIC_FIREBASE_*` values were not set when the site was built. Set them and redeploy. |
| "This website is not allowed to send codes yet" | The domain is missing from Firebase's Authorized domains. |
| "Sign-in with a mobile number is not switched on for this app yet" | The Phone provider is not enabled in Firebase. |
| "The mobile number could not be confirmed" after a correct code | The web app and the server point at different Firebase projects. `FIREBASE_PROJECT_ID` must be the project of the `NEXT_PUBLIC_FIREBASE_*` values. |
| Agent says "This server does not offer sign-in with a code yet" | The backend is older than this change. Deploy the backend first. |
| Connect Tally says "That code is wrong or has expired" | Codes last 10 minutes and belong to the PC that shows them. Press "Get a new code" in the agent. |
| Connect Tally says "You are not allowed to use the sync agent" | The person is not ticked under Admin → Sync agent & team → "Who may use the sync agent". |

## 11. Company profile edits sent to Tally (a trial)

Editing the company profile in the app (header → company details) now sends the changed values to Tally through the agent: address, state, country, pincode, telephone, mobile, email, website, GSTIN and PAN. The company name, the books and financial-year dates and the UPI ID are never sent. It is not yet known whether TallyPrime accepts a company alteration this way, so the app checks: the sync after the push reads the profile back from Tally and compares.

- [ ] Deploy the backend. Nothing to migrate.
- [ ] Update the agent on the Tally PC (the new build also reads back Tally's phone and mobile numbers; an older agent still sends edits, but telephone and mobile will be reported as not taken).
- [ ] Take a Tally backup of the company, then change one value in the app, for example the pincode.
- [ ] Wait for two syncs, then look at the company in TallyPrime (F11/Alt+K → Alter) and at the `sync_queue` row with `record_type = 'Company'`:

| What the row says | What it means |
|---|---|
| `status = SUCCESS`, `snapshot_data.verified = true` | Tally took the edit. |
| `status = FAILED`, `error_message` "Tally did not take: …" | Tally ignored those values. The app shows Tally's value again after the sync. Change it in TallyPrime. |
| `is_processed = 0` for many syncs | Tally rejected the request outright; the reason is in the agent's log ("Tally Rejected Company"). |

If every field fails, the trial has its answer: make the profile read-only in the app and keep Tally as the only place to change it.
