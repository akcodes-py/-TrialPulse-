from datetime import timedelta

from backend.app.eligibility import critique, eligibility_status, evaluate_rule
from backend.app.fixtures import demo_trials
from backend.app.schemas import Criterion, Verdict


def test_absent_medication_is_unknown_not_exclusion_failure(patient):
    rule = Criterion(
        rule_id="EXC-1",
        text="Prior anti-PD-1 therapy",
        polarity="exclusion",
        kind="medication",
        code="1547545",
    )
    verdict = evaluate_rule(rule, patient)
    assert verdict.verdict == "UNKNOWN"
    assert verdict.fhir_evidence_ids == []


def test_negative_egfr_passes_exclusion_but_fails_positive_inclusion(patient):
    rule = demo_trials()[0].criteria[3]
    exclusion = evaluate_rule(rule, patient)
    inclusion = evaluate_rule(rule.model_copy(update={"polarity": "inclusion"}), patient)
    assert exclusion.verdict == "PASS"
    assert inclusion.verdict == "FAIL"
    assert exclusion.fhir_evidence_ids == ["Observation/egfr-mutation"]


def test_critic_overrides_numeric_pass_for_stale_lab(patient, as_of):
    rule = demo_trials()[0].criteria[2]
    initial = evaluate_rule(rule, patient)
    assert initial.verdict == "PASS"
    checked = critique(rule, initial, patient, as_of)
    assert checked.verdict == "MISSING_LAB"
    assert "42 days old" in checked.critic_note
    assert checked.fhir_evidence_ids == ["Observation/egfr-renal"]


def test_lab_freshness_boundary_and_future_dates(patient, as_of):
    rule = demo_trials()[0].criteria[2]
    fact = next(f for f in patient.facts if f.code == rule.code)
    for days, expected in [(30, "PASS"), (31, "MISSING_LAB"), (-1, "UNKNOWN")]:
        fact.observed_on = as_of - timedelta(days=days)
        assert critique(rule, evaluate_rule(rule, patient), patient, as_of).verdict == expected


def test_incompatible_units_and_conflicting_labs_require_review(patient):
    rule = demo_trials()[0].criteria[2]
    fact = next(f for f in patient.facts if f.code == rule.code)
    fact.unit = "mg/dL"
    assert evaluate_rule(rule, patient).verdict == "UNKNOWN"
    fact.unit = rule.unit
    patient.facts.append(fact.model_copy(update={"reference": "Observation/conflicting", "value": 10}))
    assert evaluate_rule(rule, patient).verdict == "UNKNOWN"


def test_critic_rejects_hallucinated_citation(patient, as_of):
    rule = demo_trials()[0].criteria[0]
    forged = Verdict(
        rule_id=rule.rule_id,
        verdict="PASS",
        fhir_evidence_ids=["Condition/not-real"],
        reasoning="Unsupported assertion",
    )
    checked = critique(rule, forged, patient, as_of)
    assert checked.verdict == "UNKNOWN"
    assert checked.fhir_evidence_ids == []
    uncited = forged.model_copy(update={"fhir_evidence_ids": []})
    assert critique(rule, uncited, patient, as_of).verdict == "UNKNOWN"


def test_failure_dominates_missing_data_and_empty_audit_is_not_eligible():
    verdicts = [
        Verdict(rule_id="1", verdict="FAIL", fhir_evidence_ids=[], reasoning="Fail"),
        Verdict(rule_id="2", verdict="MISSING_LAB", fhir_evidence_ids=[], reasoning="Missing"),
    ]
    assert eligibility_status(verdicts) == "INELIGIBLE"
    assert eligibility_status([]) == "NEEDS_REVIEW"
