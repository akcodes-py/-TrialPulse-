from datetime import date

import pytest

from backend.app.fhir import parse_fhir
from backend.app.fixtures import patient_bundle


@pytest.fixture
def as_of():
    return date(2026, 11, 16)


@pytest.fixture
def bundle(as_of):
    return patient_bundle("P-4092", as_of)


@pytest.fixture
def patient(bundle, as_of):
    return parse_fhir(bundle, as_of)
