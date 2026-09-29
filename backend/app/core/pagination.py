from typing import Optional, Generic, TypeVar, List
from pydantic import BaseModel
from fastapi import Query
from fastapi.responses import Response
from sqlalchemy.sql.selectable import Select
from app.core.config import settings

T = TypeVar("T")

class PaginationParams:
    """
    Standard pagination query parameters dependency.
    Supports either 1-based page/page_size or offset/limit styles.
    Defaults to unpaginated (is_paginated=False) when parameters are omitted
    to preserve 100% backwards compatibility with legacy frontend callers.
    """
    def __init__(
        self,
        page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
        page_size: Optional[int] = Query(None, ge=1, le=500, description="Items per page (max 500)"),
        skip: Optional[int] = Query(None, ge=0, description="Number of records to skip"),
        limit: Optional[int] = Query(None, ge=1, le=500, description="Max records to return")
    ):
        if page is not None or page_size is not None:
            self.page = page or 1
            self.page_size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
            self.offset = (self.page - 1) * self.page_size
            self.limit = self.page_size
            self.is_paginated = True
        elif skip is not None or limit is not None:
            self.offset = skip or 0
            self.limit = min(limit or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
            self.page_size = self.limit
            self.page = (self.offset // self.page_size) + 1
            self.is_paginated = True
        else:
            self.offset = 0
            self.limit = None
            self.page = 1
            self.page_size = None
            self.is_paginated = False

    def apply_to_query(self, stmt: Select) -> Select:
        """Applies offset and limit to an async SQLAlchemy Select statement if pagination was requested."""
        if self.offset:
            stmt = stmt.offset(self.offset)
        if self.limit:
            stmt = stmt.limit(self.limit)
        return stmt

    def slice_list(self, items: List[T]) -> List[T]:
        """Slices an in-memory Python list if pagination was requested."""
        if not self.is_paginated:
            return items
        end = self.offset + self.limit if self.limit is not None else None
        return items[self.offset:end]


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic envelope schema for paginated responses."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


def apply_pagination_headers(
    response: Response,
    total: int,
    pagination: PaginationParams
) -> None:
    """
    Sets standard REST pagination headers on the outgoing HTTP response.
    Headers set:
      X-Total-Count: total count of matching records
      X-Page: current page number (if paginated)
      X-Page-Size: current page size (if paginated)
      X-Total-Pages: total number of pages (if paginated)
      X-Has-Next: true/false (if paginated)
      X-Has-Prev: true/false (if paginated)
    """
    response.headers["X-Total-Count"] = str(total)
    if pagination.is_paginated and pagination.page_size:
        total_pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 1
        response.headers["X-Page"] = str(pagination.page)
        response.headers["X-Page-Size"] = str(pagination.page_size)
        response.headers["X-Total-Pages"] = str(total_pages)
        response.headers["X-Has-Next"] = "true" if pagination.page < total_pages else "false"
        response.headers["X-Has-Prev"] = "true" if pagination.page > 1 else "false"
