import base64
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from internal.config import InternalConfig
from internal.repository import InternalRepository
from internal.tokens import create_access_token


@pytest.fixture()
def internal_client_jwt(monkeypatch, tmp_path):
    db_path = tmp_path / "internal.db"
    cfg = InternalConfig(
        enabled=True,
        db_path=str(db_path),
        admin_ids=set(),
        telegram_bot_token="test-bot-token",
        worker_poll_seconds=0.01,
        max_concurrent_jobs_per_user=3,
        jwt_secret="unit-test-secret-key-at-least-32-bytes-long!",
        jwt_exp_hours=24,
        cors_origins=("https://mini.example",),
    )
    monkeypatch.setattr(main, "internal_cfg", cfg)
    monkeypatch.setattr(main, "internal_repo", InternalRepository(str(db_path)))
    return TestClient(main.app)


def _png_b64() -> str:
    im = Image.new("RGB", (32, 32), (200, 100, 50))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


@patch("main.verify_telegram_init_data")
def test_auth_returns_jwt_when_secret_set(mock_verify, internal_client_jwt):
    mock_verify.return_value = {"user": '{"id": 999001, "first_name": "Test"}'}
    main.internal_repo.allow_user(999001, "test")

    r = internal_client_jwt.post(
        "/internal/auth/telegram",
        json={"init_data": "dummy"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["telegram_id"] == 999001
    user_id = data["user"]["id"]

    job_r = internal_client_jwt.post(
        "/internal/jobs",
        headers={"Authorization": f"Bearer {data['access_token']}"},
        json={"preset_key": "staff_portrait", "image_base64": _png_b64()},
    )
    assert job_r.status_code == 200, job_r.text
    job_id = job_r.json()["id"]

    st = internal_client_jwt.get(
        f"/internal/jobs/{job_id}",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert st.status_code == 200
    assert st.json()["user_id"] == user_id


def test_jobs_require_bearer_when_jwt_configured(internal_client_jwt):
    r = internal_client_jwt.post(
        "/internal/jobs",
        json={
            "user_id": "some-id",
            "preset_key": "staff_portrait",
            "image_base64": _png_b64(),
        },
    )
    assert r.status_code == 401


def test_client_config_shows_jwt_required(internal_client_jwt):
    r = internal_client_jwt.get("/internal/client-config")
    assert r.status_code == 200
    assert r.json()["jwt_required"] is True


def test_invalid_bearer_rejected(internal_client_jwt):
    r = internal_client_jwt.get(
        "/internal/jobs",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert r.status_code == 401


def test_bearer_can_list_jobs(internal_client_jwt):
    main.internal_repo.allow_user(999002, "t")
    user = main.internal_repo.upsert_user(999002, "u", "User", "user")
    real_token = create_access_token(
        secret=main.internal_cfg.jwt_secret,
        user_id=user.id,
        telegram_id=999002,
        role="user",
        exp_hours=1,
    )
    internal_client_jwt.post(
        "/internal/jobs",
        headers={"Authorization": f"Bearer {real_token}"},
        json={"preset_key": "hero_slide", "image_base64": _png_b64()},
    )
    lr = internal_client_jwt.get(
        "/internal/jobs",
        headers={"Authorization": f"Bearer {real_token}"},
    )
    assert lr.status_code == 200
    assert len(lr.json()["items"]) >= 1
