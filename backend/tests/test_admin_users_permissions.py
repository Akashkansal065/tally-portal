"""GET /admin/users resolves every user's permissions in a fixed number of queries, with the same result."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.models.portal_core as P
from app.core.permissions import (
    clear_all_auth_and_permission_caches,
    get_all_user_permissions,
    get_permissions_for_users,
)
from app.routers import admin, auth
from tests.conftest import bearer, login, run


def seed(harness, field_users):
    company = harness.company()
    owner = harness.user(company, harness.role("Admin"), "owner")
    sales_role = harness.role("Sales")
    modules = {code: harness.add(P.Module(code=code, name=code.title())) for code in ("vouchers", "ledgers", "orders")}
    harness.add(P.Permission(role_id=sales_role.role_id, module_id=modules["vouchers"].module_id,
                             can_create=True, can_read=True, can_update=False, can_delete=False))
    harness.add(P.Permission(role_id=sales_role.role_id, module_id=modules["orders"].module_id,
                             can_create=True, can_read=True, can_update=True, can_delete=True))
    users = [harness.user(company, sales_role, f"sales.{i}") for i in range(field_users)]
    # Varied overrides and scopes so each user resolves differently
    harness.add(P.UserPermissionOverride(user_id=users[0].user_id, module_id=modules["orders"].module_id, can_read=False,
                                         granted_by=owner.user_id))
    harness.add(P.UserPermissionOverride(user_id=owner.user_id, module_id=modules["ledgers"].module_id, can_delete=False,
                                         granted_by=owner.user_id))
    harness.add(P.UserDataScope(user_id=users[1].user_id, scope_type="VoucherType", scope_ref_id=7))
    harness.add(P.UserDataScope(user_id=users[1].user_id, scope_type="VoucherType", scope_ref_id=9))
    return owner


def test_batch_matches_one_user_at_a_time(harness):
    seed(harness, field_users=3)

    async def compare():
        async with harness.Session() as db:
            users = (await db.execute(select(P.User).options(selectinload(P.User.role)))).scalars().all()
            batch = await get_permissions_for_users(users, db)
            clear_all_auth_and_permission_caches()
            single = {u.user_id: await get_all_user_permissions(u.user_id, u.role_id, u.role.name, db) for u in users}
            return batch, single

    batch, single = run(compare())
    assert batch == single
    assert len({repr(v) for v in batch.values()}) == 4  # owner and three differently configured sales users


def test_admin_user_list_query_count_does_not_grow_with_users(harness):
    def queries_for_user_list(field_users, tmp):
        clear_all_auth_and_permission_caches()
        owner = seed(tmp, field_users)
        client = tmp.app(auth.router, admin.router)
        headers = bearer(login(client, owner.email))
        clear_all_auth_and_permission_caches()
        with tmp.count_queries() as statements:
            reply = client.get("/admin/users", headers=headers)
        assert reply.status_code == 200 and len(reply.json()) == field_users + 1
        return len(statements)

    from tests.conftest import Harness
    import tempfile
    few = queries_for_user_list(2, Harness(tempfile.mkdtemp()))
    many = queries_for_user_list(12, Harness(tempfile.mkdtemp()))
    assert few == many
