# Three-minute demo

## 1. Patient context

Open the workspace. Alexandra Morgan is an authored synthetic oncology patient, not a real person. Show age, coded conditions, observation dates, and raw FHIR. Click a condition to inspect the exact `Condition/id` resource.

## 2. Evidence-grounded screening

Run the pipeline. The bottom bar receives real completed-node timings from LangGraph. Search for `DEMO-001` and expand the protocol.

- Confirmed NSCLC is supported by a coded Condition.
- ECOG is supported by a dated Observation.
- The renal-function value meets the numeric threshold, but its observation is 42 days old. The critic requires a repeat lab when the protocol demands ≤ 30 days.
- A negative mutation observation passes a corresponding positive-mutation exclusion.

Show `DEMO-003` to contrast the same negative evidence with a positive-mutation **inclusion** requirement. Show `DEMO-004` to explain why missing prior-treatment documentation is unknown rather than evidence of no treatment. Some candidates may be outside the five-trial audit window; those explicitly say “Not audited.”

Change to James Chen or Sofia Rivera. The renal lab is fresh; rerun results and citations change together. Use the status filter and export a full audit JSON.

## 3. Retention provenance

Select an audited trial. Toggle 6/12/24 months on the curve. Without artifacts, describe the score and contributions as illustrative formulas. After running the synthetic training command, show the **Synthetic-trained model** badge, actual CoxPH curve, and SHAP contributions in base-model log-odds. Explain that synthetic training is not clinical validation.

## 4. Evaluation and protocol design

Open **Benchmark lab**. Change metric selection and point to the synthetic-fixture label. Explain that a real TREC report replaces this using the same evaluator and a frozen corpus/qrels set.

Open **Protocol sandbox**. Raise maximum age and lower the eGFR threshold. Show the patient-count delta and age-group distribution. Reset to baseline. This simulates only those two criteria on 240 authored synthetic profiles.

## Good portfolio evidence

- Include the decision log alongside screenshots or a recording.
- Report actual test results and the environment used.
- Label any demonstration/training dataset in the image or caption.
- Present clinical KPIs as unmeasured targets until there is a reproducible, independent evaluation.

## Screenshot capture

Run the local API and Vite, then run `npm run capture` in `frontend/`. It creates `docs/dashboard.png`, `docs/benchmark.png`, and `docs/sandbox.png` with Playwright. Set `TRIALPULSE_DEMO_URL` to capture another locally running deployment.
