from fastapi.testclient import TestClient

from src.api.main import app


def test_info() -> None:
    client = TestClient(app)
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "app_name" in data
    assert "app_env" in data
