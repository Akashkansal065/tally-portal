"""audit_logs.action is a 20-character column. SQLite (the tests) does not enforce lengths but MySQL does, so a
longer action name only fails on a real server: found when a restore answered 500 after it had imported everything."""
from app.models.portal_core import AuditLog
from app.services import backup_restore_new, reconcile_writeback


def test_audit_actions_written_by_the_new_features_fit_the_column():
    width = AuditLog.__table__.c.action.type.length
    names = [backup_restore_new.AUDIT_RESTORED, reconcile_writeback.AUDIT_QUEUED,
             "DRIVE_LINKED", "DRIVE_UNLINKED"]
    names += [f"{reconcile_writeback.AUDIT_RESULT_PREFIX}{o.upper()}"
              for o in ("done", "already", "stale", "failed")]
    assert all(len(n) <= width for n in names), [n for n in names if len(n) > width]
