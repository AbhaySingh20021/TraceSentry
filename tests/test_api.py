import json

from fastapi.testclient import TestClient

from tracesentry.main import app


def sample_trace():
    return {
        "trace_id": "api-test-trace",
        "source": "pytest",
        "spans": [
            {
                "span_id": "root",
                "name": "agent.run",
                "start_time": "2026-01-12T10:00:00Z",
                "duration_ms": 100,
                "status": "ok",
                "attributes": {},
            }
        ],
    }


def test_ingest_read_and_analyze_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACESENTRY_DB", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        response = client.post("/v1/traces", json=sample_trace())
        assert response.status_code == 201
        run_id = response.json()["run_id"]

        detail = client.get(f"/v1/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["trace"]["trace_id"] == "api-test-trace"

        report = client.post(f"/v1/runs/{run_id}/analyze")
        assert report.status_code == 200
        assert report.json()["finding_count"] == 1
        assert report.json()["findings"][0]["code"] == "NO_RULE_MATCH"


def test_duplicate_span_ids_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACESENTRY_DB", str(tmp_path / "test.db"))
    trace = sample_trace()
    trace["spans"].append(dict(trace["spans"][0]))
    with TestClient(app) as client:
        response = client.post("/v1/traces", json=trace)
    assert response.status_code == 422
    assert "unique" in response.json()["detail"]


def test_unknown_run_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACESENTRY_DB", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        response = client.get("/v1/runs/does-not-exist")
    assert response.status_code == 404
