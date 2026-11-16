"""TrialPulse AI API: synthetic-patient screening with evidence-grounded audits."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.fhir import parse_fhir
from backend.app.fhir_store import patient_ids, read_bundle
from backend.app.fixtures import PATIENTS, patient_bundle
from backend.app.middleware import RateLimitMiddleware, RequestContextMiddleware
from backend.app.observability import configure_logging, request_id
from backend.app.pipeline import graph, response_from_state, run_pipeline
from backend.app.schemas import FHIRRequest, PipelineRequest, PipelineResponse, SandboxRequest
from backend.app.settings import Settings, get_settings
from backend.app.version import __version__
from evaluation.eval_trec import evaluate_files

logger = logging.getLogger("trialpulse.app")


def _validate_runtime(settings: Settings) -> list[str]:
    warnings = []
    if settings.environment == "production":
        if settings.allowed_hosts == ["*"]:
            warnings.append("TRIALPULSE_ALLOWED_HOSTS is wildcard in production; restrict it to known hosts.")
        if settings.retrieval == "qdrant" and "localhost" in settings.qdrant_url:
            warnings.append("Production retrieval points at localhost Qdrant; use a managed service URL.")
        if settings.llm_url and not settings.llm_api_key:
            warnings.append("An LLM URL is set without a key; structured decomposition will be skipped.")
    return warnings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    for warning in _validate_runtime(settings):
        logger.warning(warning, extra={"path": "startup"})
    logger.info(
        f"startup version={__version__} env={settings.environment} retrieval={settings.retrieval}",
        extra={"path": "startup"},
    )
    yield
    logger.info("shutdown", extra={"path": "shutdown"})


app = FastAPI(
    title="TrialPulse AI",
    version=__version__,
    description="Synthetic-data clinical screening research workspace. Not a medical device.",
    lifespan=lifespan,
)

_settings = Settings()
# Middleware order: the last added is outermost. RequestContext wraps everything so every
# response (including rate-limit and error responses) receives correlation and security headers.
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
app.add_middleware(GZipMiddleware, minimum_size=1000)
if _settings.allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_settings.allowed_hosts)
app.add_middleware(RateLimitMiddleware, limit=_settings.rate_limit_per_minute)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Request validation failed", "errors": exc.errors()}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    # Never echo exception text or payloads to the client; record the correlation id for tracing.
    logger.error("unhandled_error", exc_info=exc, extra={"path": "error", "status": 500})
    return JSONResponse(
        {"detail": "Internal server error", "request_id": request_id.get("-")}, status_code=500
    )


def bundle_for(patient_id: str, as_of: date):
    local_bundle = read_bundle(patient_id)
    if local_bundle is not None:
        return local_bundle
    try:
        return patient_bundle(patient_id, as_of)
    except KeyError:
        raise HTTPException(404, "Unknown synthetic patient") from None


@app.get("/api/health")
def health():
    """Liveness: process is up. Must not depend on downstream services."""
    return {"status": "ok", "version": __version__, "environment": _settings.environment}


@app.get("/api/ready")
def ready():
    """Readiness: dependencies needed to serve the configured mode are usable."""
    settings = get_settings()
    checks = {"retrieval": settings.retrieval}
    failures: list[str] = []
    try:
        settings.artifact_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.artifact_dir / f".probe-{uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["artifact_dir"] = "ok"
    except OSError:
        checks["artifact_dir"] = "unwritable"
        failures.append("artifact_dir")
    if settings.retrieval == "qdrant":
        try:
            from backend.app.retrieval import qdrant_client

            qdrant_client().get_collections()
            checks["qdrant"] = "ok"
        except Exception as exc:  # noqa: BLE001 - readiness must degrade, not crash
            checks["qdrant"] = f"unavailable: {type(exc).__name__}"
            failures.append("qdrant")
    status = 503 if failures else 200
    return JSONResponse(
        {"status": "degraded" if failures else "ready", "checks": checks, "version": __version__},
        status_code=status,
    )


@app.get("/api/patients")
def patients():
    today = date.today()
    profiles = [parse_fhir(patient_bundle(identifier, today), today) for identifier in PATIENTS]
    for identifier in patient_ids():
        if identifier not in PATIENTS:
            bundle = read_bundle(identifier)
            if bundle is not None:
                try:
                    profiles.append(parse_fhir(bundle, today))
                except ValueError:
                    continue
    return profiles


@app.get("/api/patients/{patient_id}/fhir")
def fhir(patient_id: str):
    return bundle_for(patient_id, date.today())


@app.post("/api/pipeline", response_model=PipelineResponse)
async def pipeline(request: PipelineRequest):
    today = date.today()
    bundle = bundle_for(request.patient_id, today)
    try:
        return await run_pipeline(bundle, request, today)
    except (ImportError, ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, f"Pipeline dependency unavailable: {type(exc).__name__}") from exc


@app.post("/api/pipeline/stream")
async def pipeline_stream(request: PipelineRequest):
    today = date.today()
    bundle = bundle_for(request.patient_id, today)

    async def events():
        state = {"bundle": bundle, "request": request, "as_of": today, "trace": []}
        try:
            async for update in graph.astream(state, stream_mode="updates"):
                for values in update.values():
                    state.update(values)
                    yield "event: step\ndata: " + state["trace"][-1].model_dump_json() + "\n\n"
            yield "event: result\ndata: " + response_from_state(state).model_dump_json() + "\n\n"
        except Exception as exc:
            logger.error("pipeline_stream_error", exc_info=exc, extra={"path": "stream", "status": 500})
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "message": "Pipeline failed. Check backend dependencies and service configuration.",
                        "request_id": request_id.get("-"),
                    }
                )
                + "\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/pipeline/fhir", response_model=PipelineResponse)
async def screen_fhir(request: FHIRRequest):
    today = date.today()
    encoded = json.dumps(request.bundle)
    if len(encoded) > get_settings().max_request_bytes:
        raise HTTPException(413, "Synthetic bundle exceeds the configured size limit")
    try:
        parse_fhir(request.bundle, today)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return await run_pipeline(request.bundle, PipelineRequest(), today)
    except (ImportError, ConnectionError, RuntimeError) as exc:
        raise HTTPException(503, f"Pipeline dependency unavailable: {type(exc).__name__}") from exc


@app.get("/api/benchmarks")
def benchmarks():
    artifact = get_settings().artifact_dir / "evaluation_results.json"
    if artifact.exists():
        return json.loads(artifact.read_text(encoding="utf-8"))
    fixture_dir = Path(__file__).resolve().parents[2] / "evaluation" / "fixtures"
    return evaluate_files(
        fixture_dir / "qrels.txt",
        {
            "BM25": fixture_dir / "bm25.run",
            "Dense": fixture_dir / "dense.run",
            "Hybrid + audit": fixture_dir / "hybrid.run",
        },
        dataset="Synthetic fixture · 3 topics (not TREC)",
    )


@app.post("/api/sandbox")
def sandbox(request: SandboxRequest):
    # Fixed, reproducible synthetic cohort; no patient data persists between requests.
    cohort = [{"age": 30 + (i * 17) % 61, "egfr": 20 + (i * 29) % 96} for i in range(240)]

    def eligible(patient, age, egfr):
        return patient["age"] <= age and patient["egfr"] >= egfr

    baseline = sum(eligible(p, 75, 45) for p in cohort)
    modified = sum(eligible(p, request.max_age, request.min_egfr) for p in cohort)
    bins = []
    for lower in range(30, 90, 10):
        subset = [p for p in cohort if lower <= p["age"] < lower + 10 + (1 if lower == 80 else 0)]
        bins.append(
            {
                "label": f"{lower}–{lower + 9 if lower < 80 else 90}",
                "baseline": sum(eligible(p, 75, 45) for p in subset),
                "modified": sum(eligible(p, request.max_age, request.min_egfr) for p in subset),
            }
        )
    return {
        "total": len(cohort),
        "baseline": baseline,
        "modified": modified,
        "delta": modified - baseline,
        "bins": bins,
        "source": "Synthetic cohort; age and eGFR only. Other protocol criteria are not simulated.",
    }
