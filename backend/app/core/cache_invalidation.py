"""Clears cached responses automatically when the tables behind them change.

A response cached per company (app/core/cache.py) registers the models it reads with watch(). Any ORM write to
those models clears the matching cache keys once the transaction commits:
  - rows inserted, updated or deleted by a flush clear the key for their own company (mapper events, so only
    rows of watched tables that were actually written cost anything, even during a large Tally import);
  - ORM insert()/update()/delete() statements clear the key for every company, since the affected
    companies aren't known without reading the rows.
Writes made with raw SQL text() are not seen; the Tally sync clears the whole company cache when it finishes.
Clearing happens after commit, so a request running at the same time can't re-cache the old rows afterwards
from a transaction that hasn't committed yet. The TTL on each cached response bounds any remaining race.
"""
from typing import Dict, Optional, Set, Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session, object_session

from app.core.cache import clear_cache_prefix, clear_company_cache

_watched: Dict[type, Set[str]] = {}
_PENDING = "cache_keys_to_clear"


def watch(cache_key_prefix: str, *models: type) -> None:
    """Clear cached responses whose key starts with cache_key_prefix whenever one of these models is written."""
    for model in models:
        if model not in _watched:
            _watched[model] = set()
            for row_event in ("after_insert", "after_update", "after_delete"):
                event.listen(model, row_event, _collect_written_row)
        _watched[model].add(cache_key_prefix)


def _pending(session: Session) -> Set[Tuple[Optional[int], str]]:
    return session.info.setdefault(_PENDING, set())


def _collect_written_row(mapper, connection, target):
    session = object_session(target)
    prefixes = _watched.get(mapper.class_)
    if session is not None and prefixes:
        company_id = getattr(target, "company_id", None)
        _pending(session).update((company_id, prefix) for prefix in prefixes)


@event.listens_for(Session, "do_orm_execute")
def _collect_bulk_statements(state):
    if not (state.is_insert or state.is_update or state.is_delete):
        return
    mapper = state.bind_mapper
    prefixes = _watched.get(mapper.class_) if mapper is not None else None
    if prefixes:
        _pending(state.session).update((None, prefix) for prefix in prefixes)


@event.listens_for(Session, "after_commit")
def _clear_after_commit(session):
    for company_id, prefix in session.info.pop(_PENDING, ()):
        if company_id is None:
            clear_cache_prefix(prefix)
        else:
            clear_company_cache(company_id, prefix)


@event.listens_for(Session, "after_rollback")
def _forget_after_rollback(session):
    session.info.pop(_PENDING, None)
