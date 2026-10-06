"""Outstanding (every customer's dues and reminders) is its own permission. Payments access, which field staff
need for collecting, no longer opens it."""
import app.models.portal_core as P
from app.core.permissions import clear_all_auth_and_permission_caches
from app.routers import auth, payment, reminders
from tests.conftest import bearer, login


def test_payments_access_does_not_open_outstanding(harness):
    h = harness
    alpha = h.company("Alpha")
    sales_role = h.role("Sales")
    h.user(alpha, h.role("Admin"), "owner")
    h.user(alpha, sales_role, "rep")
    payments = h.add(P.Module(code="payments", name="Payments"))
    outstanding = h.add(P.Module(code="outstanding", name="Outstanding"))
    h.add(P.Permission(role_id=sales_role.role_id, module_id=payments.module_id, can_read=True, can_create=True))
    client = h.app(auth.router, payment.router, reminders.router)
    rep, owner = bearer(login(client, "rep@example.com")), bearer(login(client, "owner@example.com"))

    me = client.get("/auth/me", headers=rep).json()
    assert me["capabilities"]["outstanding"]["can_read"] is False and me["showPayments"] is True
    assert client.get("/payment/outstanding", headers=rep).status_code == 200      # bills, used when collecting
    for path in ("/payment/aging/dashboard", "/reminders/summary", "/reminders/channels", "/reminders/log"):
        assert client.get(path, headers=rep).status_code == 403, path
        assert client.get(path, headers=owner).status_code == 200, path            # admins have it by default

    # Granting it in the role opens it
    h.add(P.Permission(role_id=sales_role.role_id, module_id=outstanding.module_id, can_read=True))
    clear_all_auth_and_permission_caches()
    assert client.get("/payment/aging/dashboard", headers=rep).status_code == 200
