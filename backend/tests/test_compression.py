"""Large API responses are gzipped; backup downloads and small replies are sent as they are."""
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.core.compression import ApiGZipMiddleware

app = FastAPI()
app.add_middleware(ApiGZipMiddleware)
ROWS = [{"name": f"Customer {i}", "city": "New Delhi", "route_name": "Route 4"} for i in range(200)]


@app.get("/customers")
def customers():
    return ROWS


@app.get("/attendance/ping-location")
def ping():
    return {"success": True, "active": True}


@app.get("/backup/1/download")
def backup():
    return Response(b"PK\x03\x04" + b"0" * 50_000, media_type="application/zip")


client = TestClient(app)
GZIP = {"Accept-Encoding": "gzip"}


def test_large_json_is_compressed():
    response = client.get("/customers", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert response.json() == ROWS  # the client decompresses transparently


def test_small_replies_are_not_compressed():
    assert "content-encoding" not in client.get("/attendance/ping-location", headers=GZIP).headers


def test_backup_downloads_are_not_recompressed():
    response = client.get("/backup/1/download", headers=GZIP)
    assert "content-encoding" not in response.headers
    assert len(response.content) == 50_004


def test_clients_that_dont_accept_gzip_get_plain_responses():
    assert "content-encoding" not in client.get("/customers", headers={"Accept-Encoding": "identity"}).headers
