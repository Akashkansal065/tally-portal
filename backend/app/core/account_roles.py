"""Roles belong to an account. Each account has its own Admin and Sales roles and whatever it adds, so one
customer changing what a role may do never changes it for another. Roles from before accounts existed have no
account and are seen only by users who have none."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.portal_core import Module, Permission, Role

# What a new account's Sales role starts with: (create, read, update, delete) per module. Admin gets everything.
DEFAULT_SALES_PERMISSIONS = {
    "visits": (True, True, True, True),
    "payments": (True, True, True, True),
    "orders": (True, True, True, True),
    "attendance": (True, True, True, True),
    "customers": (True, True, True, False),
}


def role_in_account(account_id: Optional[int]):
    """SQL condition: the role is one of this account's."""
    return Role.account_id.is_(None) if account_id is None else Role.account_id == account_id


async def create_default_roles(db: AsyncSession, account_id: int) -> Role:
    """Give a new account its own Admin and Sales roles and return the Admin one. Doing it again changes nothing."""
    modules = (await db.execute(select(Module))).scalars().all()
    wanted = (
        ("Admin", "Full access to all modules including user management", None),
        ("Sales", "Field sales, check-in, orders, payments collection & attendance", DEFAULT_SALES_PERMISSIONS),
    )
    admin_role = None
    for name, description, grants in wanted:
        role = (await db.execute(select(Role).where(Role.name == name, Role.account_id == account_id))).scalars().first()
        if role is None:
            role = Role(name=name, description=description, account_id=account_id)
            db.add(role)
            await db.flush()
            for module in modules:
                if grants is None:
                    allowed = (True, True, True, True)
                elif module.code in grants:
                    allowed = grants[module.code]
                else:
                    continue
                db.add(Permission(role_id=role.role_id, module_id=module.module_id, can_create=allowed[0],
                                  can_read=allowed[1], can_update=allowed[2], can_delete=allowed[3]))
        if name == "Admin":
            admin_role = role
    await db.flush()
    return admin_role
