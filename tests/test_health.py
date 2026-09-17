from fastapi.testclient import TestClient

from backend.api import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_batch_application_requires_explicit_approval(monkeypatch) -> None:
    calls: list[bool] = []

    async def prepare(*args, **kwargs):
        calls.append(args[-1])
        return {"status": "ready_for_review", "reason": "Approval required.", "fields_filled": [], "fields_missing": []}

    monkeypatch.setattr("backend.api.ats_automation.prepare", prepare)
    response = TestClient(app).post(
        "/applications/batch",
        json={
            "jobs": [{"application_url": "https://example.com/job/1"}],
            "name": "Candidate",
            "email": "candidate@example.com",
            "phone": "555-0100",
            "resume_path": "resume.docx",
        },
    )

    assert response.status_code == 200
    assert calls == [False]
    assert response.json()["submitted"] == 0
