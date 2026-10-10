"""Which rows belong to the caller's company or account.

Field-sales rows (orders, visits, shop payments, expenses) carry the company they were made for, and
attendance carries its account. Rows written before those columns existed have neither until they are
backfilled; for those the old rule still answers: the row is where its owner's active company is.
Every query using these must be joined to User on the row's owner.
"""
from sqlalchemy import and_, or_, select

from app.models.portal_core import User
from app.models.tally_core import MstLedger


def rows_of_company(model, user: User):
    """Rows of a field-sales table made for the caller's company."""
    return or_(model.company_id == user.company_id,
               and_(model.company_id.is_(None), User.company_id == user.company_id))


def rows_of_account(model, user: User):
    """Rows of an account-wide table (attendance) that belong to the caller's account."""
    if user.account_id is None:
        return User.company_id == user.company_id
    return or_(model.account_id == user.account_id,
               and_(model.account_id.is_(None), User.company_id == user.company_id))


def users_of_account(user: User):
    """The people whose account-wide rows (attendance) the caller's lists cover."""
    if user.account_id is None:
        return User.company_id == user.company_id
    return User.account_id == user.account_id


def rows_of_company_by_ledger(model, user: User):
    """Like rows_of_company for a table whose rows name a ledger, without needing the owner joined: a row from
    before rows carried a company belongs where its ledger does."""
    return or_(model.company_id == user.company_id,
               and_(model.company_id.is_(None),
                    model.ledger_id.in_(select(MstLedger.ledger_id).where(MstLedger.company_id == user.company_id))))
