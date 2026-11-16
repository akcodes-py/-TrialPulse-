# TrialPulse AI — implementation decisions

This is the requested **`decision.md`** decision log. It records how the product specification maps to the delivered research starter.

## 001 · Deliver the complete vertical slice

**Decision:** ship a React/TypeScript dashboard, FastAPI service, real LangGraph orchestration, runnable synthetic examples, optional biomedical retrieval and trained retention integrations, evaluation tools, Docker Compose, and project documentation together.

**Reason:** the first run should demonstrate a complete patient-to-audit workflow without requiring model downloads, credentials, or cohort data.

## 002 · Explicit provenance in every mode

| Component | Default | Optional research integration |
|---|---|---|
| Patient data | Three authored synthetic FHIR bundles | Imported synthetic Synthea FHIR R4 bundle |
| Protocols | Six authored `DEMO-*` protocols | ClinicalTrials.gov recruiting records with real NCT IDs |
| Retrieval | Local BM25 + signed token-hash vectors + RRF | BioLORD + FastEmbed BM25 + Qdrant RRF |
| Rule verification | Typed deterministic rules | Same evidence evaluator with curated rules; structured LLM decomposition is optional |
| Retention | Labeled illustrative formula and exponential curve | Calibrated XGBoost, Lifelines CoxPH, base-model SHAP |
| Benchmarks | Metrics computed on hand-authored synthetic rankings | User-provided TREC qrels and run files |

Default dense vectors are **not** biomedical embeddings. Formula terms are **not** SHAP. Fixture rankings are **not** TREC results. No ROC-AUC, latency SLO, or relevance target is declared achieved by shipping this code.

## 003 · Four verdicts, with consistent exclusion semantics

- `PASS`: the inclusion requirement is satisfied, or the exclusion condition is explicitly absent.
- `FAIL`: an inclusion requirement is not satisfied, or an exclusion condition is present.
- `MISSING_LAB`: the required observation is missing, undated when freshness is required, or too old.
- `UNKNOWN`: missing non-lab documentation, incompatible units, conflicting observations, unsupported logic, or invalid citations.

**Reason:** the original three-value schema cannot distinguish an unknown medication history from a missing lab. No matching MedicationRequest is not evidence that prior exposure did not occur. A negative EGFR result can satisfy an exclusion rule; the same result fails a positive-mutation inclusion rule.

Any `FAIL` makes a trial `INELIGIBLE`. Otherwise unresolved rules make it `NEEDS_REVIEW`. Only a nonempty, fully passing audit yields `ELIGIBLE` (displayed as “Criteria met”). This is a screening result, not an enrollment authorization.

## 004 · Make evidence identities inspectable

Every resolved verdict cites one or more `ResourceType/id` values from the current patient profile. The critic rejects unknown references. The parser rejects duplicate identities and multi-patient bundles and ignores unrelated subjects. The UI opens the exact source resource in a keyboard-accessible dialog.

FHIR parsing supports direct `Patient/id` and bundle `fullUrl` subject references, dated observations, codeable medication requests, completed procedures, and confirmed/refuted conditions. It is a targeted normalizer, not a complete FHIR validator or terminology server. Reference-based medications, component observations, all coding translations, UCUM conversions, historical resolved diseases, temporal washouts, staging logic, and image interpretation need additional domain handling.

## 005 · Deterministic graph, bounded optional extraction

`FHIR Parser → Hybrid Search → Evaluator → Protocol Critic → Retention Scorer`

The graph retrieves at most 25 candidates and audits at most five concurrently. Each request owns its graph state; no checkpoint database persists patient data. Actual completed-node durations stream over SSE. The imported-bundle endpoint returns the same trace after completion.

Simple age rules and authored coded criteria are executable. Unknown natural-language rules remain review items. Optional LLM decomposition uses an OpenAI-compatible structured response, validates with Pydantic v2, requires verbatim protocol text, and retries schema/grounding failures up to three times. The original protocol remains an unresolved review criterion after LLM extraction to avoid silently treating an incomplete extraction as complete eligibility coverage.

## 006 · Ranking scores are not calibrated clinical probabilities

Display RRF scores as scores, not “94% fit.” Candidates are grouped by screening status; retention is a secondary ranking signal for audited matches. Ineligible candidates cannot outrank eligible ones through retention alone. Never infer enrollment appropriateness from completion probability.

Demo RRF uses `k=60`; live Qdrant uses its server RRF defaults. Absolute scores across these modes are not comparable.

## 007 · Retention labels, horizons, and explanations

Training uses one independent row per participant, a held-out test split, a disjoint sigmoid-calibration split, and five-fold base-classifier ROC-AUC. CoxPH uses duration in months and an explicit dropout event indicator. The completion outcome must be known; early-censored participants must not be treated as non-completers.

The classifier predicts the dataset-defined completion endpoint. The independently fitted survival model reports retention at 6, 12, and 24 months; its values are not forced to equal the classifier score. SHAP describes the base XGBoost margin in log-odds, not the calibrated probability. The comorbidity feature here counts distinct active coded conditions; it is not a validated Charlson index.

Live protocols do not receive invented distance or visit-frequency inputs. Their retention result is `unavailable` until those inputs are populated from a valid source. A `cohort-trained` label identifies data origin, not clinical validation.

## 008 · Reproducible evaluation conventions

- Read standard four-column qrels and six-column TREC run files.
- Rank by run score descending; use descending document ID to break score ties.
- Use grade ≥ 2 as eligible for Precision@K by default; configurable on the CLI.
- Use linear nonnegative graded gain for NDCG@10, matching `trec_eval ndcg_cut` conventions.
- Keep denominators fixed at K, even for short runs.
- Evaluate every qrels topic; missing run topics score zero.
- Treat unjudged documents as nonrelevant; reject duplicate topic/document pairs.

The included three synthetic ranking files are unit/demo inputs. Their labels describe intended baseline shapes, not outputs of trained biomedical systems. A real comparison needs the same frozen TREC corpus, topic set, and judgment release for all runs. Live current trials cannot be substituted for a historical TREC corpus.

## 009 · Local-first deployment

Compose starts Qdrant, a non-root Python backend, and an Nginx-served Vite build. Published ports bind to loopback. The default Python image omits optional large ML/retrieval dependencies; set `PYTHON_EXTRAS=retrieval,ml` to enable them. Artifacts and Qdrant indexes persist, but uploaded patient bundles do not.

`package-lock.json` locks frontend dependencies. Python direct dependencies have compatibility bounds in `pyproject.toml`; a deployment should freeze the resolved environment for its OS/accelerator. Docker image tags and model revisions should be pinned to digests/revisions for a fixed benchmark release. First model download and cold-start embedding time are separate from warmed retrieval latency.

## 010 · Scope of this release

This release is a functioning **research/portfolio starter**, not a certified clinical product. It includes the UI and software integrations requested in the PRD. Clinical validation, full temporal reasoning, an annotated TREC-to-FHIR bridge, a real retention cohort, production authentication, and 50,000-trial performance measurements are subsequent milestones. The word “multimodal” currently means structured records plus text; DICOM/image models are not included.

## 011 · Dataset loaders and labels

**Decision:** add loaders for the recommended public sources, but do not imply that availability makes all data interchangeable.

- Synthea bundles are discovered locally and surfaced as synthetic patient records.
- ClinicalTrials.gov is fetched live and is not treated as a historical TREC snapshot.
- `ir_datasets` exports versioned TREC docs/topics/qrels into the existing evaluator format.
- AACT study status is normalized only to study-level labels. It is intentionally rejected as a participant dropout target.
- MIMIC-IV and Project Data Sphere remain manual, approval/registration-gated inputs; there is no downloader or automatic training path.

This prevents the most dangerous shortcut in the proposed matrix: attaching a trial's `TERMINATED` status to unrelated Synthea patients and reporting it as observed individual retention.
