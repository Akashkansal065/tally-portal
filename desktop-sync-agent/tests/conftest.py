"""Agent tests: a fake MyTally backend over real HTTP, and an in-memory keyring so tests never
write to the OS credential vault."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import keyring  # noqa: E402
from keyring.backend import KeyringBackend  # noqa: E402


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


keyring.set_keyring(MemoryKeyring())


class FakeBackend:
    """Records requests; tests decide how /auth/login and the sync endpoints respond."""

    def __init__(self):
        self.requests = []          # (method, path, headers)
        self.logins = 0
        self.login_response = (200, {"access_token": "token-1"}, {})
        self.api_responses = []     # queued (status, body, headers) for non-login calls; default 200 []

    def handle(self, handler, method):
        length = int(handler.headers.get("Content-Length") or 0)
        if length:
            handler.rfile.read(length)
        self.requests.append((method, handler.path, dict(handler.headers)))
        if handler.path.startswith("/auth/login"):
            self.logins += 1
            status, body, headers = self.login_response
            if status == 200:
                body = {"access_token": f"token-{self.logins}"}
        elif self.api_responses:
            status, body, headers = self.api_responses.pop(0)
        else:
            status, body, headers = 200, [], {}
        raw = json.dumps(body).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(raw)))
        for k, v in headers.items():
            handler.send_header(k, v)
        handler.end_headers()
        handler.wfile.write(raw)


@pytest.fixture
def backend():
    fake = FakeBackend()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            fake.handle(self, "GET")

        def do_POST(self):
            fake.handle(self, "POST")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield fake
    server.shutdown()
