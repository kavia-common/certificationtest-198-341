from fastapi.testclient import TestClient

from src.api.main import app


def test_health_endpoint_returns_healthy():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("message") == "Healthy"
