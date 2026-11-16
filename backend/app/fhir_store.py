"""Read-only discovery of locally downloaded synthetic FHIR bundles."""

import json
from pathlib import Path

from backend.app.settings import get_settings


def bundle_paths(root: Path | None = None) -> list[Path]:
    directory = root or get_settings().fhir_dir
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.rglob("*.json") if path.is_file() and path.stat().st_size <= 5_000_000
    )


def read_bundle(patient_id: str, root: Path | None = None) -> dict | None:
    """Find a single Patient/{patient_id} Bundle without following arbitrary references."""
    for path in bundle_paths(root):
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if bundle.get("resourceType") != "Bundle":
            continue
        if any(
            entry.get("resource", {}).get("resourceType") == "Patient"
            and entry.get("resource", {}).get("id") == patient_id
            for entry in bundle.get("entry", [])
        ):
            return bundle
    return None


def patient_ids(root: Path | None = None) -> list[str]:
    found = []
    for path in bundle_paths(root):
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        patients = [
            entry.get("resource", {})
            for entry in bundle.get("entry", [])
            if entry.get("resource", {}).get("resourceType") == "Patient"
        ]
        if len(patients) == 1 and patients[0].get("id"):
            found.append(patients[0]["id"])
    return sorted(set(found))
