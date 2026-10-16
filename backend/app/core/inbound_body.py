"""Reading the body of /sync/inbound: plain or gzip, never more than SYNC_INBOUND_MAX_BYTES (WS-8).

The cap is on the bytes that end up in memory, so a small gzip that expands to gigabytes (a bomb) is refused
as soon as it grows past the cap, without being decompressed further.
"""
import zlib
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.config import settings

SUPPORTED_ENCODINGS = ("", "identity", "gzip")


def inbound_limit() -> int:
    return max(1, int(settings.SYNC_INBOUND_MAX_BYTES))


def _too_large(limit: int) -> HTTPException:
    return HTTPException(status_code=413,
                         detail=f"The sync upload is larger than this server accepts ({limit // (1024 * 1024)} MB "
                                "after decompression). Send it in smaller date ranges.")


async def read_inbound_body(request: Request, limit: Optional[int] = None) -> bytes:
    limit = limit or inbound_limit()
    encoding = (request.headers.get("content-encoding") or "").strip().lower()
    if encoding not in SUPPORTED_ENCODINGS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail=f"Content-Encoding '{encoding}' is not supported here; send plain XML or gzip.")
    declared = request.headers.get("content-length")
    if encoding != "gzip" and declared and declared.isdigit() and int(declared) > limit:
        raise _too_large(limit)

    out = bytearray()
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            if decompressor is None:
                out += chunk
                if len(out) > limit:
                    raise _too_large(limit)
                continue
            # Decompress in bounded steps so a bomb is stopped at the cap, not after it has been inflated
            pending = chunk
            while pending:
                out += decompressor.decompress(pending, limit + 1 - len(out))
                if len(out) > limit:
                    raise _too_large(limit)
                pending = decompressor.unconsumed_tail
        if decompressor is not None:
            out += decompressor.flush()
            if len(out) > limit:
                raise _too_large(limit)
            if not decompressor.eof:
                raise zlib.error("truncated gzip stream")
    except zlib.error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The gzip upload is damaged or incomplete.")
    return bytes(out)
