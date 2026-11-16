from backend.app.criteria import decompose_text
from backend.scripts.fetch_trials import parse_study


def test_live_protocol_fields_are_normalized_without_inventing_retention_inputs():
    trial = parse_study(
        {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Protocol"},
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE2"]},
                "eligibilityModule": {
                    "eligibilityCriteria": "Inclusion Criteria:\nAge >= 18 years\nComplex clinical requirement"
                },
            }
        }
    )
    assert trial.distance_km is None
    assert trial.visits_per_month is None
    assert trial.criteria[0].kind == "age"
    assert trial.criteria[1].kind == "unsupported"


def test_compound_rule_is_not_silently_partially_accepted():
    rules = decompose_text(
        "Inclusion Criteria:\nAge >= 18 years and confirmed cancer\nExclusion Criteria:\nPrior treatment"
    )
    assert all(rule.kind == "unsupported" for rule in rules)
    assert rules[1].polarity == "exclusion"
