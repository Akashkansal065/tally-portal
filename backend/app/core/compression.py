"""Gzip for API responses. Lists of customers, vouchers and ledgers are large JSON, and most field users are on
mobile data."""
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import Receive, Scope, Send


class ApiGZipMiddleware(GZipMiddleware):
    """Compresses responses of at least 1 KB at level 6 (level 9 costs far more CPU for little gain).
    Backup routes are passed through untouched: downloads are already-compressed ZIP archives, and recompressing
    them would only tie up the single worker's event loop. Server-sent events are never compressed (Starlette
    excludes text/event-stream)."""

    SKIP_PATH_PREFIXES = ("/backup/",)

    def __init__(self, app, minimum_size: int = 1000, compresslevel: int = 6) -> None:
        super().__init__(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith(self.SKIP_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
