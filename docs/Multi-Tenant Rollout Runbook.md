# Multi-Tenant Rollout Runbook

Last updated: 10 Oct 2026 (covers Phase 0 and Steps 1 to 3)

The steps to run by hand, in order, once development is complete. The design and the reasons are in `Multi-Tenant Working Plan.md`; this file is only what to do. Each development step that adds a manual action adds it here.

Status of each part:

| Part | Needs a manual step? | In this runbook |
| --- | --- | --- |
| Phase 0: explicit sync company, accounts | Deploy, in a set order | Sections 2 to 5 |
| Step 1: schema expansion | No: startup creates it | Section 3 |
| Step 2: move existing data into one account | Yes: one script | Section 4 |
| Step 3: agent sign-up and device tokens | Yes: two settings, and signing the PC in | Sections 3, 5 and 6 |
| Step 4: multi-company agent | Not built yet | To be added |
| Step 5: app switcher and last synced | Not built yet | To be added |
| Step 6: enforce and harden | Not built yet | To be added |

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

- [ ] In `backend/.env`, check the email settings are there: `SMTP_USER` and `SMTP_PASS` (a Gmail app password). Sign-up codes and invitations are sent with them. Without them, creating an account fails with "The verification email could not be sent".
- [ ] In `backend/.env`, add `APP_PUBLIC_URL=` with the address people open the app at (for example `https://app.yourdomain.com`). Invitation emails link to it. Without it the email carries a code to paste instead.
- [ ] Deploy the backend from `master` and start it once.
- [ ] In the startup log, look for lines beginning `Auto Schema Synchronizer:`. They list each column and index it adds. New tables (`accounts`, `agent_devices`, `agent_company_links`, `company_sync_state`, `user_invites`, `signup_verifications`) are created silently.
- [ ] Confirm there is no line beginning `Warning during auto schema sync`.
- [ ] Sign in to the web app and open a ledger and a voucher. Nothing should look different.

The old agent keeps working against the new backend. The backend log will show a warning that the agent "names no Tally company"; that is expected until section 5.

## 4. Move the existing data into one account

Run from the `backend` folder, with the same `.env` the backend uses. The script creates no user and deletes nothing.

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
- [ ] If "Still to deal with" lists a company with no Tally GUID, do a full sync from the agent after section 5 (Sync All in the agent window).
- [ ] If it lists duplicate Tally GUIDs, leave them. They are handled in Step 6 and block nothing before it.

To give the account a different name than the company's: add `--name "Your Business Name"`. Running the script again later is safe; it changes nothing the second time.

## 5. Deploy the agent (after the backend)

- [ ] On a Windows PC, in `desktop-sync-agent\installer\`, run `build_windows_exe.bat`. The result is `desktop-sync-agent\dist\SnehDistribuorsSync.exe`.
- [ ] Close the running agent on the Tally PC, replace the `.exe`, start it again. The existing `agent_config.json` is kept, and the agent keeps syncing on the old login for now.
- [ ] Sign the PC in. With the company open in Tally, open the agent's Setup screen (from Settings), enter an admin's email and password, and press Connect & Start Sync. The agent signs in as this PC, links the company and returns to the dashboard. From then on it stores no password.
- [ ] If it says "You are not allowed to use the sync agent", section 4 has not been run, or that person is not an admin.
- [ ] If it asks "Move sync to this PC?", another PC is syncing the company. Answer Yes only if this PC should take over.
- [ ] In the agent log, the next cycle should sync as before.

## 6. Check it worked

- [ ] With the agent running, switch company in the web app (if you have more than one) or sign in on a second device. The agent's log should show no change of company and no errors.
- [ ] Create a test voucher in the app and confirm it reaches Tally in the right company.
- [ ] Change something in Tally and confirm it appears in the app within a minute or two.
- [ ] In the backend log, the "names no Tally company" warning should have stopped.
- [ ] In the web app, open Admin → Sync agent & team. The PC should be listed as signed in, syncing your company, and every admin should be ticked under "Who may use the sync agent".
- [ ] Untick any admin who should not be able to use the sync agent.
- [ ] Invite a test user from that tab, open the link in a private browser window, set a password and sign in. Then try that user's email in the agent's Setup screen: it must be refused.

For a new customer later, nothing here is needed: they install the agent, press "New here? Create an account for your business" on the Setup screen, and enter the code emailed to them.

## 7. If something goes wrong

| Problem | What to do |
| --- | --- |
| Backend will not start after deploying | Redeploy the previous version. The new columns and tables are ignored by the old code. |
| The migration script prints `Refused` | Nothing was changed. Send me the message. |
| The migration script prints `NOT saved` | Nothing was changed. The lines starting with `!` say why. |
| Users cannot see their company after section 4 | Run the script again without `--apply` and check every user shows the same account as the company. |
| Agent stops syncing after section 5 | Put the previous `.exe` back. The new backend still accepts the old agent. |
| Agent says "This PC is signed out of the sync agent" | Someone signed it out in Admin → Sync agent & team, or the person who signed it in was deactivated. Sign in again from Setup. |
| Sign-up or invitation email never arrives | Check `SMTP_USER` / `SMTP_PASS` and the backend log line "could not be emailed". The admin can copy the invitation link from the screen instead. |
| You need to undo section 4 completely | Restore `tally_portal` from the backup taken in section 1. |
