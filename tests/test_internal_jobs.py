import base64
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from internal.config import InternalConfig
from internal.repository import InternalRepository


@pytest.fixture()
def internal_client(monkeypatch, tmp_path):
    db_path = tmp_path / "internal.db"
    cfg = InternalConfig(
        enabled=True,
        db_path=str(db_path),
        admin_ids=set(),
        telegram_bot_token="dummy",
        worker_poll_seconds=0.01,
        max_concurrent_jobs_per_user=2,
        jwt_secret="",
        jwt_exp_hours=168,
        cors_origins=(),
    )
    monkeypatch.setattr(main, "internal_cfg", cfg)
    monkeypatch.setattr(main, "internal_repo", InternalRepository(str(db_path)))
    return TestClient(main.app)


def _png_b64() -> str:
    im = Image.new("RGB", (32, 32), (200, 100, 50))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def test_create_job_requires_valid_preset(internal_client):
    r = internal_client.post(
        "/internal/jobs",
        json={
            "user_id": "u1",
            "preset_key": "no_such_preset",
            "image_base64": _png_b64(),
        },
    )
    assert r.status_code == 400
    assert "preset" in r.json()["detail"].lower()


def test_create_job_enforces_concurrency(internal_client):
    body = {"user_id": "u1", "preset_key": "staff_portrait", "image_base64": _png_b64()}
    assert internal_client.post("/internal/jobs", json=body).status_code == 200
    assert internal_client.post("/internal/jobs", json=body).status_code == 200
    r = internal_client.post("/internal/jobs", json=body)
    assert r.status_code == 429


def test_get_job_requires_matching_user(internal_client):
    create = internal_client.post(
        "/internal/jobs",
        json={"user_id": "alice", "preset_key": "staff_portrait", "image_base64": _png_b64()},
    )
    job_id = create.json()["id"]
    ok = internal_client.get(f"/internal/jobs/{job_id}", params={"user_id": "alice"})
    assert ok.status_code == 200
    denied = internal_client.get(f"/internal/jobs/{job_id}", params={"user_id": "bob"})
    assert denied.status_code == 403


def test_list_jobs(internal_client):
    internal_client.post(
        "/internal/jobs",
        json={"user_id": "u2", "preset_key": "hero_slide", "image_base64": _png_b64()},
    )
    r = internal_client.get("/internal/jobs", params={"user_id": "u2"})
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_internal_health_when_disabled(monkeypatch, tmp_path):
    cfg = InternalConfig(
        enabled=False,
        db_path=str(tmp_path / "unused.db"),
        admin_ids=set(),
        telegram_bot_token="",
        worker_poll_seconds=1.0,
        max_concurrent_jobs_per_user=3,
        jwt_secret="",
        jwt_exp_hours=168,
        cors_origins=(),
    )
    monkeypatch.setattr(main, "internal_cfg", cfg)
    client = TestClient(main.app)
    r = client.get("/internal/health")
    assert r.status_code == 200
    data = r.json()
    assert data["internal_mode"] is False
    assert data["status"] == "ok"


def test_internal_health_when_enabled(internal_client):
    r = internal_client.get("/internal/health")
    assert r.status_code == 200
    data = r.json()
    assert data["internal_mode"] is True
    assert data["db_ok"] is True
    assert data["outputs_writable"] is True
    assert data["status"] == "ok"
