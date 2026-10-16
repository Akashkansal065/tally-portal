"""WS-8 agent side: gzip is sent only to a server that said it takes it; an older one gets plain XML."""
import gzip

from cloud_client import CloudClient

XML = "<ENVELOPE>" + "<VOUCHER>x</VOUCHER>" * 500 + "</ENVELOPE>"
OK = (200, {"status": "success", "imported_vouchers": 1}, {})


def client(backend):
    c = CloudClient(backend_url=backend.url, token="t")
    c.company_guid = "guid-1"
    return c


def test_plain_xml_to_a_server_that_never_said_it_takes_gzip(backend):
    c = client(backend)
    backend.api_responses.append(OK)
    ok, res = c.push_inbound_xml(XML, "Alpha")
    assert ok
    method, path, headers = backend.requests[-1]
    assert "Content-Encoding" not in headers and backend.bodies[-1] == XML.encode()
    assert res["payload_bytes"] == res["sent_bytes"] == len(XML.encode())


def test_gzip_once_the_server_has_advertised_it(backend):
    c = client(backend)
    backend.api_responses.append((200, {"last_alter_id": 0, "inbound": {"gzip": True, "max_bytes": 1000}}, {}))
    c.get_last_alter_id()
    assert c.server_accepts_gzip is True
    backend.api_responses.append(OK)
    ok, res = c.push_inbound_xml(XML, "Alpha")
    assert ok
    headers = backend.requests[-1][2]
    assert headers.get("Content-Encoding") == "gzip"
    assert gzip.decompress(backend.bodies[-1]).decode() == XML
    assert res["sent_bytes"] < res["payload_bytes"] / 5


def test_small_payloads_and_a_server_that_stops_advertising_go_plain(backend):
    c = client(backend)
    c.server_accepts_gzip = True
    backend.api_responses.append(OK)
    c.push_inbound_xml("<ENVELOPE/>", "Alpha")
    assert "Content-Encoding" not in backend.requests[-1][2]
    backend.api_responses.append((200, {"last_alter_id": 0}, {}))      # an older server after a rollback
    c.get_last_alter_id()
    assert c.server_accepts_gzip is False
