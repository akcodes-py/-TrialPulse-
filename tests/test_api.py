import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import Settings, get_settings


def test_full_pipeline_has_grounded_citations_and_measured_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALPULSE_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("TRIALPULSE_RETRIEVAL", "demo")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.post("/api/pipeline", json={"patient_id": "P-4092"})
        assert response.status_code == 200
        result = response.json()
        assert result["total_candidates"] == 6
        assert len(result["trace"]) == 5
        assert all(step["duration_ms"] >= 0 for step in result["trace"])
        ids = {result["patient"]["reference"], *(fact["reference"] for fact in result["patient"]["facts"])}
        assert all(
            set(verdict["fhir_evidence_ids"]) <= ids
            for match in result["matches"]
            for verdict in match["verdicts"]
        )
        assert any(v["verdict"] == "MISSING_LAB" for m in result["matches"] for v in m["verdicts"])
        assert sum(bool(m["verdicts"]) for m in result["matches"]) == 5
        assert all(m["retention"]["source"] == "illustrative" for m in result["matches"] if m["retention"])
        for match in result["matches"]:
            if match["retention"]:
                curve = [point["probability"] for point in match["retention"]["survival"]]
                assert curve == sorted(curve, reverse=True)
    finally:
        get_settings.cache_clear()


def test_sse_stream_has_steps_then_result(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALPULSE_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("TRIALPULSE_RETRIEVAL", "demo")
    get_settings.cache_clear()
    try:
        response = TestClient(app).post("/api/pipeline/stream", json={"patient_id": "P-2187"})
        assert response.status_code == 200
        events = response.text.strip().split("\n\n")
        assert len(events) == 6
        assert events[-1].startswith("event: result\n")
        assert json.loads(events[-1].split("data: ", 1)[1])["patient"]["id"] == "P-2187"
    finally:
        get_settings.cache_clear()


def test_upload_validation_and_unknown_patient(bundle):
    client = TestClient(app)
    assert client.get("/api/patients/unknown/fhir").status_code == 404
    assert client.post("/api/pipeline", json={"top_k": 26}).status_code == 422
    assert (
        client.post(
            "/api/pipeline/fhir", json={"bundle": bundle, "synthetic_acknowledged": False}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/pipeline/fhir", json={"bundle": {}, "synthetic_acknowledged": True}).status_code
        == 422
    )


def test_sandbox_threshold_relaxation_expands_pool():
    client = TestClient(app)
    baseline = client.post("/api/sandbox", json={"max_age": 75, "min_egfr": 45}).json()
    relaxed = client.post("/api/sandbox", json={"max_age": 85, "min_egfr": 30}).json()
    assert baseline["delta"] == 0
    assert relaxed["modified"] >= baseline["modified"]
    assert sum(bin["modified"] for bin in relaxed["bins"]) == relaxed["modified"]


def test_fixture_benchmark_is_labeled(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALPULSE_ARTIFACT_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        result = TestClient(app).get("/api/benchmarks")
        assert result.status_code == 200
        assert "not TREC" in result.json()["dataset"]
        assert len(result.json()["results"]) == 3
    finally:
        get_settings.cache_clear()


def test_settings_reject_unknown_retrieval_mode():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(retrieval="bogus")
