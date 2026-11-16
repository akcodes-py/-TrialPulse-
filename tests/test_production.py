"""Production-readiness contracts: liveness, readiness, limits, headers, and error shape."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import get_settings


def test_liveness_is_dependency_free_and_versioned():
    body = TestClient(app).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"]


def test_readiness_reports_checks(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALPULSE_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("TRIALPULSE_RETRIEVAL", "demo")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/api/ready")
        assert response.status_code == 200
        assert response.json()["checks"]["artifact_dir"] == "ok"
    finally:
        get_settings.cache_clear()


def test_readiness_degrades_when_qdrant_unreachable(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALPULSE_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("TRIALPULSE_RETRIEVAL", "qdrant")
    monkeypatch.setenv("TRIALPULSE_QDRANT_URL", "http://127.0.0.1:1")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/api/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
    finally:
        get_settings.cache_clear()


def test_security_and_correlation_headers_are_always_present():
    response = TestClient(app).get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert len(response.headers["X-Request-ID"]) == 32


def test_declared_oversized_body_is_rejected_before_parsing(monkeypatch):
    monkeypatch.setenv("TRIALPULSE_MAX_REQUEST_BYTES", "100")
    get_settings.cache_clear()
    try:
        response = TestClient(app).post("/api/pipeline", json={"patient_id": "P-" + "x" * 400})
        assert response.status_code == 413
    finally:
        get_settings.cache_clear()


def test_validation_error_shape_is_stable():
    response = TestClient(app).post("/api/pipeline", json={"top_k": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"
