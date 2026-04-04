from fastapi.testclient import TestClient

from main import app


def test_metrics_includes_disk_volume_fields():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "disk_volume_used_pct" in data
    assert "disk_volume_free_gb" in data
    assert "disk_volume_total_gb" in data
    assert data["disk_volume_used_pct"] >= 0 or data["disk_volume_used_pct"] == -1.0
