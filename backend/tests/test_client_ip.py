"""Who made a request: forwarding headers are believed only from a trusted proxy."""

from starlette.requests import Request

from app.core.config import settings
from app.core.rate_limiter import get_client_ip


def request_from(peer, headers=None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw, "client": (peer, 1234)})


def test_forwarding_headers_from_an_untrusted_peer_are_ignored(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "127.0.0.1")
    forged = request_from("203.0.113.9", {"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "1.2.3.4", "CF-Connecting-IP": "1.2.3.4"})
    assert get_client_ip(forged) == "203.0.113.9"


def test_behind_a_trusted_proxy_the_right_most_untrusted_hop_is_the_client(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "127.0.0.1, 10.0.0.0/8")
    # The caller forged 1.2.3.4; the proxies appended the real address and their own
    proxied = request_from("127.0.0.1", {"X-Forwarded-For": "1.2.3.4, 198.51.100.7, 10.0.0.5"})
    assert get_client_ip(proxied) == "198.51.100.7"
    assert get_client_ip(request_from("127.0.0.1", {"X-Real-IP": "198.51.100.8"})) == "198.51.100.8"
    assert get_client_ip(request_from("127.0.0.1")) == "127.0.0.1"
