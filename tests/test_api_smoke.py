from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from gpt_agent.schema import VisionAnalysis
from main import app


@patch("main.analyze_image_for_pipeline")
def test_process_image_product_keep(mock_vision):
    mock_vision.return_value = VisionAnalysis(scene_description="mock")
    client = TestClient(app)
    im = Image.new("RGB", (600, 600), (90, 120, 140))
    buf = BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/process-image",
        files={"image": ("x.png", buf.getvalue(), "image/png")},
        data={"type": "product", "background": "keep", "format": "webp"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "product"
    assert data["width"] == 800 and data["height"] == 800
    assert data["validation_ok"] is True
    fid = data["file_id"]
    d = client.get(f"/outputs/{fid}")
    assert d.status_code == 200
