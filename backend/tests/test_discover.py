"""wigolo lane (mocked subprocess — no network)."""
from unittest.mock import patch


def test_discover_boosts_gov():
    from app import discover as D
    fake = {"results": [
        {"url": "https://blog.example.com/udyam-guide", "score": 0.99},
        {"url": "https://udyamregistration.gov.in/", "score": 0.5},
    ]}
    with patch.object(D, "_run", return_value=fake):
        out = D.discover("udyam", 2)
    assert out[0]["url"] == "https://udyamregistration.gov.in/"
    assert out[1]["url"].startswith("https://blog")


def test_fetch_thin_raises():
    from app import discover as D
    with patch.object(D, "_run", return_value={"markdown": "hi"}):
        try:
            D.fetch_text("https://x.example/")
            raise SystemExit("should have raised")
        except RuntimeError:
            pass
