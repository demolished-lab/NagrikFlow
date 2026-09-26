"""External branches with mocked transports — every provider path executes."""
from unittest.mock import patch


class FakeResp:
    def __init__(self, payload=None):
        self._p = payload or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_notify_console():
    from app import notify as N
    old = N.PROVIDER
    N.PROVIDER = "console"
    try:
        assert N.send("a@x.co", "s", "b") == {"via": "console"}
    finally:
        N.PROVIDER = old


def test_notify_resend_posts_correctly():
    from app import notify as N
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return FakeResp({"id": "re_123"})

    with patch.object(N.httpx, "post", side_effect=fake_post), \
         patch.object(N, "RESEND_KEY", "re_test"), \
         patch.object(N, "PROVIDER", "resend"):
        out = N.send("a@x.co", "Sub", "Body")
    assert out == {"via": "resend", "id": "re_123"}
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"] == "Bearer re_test"
    assert seen["json"]["to"] == ["a@x.co"]


def test_notify_smtp_logs_in():
    from app import notify as N
    calls = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def starttls(self):
            calls["tls"] = True

        def login(self, u, p):
            calls["login"] = (u, p)

        def send_message(self, m):
            calls["to"] = m["To"]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch.object(N.smtplib, "SMTP", FakeSMTP), \
         patch.object(N, "PROVIDER", "smtp"), \
         patch.object(N, "SMTP_HOST", "smtp.test"), \
         patch.object(N, "SMTP_USER", "u"), \
         patch.object(N, "SMTP_PASS", "p"):
        assert N.send("a@x.co", "S", "B") == {"via": "smtp"}
    assert calls == {"tls": True, "login": ("u", "p"), "to": "a@x.co"}


def test_alerts_telegram_posts():
    from app import alerts as A
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen.update(url=url, json=json)
        return FakeResp({"result": {"message_id": 7}})

    with patch.object(A.httpx, "post", side_effect=fake_post), \
         patch.object(A, "TOKEN", "tok123"):
        out = A.send("9178", "hello")
    assert out == {"via": "telegram", "id": 7}
    assert seen["url"] == "https://api.telegram.org/bottok123/sendMessage"
    assert seen["json"] == {"chat_id": "9178", "text": "hello"}


def test_alerts_without_token_degrades():
    from app import alerts as A
    with patch.object(A, "TOKEN", ""):
        assert A.send("", "x")["via"] == "console"


def test_digilocker_pkce_flow(client, user):
    """connect persists verifier; callback consumes it; foreign state refused."""
    c1 = client.get("/auth/digilocker/connect", headers=user["headers"]).json()
    assert c1["authorize_url"].startswith("http")
    assert c1["state"].split(".")[0].isdigit()  # "<user_id>.<rand>", never user-blind
    assert "pkce_verifier" not in c1  # verifier never leaves the server anymore

    from app import digilocker as dg
    with patch.object(dg.httpx, "post", return_value=FakeResp({"access_token": "tok"})), \
         patch.object(dg.httpx, "get", return_value=FakeResp({"files": [
             {"name": "DL", "doctype": "DRVLC", "issuer": "in.gov.morth",
              "uri": "dg://dl"}]})):
        imp = client.post("/auth/digilocker/callback", headers=user["headers"],
                          json={"code": "c", "state": c1["state"]}).json()
    assert imp["imported_kinds"] == ["dl"]
    dash = client.get("/me/dashboard", headers=user["headers"]).json()
    assert "Driving Licence" in dash["have"]

    # replay same state -> refused (single-use)
    r = client.post("/auth/digilocker/callback", headers=user["headers"],
                    json={"code": "c", "state": c1["state"]})
    assert r.status_code == 400


def test_attention_engine():
    from app import eligibility as elig
    b = elig.personalize({"dl"}, {}, [
        {"kind": "dl", "label": "Driving Licence", "expires_at": "2020-01-01T00:00:00+00:00", "meta": "{}"},
        {"kind": "gstin", "label": "GSTIN", "expires_at": "",
         "meta": '{"due": "GST filing", "date": "2026-10-20T00:00:00+00:00"}'},
    ])
    levels = {a["level"] for a in b["attention"]}
    assert "overdue" in levels  # expired DL surfaces even without network
    assert any("GST filing" in a["text"] for a in b["attention"])
