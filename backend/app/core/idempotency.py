"""
Request idempotency for every write endpoint.

The same write must never be carried out twice because a button was pressed twice or a client retried
after a dropped connection. Two rules, applied to POST, PUT, PATCH and DELETE:

  * Identical requests that overlap are carried out once. The later ones wait for the first and return
    its response. "Identical" means same caller, method, path, query and body.
  * A request carrying an Idempotency-Key header is carried out once per key: for IDEMPOTENCY_TTL_SECONDS
    the stored response is returned again instead of running the request a second time. The web app
    sends a key with every write (see the fetch wrapper in AuthContext). A key belongs to one request:
    the same key arriving with a different body is refused with 422 rather than answered with the
    first request's response.

Only successful responses are kept for a key. A request that failed or was refused (4xx, 5xx) changed
nothing, so sending it again simply runs it again.
State is held in this process; with several workers a duplicate can still reach a different worker.
"""
import asyncio
import hashlib
import time
from typing import Dict, Optional, Tuple

IDEMPOTENCY_TTL_SECONDS = 600
MAX_BODY_BYTES = 1_000_000
MAX_STORED_RESPONSES = 5000

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Sign-in must always reach the server; the sync bridge uploads are large and already repeat-safe
SKIP_PREFIXES = ("/auth/", "/sync/inbound")

StoredResponse = Tuple[int, list, bytes]
KEY_REUSED = (422, [(b"content-type", b"application/json")],
              b'{"detail":"This Idempotency-Key was already used for a different request."}')


class IdempotencyMiddleware:
    def __init__(self, app):
        self.app = app
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._in_flight_body: Dict[str, bytes] = {}
        self._stored: Dict[str, Tuple[float, bytes, StoredResponse]] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS or scope["path"].startswith(SKIP_PREFIXES):
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        content_type = headers.get(b"content-type", b"")
        try:
            content_length = int(headers.get(b"content-length", b"0") or 0)
        except ValueError:
            content_length = 0
        # File uploads and oversized bodies pass straight through
        if content_length > MAX_BODY_BYTES or (content_type and not content_type.startswith((b"application/json", b"text/"))):
            return await self.app(scope, receive, send)

        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > MAX_BODY_BYTES:
                # Too large to fingerprint after all: hand over what was read and stop interfering
                return await self.app(scope, _replay_body(body, receive, more), send)

        key = headers.get(b"idempotency-key")
        caller = headers.get(b"authorization", b"") + b"|" + headers.get(b"cookie", b"")
        digest = hashlib.sha256()
        for part in (caller, scope["method"].encode(), scope["path"].encode(), scope.get("query_string", b""),
                     b"key:" + key if key else b"body:" + body):
            digest.update(part + b"\x00")
        fingerprint = digest.hexdigest()
        body_hash = hashlib.sha256(body).digest()

        if key:
            stored = self._stored.get(fingerprint)
            if stored and stored[0] > time.monotonic():
                return await _send_stored(send, stored[2] if stored[1] == body_hash else KEY_REUSED, replay=stored[1] == body_hash)
            if self._in_flight_body.get(fingerprint, body_hash) != body_hash:
                return await _send_stored(send, KEY_REUSED, replay=False)

        running = self._in_flight.get(fingerprint)
        if running is not None:
            result = await running
            if result is not None:
                return await _send_stored(send, result)
            # The first attempt produced nothing reusable (it failed): run this one normally

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._in_flight[fingerprint] = future
        self._in_flight_body[fingerprint] = body_hash
        captured: Optional[StoredResponse] = None
        try:
            status_code = 500
            response_headers: list = []
            chunks = []

            async def capture(message):
                nonlocal status_code, response_headers
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    response_headers = list(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    chunks.append(message.get("body", b""))
                await send(message)

            await self.app(scope, _replay_body(body, receive, False), capture)
            response_body = b"".join(chunks)
            if status_code < 500 and len(response_body) <= MAX_BODY_BYTES:
                captured = (status_code, response_headers, response_body)
                if key and status_code < 400:
                    self._remember(fingerprint, body_hash, captured)
        finally:
            self._in_flight.pop(fingerprint, None)
            self._in_flight_body.pop(fingerprint, None)
            if not future.done():
                future.set_result(captured)

    def _remember(self, fingerprint: str, body_hash: bytes, response: StoredResponse):
        now = time.monotonic()
        if len(self._stored) >= MAX_STORED_RESPONSES:
            for old in [k for k, entry in self._stored.items() if entry[0] <= now]:
                self._stored.pop(old, None)
            while len(self._stored) >= MAX_STORED_RESPONSES:
                self._stored.pop(next(iter(self._stored)))
        self._stored[fingerprint] = (now + IDEMPOTENCY_TTL_SECONDS, body_hash, response)


def _replay_body(body: bytes, receive, more_body: bool):
    """A receive() that first hands back the body already read, then defers to the real one."""
    sent = False

    async def replay():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": more_body}
        return await receive()

    return replay


async def _send_stored(send, response: StoredResponse, replay: bool = True):
    status_code, headers, body = response
    headers = [(k, v) for k, v in headers if k.lower() != b"content-length"]
    headers += [(b"content-length", str(len(body)).encode())] + ([(b"idempotent-replay", b"true")] if replay else [])
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})
