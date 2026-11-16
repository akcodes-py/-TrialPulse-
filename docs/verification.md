# Implementation verification

Environment: Windows, Python 3.12.13, Node.js 24.15.0. The recommended portable runtime remains Python 3.12 / Node 22+.

| Check | Result |
|---|---|
| Backend suite | 23 tests passed, including actual in-memory Qdrant RRF querying with deterministic test encoders. |
| Python lint | Ruff passed. |
| Frontend | Strict TypeScript and Vite production build passed. |
| Browser flows | Four Playwright tests passed across desktop Chrome and mobile Chromium. |
| ClinicalTrials.gov | Live recruiting-study fetch completed; two normalized protocols written to ignored local data. |
| Training | XGBoost fitting, disjoint calibration, five-fold evaluation, CoxPH fitting, and joblib artifact creation completed on 1,200 synthetic rows. |
| Model inference | Five audited matches scored using the trained artifact; actual SHAP values and CoxPH curves returned. |
| Benchmark CLI | Three fixture runs evaluated successfully with per-topic and macro metrics. |
| Docker | Compose configuration validated. Container build/launch was not executed because the Docker daemon was stopped. |

Synthetic training artifacts from verification are stored locally under `artifacts/verified-synthetic/` and are not committed. To reproduce:

```sh
python -m backend.scripts.train_retention --synthetic --output artifacts/verified-synthetic
```

The verification run's base-classifier five-fold mean ROC-AUC was approximately **0.724**, held-out calibrated ROC-AUC **0.623**, and survival concordance **0.618**. These are synthetic-process diagnostics, not clinical KPIs. No tuning was performed to force the PRD targets to pass.

The Qdrant contract test uses a real local collection, named dense/sparse vectors, IDF configuration, RRF query, and payload round-trip. Its encoders are deterministic test doubles; downloading BioLORD and benchmarking a populated remote server were not part of this check. Optional provider-based LLM extraction also requires independent verification with configured credentials.

No 50,000-trial latency benchmark or real TREC retrieval comparison has been claimed. Screenshot labels preserve synthetic/illustrative provenance.
