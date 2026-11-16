import copy

import pytest

from backend.app.fhir import parse_fhir


def test_ignores_other_patient_and_nonfinal_observations(bundle, as_of):
    extra = copy.deepcopy(bundle["entry"][-1])
    extra["resource"]["id"] = "other-patient-lab"
    extra["resource"]["subject"]["reference"] = "Patient/elsewhere"
    bundle["entry"].append(extra)
    bundle["entry"][-2]["resource"]["status"] = "entered-in-error"
    result = parse_fhir(bundle, as_of)
    assert not any(
        f.reference in {"Observation/other-patient-lab", "Observation/hba1c"} for f in result.facts
    )


def test_fullurl_patient_references_resolve(bundle, as_of):
    bundle["entry"][0]["fullUrl"] = "urn:uuid:patient-id"
    for entry in bundle["entry"][1:]:
        entry["resource"]["subject"]["reference"] = "urn:uuid:patient-id"
    assert len(parse_fhir(bundle, as_of).facts) == 7


def test_multiple_patients_and_duplicate_citations_are_rejected(bundle, as_of):
    duplicate = copy.deepcopy(bundle)
    duplicate["entry"].append(duplicate["entry"][1])
    with pytest.raises(ValueError, match="Duplicate"):
        parse_fhir(duplicate, as_of)
    bundle["entry"].append(bundle["entry"][0])
    with pytest.raises(ValueError, match="exactly one"):
        parse_fhir(bundle, as_of)


def test_partial_or_future_birth_date_is_rejected(bundle, as_of):
    for birth in ["1968", "2999-01-01"]:
        bundle["entry"][0]["resource"]["birthDate"] = birth
        with pytest.raises(ValueError, match="birthDate"):
            parse_fhir(bundle, as_of)
