"""App (Firebase) push: tokens follow whoever is signed in, signing out stops a device's alerts, and the FCM
sender signs in with the service account, sends the right message and drops tokens Firebase says are gone."""
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

import app.models.portal_core as P
from app.core.config import settings
from app.routers import auth, notifications
from app.services import fcm
from app.services import notifications as service
from tests.conftest import ANDROID_APP, CHROME_WINDOWS, bearer, login, run


@pytest.fixture
def people(harness):
    company = harness.company()
    role = harness.role("Sales")
    asha = harness.user(company, role, "asha")
    ravi = harness.user(company, role, "ravi")
    client = harness.app(auth.router, notifications.router)
    return dict(harness=harness, client=client, asha=asha, ravi=ravi)


def tokens(harness):
    return harness.query(select(P.DevicePushToken.token, P.DevicePushToken.user_id, P.DevicePushToken.device_id))


def test_app_token_moves_to_whoever_signs_in_on_the_phone(people):
    h, client = people["harness"], people["client"]
    asha = login(client, "asha@example.com", headers=ANDROID_APP)
    assert client.post("/notifications/native-token", json={"token": "fcm-token-1"},
                       headers=bearer(asha, ANDROID_APP)).status_code == 200
    assert tokens(h) == [("fcm-token-1", people["asha"].user_id, ANDROID_APP["X-Device-Id"])]

    ravi = login(client, "ravi@example.com", headers=ANDROID_APP)
    client.post("/notifications/native-token", json={"token": "fcm-token-1"}, headers=bearer(ravi, ANDROID_APP))
    assert tokens(h) == [("fcm-token-1", people["ravi"].user_id, ANDROID_APP["X-Device-Id"])]


def test_signing_out_stops_that_devices_alerts_only(people):
    h, client = people["harness"], people["client"]
    phone = login(client, "asha@example.com", headers=ANDROID_APP)
    laptop = login(client, "asha@example.com", headers=CHROME_WINDOWS)
    client.post("/notifications/native-token", json={"token": "fcm-phone"}, headers=bearer(phone, ANDROID_APP))
    client.post("/notifications/subscribe", headers=bearer(laptop, CHROME_WINDOWS), json={
        "endpoint": "https://push.example/laptop", "keys": {"p256dh": "k", "auth": "a"}})

    assert client.post("/auth/logout", headers=bearer(phone, ANDROID_APP)).status_code == 200
    assert tokens(h) == []                                                            # phone: gone
    assert h.scalar(select(P.PushSubscription.endpoint)) == "https://push.example/laptop"  # laptop: kept


def test_delivery_sends_to_app_tokens_and_drops_dead_ones(people, monkeypatch):
    h = people["harness"]
    asha, ravi = people["asha"], people["ravi"]
    h.add(P.DevicePushToken(user_id=asha.user_id, token="alive"), P.DevicePushToken(user_id=ravi.user_id, token="dead"))
    sent = []

    async def fake_send(messages):
        sent.extend(messages)
        return 1, ["dead"]

    monkeypatch.setattr(fcm, "enabled", lambda: True)
    monkeypatch.setattr(fcm, "send", fake_send)
    payloads = [(asha.user_id, {"title": "For Asha"}), (ravi.user_id, {"title": "For Ravi"})]
    assert run(service.deliver_push(payloads, session_factory=h.Session)) == 1
    assert sorted(sent, key=lambda m: m[0]) == [("alive", {"title": "For Asha"}), ("dead", {"title": "For Ravi"})]
    assert [t for t, *_ in tokens(h)] == ["alive"]


@pytest.fixture
def service_account(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    account = {"project_id": "mytally-test", "client_email": "push@mytally-test.iam.gserviceaccount.com",
               "private_key": pem, "token_uri": "https://oauth2.example/token"}
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON", json.dumps(account))
    monkeypatch.setattr(fcm, "_account", None)
    monkeypatch.setattr(fcm, "_access_token", (None, 0.0))
    return key.public_key()


def test_fcm_sender_signs_in_and_reports_gone_tokens(service_account, monkeypatch):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "oauth2.example":
            assertion = dict(httpx.QueryParams(request.content.decode()))["assertion"]
            claims = jwt.decode(assertion, service_account, algorithms=["RS256"], audience="https://oauth2.example/token")
            assert claims["scope"] == fcm.SCOPE
            return httpx.Response(200, json={"access_token": "google-token", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer google-token"
        token = json.loads(request.content)["message"]["token"]
        if token == "gone":
            return httpx.Response(404, json={"error": {"status": "NOT_FOUND",
                                                       "details": [{"errorCode": "UNREGISTERED"}]}})
        if token == "bad-message":
            return httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}})
        return httpx.Response(200, json={"name": "projects/mytally-test/messages/1"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(fcm.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))

    payload = service.push_payload(42, "New Order", "sales placed order #7", company_id=3, tag="notif-42")
    delivered, gone = run(fcm.send([("ok", payload), ("gone", payload), ("bad-message", payload)]))
    assert (delivered, gone) == (1, ["gone"])  # a malformed message never deletes a token

    sent = json.loads(requests[1].content)["message"]
    assert requests[1].url.path == "/v1/projects/mytally-test/messages:send"
    assert sent["notification"] == {"title": "New Order", "body": "sales placed order #7"}
    assert sent["data"]["url"] == "/notifications/open?id=42"
    assert all(isinstance(v, str) for v in sent["data"].values())  # FCM data must be strings
    assert sent["android"]["notification"]["tag"] == "notif-42"
    assert sum(r.url.host == "oauth2.example" for r in requests) == 1  # token reused across messages


def test_fcm_is_off_without_a_service_account(monkeypatch):
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
    monkeypatch.setattr(fcm, "_account", None)
    assert not fcm.enabled()
    assert run(fcm.send([("t", {"title": "x"})])) == (0, [])
