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
- [ ] In `backend/.env`, add `PLATFORM_ADMIN_EMAILS=` with the sign-in email of each person who runs this server, comma-separated (for example `PLATFORM_ADMIN_EMAILS=you@example.com`). Only they can start a sync against the server's own Tally (`TALLY_URL`, "Sync now" in Admin), because that Tally belongs to one customer. Being an Admin of an account is not enough, since anyone who signs up from the sync agent is the Admin of their own account. Backups no longer depend on it: each company's sync agent makes them (section 12).
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
- [ ] Backups: the checks are in section 12.
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

## 12. Backups made by the sync agent

Each company's sync agent backs the company up from the Tally on its own PC: every hour while the company is open in Tally, and when an Admin presses "Back up now" on the Backup page. Each backup is kept in two places, on the Tally PC and on the server. Both keep every backup from today and, for each of the previous 7 days, only the last one of that day; older ones are deleted. The newest backup is always kept, so a PC that was switched off for a fortnight still leaves one. A backup holds every group, currency, ledger, cost category and centre, unit, attendance type, stock group, category and item, godown, voucher type and voucher, as Tally exports them. It is not a copy of Tally's data folder.

The server no longer reaches Tally for backups. The old Backup & Restore module (`backend/backup_module`) and the server-wide daily schedule are no longer part of the app.

### Set it up

- [ ] Where the server keeps uploaded backups: with no setting, in a folder beside the project, named after it. For a project in `/srv/MyTally` that is `/srv/MyTally-backups`; it is made on the first upload. A redeploy that replaces the project folder leaves it alone. To keep them somewhere else, for example a mounted volume, add `BACKUP_STORAGE_DIR=/data/mytally-backups` to `backend/.env`. In a container, the folder beside the project is inside the container and is lost when the container is replaced, so set `BACKUP_STORAGE_DIR` to a mounted volume there. If the server cannot write the folder, the agent's upload is refused with a message naming the folder and this setting.
- [ ] Space: up to about 31 backups per company (24 from today, 7 earlier days), each about the size of the company's XML export, zipped. Look at the size of the first backup on the Backup page and multiply.
- [ ] If a proxy sits in front of the backend, it must let through request bodies of at least 5 MB: the agent uploads in 4 MB pieces. In nginx: `client_max_body_size 8m;` on the API's `location`.
- [ ] Restart the backend. The tables `company_backups` and `company_restores` are made on start.
- [ ] Update the agent on each Tally PC to a build that includes backups (section 5 for how).
- [ ] On each Tally PC, choose where it keeps its backups: in the agent, Settings → Backups → **Choose folder…**. A folder on a drive other than the one Windows is on is safest. Until a folder is chosen nothing is backed up, and the health line reads "Backups wait: choose a folder for them in Settings". Choosing another folder later moves the backups already made into it.

### Check it worked

- [ ] Open Backup in the app as an Admin and press "Back up now". Within a few minutes a row appears with today's time, "Backed up now", and the number of ledgers and vouchers. Compare those with the counts in TallyPrime.
- [ ] In the agent's log: `Backing up 'ABC Corp' (manual)`, then `Backup of 'ABC Corp' made in Ns: … ledgers, … vouchers`, then `Backup … stored on the server`.
- [ ] Press Download and open the ZIP: `manifest.json` names the company and its counts, with one XML file per kind of master and the vouchers in one or more `vouchers_….xml` files.
- [ ] Leave the agent running for two hours: two hourly rows appear.
- [ ] Sign in as an Admin of another account: the Backup page shows only that account's company and none of these backups.

### Restore (off until checked)

Restore writes a backup back into the same company in Tally. Each master and voucher is sent as Tally exported it, with `ACTION="Alter"`. It brings back what the backup holds; it does not remove what was added since. Safeguards:
- It only goes into the company the backup was taken from.
- It refuses when the copy of the books open in Tally differs from the one backed up.
- The person must type the company's name.
- Before writing anything, the agent backs up the company as it is and stores that backup on the server ("Before a restore"). That backup is the way back.

Tally matches imported records loosely, and an Alter that matches nothing can create a second record. So restore stays off (`BACKUP_RESTORE_ENABLED=false`) until one round trip has been checked on a test company:

- [ ] In TallyPrime, make a test company (not a customer's) with a few ledgers, a stock item and some vouchers. Link it in the agent and let it sync.
- [ ] Press "Back up now" and wait for the row.
- [ ] In TallyPrime, change the test company: alter the amount of one voucher, delete another voucher, rename one ledger, and add a new voucher.
- [ ] On the server only, set `BACKUP_RESTORE_ENABLED=true` and restart. With the test company selected in the app, press Restore on the backup, type the name and confirm.
- [ ] Within a minute the agent logs `Restore of '…' asked for`, makes the "Before a restore" backup, and writes. When it finishes, the page lists the restore under Recent restores.
- [ ] In TallyPrime, check the test company record by record:
  - **Altered voucher:** has its old amount, and there is still only one of it.
  - **Deleted voucher:** if it is back, note its voucher number.
  - **Renamed ledger:** see whether Tally now has two ledgers, one under the old name and one under the new. If it does, restore must not be switched on for customers as it is.
  - **New voucher:** is still there. Restore does not remove what was added since.
  - **Duplicates:** no voucher appears twice. Compare the voucher count with the backup's count plus the vouchers added since.
- [ ] Restore the "Before a restore" backup the same way. The company must return to the state after your changes.
- [ ] Send me what you found. Only if every check holds, keep `BACKUP_RESTORE_ENABLED=true`. Otherwise set it back to `false` and restart.

### If something goes wrong

| What you see | What to do |
|---|---|
| A "Back up now" row says "Not made: Tally did not answer the export of …" | Tally was busy or closed. Open the company in TallyPrime and press "Back up now" again. |
| "Not made: Tally exported no groups for '…'" | The company named was not the one open in Tally. Check the company is open, and only once. |
| "Not made: Tally exported N of the company's M vouchers" | Tally left vouchers out. Nothing partial was kept. Try again; if it repeats, send me the agent's log. |
| Rows stay at "Uploading from the Tally PC…" | The PC cannot reach the server or the proxy refuses 4 MB requests (see Set it up). The backup is safe on the PC and uploads when it can. Requests and uploads that never finish are cleared after 2 days. |
| A restore stays "being written" for hours | The PC stopped part-way (switched off, Tally closed). After 6 hours "Close a stuck restore" closes it as failed. Check the company in TallyPrime; the "Before a restore" backup is kept. |
| A restore failed with "different copy of the books" | The company open in Tally is a copy or another year's company with the same identity. Open the right one, then ask for the restore again. |

### The old module's files

- [ ] Backups made by the old module are in `backend/backup_module/backups/` on the server (and its records in `backend/backup_module/backup.db`). They are not shown in the app any more. Copy out any you want to keep before deleting that folder.

## 13. Plans, pricing and billing (Phases 0–7)

The full design is in `docs/Pricing and Billing Implementation Plan.md`. This section lists the deployed billing subsystems and the exact manual steps for environment configuration and rollout.

### What is implemented across phases

1. **Phase 0: Stop the leak:**
   - Client-side and mock payment verifications disabled.
   - `BILLING_CHECKOUT_ENABLED` flag added to `app/core/config.py` (defaults to `False`).
2. **Phase 1: Catalog & Quote Engine:**
   - 13 relational billing tables in `app/models/billing.py`.
   - Idempotent `seed_catalog(db)` seeds Silver, Gold, Diamond and add-ons.
   - Pure integer-paise quote engine (`app/services/billing/quote.py`) calculating itemised GST splits (CGST+SGST vs. IGST).
3. **Phase 2: Subscriptions & Entitlements:**
   - Automatic `ensure_legacy_subscription(db, account_id)` preserves all existing accounts as `legacy` (unlimited, no expiration).
   - Signups receive a 7-day Gold trial (`start_trial`).
   - Dynamic entitlements cache (60s TTL) with invalidation hooks.
   - Limit checks wired to entitlements in `team.py` (users) and `agent.py` (devices & companies).
4. **Phase 3: Prepaid Checkout & Gateways:**
   - Direct HTTP adapters for Razorpay and Cashfree without external SDK dependencies.
   - Idempotent order fulfilment with transaction locks and webhook de-duplication.
   - Dynamic JS gateway script loader (`src/lib/loadScript.ts`) in Next.js frontend.
   - Dual-gateway checkout with fallback to WhatsApp concierge in `PlanCheckoutModal.tsx`.
5. **Phase 4: GST Invoicing & Profiles:**
   - Sequential financial-year invoice numbering (`MT/2627/00001`, credit notes `MTCN/2627/00001`) with database row locks. GST allows at most 16 characters, so each prefix is at most 5.
   - GSTIN format validation (15-character alphanumeric regex) and buyer billing profile endpoints (`GET|PUT /billing/profile`).
   - Tenant-isolated invoices list and detail endpoints (`GET /billing/invoices`).
6. **Phase 5: Lifecycle & 402 Full Lock:**
   - Background worker `billing_lifecycle_worker(300)` runs every 5 minutes in FastAPI lifespan.
   - State progression: `trialing` → `active` → `grace` (7 days) → `locked`.
   - 402 Payment Required interceptor in `permissions.py` with `X-Billing-State: locked` header on business routes. Exempt routes: `/auth/*`, `/billing/*`, `/platform/*`, `/health`, and notification counts.
   - Desktop sync agent pauses sync for 15 minutes when receiving 402, preserving Tally data intact.
   - Dedicated `/billing/locked` page in frontend with auto-redirect from `AuthContext.tsx`.
7. **Phase 6: Operator Console:**
   - Mounted at `/platform/billing/*`, protected by `require_platform_admin`.
   - Real-time business metrics (`/platform/billing/metrics`), accounts listing, plan assignment, bespoke custom plan creation, manual overrides, lock/unlock, offline payment recording, leads, and webhook logs.
8. **Phase 7: Feature Gating:**
   - `require_feature(...)` dependency applied across:
     - `backend/app/routers/gst.py` (`einvoice_eway_bill`)
     - `backend/app/routers/bank_recon.py` (`bank_reconciliation`)
     - `backend/app/routers/approvals.py` (`approval_rules_matrix`)
     - `backend/app/routers/visits.py` and `orders.py` (`salesman_checkin_orders`)
     - `backend/app/routers/reminders.py` (`auto_payment_reminders`)
     - `backend/app/routers/payment_gateway.py` (`payment_links_collect`)
   - Returns 403 Forbidden with `X-Billing-Reason: feature` and `X-Billing-Required-Feature`.
   - Frontend `UpgradePromptModal` intercepts 403 globally and displays an upgrade modal with value propositions and direct links to `/pricing`.
9. **Phase 8: Monthly Autopay & Recurring Billing (only partly built: no mandate is ever created with a gateway, so it is switched off by `BILLING_AUTOPAY_ENABLED=false`; see "Autopay stays off" below):**
   - Seeded monthly prices with `autopay_allowed=True`.
   - Recurring charge webhooks (`subscription.charged`, `SUBSCRIPTION_CHARGED`) create an automatic `BillingOrder(purpose="autopay_charge")`, extend period by 30 days, and issue sequential GST tax invoice.
   - Recurring charge failure webhooks (`subscription.halted`, `SUBSCRIPTION_PAYMENT_FAILED`) transition the subscription to a 7-day `grace` period without immediate locking.
   - User cancellation endpoint `POST /billing/subscription/autopay/cancel` sets `cancel_at_period_end = True` and `autopay = False` while keeping current term valid.
10. **Phase 9: Prorated Upgrades & Metered Pack Credits:**
    - Proration math in quote engine: when upgrading an active paid subscription, unused days in the current term (`(days_left / total_days) * term_price`) are automatically computed and credited (`proration_credit_paise`).
    - Append-only credit ledger (`billing_credit_ledger`) with atomic balance aggregations (`get_credit_balance`, `grant_credits`, `consume_credits`).
    - Supports `einvoice` credits (IRN / E-Way bill generation) and `whatsapp` credits (Meta Cloud API utility messages).
    - Credit allocations fulfilled automatically when ordering add-on packs (`credit_pack`).

---

### Settings to make before anyone can pay

All of these go in `backend/.env`. The names are the ones the code reads (`app/core/config.py`); a name that is
not listed here is ignored.

#### 1. Who issues the invoice (required)

There are no defaults. Until the legal name and a real GSTIN are set, nothing can be sold: online checkout
stays closed and the operator's "record offline payment" is refused, so that no invoice ever carries made-up
seller details.

```env
BILLING_SELLER_NAME=<registered legal name>
BILLING_SELLER_GSTIN=<15-character GSTIN>
BILLING_SELLER_STATE_NAME=<state, as on the registration>
BILLING_SELLER_ADDRESS=<registered address, one line>
BILLING_SELLER_EMAIL=<billing email shown on invoices>
BILLING_SELLER_PHONE=<phone shown on invoices>
# Optional. The state code is taken from the first two digits of the GSTIN unless set here.
# BILLING_SELLER_STATE_CODE=
# BILLING_INVOICE_PREFIX=MT       (at most 5 characters: GST invoice numbers are limited to 16)
# BILLING_CREDIT_NOTE_PREFIX=MTCN
```

- [ ] `GET /billing/plans` shows `"checkout_enabled": false` while any of name, GSTIN or a gateway's keys is missing, whatever `BILLING_CHECKOUT_ENABLED` says.

#### 2. Payment gateways

A gateway is offered at checkout only when both of its values are set.

```env
BILLING_RAZORPAY_KEY_ID=rzp_live_...
BILLING_RAZORPAY_KEY_SECRET=...
BILLING_RAZORPAY_WEBHOOK_SECRET=...

BILLING_CASHFREE_APP_ID=...
BILLING_CASHFREE_SECRET=...
BILLING_CASHFREE_ENV=production      # "sandbox" until you go live
```

- `RAZORPAY_WEBHOOK_SECRET` (without `BILLING_`) is a different setting: it belongs to the payment links a
  customer's own company sends, not to MyTally's subscriptions.
- Cashfree signs its webhooks with the same secret key as the API (`BILLING_CASHFREE_SECRET`); there is no
  separate webhook secret.
- Cashfree needs the buyer's 10-digit mobile number. A customer without one on their billing details is asked
  to add it; no stand-in number is sent.

#### 3. Webhook addresses in the gateway dashboards

- **Razorpay** → Settings → Webhooks
  - URL: `https://<your API host>/billing/webhooks/razorpay`
  - Secret: the value of `BILLING_RAZORPAY_WEBHOOK_SECRET`
  - Events: `payment.captured`, `order.paid`
- **Cashfree** → Developers → Webhooks
  - URL: `https://<your API host>/billing/webhooks/cashfree` (also sent with each order when `APP_PUBLIC_URL` is set)
  - Events: payment success

A webhook that cannot be carried out is answered 500, its error is kept on the event (operator console →
webhooks), and nothing it started is saved. The gateway's next delivery is tried again.

#### 4. Autopay stays off

```env
BILLING_AUTOPAY_ENABLED=false
```

Recurring debits need a mandate created with the gateway, and that is not built. While this is `false` an order
asking for autopay is refused, so nobody is told they are on autopay and then never charged. Do not switch it on.

#### 4a. The sales number customers are shown

```env
# Country code and number, digits only
BILLING_SALES_PHONE=919876543210
```

- [ ] Set it to the number the sales team answers, on WhatsApp too, and restart. The pricing page, the locked-account
  page, the checkout window and the subscription panel in Admin show it, and "Chat on WhatsApp" opens a chat with it.
  Until it is set, no number is shown anywhere and "Talk to sales" only saves the request (it appears under leads in
  the operator console) for the team to call back.

#### 5. Who may use the operator console

The console (`/console`) takes only its own operator sign-in (password plus passkey). A normal MyTally sign-in is
refused there, even for an email in `PLATFORM_ADMIN_EMAILS`. That list only names who becomes the first operator:

```env
PLATFORM_ADMIN_EMAILS=<comma-separated emails>
# Set once, from the deployment secret store, for the very first start; remove it after the first operator signs in.
PLATFORM_ADMIN_INITIAL_PASSWORD=<one-time password>
```

- [ ] On the first start with no operators, the first email in `PLATFORM_ADMIN_EMAILS` becomes the super admin with
  `PLATFORM_ADMIN_INITIAL_PASSWORD`. Sign in at `/console/login`, register a passkey, then remove
  `PLATFORM_ADMIN_INITIAL_PASSWORD` from `backend/.env` and restart. Further operators are invited from the console.
- [ ] Lost access: run `python scripts/break_glass.py` from the `backend` folder on the server.

#### 6. Real client addresses behind a proxy

Rate limits, operator sign-in lockouts, IP allowlists and audit logs use the caller's address. `X-Forwarded-For` is
believed only from the proxies in `TRUSTED_PROXY_IPS` (default `127.0.0.1,::1`: the Next.js `/console-api` rewrite and
an nginx on the same machine). From anyone else it is ignored, since a caller can write anything there.

- [ ] If a load balancer or nginx on another machine sits in front of the backend, add its address (or CIDR) to
  `TRUSTED_PROXY_IPS` in `backend/.env` and restart. Otherwise every request looks like it came from that proxy, and
  one person's failed sign-ins lock everyone out.

---

### How orders behave (for support)

- What an order is (new, renewal, upgrade, downgrade, add-on) is decided by the server from the account's
  subscription. It is never taken from the request.
- **Add-ons on their own** can be bought only while a paid term is running. They are charged for the days left
  in that term and never change the plan, the end date or the status.
- **Renewal** during a running term is added to its end and keeps the seats already paid for.
- **Upgrade** starts a new term now. The unused part of what was actually paid for the old term comes off the price.
- **Downgrade** is refused while the account has more active users or companies than the smaller plan allows.
  Otherwise it is paid now and takes over when the running term ends.
- The tax (CGST+SGST or IGST) follows the state on the account's saved billing profile. The invoice shows the
  same state.
- Customers are told in the app, and by email when a billing email is on file: on payment, 7, 3 and 1 days
  before a trial or a term ends, when grace starts, and when the account is locked.

---

### Going live (switching on self-serve checkout)

- [ ] From `backend/`: `venv/bin/pytest tests` passes.
- [ ] From `frontend-nextjs/`: `npm run build` passes.
- [ ] Existing customers are still unlimited and not locked:
  ```sql
  SELECT account_id, status, plan_id FROM account_subscriptions WHERE status <> 'legacy';
  ```
  Before launch this should list only accounts you put on a plan yourself and new sign-ups on trial.
- [ ] Sections 1 to 3 above are done, and a test purchase in each gateway's test mode produced a paid order, an
  active subscription and an invoice with your real seller details.
- [ ] Set `BILLING_CHECKOUT_ENABLED=true` in `backend/.env` and restart the backend.

### Not built yet

- Autopay mandates (see 4 above).
- Refunds and credit notes, and managing coupons and standard plans, from the operator console.
- Buying e-invoice and WhatsApp credit packs, and using the credits up.
