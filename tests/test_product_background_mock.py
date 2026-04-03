"""Product pipeline with rembg mocked — runs without installing rembg/onnx."""

import numpy as np
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from gpt_agent.schema import VisionAnalysis
from main import app


def _fake_rembg_output(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = rgb
    out[:, :, 3] = 255
    return out


@patch("main.analyze_image_for_pipeline")
@patch("image_processor.ops._rembg_remove")
def test_product_background_white(mock_rembg, mock_vision):
    mock_vision.return_value = VisionAnalysis(scene_description="mock")

    def _side_effect(arr: np.ndarray) -> np.ndarray:
        return _fake_rembg_output(arr)

    mock_rembg.side_effect = _side_effect

    client = TestClient(app)
    im = Image.new("RGB", (400, 300), (200, 50, 80))
    buf = BytesIO()
    im.save(buf, format="PNG")
    r = client.post(
        "/process-image",
        files={"image": ("p.png", buf.getvalue(), "image/png")},
        data={"type": "product", "background": "white", "format": "webp"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["validation_ok"] is True
    assert data["background"] == "white"
    assert "background_removal" in data["operations"]
    mock_rembg.assert_called()


@patch("main.analyze_image_for_pipeline")
@patch("image_processor.ops._rembg_remove")
def test_product_background_transparent_webp(mock_rembg, mock_vision):
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    mock_rembg.side_effect = lambda arr: _fake_rembg_output(arr)

    client = TestClient(app)
    im = Image.new("RGB", (500, 500), (10, 200, 100))
    buf = BytesIO()
    im.save(buf, format="PNG")
    r = client.post(
        "/process-image",
        files={"image": ("p.png", buf.getvalue(), "image/png")},
        data={"type": "product", "background": "transparent", "format": "webp"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["validation_ok"] is True
    assert data["background"] == "transparent"
    assert "background_removal" in data["operations"]
