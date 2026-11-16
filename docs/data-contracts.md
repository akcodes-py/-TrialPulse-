# Data and model contracts

## FHIR inputs

The import endpoint accepts JSON with a single FHIR R4 Patient and supporting resources. `synthetic_acknowledged: true` is required; it is an input contract, not a PHI detector. The UI/import route limit bundles to approximately 5 MB. Nginx enforces the network request limit in Compose.

Required Patient fields: `id`, complete `birthDate`. Supporting resources require an `id`, relevant `code.coding`, and `subject.reference` matching `Patient/{id}` or the Patient entry's `fullUrl`. Patient name/address may be absent.

Normalized facts preserve `reference`, `kind`, first coding `code`, label, typed scalar `value`, unit, observation date, and explicit negative evidence. Unsupported coding systems and alternate equivalent codes are not translated. The sample FHIR resources exercise code-level mechanics; the synthetic examples are not a medically adjudicated terminology reference.

Supported dates: ISO dates/datetimes in `effectiveDateTime`, `effectivePeriod.end`, `onsetDateTime`, `authoredOn`, and `performedDateTime`. Partial dates stay unknown. Future laboratory dates become unresolved at audit time. Age uses the request screening date rather than an LLM estimate.

Skipped resources: unrelated subjects, missing IDs, entered-in-error/cancelled/draft/preliminary states, conditions without confirmed/refuted verification, resolved/inactive/remission conditions, and incomplete procedures. Historical resolved diagnoses need an explicitly extended rule/parser design; they must not be inferred absent.

## Executable criterion

```json
{
  "rule_id": "INC-3",
  "text": "eGFR ≥ 45 mL/min/1.73m² within 30 days",
  "polarity": "inclusion",
  "kind": "lab",
  "code": "33914-3",
  "operator": "gte",
  "threshold": 45,
  "unit": "mL/min/{1.73_m2}",
  "max_age_days": 30
}
```

Kinds: age, condition, lab, medication, procedure, unsupported. Operators: gte, lte, eq, present. A coded clinical rule requires a code; numeric comparisons require numeric thresholds. Matching uses exact codes and exact declared units. A dimensional mismatch is unknown, never an implicit numeric conversion.

“eGFR” and “creatinine clearance” are not interchangeable in this implementation. Neither is calculated from an unrelated creatinine value. Latest dated lab observations are used; contradictory same-date values require review. Explicit negatives can resolve exclusions; a missing resource cannot.

## Verdict

```json
{
  "rule_id": "INC-3",
  "verdict": "MISSING_LAB",
  "fhir_evidence_ids": ["Observation/egfr-renal"],
  "reasoning": "A current observation is required before this rule can be resolved.",
  "critic_note": "Lab is 42 days old; protocol requires ≤ 30 days. Request a repeat lab."
}
```

Evidence is a list because multiple resources may support a verdict. Empty evidence is allowed only for unresolved/missing documentation; the deterministic evaluator supplies concrete citations for resolved comparisons. Citation identity validation proves the resource exists, not independently that every clinical interpretation is correct.

## Trial ingestion and indexing

Ingested JSONL has one `Trial` schema object per line. ClinicalTrials.gov NCT IDs are retained verbatim. Recruitment status is filtered to `RECRUITING`. Locations remain source text; no automatic geocoding or patient distance estimation is performed. Visits per month remain absent unless supplied by a protocol-curation process.

Collections use named `dense` and `sparse` vectors, cosine similarity for normalized dense embeddings, and Qdrant IDF handling for BM25 sparse vectors. Point IDs are stable UUID5 values derived from trial IDs. A new corpus/model requires a new collection. Model identity is included in each payload. Freeze a model revision and corpus snapshot for formal experiments.

## Retention cohort and model artifacts

Features, in fixed order:

1. `age`: years.
2. `comorbidity_count`: number of distinct active coded conditions, including the index disease in this starter.
3. `visits_per_month`: visits/month.
4. `phase`: 1, 2, 3, or 4.
5. `distance_km`: patient-to-site distance in kilometers.

Labels: `completed` (0/1, known outcome), `duration_months` (>0), `event_observed` (0/1 dropout). Completed participants cannot have a dropout event. The script expects one independent row per participant and complete finite features. Repeated patients, site clustering, time-varying covariates, and censoring/label ambiguity require a different split/modeling strategy.

Synthetic generation uses a fixed seed, sampled covariates, exponential dropout times, and planned 12/18/24-month completion. Metrics quantify only recovery of that simulated process. Real-data use must define a consistent completion endpoint and account for protocol duration, selection, missingness, confounding, site effects, competing risks, and proportional-hazards assumptions.

The local joblib artifact holds the base classifier, calibrated classifier, CoxPH model, provenance label, and training report. Only server-managed local artifacts are loaded. Prediction caches use file modification time. Python/sklearn/XGBoost/Lifelines/SHAP versions must remain compatible with the training environment.

SHAP contributions explain the base XGBoost log-odds; they do not sum to the calibrated probability. CoxPH and the classifier are separate fitted models. The default formula uses probability-point contributions and an exponential curve instead, with explicit illustrative labels.

## Evaluation files

Qrels: `topic iteration document relevance`.

Run: `topic Q0 document rank score run_name`.

The evaluator ranks by numeric score, requires unique topic/document pairs, and evaluates all qrels topics. Grade threshold is configurable; TREC eligible grade 2 is the default for Precision. Linear graded NDCG retains grade 1 as partial relevance. Negative judgments and unjudged documents have zero gain.

Report fields include dataset, topic count, grade threshold, gain convention, policy, per-baseline metrics, per-topic metrics, and missing topics. `targets` are product aspirations. The UI distinguishes the included hand-authored fixtures from real evaluation reports.

## Dataset provenance and restrictions

- **ClinicalTrials.gov:** current public API records are protocol/search documents and are not historical TREC judgments. Store retrieval date and query parameters for reproducibility.
- **Synthea:** synthetic FHIR data are suitable for pipeline development, but they are not a substitute for clinical validation. The local archive loader rejects path traversal and does not transmit bundles.
- **TREC:** historical snapshots, topics, and qrels must remain joined to their release/version. Do not compare a current live-trial index against historical qrels without documenting corpus mismatch.
- **Chia / TrialGPT-style rule corpora:** use only after verifying the exact license, sentence/criterion annotation schema, and whether the labels are permitted for redistribution. No unverified third-party URL is hard-coded in this starter.
- **AACT:** study-level outcomes can label protocol analytics only. They cannot label individual patient dropout or survival and must not be mixed with Synthea profiles for a purported observed model.
- **MIMIC-IV / Project Data Sphere:** access-controlled or registration-based patient-level sources require their own approvals, permitted-use review, de-identification controls, and secure storage. The application’s synthetic-only default does not make an imported restricted dataset automatically compliant.
