export type VerdictStatus = "PASS" | "FAIL" | "MISSING_LAB" | "UNKNOWN";
export interface Fact {
  reference: string;
  kind: string;
  code: string;
  label: string;
  value: string | number | null;
  unit: string | null;
  observed_on: string | null;
  negative: boolean;
}
export interface Patient {
  id: string;
  reference: string;
  name: string;
  age: number;
  gender: string;
  city: string;
  facts: Fact[];
  synthetic: boolean;
}
export interface Criterion {
  rule_id: string;
  text: string;
  polarity: string;
  kind: string;
}
export interface Trial {
  id: string;
  title: string;
  phase: string;
  conditions: string[];
  status: string;
  summary: string;
  eligibility_text: string;
  criteria: Criterion[];
  locations: string[];
  distance_km: number | null;
  visits_per_month: number | null;
  synthetic: boolean;
}
export interface Verdict {
  rule_id: string;
  verdict: VerdictStatus;
  fhir_evidence_ids: string[];
  reasoning: string;
  critic_note: string | null;
}
export interface Retention {
  completion_probability: number | null;
  source:
    | "illustrative"
    | "synthetic-trained"
    | "cohort-trained"
    | "unavailable";
  explanation: string;
  survival: { month: number; probability: number }[];
  drivers: { feature: string; impact: number }[];
  driver_units: string;
}
export interface Match {
  trial: Trial;
  retrieval_score: number;
  dense_score: number | null;
  lexical_score: number | null;
  verdicts: Verdict[];
  eligibility: "ELIGIBLE" | "INELIGIBLE" | "NEEDS_REVIEW";
  retention: Retention | null;
}
export interface TraceStep {
  node: string;
  duration_ms: number;
  detail: string;
}
export interface PipelineResult {
  patient: Patient;
  matches: Match[];
  trace: TraceStep[];
  retrieval_mode: string;
  total_candidates: number;
  as_of: string;
}
export interface Bundle {
  resourceType: string;
  entry?: { resource: Record<string, unknown> }[];
}
export interface Benchmark {
  dataset: string;
  topic_count: number;
  relevant_grade: number;
  note: string;
  gain: string;
  results: {
    name: string;
    precision_5: number;
    precision_10: number;
    ndcg_10: number;
  }[];
  targets: { ndcg_10: number; precision_5: number };
}
export interface SandboxResult {
  total: number;
  baseline: number;
  modified: number;
  delta: number;
  source: string;
  bins: { label: string; baseline: number; modified: number }[];
}
