"""Entirely authored synthetic examples; no real trial identifiers or patient records."""

from datetime import date, timedelta

from backend.app.schemas import Criterion, Trial

PATIENTS = {
    "P-4092": ("Alexandra", "Morgan", "female", 58, 65, 62, 42),
    "P-2187": ("James", "Chen", "male", 67, 30, 72, 8),
    "P-6031": ("Sofia", "Rivera", "female", 45, 80, 91, 5),
}


def patient_bundle(patient_id: str, as_of: date) -> dict:
    if patient_id not in PATIENTS:
        raise KeyError(patient_id)
    first, last, gender, age, pdl1, egfr, lab_days = PATIENTS[patient_id]
    subject = {"reference": f"Patient/{patient_id}"}

    def concept(code, display, system="http://loinc.org"):
        return {"coding": [{"system": system, "code": code, "display": display}], "text": display}

    def observation(identifier, code, label, value, unit, days):
        result = {
            "resourceType": "Observation",
            "id": identifier,
            "status": "final",
            "subject": subject,
            "code": concept(code, label),
            "effectiveDateTime": (as_of - timedelta(days=days)).isoformat(),
        }
        if isinstance(value, (float, int)):
            result["valueQuantity"] = {
                "value": value,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": unit,
            }
        else:
            result["valueString"] = value
        return result

    resources = [
        {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {"tag": [{"system": "https://trialpulse.local/data", "code": "synthetic"}]},
            "name": [{"given": [first], "family": last}],
            "gender": gender,
            "birthDate": f"{as_of.year - age}-01-15",
            "address": [{"city": "Boston", "state": "MA"}],
        }
    ]
    for identifier, code, label in [
        ("nsclc", "254637007", "Non-small cell lung cancer"),
        ("hypertension", "38341003", "Hypertension"),
    ]:
        resources.append(
            {
                "resourceType": "Condition",
                "id": identifier,
                "subject": subject,
                "clinicalStatus": concept(
                    "active", "Active", "http://terminology.hl7.org/CodeSystem/condition-clinical"
                ),
                "verificationStatus": concept(
                    "confirmed", "Confirmed", "http://terminology.hl7.org/CodeSystem/condition-ver-status"
                ),
                "code": concept(code, label, "http://snomed.info/sct"),
            }
        )
    resources.extend(
        [
            observation("ecog", "89247-1", "ECOG performance status", 1, "{score}", 7),
            observation("pdl1", "85337-4", "PD-L1 tumor proportion score", pdl1, "%", 10),
            observation("egfr-mutation", "49551-5", "EGFR mutation", "Negative", None, 10),
            observation("egfr-renal", "33914-3", "eGFR", egfr, "mL/min/{1.73_m2}", lab_days),
            observation("hba1c", "4548-4", "Hemoglobin A1c", 6.1, "%", 12),
        ]
    )
    return {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": r} for r in resources]}


def demo_trials() -> list[Trial]:
    common = [
        Criterion(
            rule_id="INC-1",
            text="Confirmed non-small cell lung cancer",
            polarity="inclusion",
            kind="condition",
            code="254637007",
        ),
        Criterion(
            rule_id="INC-2",
            text="ECOG performance status ≤ 1",
            polarity="inclusion",
            kind="lab",
            code="89247-1",
            operator="lte",
            threshold=1,
            unit="{score}",
            max_age_days=30,
        ),
        Criterion(
            rule_id="INC-3",
            text="eGFR ≥ 45 mL/min/1.73m² within 30 days",
            polarity="inclusion",
            kind="lab",
            code="33914-3",
            operator="gte",
            threshold=45,
            unit="mL/min/{1.73_m2}",
            max_age_days=30,
        ),
        Criterion(
            rule_id="EXC-1",
            text="Activating EGFR mutation",
            polarity="exclusion",
            kind="lab",
            code="49551-5",
            operator="eq",
            threshold="Positive",
        ),
    ]
    definitions = [
        ("DEMO-001", "Precision immunotherapy for advanced NSCLC", "PHASE3", 12, 2, 50),
        ("DEMO-002", "Combination therapy in PD-L1 positive lung cancer", "PHASE2", 28, 3, 1),
        ("DEMO-003", "Targeted treatment for EGFR-mutated NSCLC", "PHASE2", 8, 4, None),
        ("DEMO-004", "Maintenance therapy after first-line lung cancer treatment", "PHASE3", 46, 1, None),
        ("DEMO-005", "Remote monitoring for adults with lung cancer", "PHASE4", 3, 1, None),
        ("DEMO-006", "Dose escalation in refractory solid tumors", "PHASE1", 95, 6, None),
    ]
    trials = []
    for identifier, title, phase, distance, visits, pdl1 in definitions:
        criteria = [r.model_copy(deep=True) for r in common]
        criteria.append(
            Criterion(
                rule_id="INC-4",
                text="Age ≥ 18 years",
                polarity="inclusion",
                kind="age",
                operator="gte",
                threshold=18,
            )
        )
        if pdl1:
            criteria.append(
                Criterion(
                    rule_id="INC-5",
                    text=f"PD-L1 expression ≥ {pdl1}%",
                    polarity="inclusion",
                    kind="lab",
                    code="85337-4",
                    operator="gte",
                    threshold=pdl1,
                    unit="%",
                )
            )
        if identifier == "DEMO-003":
            criteria[3] = Criterion(
                rule_id="INC-EGFR",
                text="Positive EGFR mutation required",
                polarity="inclusion",
                kind="lab",
                code="49551-5",
                operator="eq",
                threshold="Positive",
            )
        if identifier == "DEMO-004":
            criteria.append(
                Criterion(
                    rule_id="EXC-2",
                    text="Prior pembrolizumab therapy",
                    polarity="exclusion",
                    kind="medication",
                    code="1547545",
                )
            )
        if identifier == "DEMO-005":
            criteria = [r for r in criteria if r.rule_id != "INC-3"]
        trials.append(
            Trial(
                id=identifier,
                title=title,
                phase=phase,
                conditions=["Non-small cell lung cancer"],
                summary="Synthetic protocol for demonstrating evidence-grounded oncology screening.",
                eligibility_text="\n".join(f"{r.polarity}: {r.text}" for r in criteria),
                criteria=criteria,
                locations=["Boston, Massachusetts, United States"],
                distance_km=distance,
                visits_per_month=visits,
                synthetic=True,
            )
        )
    return trials
