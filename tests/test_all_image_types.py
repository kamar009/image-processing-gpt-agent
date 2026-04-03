"""Smoke: каждый тип пресета даёт ожидаемые размеры (Vision замокан)."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from gpt_agent.schema import VisionAnalysis
from main import app


@patch("main.analyze_image_for_pipeline")
@pytest.mark.parametrize(
    ("itype", "exp_w", "exp_h"),
    [
        ("category", 1200, 800),
        ("banner", 1920, 900),
        ("portfolio_interior", 1600, 900),
    ],
)
def test_preset_output_dimensions(mock_vision, itype: str, exp_w: int, exp_h: int):
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    im = Image.new("RGB", (900, 600), (40, 90, 120))
    buf = BytesIO()
    im.save(buf, format="PNG")
    r = client.post(
        "/process-image",
        files={"image": ("x.png", buf.getvalue(), "image/png")},
        data={"type": itype, "format": "webp", "background": "keep"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["validation_ok"] is True
    assert data["width"] == exp_w and data["height"] == exp_h
