# Product Requirements Document

**Project:** TrialPulse AI — Agentic Clinical Trial Matcher & Retention Predictor  
**Product specification version:** 1.0  
**Implementation version:** 0.1.0 — Research / portfolio starter  
**Decision log:** [`decision.md`](decision.md)

## 1. Executive summary

Clinical trial recruitment faces two connected problems: determining eligibility across complex medical criteria and retaining enrolled participants through completion. Keyword search alone does not verify laboratory thresholds, exclusions, or temporal requirements; semantic similarity alone does not establish clinical eligibility.

TrialPulse AI brings patient context, biomedical retrieval, auditable criterion verification, and retention analytics into one workspace. The target architecture combines HL7 FHIR R4 records, ClinicalTrials.gov v2 protocols, BioLORD/PubMedBERT embeddings, hybrid Qdrant search, LangGraph, Pydantic v2, calibrated XGBoost, Lifelines survival analysis, and TREC evaluation.

The first release supplies an end-to-end synthetic demo and optional research integrations. Targets below are requirements to measure, not claims of completed clinical validation.

## 2. Users and jobs to be done

| Persona | Need |
|---|---|
| Clinical research coordinator | Quickly screen synthetic patient profiles, inspect exact evidence, and identify missing screening labs. |
| Principal investigator / protocol designer | Explore how age and renal-function thresholds affect a patient pool. |
| ML evaluator / hiring manager | Inspect reproducible retrieval metrics, graph traces, structured schemas, and explainable model predictions. |

## 3. Functional requirements

### Module 1: Data and standards

**FR-1.1 — Trial ingestion.** Fetch recruiting studies through the ClinicalTrials.gov REST API v2 with pagination and transient-error retries. Normalize NCT ID, title, phase, conditions, recruitment status, site locations, summary, and raw eligibility text. Store a local JSONL corpus atomically.

**FR-1.2 — Synthetic EHR parsing.** Normalize synthetic FHIR R4 bundles containing Patient, Condition, Observation, MedicationRequest, and Procedure resources. Preserve exact source identities. Calculate age at the screening date. Support Synthea-style direct and fullUrl subject references. Reject ambiguous multi-patient or duplicate-identity bundles.

### Module 2: Biomedical embeddings and hybrid search

**FR-2.1 — Dual-vector indexing.** In research mode, generate normalized BioLORD dense embeddings and FastEmbed BM25 sparse vectors, store both in a named Qdrant collection, and retain full trial payloads. A replaceable biomedical embedding model must use the same representation at index and query time.

**FR-2.2 — Candidate retrieval.** Fuse dense and sparse prefetched results with Reciprocal Rank Fusion and return top K ≤ 25. Target a warmed retrieval latency under 300 ms against a 50,000+ trial index. Display RRF as a ranking score rather than a probability. The local demo uses clearly labeled token-hash vectors and BM25.

### Module 3: Agentic eligibility verification

**FR-3.1 — Decomposition.** Split inclusion/exclusion text into independently reviewable rules. Execute only supported typed comparisons or curated coded rules. Unsupported or compound medical logic must remain unresolved. Optional LLM extraction must validate against Pydantic and preserve protocol text grounding.

**FR-3.2 — Stateful workflow.** Use an actual LangGraph graph with:

1. **EHR Extractor:** produce a normalized context with source citations.
2. **Retrieval node:** obtain up to 25 candidate protocols.
3. **Criteria Evaluator:** concurrently audit the top five with rule ID, verdict, FHIR evidence IDs, and reasoning.
4. **Protocol Critic:** verify citation identity, exclusion interpretation, conflicting observations, and lab freshness.
5. **Retention Scorer:** attach available completion/survival analytics and rank without overriding eligibility.

**FR-3.3 — Verdict semantics.** Return `PASS`, `FAIL`, `MISSING_LAB`, or `UNKNOWN`. The fourth status is an implementation correction described in `decision.md`. Missing history must not be interpreted as an explicit negative. A `FAIL` dominates unresolved rules. Empty audits are not eligible.

### Module 4: Retention and dropout prediction

**FR-4.1 — Completion classification.** Train a calibrated XGBoost classifier from age, active-condition count, visit frequency, phase, and travel distance. Report five-fold base-model ROC-AUC, held-out calibrated ROC-AUC, and Brier score. Keep calibration and test observations disjoint from base-model fitting.

**FR-4.2 — Survival analysis.** Fit Lifelines CoxPH to observed time and dropout-event labels. Report a personalized curve including 6, 12, and 24 months. Show SHAP feature contributions with their correct base-margin units. Explicitly distinguish synthetic training, cohort training, and illustrative formulas.

**FR-4.3 — Missing inputs.** Do not invent visit counts or travel distances for live trials. Surface an unavailable score with the required inputs when features are incomplete.

### Module 5: Evaluation and benchmarking

**FR-5.1 — Offline comparison.** Evaluate BM25, dense, and hybrid/agent-reranked TREC run files against a shared qrels release. Compute Precision@5, Precision@10, and NDCG@10, per topic and macro averaged. Preserve topic denominators and report missing topics. Default Precision relevance threshold is grade ≥ 2; NDCG uses linear graded gain.

**FR-5.2 — Honest provenance.** Included fixture scores must be labeled synthetic and must not be described as measured TREC gains. Targets and observed results must be visually distinct.

## 4. UI and experience

### 4.1 Three-pane command center

- **Patient inspector:** demographics, active conditions, observations with dates/units, raw FHIR viewer, and exact resource inspection.
- **Ranked matches and audit:** searchable/filterable protocol cards, phase, distance when known, RRF score, eligibility badge, criterion-level verdicts, critic flags, and clickable citations.
- **Retention analytics:** source-labeled probability, selectable 6/12/24-month retention horizon, and directional explanation bars.
- **Execution bar:** actual node-by-node durations streamed as the graph executes.
- **Actions:** change synthetic patient, rerun, import a synthetic JSON bundle in memory, and export a structured audit.

### 4.2 Secondary views

- **Benchmark lab:** interactive metric selector, baseline comparison chart, results table, dataset provenance, and visible target KPIs.
- **Protocol sandbox:** maximum-age/minimum-eGFR sliders, reproducible synthetic cohort, baseline/modified counts, age-group chart, and reset action.

### 4.3 Usability

Responsive desktop/mobile layouts, keyboard-accessible controls, modal focus/escape handling, reduced-motion support, loading and empty states, network-error messages, and request cancellation when patient selection changes.

## 5. Non-functional requirements

| Requirement | Target / implementation contract |
|---|---|
| Retrieval latency | < 300 ms on a warmed, documented 50,000+ trial deployment; not yet benchmarked. |
| Full five-trial audit | < 4 seconds for the supported execution mode; track observed node timings. External LLM decomposition is an offline ingestion step. |
| Schema validity | All API responses and optional LLM extraction outputs validate with Pydantic v2. Invalid optional extraction receives up to three attempts and conservative fallback. |
| Citation grounding | Cite only current-patient resource identities; reject invented IDs. |
| Data handling | Default synthetic fixtures only; imported synthetic bundles processed in memory; no patient checkpoint persistence. |
| Reproducibility | Single-command Docker Compose launch; documented optional dependency groups, fixed random seeds, frontend lockfile, repeatable test commands. |
| Observability | Request-scoped trace; labeled data/model sources; explicit errors rather than silent fallback from failed live retrieval. |

## 6. Success metrics

| Category | Target | Evaluation requirement |
|---|---|---|
| Retrieval quality | NDCG@10 ≥ 0.68; ≥ 18% relative improvement over BM25 | Shared held-out TREC topics and corpus; report uncertainty and evaluation conventions. |
| Eligibility precision | Precision@5 ≥ 0.80 | Human-annotated relevance judgments; separate retrieval relevance from complete clinical eligibility. |
| Citation grounding | ≥ 98% valid FHIR IDs | Check exact identities; separately evaluate whether cited content supports the verdict. |
| Retention discrimination | ROC-AUC ≥ 0.78 | Five-fold cohort evaluation with appropriate independent/grouped splits. |

No clinical KPI is established by synthetic fixture performance.

## 7. Milestones

1. **Core data and retrieval:** ingestor, FHIR normalizer, dual-vector Qdrant indexing, reproducible local demo.
2. **Agentic reasoning:** LangGraph, strict schemas, conservative decomposition, citations, critic edge cases.
3. **Predictive ML:** synthetic/cohort training interface, calibrated completion classification, survival model, SHAP, metrics artifacts.
4. **UI and evaluation:** responsive command center, benchmark runner/view, sandbox, Docker, README and demo assets.
5. **Research validation:** frozen TREC corpus runs, adjudicated rule coverage, real labeled retention cohort, temporal/survival diagnostics, scale/latency measurement.

## 8. Release acceptance

- Synthetic first run works without model credentials.
- Demonstration evidence is inspectable and exported audits validate.
- Stale labs and unknown prior-medication histories remain unresolved.
- Optional live ingestion and indexing have documented commands.
- Retention artifacts can be trained and loaded with explicit provenance.
- Fixture evaluation is labeled and real run files are accepted by the same evaluator.
- Backend tests, TypeScript build, browser interactions, and Compose configuration checks are executable from the repository.
