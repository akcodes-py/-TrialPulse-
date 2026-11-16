from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(StrictModel):
    reference: str
    kind: str
    code: str
    label: str
    value: float | str | None = None
    unit: str | None = None
    observed_on: date | None = None
    negative: bool = False


class PatientProfile(StrictModel):
    id: str
    reference: str
    name: str
    age: int = Field(ge=0, le=130)
    gender: str
    city: str
    facts: list[Fact]
    synthetic: bool = True


class Criterion(StrictModel):
    rule_id: str
    text: str
    polarity: Literal["inclusion", "exclusion"]
    kind: Literal["age", "condition", "lab", "medication", "procedure", "unsupported"]
    code: str | None = None
    operator: Literal["gte", "lte", "eq", "present"] = "present"
    threshold: float | str | None = None
    unit: str | None = None
    max_age_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_rule(self):
        if self.kind in {"condition", "lab", "medication", "procedure"} and not self.code:
            raise ValueError("A coded clinical rule requires code")
        if self.operator in {"gte", "lte"} and not isinstance(self.threshold, (int, float)):
            raise ValueError("Numeric comparisons require a numeric threshold")
        if self.operator == "eq" and self.threshold is None:
            raise ValueError("Equality requires a threshold")
        return self


class Trial(StrictModel):
    id: str
    title: str
    phase: str
    conditions: list[str]
    status: str = "RECRUITING"
    summary: str
    eligibility_text: str
    criteria: list[Criterion] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    distance_km: float | None = Field(default=None, ge=0)
    visits_per_month: float | None = Field(default=None, ge=0)
    synthetic: bool = False


class Verdict(StrictModel):
    rule_id: str
    verdict: Literal["PASS", "FAIL", "MISSING_LAB", "UNKNOWN"]
    fhir_evidence_ids: list[str]
    reasoning: str
    critic_note: str | None = None


class Driver(StrictModel):
    feature: str
    impact: float


class SurvivalPoint(StrictModel):
    month: int
    probability: float = Field(ge=0, le=1)


class Retention(StrictModel):
    completion_probability: float | None = Field(default=None, ge=0, le=1)
    source: Literal["illustrative", "synthetic-trained", "cohort-trained", "unavailable"]
    explanation: str
    survival: list[SurvivalPoint] = Field(default_factory=list)
    drivers: list[Driver] = Field(default_factory=list)
    driver_units: str


class Match(StrictModel):
    trial: Trial
    retrieval_score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    verdicts: list[Verdict] = Field(default_factory=list)
    eligibility: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"] = "NEEDS_REVIEW"
    retention: Retention | None = None


class TraceStep(StrictModel):
    node: str
    duration_ms: float
    detail: str


class PipelineRequest(StrictModel):
    patient_id: str = "P-4092"
    top_k: int = Field(default=25, ge=1, le=25)
    audit_k: int = Field(default=5, ge=1, le=5)


class PipelineResponse(StrictModel):
    patient: PatientProfile
    matches: list[Match]
    trace: list[TraceStep]
    retrieval_mode: str
    total_candidates: int
    as_of: date


class SandboxRequest(StrictModel):
    max_age: int = Field(default=75, ge=18, le=100)
    min_egfr: float = Field(default=45, ge=0, le=120)


class FHIRRequest(StrictModel):
    bundle: dict[str, Any]
    synthetic_acknowledged: Literal[True]
