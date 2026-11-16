from datetime import date

from backend.app.schemas import Criterion, PatientProfile, Verdict

KINDS = {
    "condition": "Condition",
    "lab": "Observation",
    "medication": "MedicationRequest",
    "procedure": "Procedure",
}


def compare(value: float | str | None, rule: Criterion) -> bool | None:
    if rule.operator == "present":
        return True
    if value is None:
        return None
    if rule.operator == "eq":
        if isinstance(value, (int, float)) and isinstance(rule.threshold, (int, float)):
            return value == rule.threshold
        return str(value).casefold() == str(rule.threshold).casefold()
    if not isinstance(value, (int, float)) or not isinstance(rule.threshold, (int, float)):
        return None
    return value >= rule.threshold if rule.operator == "gte" else value <= rule.threshold


def evaluate_rule(rule: Criterion, patient: PatientProfile) -> Verdict:
    def output(status, evidence, reason):
        return Verdict(rule_id=rule.rule_id, verdict=status, fhir_evidence_ids=evidence, reasoning=reason)

    if rule.kind == "unsupported":
        return output("UNKNOWN", [], "This criterion requires protocol review or a curated executable rule.")
    if rule.kind == "age":
        result, evidence = compare(patient.age, rule), [patient.reference]
        observation = f"Age {patient.age} years"
    else:
        facts = [f for f in patient.facts if f.kind == KINDS[rule.kind] and f.code == rule.code]
        if not facts:
            status = "MISSING_LAB" if rule.kind == "lab" else "UNKNOWN"
            return output(
                status, [], "No matching coded resource. Missing documentation does not establish absence."
            )
        facts.sort(key=lambda f: f.observed_on or date.min, reverse=True)
        fact = facts[0]
        if (
            rule.kind == "lab"
            and len({(str(f.value), f.unit) for f in facts if f.observed_on == fact.observed_on}) > 1
        ):
            return output(
                "UNKNOWN",
                [f.reference for f in facts if f.observed_on == fact.observed_on],
                "Conflicting observations at the same latest date require review.",
            )
        if rule.unit and fact.unit != rule.unit:
            return output(
                "UNKNOWN",
                [fact.reference],
                f"Unit mismatch: expected {rule.unit}; found {fact.unit}. No implicit conversion applied.",
            )
        if rule.kind in {"condition", "medication", "procedure"}:
            # Any documented positive exposure matters for exclusion, not just the latest entry.
            positives = [f for f in facts if not f.negative]
            result = bool(positives)
            evidence = [f.reference for f in positives] if positives else [fact.reference]
        elif rule.operator == "present":
            result, evidence = not fact.negative, [fact.reference]
        else:
            result, evidence = compare(fact.value, rule), [fact.reference]
        observation = f"{fact.label}: {fact.value if fact.value is not None else ('absent' if fact.negative else 'documented')} {fact.unit or ''}".strip()
    if result is None:
        return output("UNKNOWN", evidence, "The observed value cannot be evaluated by this typed comparison.")
    passed = result if rule.polarity == "inclusion" else not result
    reason = (
        "Inclusion requirement satisfied" if rule.polarity == "inclusion" else "Exclusion condition absent"
    )
    if not passed:
        reason = (
            "Inclusion requirement not satisfied"
            if rule.polarity == "inclusion"
            else "Exclusion condition present"
        )
    return output("PASS" if passed else "FAIL", evidence, f"{reason}. {observation}.")


def critique(rule: Criterion, verdict: Verdict, patient: PatientProfile, as_of: date) -> Verdict:
    valid_ids = {patient.reference, *(fact.reference for fact in patient.facts)}
    if verdict.verdict in {"PASS", "FAIL"} and not verdict.fhir_evidence_ids:
        return verdict.model_copy(
            update={"verdict": "UNKNOWN", "critic_note": "A resolved verdict requires a source citation."}
        )
    if any(reference not in valid_ids for reference in verdict.fhir_evidence_ids):
        return verdict.model_copy(
            update={
                "verdict": "UNKNOWN",
                "fhir_evidence_ids": [],
                "critic_note": "Rejected an ungrounded citation.",
            }
        )
    if rule.kind == "lab" and verdict.fhir_evidence_ids:
        fact = next(f for f in patient.facts if f.reference == verdict.fhir_evidence_ids[0])
        days = (as_of - fact.observed_on).days if fact.observed_on else None
        if days is not None and days < 0:
            return verdict.model_copy(
                update={"verdict": "UNKNOWN", "critic_note": "Observation is dated after the screening date."}
            )
        if rule.max_age_days is not None and (days is None or days > rule.max_age_days):
            age_label = f"{days} days old" if days is not None else "undated"
            return verdict.model_copy(
                update={
                    "verdict": "MISSING_LAB",
                    "reasoning": "A current observation is required before this rule can be resolved.",
                    "critic_note": f"Lab is {age_label}; protocol requires ≤ {rule.max_age_days} days. Request a repeat lab.",
                }
            )
    return verdict


def eligibility_status(verdicts: list[Verdict]) -> str:
    if any(v.verdict == "FAIL" for v in verdicts):
        return "INELIGIBLE"
    if not verdicts or any(v.verdict != "PASS" for v in verdicts):
        return "NEEDS_REVIEW"
    return "ELIGIBLE"
