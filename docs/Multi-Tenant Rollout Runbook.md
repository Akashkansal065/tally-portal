# Multi-Tenant Rollout Runbook

Manual steps and real-TallyPrime checks that go with each change. Add to this with every change that needs one.

## Tally integration review v2, Phase 0 (P0.2, P0.3, P0.4)

### Deploy

1. Deploy the backend first, then release the agent. Nothing to run by hand: `sync_queue` gains `failure_kind` and
   `verified_guid`, and the new `sync_events` table is created, by the startup schema sync
   (`auto_sync_all_model_schemas`). Check both exist after the first start.
2. An older agent against the new backend still works; it never sees `address` and sends as before. A **new** agent
   against an **older** backend holds back every name-addressed master delete (no `address`, so nothing to check
   against) and the server does not take `/sync/events` or `/sync/needs-review` (404, ignored). Deploy in the order above.

### Behaviour to know

* **Held items.** A ledger delete/rename whose Tally object is not the one MyTally means, and a ledger whose group is
  missing, are set aside: `sync_queue.failure_kind = 'needs_review'`, `status = 'NEEDS_REVIEW'`, `error_message` says
  why, `is_processed` stays 0, and the item is no longer offered to the agent. A later change to the same record
  supersedes it. Find them with
  `SELECT * FROM sync_queue WHERE failure_kind = 'needs_review' AND is_processed = 0;`. There is no screen for them yet.
* **A name-addressed delete needs the object's GUID.** A ledger/group/stock item created in MyTally and deleted before
  the next inbound sync has no `tally_guid` yet; its delete is held until the GUID is known (or the item is deleted in Tally).
* **AlterID regression.** When Tally's `AltMstId`/`AltVchId` is below the server's watermark the agent runs a full sync
  of that company, forced (so lower AlterIDs overwrite higher stored ones), and writes `sync_events.kind =
  'alterid_regression'`. The server's watermark is `MAX(tally_alter_id)` of what it stores, so it can stay high after
  the full sync; the agent keeps `alter_ceilings[company_guid]` in its config so the same restore does not trigger a
  full sync every cycle.
* A finished restore (backup restore through the agent) now requests a full sync of every linked company.

### Check on a real TallyPrime (read-only checks done 2026-10-17 on 'Bhrama Enterprises'; restore test still open)

1. `AltVchId` equals the highest voucher AlterID, and drops after restoring an older backup (P0.2). The probe has
   always been marked UNVERIFIED; this change relies on it more.
2. `MyTallyVerifyMaster` (`tally_client.verify_master`): the name travels as `<MTV_NAME>` in STATICVARIABLES, declared
   by `<VARIABLE NAME="MTV_NAME">`, read by the filter `$Name = ##MTV_NAME`. Confirm Tally honours the filter for a
   name with quotes, `&`, `<`. If it ignores the filter the reply holds many objects and every delete is held
   (safe, but nothing is deleted until this is fixed).
3. Delete a ledger in MyTally whose name was reused in Tally: expect `needs_review`, nothing deleted in Tally.

### Results of the read-only checks (2026-10-17, TallyPrime at 192.168.71.133:9001, company 'Bhrama Enterprises')

* `verify_master` works: the `##MTV_NAME` filter is honoured. A real ledger returns exactly one object with its GUID, the
  name matches case-insensitively, a missing name returns an empty list, and a name with quotes, `&` and `<` is safe.
* The probe returned AltMstId 848 and AltVchId 585 while the highest voucher AlterID was 318 (44 vouchers). So
  `AltVchId` is **not** equal to the highest voucher AlterID: it is a company-wide counter at or above it. The
  regression rule (`AltVchId < server watermark`) stays safe in that direction, but a regression is only caught once the
  counter falls below the highest stored AlterID, not merely below the last counter value seen.
* Still open: restore an older backup and confirm the counters drop (needs a test company), and the P0.1 period check.
