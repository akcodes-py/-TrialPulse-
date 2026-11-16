from datetime import date, datetime
from typing import Any

from backend.app.schemas import Fact, PatientProfile


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None


def coding(concept: dict) -> tuple[str, str]:
    codes = concept.get("coding", [])
    first = codes[0] if codes else {}
    return first.get("code", "uncoded"), concept.get("text") or first.get("display", "Uncoded")


def parse_fhir(bundle: dict[str, Any], as_of: date) -> PatientProfile:
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("Expected a FHIR R4 Bundle")
    resources = [e.get("resource", {}) for e in bundle.get("entry", [])]
    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    if len(patients) != 1:
        raise ValueError("Provide exactly one Patient per bundle")
    patient = patients[0]
    if not patient.get("id"):
        raise ValueError("Patient.id is required")
    birth = parse_date(patient.get("birthDate"))
    if birth is None or birth > as_of:
        raise ValueError("Patient.birthDate must be a valid past date")
    age = as_of.year - birth.year - ((as_of.month, as_of.day) < (birth.month, birth.day))
    patient_ref = f"Patient/{patient['id']}"
    aliases = {patient_ref}
    aliases.update(
        e["fullUrl"] for e in bundle.get("entry", []) if e.get("resource") == patient and e.get("fullUrl")
    )
    # Citation identities must be unique, otherwise a link could point to the wrong resource.
    references = [f"{r.get('resourceType')}/{r['id']}" for r in resources if r.get("id")]
    if len(references) != len(set(references)):
        raise ValueError("Duplicate resourceType/id in bundle")
    facts = []
    for resource in resources:
        kind = resource.get("resourceType")
        if kind not in {"Condition", "Observation", "MedicationRequest", "Procedure"}:
            continue
        if not resource.get("id") or resource.get("subject", {}).get("reference") not in aliases:
            continue
        if resource.get("status") in {"entered-in-error", "cancelled", "draft", "preliminary"}:
            continue
        if kind == "Condition":
            clinical = coding(resource.get("clinicalStatus", {}))[0]
            verification = coding(resource.get("verificationStatus", {}))[0]
            if verification not in {"confirmed", "refuted"} or clinical in {
                "resolved",
                "inactive",
                "remission",
            }:
                continue
        if kind == "Procedure" and resource.get("status") != "completed":
            continue
        concept = (
            resource.get("medicationCodeableConcept", {})
            if kind == "MedicationRequest"
            else resource.get("code", {})
        )
        code, label = coding(concept)
        quantity = resource.get("valueQuantity", {})
        value = quantity.get("value")
        if value is None:
            value = resource.get("valueString")
        if value is None and resource.get("valueCodeableConcept"):
            _, value = coding(resource["valueCodeableConcept"])
        negative = coding(resource.get("verificationStatus", {}))[0] == "refuted"
        negative = negative or str(value).lower() in {"negative", "not detected", "absent"}
        facts.append(
            Fact(
                reference=f"{kind}/{resource['id']}",
                kind=kind,
                code=code,
                label=label,
                value=value,
                unit=quantity.get("code") or quantity.get("unit"),
                negative=negative,
                observed_on=parse_date(
                    resource.get("effectiveDateTime")
                    or resource.get("effectivePeriod", {}).get("end")
                    or resource.get("onsetDateTime")
                    or resource.get("authoredOn")
                    or resource.get("performedDateTime")
                ),
            )
        )
    name = patient.get("name", [{}])[0]
    full_name = " ".join([*name.get("given", []), name.get("family", "")]).strip()
    address = patient.get("address", [{}])[0]
    return PatientProfile(
        id=patient["id"],
        reference=patient_ref,
        name=full_name or patient["id"],
        age=age,
        gender=patient.get("gender", "unknown"),
        city=", ".join(filter(None, [address.get("city"), address.get("state")])),
        facts=facts,
    )
