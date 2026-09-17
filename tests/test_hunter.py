from fastapi.testclient import TestClient

from backend.api import app


def test_naukri_session_check() -> None:
    client = TestClient(app)
    response = client.get("/integrations/naukri/session")
    assert response.status_code == 200
    data = response.json()
    assert "open" in data
    assert "logged_in" in data


def test_hunt_status_initial() -> None:
    client = TestClient(app)
    response = client.get("/hunt/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "stats" in data
    assert "jobs_found" in data["stats"]
