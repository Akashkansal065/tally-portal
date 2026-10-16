"""WS-9 agent side: a deterministic key per export, and a retry after a timeout only with that key."""
import urllib.request

import pytest

from cloud_client import CloudClient

XML = "<ENVELOPE><VOUCHER>1</VOUCHER></ENVELOPE>"
OK = (200, {"status": "success", "imported_vouchers": 1}, {})


def client(backend):
    c = CloudClient(backend_url=backend.url, token="t")
    c.company_guid = "guid-1"
    c.RETRY_PAUSE_SECONDS = 0
    return c


def key_of(backend, n=-1):
    return backend.requests[n][2].get("Idempotency-Key")


def test_the_key_is_the_same_for_the_same_export_and_differs_otherwise(backend):
    c = client(backend)
    base = c.receipt_key("g", "Ledgers|alter>5/5", XML, False)
    assert base == c.receipt_key("g", "Ledgers|alter>5/5", XML, False)
    assert len(base) == 64
    assert len({base, c.receipt_key("g2", "Ledgers|alter>5/5", XML, False), c.receipt_key("g", "Vouchers|alter>5/5", XML, False),
                c.receipt_key("g", "Ledgers|alter>6/5", XML, False), c.receipt_key("g", "Ledgers|alter>5/5", XML + " ", False),
                c.receipt_key("g", "Ledgers|alter>5/5", XML, True)}) == 6


def test_an_upload_with_a_scope_carries_the_key_and_one_without_does_not(backend):
    c = client(backend)
    backend.api_responses += [OK, OK]
    c.push_inbound_xml(XML, "Alpha", scope="Ledgers|full")
    assert key_of(backend) == c.receipt_key("guid-1", "Ledgers|full", XML, False)
    c.push_inbound_xml(XML, "Alpha")
    assert key_of(backend) is None


def test_a_timeout_is_retried_once_with_the_same_key(backend, monkeypatch):
    c = client(backend)
    real = urllib.request.urlopen
    calls = []

    def flaky(req, timeout=None):
        calls.append(req.get_header("Idempotency-key"))
        if len(calls) == 1:
            raise TimeoutError("timed out")
        return real(req, timeout=timeout)
    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    backend.api_responses.append(OK)
    ok, res = c.push_inbound_xml(XML, "Alpha", scope="Ledgers|full")
    assert ok and res.get("retried_with_key") is True
    assert len(calls) == 2 and calls[0] == calls[1] and calls[0]


def test_without_a_key_a_timeout_is_not_retried(backend, monkeypatch):
    c = client(backend)
    calls = []

    def dead(req, timeout=None):
        calls.append(1)
        raise TimeoutError("timed out")
    monkeypatch.setattr(urllib.request, "urlopen", dead)
    ok, res = c.push_inbound_xml(XML, "Alpha")
    assert not ok and res["error_type"] == "TIMEOUT" and len(calls) == 1
