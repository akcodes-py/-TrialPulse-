# TrialPulse AI — Engineering Manual

**Objective → Observation.** This manual explains what TrialPulse AI is, why each layer exists, which technologies and datasets are used, what was actually implemented, why those decisions were made, and what advantages and limits the design carries.

Audience: engineers, reviewers, and hiring managers evaluating the system's reasoning quality, not just its UI.

Companion documents:

| Document | Purpose |
|---|---|
| [`PRD.md`](PRD.md) | Requirements, KPIs, and acceptance scope |
| [`decision.md`](decision.md) | Decision log — the "why" behind each trade-off |
| [`docs/data-contracts.md`](docs/data-contracts.md) | Exact input/output schemas and limitations |
| [`docs/verification.md`](docs/verification.md) | What was executed and observed |
| [`README.md`](README.md) | Setup, commands, and repository map |

---

## 1. Objective — what we are building and why

### 1.1 The problem

Clinical trial recruitment fails at two stages:

1. **Eligibility screening.** Deciding whether a specific patient satisfies a protocol's inclusion/exclusion criteria requires multi-hop medical logic: lab thresholds, timing windows, prior-therapy exclusions, and documented absence versus missing data.
2. **Retention.** Participants drop out before completion for reasons partly predictable from age, comorbidity burden, visit frequency, phase, and travel distance.

Keyword search and plain vector similarity both fail on the first problem. They retrieve *plausible* protocols and offer no auditable justification. Most demo systems also conflate "not found" with "not true" — the single most dangerous error in eligibility screening.

### 1.2 The objective

Build one end-to-end, evidence-grounded system that:

- Retrieves candidate protocols using hybrid (dense + sparse) biomedical search.
- Verifies eligibility rule-by-rule with **typed, deterministic verdicts**, each carrying a citation to the exact source resource.
- Distinguishes four outcomes instead of three: `PASS`, `FAIL`, `MISSING_LAB`, `UNKNOWN`.
- Predicts completion probability and retention over time with explainable models.
- Measures retrieval quality with standard TREC metrics rather than asserting quality.
- Runs end-to-end on synthetic data with **no real Protected Health Information (PHI)** anywhere in the default path.

### 1.3 The observation (result)

Running the completed system on a synthetic oncology patient produced:

- LangGraph executed five nodes with **streamed per-node latencies** (FHIR Parser → Hybrid Search → Evaluator → Protocol Critic → Retention Scorer).
- The Evaluator returned criterion-level verdicts in which **every citation resolved to a resource in the current patient bundle**; the Protocol Critic converted a numerically-passing renal value into `MISSING_LAB` because the observation was 42 days old against a 30-day protocol window.
- A negative EGFR finding **passed** a positive-mutation exclusion but **failed** a positive-mutation inclusion — the same fact, opposite verdicts, because polarity is evaluated explicitly.
- A missing prior-therapy `MedicationRequest` produced `UNKNOWN`, not `PASS` — absence of documentation is not documentation of absence.
- Backend suite: **31 tests passed**. Frontend: **4 Playwright tests passed** across desktop and mobile. Lint and builds clean.
- The trained retention path produced real XGBoost probabilities, CoxPH survival curves, and SHAP values; the default UI path is explicitly labeled illustrative.

That is the through-line of this manual: **objective → mechanism → observed behavior**.

---

## 2. What we are using — technology and data

### 2.1 Technology stack by layer

| Layer | Technology | Role |
|---|---|---|
| Standards & ingestion | HL7 FHIR R4, ClinicalTrials.gov REST API v2, Synthea, AACT | Patient resources and trial protocols |
| Embeddings & search | BioLORD-2023, FastEmbed BM25/SPLADE, Qdrant, RRF | Hybrid biomedical retrieval |
| Orchestration | LangGraph, Pydantic v2 | Stateful agent graph, schema-enforced outputs |
| Predictive ML | XGBoost, scikit-learn, Lifelines, SHAP | Completion, survival, explanation |
| Evaluation | TREC qrels/run format, `ir_datasets`, NDCG/P@K | Ground-truth retrieval scoring |
| API | FastAPI, Uvicorn, Starlette middleware | Typed, observable HTTP service |
| UI | React 19, TypeScript, Vite, lucide-react | Three-pane clinical command center |
| Packaging | Docker, Docker Compose, Nginx, GitHub Actions | Reproducible deployment and CI |

### 2.2 Datasets, and how each is legitimately used

| Layer | Dataset | Access | Why it is safe/appropriate | Hard constraint honored |
|---|---|---|---|---|
| Protocols | ClinicalTrials.gov API v2 | Open API | Public study metadata, no PHI | Live data is **not** treated as a historical TREC snapshot |
| Historical outcomes | AACT | Free registration | Relational mirror of study metadata | Normalized to **study-level** labels only |
| Patient EHR | Synthea FHIR R4 samples | Direct download | Fully synthetic people | Discovered locally; never uploaded |
| Retrieval benchmark | TREC Clinical Trials (via `ir_datasets`) | Open academic | Historical frozen snapshots + human judgments | Export keeps docs/topics/qrels joined to their release |
| Criterion logic | Chia / TrialGPT-style corpora | Varies by license | Annotated eligibility sentences | Not bundled — license/schema must be verified first |
| Retention | Project Data Sphere / MIMIC-IV | Registration / credentialed | Real patient-level trajectories | Never auto-downloaded; requires approvals |

### 2.3 The label-provenance rule (most important data decision)

AACT `COMPLETED` / `TERMINATED` / `WITHDRAWN` are **whole-study** outcomes. They cannot label an **individual participant's** dropout, and joining them to unrelated Synthea patients would fabricate a retention cohort. The repository therefore:

- Normalizes AACT only to study-level outcomes (`backend/scripts/import_aact.py`).
- Emits an explicit warning in output and docs that this must not train individual retention models.
- Requires a genuine permissioned participant dataset for XGBoost/CoxPH, or an explicitly declared proxy endpoint.

This is the difference between a demo that *looks* predictive and one that is *honest* about what it predicts.

### 2.4 Optional LLM usage — scope and safety

An OpenAI-compatible **structured** LLM can decompose protocol text during *ingestion* (offline), not during patient screening. Guarantees:

- Only **public protocol text** is sent — never patient bundles.
- Output must validate against a Pydantic v2 JSON schema; up to 3 attempts on schema/grounding failure.
- Every extracted rule must be a **verbatim substring** of the protocol.
- The **entire original protocol is retained as an unresolved review criterion**, so an omitted clause can never silently make a patient eligible.
- Failure falls back to deterministic parsing, not to permissive behavior.

---

## 3. What was implemented, and why

### 3.1 Data & standards layer

**Implemented**

- `backend/scripts/fetch_trials.py` — paginated ClinicalTrials.gov v2 ingestion with transient-error retry and atomic writes.
- `backend/app/fhir.py` — targeted FHIR R4 normalizer producing a typed `PatientProfile`.
- `backend/scripts/download_synthea.py` — safe archive download/extraction (path-traversal guarded, optional SHA-256).
- `backend/app/fhir_store.py` — read-only discovery of local synthetic bundles.
- `backend/scripts/import_aact.py`, `backend/scripts/export_trec.py` — provenance-preserving dataset loaders.

**Why**

- Real protocols must come from a live, versioned source; synthetic cohorts keep PHI out of the default path.
- The parser is deliberately *narrow*: it supports exact codes, dates, and units rather than guessing. Guessing terminology is how screening systems produce confident, wrong answers.
- Supporting `Patient/id` **and** bundle `fullUrl` references covers real Synthea output without weakening identity checks.
- Atomic writes prevent a failed fetch from destroying a previously usable corpus.

### 3.2 Embeddings & hybrid search layer

**Implemented**

- `backend/app/retrieval.py` — RRF fusion of dense (BioLORD) and sparse (FastEmbed BM25) vectors from Qdrant named vectors; a deterministic local demo path (BM25 + signed token-hash vectors) for zero-setup runs.
- `backend/scripts/index_trials.py` — fresh-collection indexing with model identity stored per payload.

**Why**

- Dense semantics handle paraphrase ("kidney function" ≈ renal labs); sparse lexical matching preserves exact tokens that matter clinically (gene symbols, drug names, codes). Hybrid retrieval is the only way to get both.
- RRF needs no score normalization between incompatible similarity scales, which makes it robust across embedding models.
- Requiring a **new collection per corpus/model** prevents silently mixing embedding versions — a classic source of invisible relevance drift.
- The demo path exists so the system is runnable and testable without a 100 MB model download; it is clearly labeled as non-biomedical.

### 3.3 Agentic eligibility layer

**Implemented**

- `backend/app/pipeline.py` — a real LangGraph `StateGraph`: Extract → Search → Evaluate → Critic → Rank, with bounded fan-out (top 25 retrieved, top 5 audited concurrently) and streamed execution traces.
- `backend/app/eligibility.py` — typed rule evaluation and the Protocol Critic (citation integrity, exclusion logic, conflicting values, lab freshness).
- `backend/app/criteria.py` — conservative decomposition: only fully-supported rules become executable; everything else stays `UNKNOWN`.
- `backend/app/schemas.py` — Pydantic v2 contracts for `Criterion`, `Verdict`, `Match`, `PipelineResponse`.

**Why the four-verdict model**

The naive three-state model (`PASS`/`FAIL`/`MISSING`) cannot express the difference between "we looked and it is false" and "we cannot tell." Conflating them causes wrongful eligibility decisions in both directions. `UNKNOWN` keeps that boundary explicit and forces the UI to surface it rather than hide it.

**Why deterministic evaluation under an agentic graph**

The graph provides orchestration, ordering, concurrency, and traceability. The *clinical decision* remains a pure function of typed facts — reproducible, unit-testable, and auditable. This is the honest way to use agents in a regulated-adjacent domain: agents coordinate, deterministic code decides.

**Why the Critic exists separately**

Two distinct failure classes need independent handling: *the evaluator reasoned from the wrong evidence* (citation integrity) and *the evidence is stale or contradictory* (freshness/conflict). Separating them keeps each check small, testable, and explainable.

### 3.4 Predictive ML layer

**Implemented**

- `backend/scripts/train_retention.py` — calibrated XGBoost completion classifier + Lifelines CoxPH survival model, with disjoint fit/calibration/test splits and a metrics artifact.
- `backend/app/retention.py` — runtime scoring using the trained artifact (real SHAP + CoxPH) or an explicitly labeled illustrative fallback.

**Why this shape**

- **Calibration is mandatory** for a "probability" the UI displays; ranking well is not the same as being calibrated.
- **Two models, two questions.** Completion ("will they finish?") and timing ("when might they leave?") are different targets. Forcing one model to answer both distorts both.
- **SHAP is reported in base-model log-odds** and labeled as such, because explainability that silently mislabels its own units is worse than none.
- **Missing inputs are not invented.** Live trials without measured distance/visit frequency return an unavailable score instead of a fabricated one.

### 3.5 Evaluation layer

**Implemented**

- `evaluation/eval_trec.py` — standard qrels/run reader; Precision@5, Precision@10, NDCG@10; per-topic and macro averaging; duplicate rejection; fixed K denominators; missing-topic → zero; unjudged → nonrelevant; configurable relevance grade.

**Why**

Borrowing TREC conventions (linear graded NDCG, grade ≥ 2 as eligible for P@K, documented unjudged policy) makes results comparable to published work and removes hidden arithmetic that quietly inflates numbers. The bundled fixture is hand-authored and labeled "not TREC," so the UI never presents a demo number as a benchmark result.

### 3.6 API & production hardening (this pass)

**Implemented**

- `backend/app/settings.py` — a single validated configuration object (environment, log level, hosts, CORS, body limit, rate limit, LLM timeout).
- `backend/app/observability.py` — JSON structured logging with request correlation; access loggers that would leak query strings are silenced.
- `backend/app/middleware.py` — correlation IDs, security headers on *every* response, declared-size rejection, and a per-client fixed-window rate limiter.
- `backend/app/main.py` — lifespan startup validation with production warnings, separate **liveness** (`/api/health`) and **readiness** (`/api/ready`) probes, stable error envelope, GZip, optional TrustedHost/CORS, and versioned responses.
- `backend/Dockerfile`, `docker-compose.yml` — non-root user, read-only root filesystem, `no-new-privileges`, dropped tmpfs, CPU/memory limits, container healthcheck, graceful shutdown, server header disabled.
- `frontend/nginx.conf` — CSP, `X-Frame-Options`, `nosniff`, immutable asset caching, gzip, and SSE-friendly proxying.
- `.github/workflows/ci.yml` — lint, format check, tests, frontend build, **and container builds**.

**Why**

| Control | Failure it prevents |
|---|---|
| Liveness ≠ readiness | Restart loops when a downstream dependency is briefly down |
| Body-size limit at the edge | Memory exhaustion from oversized uploads |
| Security headers | Clickjacking, MIME sniffing, referrer leakage |
| Rate limiting | Accidental or malicious request floods |
| Correlation IDs | Untraceable errors across async graph execution |
| Structured logs, no payloads | PHI/protocol text leaking into log aggregation |
| Stable error envelope | Leaking exception text and internals to clients |
| Read-only containers + non-root | Container escape blast radius |
| Resource limits | One service starving the host |

---

## 4. Advantages of this design

**Clinical reasoning quality**

- **Auditable, not assertive.** Every `PASS`/`FAIL` maps to a specific FHIR resource; hallucinated citations are structurally rejected.
- **Safe under uncertainty.** Missing or stale data becomes a visible action item (`MISSING_LAB` / `UNKNOWN`) instead of a silent verdict.
- **Polarity-correct.** The same finding can satisfy an exclusion and fail an inclusion — evaluated explicitly, not inferred from text similarity.

**Engineering quality**

- **Deterministic core, agentic shell.** Reproducible clinical decisions with orchestration and tracing layered on top.
- **Typed end to end.** Pydantic v2 contracts on rules, verdicts, and responses; TypeScript on the client.
- **Runnable with zero secrets.** Synthetic demo works immediately; real integrations are opt-in and explicitly labeled.
- **Provenance is a first-class feature.** Synthetic vs. trained vs. measured is always visible — in code, API fields, UI badges, and docs.
- **Deployment-ready shape.** Health/readiness probes, hardened containers, CI with container builds, and documented configuration.

**Evaluation honesty**

- Retrieval claims are computed, not asserted, using standard metrics and exported TREC data.
- Clinical KPIs are marked as targets until independently reproduced.
- The most dangerous dataset shortcut (study outcome → patient dropout) is actively blocked.

---

## 5. Verification — how to reproduce the observations

```sh
# Backend correctness, production contracts, and dataset loaders
python -m pytest -q                 # 31 tests
python -m ruff check .              # lint
python -m ruff format --check .     # formatting

# Frontend
cd frontend && npm ci && npm run build
npx playwright install chromium && npm run test:e2e   # 4 browser tests

# Deployment shape
docker compose config --quiet
docker build -f backend/Dockerfile -t trialpulse-backend .
```

Live verification performed on Python 3.12.13 / Node 24.15.0:

| Probe | Observed |
|---|---|
| `GET /api/health` | `200` · `{"status":"ok","version":"0.2.0"}` |
| `GET /api/ready` | `200` · `{"status":"ready","checks":{"artifact_dir":"ok"}}` |
| `POST /api/pipeline` | `200` · 6 matches · 5 traced nodes |
| Response headers | `X-Request-ID` (32 chars), `nosniff`, `X-Frame-Options: DENY` |
| Degraded Qdrant readiness | `503` · `{"status":"degraded"}` |

Existing tests for a criterion's stale-lab override, citation hallucination rejection, exclusion polarity, and metric arithmetic all remain green.

---

## 6. Known limitations — and why they remain

| Limitation | Reason it is not "fixed" by hand-waving |
|---|---|
| No validated retention model | Requires a permissioned patient-level cohort, not synthetic or study-level data |
| No measured TREC gain | Requires running the frozen corpus; fixtures are labeled as fixtures |
| No 50k-trial latency number | Must be measured on a populated index, not estimated |
| FHIR coverage is partial | Reference-based medications, UCUM conversion, staging, and temporal washouts need governed terminology work |
| Parsing is conservative | Unsafe compound medical logic intentionally stays `UNKNOWN` |
| "Multimodal" means records + text | No imaging/DICOM models are claimed |
| No multi-user auth | Loopback-bound starter; auth is a deployment concern with its own threat model |
| Rate limiter is per-process | Correct for one instance; use an edge/gateway limiter when scaled out |

Each limitation has an owner milestone in [`PRD.md`](PRD.md) §7 and a rationale in [`decision.md`](decision.md).

---

## 7. Configuration reference

| Variable | Default | Meaning |
|---|---|---|
| `TRIALPULSE_ENVIRONMENT` | `development` | Enables production startup warnings |
| `TRIALPULSE_LOG_LEVEL` | `INFO` | Structured log threshold |
| `TRIALPULSE_RETRIEVAL` | `demo` | `demo` (local) or `qdrant` (BioLORD + BM25) |
| `TRIALPULSE_QDRANT_URL` | `http://localhost:6333` | Vector store endpoint |
| `TRIALPULSE_ALLOWED_HOSTS` | `["*"]` | Restrict in production |
| `TRIALPULSE_CORS_ORIGINS` | `[]` | Only needed for cross-origin browser clients |
| `TRIALPULSE_MAX_REQUEST_BYTES` | `5000000` | Upload/size ceiling |
| `TRIALPULSE_RATE_LIMIT_PER_MINUTE` | `240` | Per-client request ceiling |
| `TRIALPULSE_LLM_URL` / `_API_KEY` / `_MODEL` | empty | Optional structured decomposition |

Secrets (`TRIALPULSE_LLM_API_KEY`) must be injected via environment/secret manager — never committed. `.env` is git-ignored.

---

## 8. One-paragraph summary

TrialPulse AI exists because trial matching fails on evidence, not on retrieval. It uses hybrid biomedical search to find plausible protocols, a deterministic LangGraph workflow to verify them rule-by-rule with exact FHIR citations and four honest verdict states, and calibrated, explainable models to describe retention without overclaiming it. It is built on open, synthetic-by-default datasets with explicit provenance rules, hardened for deployment with health/readiness probes and security controls, and evaluated with standard metrics rather than asserted quality. Its advantage is not that it answers every question — it is that it is precise about which questions it has actually answered.
