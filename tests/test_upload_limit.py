import os

from fastapi.testclient import TestClient

from main import app


def test_upload_rejects_payload_over_max(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    client = TestClient(app)
    big = b"\xff" * (2 * 1024 * 1024)
    r = client.post(
        "/process-image",
        files={"image": ("x.bin", big, "application/octet-stream")},
        data={"type": "product", "background": "keep"},
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()
