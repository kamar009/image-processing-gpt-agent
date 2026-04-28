"""A3/A4: POST /process-image для type=furniture_portfolio — поля, разрешение, 422."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from gpt_agent.schema import VisionAnalysis
from main import app
from presets.definitions import FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX


def _png_bytes() -> bytes:
    im = Image.new("RGB", (900, 600), (10, 20, 30))
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int, h: int, *, orientation: int | None = None) -> bytes:
    im = Image.new("RGB", (w, h), (10, 20, 30))
    buf = BytesIO()
    if orientation is None:
        im.save(buf, format="JPEG", quality=88)
    else:
        ex = Image.Exif()
        ex[274] = orientation
        im.save(buf, format="JPEG", quality=88, exif=ex.tobytes())
    return buf.getvalue()


def _jpeg_meets_min_bytes() -> bytes:
    return _jpeg_bytes(FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX, 900)


def test_furniture_portfolio_requires_furniture_scene():
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={
            "type": "furniture_portfolio",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
        },
    )
    assert r.status_code == 422
    assert "furniture_scene" in r.json()["detail"].lower()


def test_furniture_portfolio_requires_output_target():
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "format": "webp",
            "background": "keep",
        },
    )
    assert r.status_code == 422
    assert "output_target" in r.json()["detail"].lower()


def test_furniture_portfolio_invalid_furniture_scene():
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "not_a_scene",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
        },
    )
    assert r.status_code == 422
    d = r.json()["detail"]
    assert "furniture_scene" in d.lower() or "invalid" in d.lower()


def test_furniture_portfolio_invalid_output_target():
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "instagram",
            "format": "webp",
            "background": "keep",
        },
    )
    assert r.status_code == 422
    assert "output_target" in r.json()["detail"].lower()


@patch("main.analyze_image_for_pipeline")
def test_furniture_portfolio_enhanced_software_v1_when_requested(mock_vision, monkeypatch):
    monkeypatch.delenv("FURNITURE_ENHANCED_ENABLED", raising=False)
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_meets_min_bytes(), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "enhanced": "1",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enhanced_requested"] is True
    assert data["enhanced_applied"] is True
    assert "furniture_enhanced_software_v1" in data["operations"]


def test_furniture_portfolio_input_resolution_too_small_422():
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_bytes(800, 1199), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 422
    detail = r.json()["detail"].lower()
    assert "longest side" in detail or "1199" in detail
    assert str(FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX) in r.json()["detail"]


def test_furniture_portfolio_exif_orientation_counts_toward_long_side():
    """Stored 900×1199 with EXIF orientation 6 → upright 1199×900; long side 1199 < 1200 → 422."""
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_bytes(900, 1199, orientation=6), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 422


@patch("main.analyze_image_for_pipeline")
def test_furniture_portfolio_exif_meets_minimum_stored_smaller_side(mock_vision):
    """Файл 900×1200 + orientation 6 → после transpose 1200×900, порог выполнен."""
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_bytes(900, 1200, orientation=6), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["validation_ok"] is True
    assert r.json()["people_detected"] is False


@patch("main.analyze_image_for_pipeline")
def test_furniture_portfolio_people_detected_adds_warning_still_200(mock_vision):
    mock_vision.return_value = VisionAnalysis(scene_description="room", people_detected=True)
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_meets_min_bytes(), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["people_detected"] is True
    assert any("люди" in w.lower() for w in data["validation_warnings"])


@pytest.mark.parametrize(
    ("target", "exp_w", "exp_h"),
    [
        ("site", 1600, 900),
        ("banner", 1920, 900),
        ("social_vk", 1080, 1080),
        ("social_telegram", 1280, 720),
        ("social_max", 1080, 1350),
    ],
)
@patch("main.analyze_image_for_pipeline")
def test_furniture_portfolio_output_dimensions_per_target(mock_vision, target, exp_w, exp_h):
    """C1/C2: пресет по output_target → размер выхода как в §4."""
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_meets_min_bytes(), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": target,
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["output_target"] == target
    assert data["width"] == exp_w and data["height"] == exp_h
    assert data["validation_ok"] is True


@patch("main.analyze_image_for_pipeline")
def test_furniture_portfolio_success_site_dimensions(mock_vision):
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    r = client.post(
        "/process-image",
        files={"image": ("x.jpg", _jpeg_meets_min_bytes(), "image/jpeg")},
        data={
            "type": "furniture_portfolio",
            "furniture_scene": "meeting_room",
            "output_target": "site",
            "format": "webp",
            "background": "keep",
            "vision_provider": "fallback",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "furniture_portfolio"
    assert data["furniture_scene"] == "meeting_room"
    assert data["output_target"] == "site"
    assert data["enhanced_requested"] is False
    assert data["enhanced_applied"] is False
    assert data["width"] == 1600 and data["height"] == 900
    assert data["validation_ok"] is True
    assert data["people_detected"] is False
