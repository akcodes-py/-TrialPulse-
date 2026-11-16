import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronDown,
  Code2,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  Info,
  MapPin,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import type {
  Bundle,
  Match,
  Patient,
  Retention,
  TraceStep,
  VerdictStatus,
} from "./types";

export const statusLabel = {
  ELIGIBLE: "Criteria met",
  INELIGIBLE: "Not eligible",
  NEEDS_REVIEW: "Needs review",
};
export const verdictLabel: Record<VerdictStatus, string> = {
  PASS: "Pass",
  FAIL: "Fail",
  MISSING_LAB: "Missing lab",
  UNKNOWN: "Review",
};

export function PatientInspector({
  patient,
  onRaw,
  onEvidence,
}: {
  patient: Patient;
  onRaw: () => void;
  onEvidence: (id: string) => void;
}) {
  const conditions = patient.facts.filter(
    (fact) => fact.kind === "Condition" && !fact.negative,
  );
  const labs = patient.facts.filter((fact) => fact.kind === "Observation");
  return (
    <aside className="panel patient-panel">
      <div className="panel-heading">
        <span>
          <span className="step-number">01</span> Patient profile
        </span>
        <span className="tiny-badge">FHIR R4</span>
      </div>
      <div className="patient-identity">
        <div className="avatar">
          {patient.name
            .split(" ")
            .map((part) => part[0])
            .slice(0, 2)
            .join("")}
          <span />
        </div>
        <h2>{patient.name}</h2>
        <span className="muted mono">{patient.id} · Synthetic patient</span>
        <div className="demographic-chips">
          <span>{patient.age} years</span>
          <span className="capitalize">{patient.gender}</span>
        </div>
        <div className="location">
          <MapPin size={13} /> {patient.city || "Location not recorded"}
        </div>
      </div>
      <section className="inspector-section">
        <h3>
          ACTIVE CONDITIONS <span>{conditions.length}</span>
        </h3>
        {conditions.length ? (
          conditions.map((fact) => (
            <button
              className="condition"
              key={fact.reference}
              onClick={() => onEvidence(fact.reference)}
            >
              <span className="condition-dot" />
              <span>
                {fact.label}
                <small className="mono">{fact.code}</small>
              </span>
              <ExternalLink size={12} />
            </button>
          ))
        ) : (
          <p className="muted">No active coded conditions found.</p>
        )}
      </section>
      <section className="inspector-section">
        <h3>
          LAB OBSERVATIONS <FlaskConical size={13} />
        </h3>
        {labs.map((fact) => (
          <button
            className="lab-row"
            key={fact.reference}
            onClick={() => onEvidence(fact.reference)}
          >
            <span>
              {fact.label}
              <small>{fact.observed_on ?? "Undated"}</small>
            </span>
            <strong className={fact.negative ? "teal-text" : ""}>
              {fact.value ?? "—"}
              <small>
                {fact.unit === "%"
                  ? "%"
                  : fact.unit === "{score}"
                    ? "score"
                    : fact.unit?.startsWith("mL")
                      ? "mL/min/1.73m²"
                      : fact.unit}
              </small>
            </strong>
          </button>
        ))}
      </section>
      <button className="raw-button" onClick={onRaw}>
        <Code2 size={16} /> Inspect raw FHIR <ExternalLink size={13} />
      </button>
      <div className="privacy-note">
        <ShieldCheck size={14} />
        <span>Synthetic records · no patient data stored</span>
      </div>
    </aside>
  );
}

export function TrialCard({
  match,
  rank,
  selected,
  onSelect,
  onEvidence,
}: {
  match: Match;
  rank: number;
  selected: boolean;
  onSelect: () => void;
  onEvidence: (id: string) => void;
}) {
  const { trial } = match;
  const passed = match.verdicts.filter((v) => v.verdict === "PASS").length;
  const missing = match.verdicts.filter(
    (v) => v.verdict === "MISSING_LAB",
  ).length;
  return (
    <article
      id={`trial-${trial.id}`}
      className={`trial-card ${selected ? "selected" : ""}`}
    >
      <button
        className="trial-toggle"
        onClick={onSelect}
        aria-expanded={selected}
        aria-controls={`audit-${trial.id}`}
      >
        <div className="trial-topline">
          <span className="trial-id mono">
            {trial.id} <span>#{String(rank).padStart(2, "0")}</span>
          </span>
          <span className={`status-badge ${match.eligibility.toLowerCase()}`}>
            <span />
            {statusLabel[match.eligibility]}
          </span>
        </div>
        <h3>{trial.title}</h3>
        <div className="trial-meta">
          <span>{trial.phase.replace("PHASE", "Phase ")}</span>
          <span>
            {trial.synthetic
              ? "Oncology"
              : (trial.conditions[0] ?? "Condition unspecified")}
          </span>
          <span>
            <MapPin size={12} />
            {trial.distance_km == null
              ? "Distance unknown"
              : `${trial.distance_km} km away`}
          </span>
        </div>
        <div className="trial-summary">
          <span className="retrieval-badge">
            <Sparkles size={12} /> RRF {match.retrieval_score.toFixed(4)}
          </span>
          <span>
            {match.verdicts.length
              ? `${passed}/${match.verdicts.length} criteria passed`
              : "Not audited"}
            {missing > 0 && ` · ${missing} lab needed`}
          </span>
          <ChevronDown size={17} className={selected ? "rotated" : ""} />
        </div>
      </button>
      {selected && (
        <div id={`audit-${trial.id}`} className="audit">
          <div className="audit-heading">
            <FileCheck2 size={14} /> CRITERION-LEVEL AUDIT{" "}
            <span>Schema validated</span>
          </div>
          {match.verdicts.length === 0 && (
            <p className="empty-copy">
              Outside the top-five audit window. Eligibility has not been
              assessed.
            </p>
          )}
          {match.verdicts.map((verdict) => (
            <div
              className={`criterion ${verdict.verdict.toLowerCase()}`}
              key={verdict.rule_id}
            >
              <div className="verdict-icon">
                {verdict.verdict === "PASS" ? (
                  <Check size={13} />
                ) : verdict.verdict === "FAIL" ? (
                  <X size={13} />
                ) : (
                  <span>!</span>
                )}
              </div>
              <div className="criterion-body">
                <div className="criterion-title">
                  <span>
                    {trial.criteria.find((c) => c.rule_id === verdict.rule_id)
                      ?.text ?? verdict.rule_id}
                  </span>
                  <span
                    className={`verdict-tag ${verdict.verdict.toLowerCase()}`}
                  >
                    {verdictLabel[verdict.verdict]}
                  </span>
                </div>
                <p>{verdict.reasoning}</p>
                {verdict.critic_note && (
                  <div className="critic-note">
                    <Info size={12} />
                    <span>{verdict.critic_note}</span>
                  </div>
                )}
                <div className="evidence-links">
                  <span className="mono rule-id">{verdict.rule_id}</span>
                  {verdict.fhir_evidence_ids.map((id) => (
                    <button key={id} onClick={() => onEvidence(id)}>
                      <ArrowUpRight size={11} />
                      {id}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <div className="audit-footer">
            <ShieldCheck size={13} />{" "}
            {trial.synthetic ? (
              "Authored synthetic protocol · exact resource citations"
            ) : (
              <a
                href={`https://clinicaltrials.gov/study/${trial.id}`}
                target="_blank"
                rel="noreferrer"
              >
                View source protocol ↗
              </a>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

function SurvivalChart({ retention }: { retention: Retention }) {
  const [month, setMonth] = useState(12);
  const width = 280,
    height = 160,
    left = 34,
    right = 12,
    top = 12,
    bottom = 27;
  const x = (m: number) => left + (m / 24) * (width - left - right);
  const y = (p: number) => top + (1 - p) * (height - top - bottom);
  const coordinates = retention.survival.map(
    (point) => `${x(point.month)},${y(point.probability)}`,
  );
  const path = `M ${coordinates.join(" L ")}`;
  const selected = retention.survival.find((point) => point.month === month);
  return (
    <div className="survival-chart">
      <div className="chart-caption">
        <span>Retention over time</span>
        <strong>
          {selected ? `${Math.round(selected.probability * 100)}%` : "—"}{" "}
          <small>at {month} mo</small>
        </strong>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Retention curve from 0 to 24 months. ${selected ? Math.round(selected.probability * 100) : "Unknown"} percent at ${month} months.`}
      >
        <defs>
          <linearGradient id="curve-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2a9d89" stopOpacity=".2" />
            <stop offset="100%" stopColor="#2a9d89" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[1, 0.75, 0.5, 0.25, 0].map((value) => (
          <g key={value}>
            <line
              x1={left}
              x2={width - right}
              y1={y(value)}
              y2={y(value)}
              stroke="#e7eceb"
              strokeDasharray="3 4"
            />
            <text x={left - 7} y={y(value) + 3} textAnchor="end">
              {value * 100}%
            </text>
          </g>
        ))}
        <path
          d={`${path} L ${x(24)},${y(0)} L ${x(0)},${y(0)} Z`}
          fill="url(#curve-fill)"
        />
        <path
          d={path}
          fill="none"
          stroke="#1b8d79"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        {selected && (
          <>
            <line
              x1={x(month)}
              x2={x(month)}
              y1={y(selected.probability)}
              y2={y(0)}
              stroke="#1b8d79"
              strokeDasharray="3 3"
            />
            <circle
              cx={x(month)}
              cy={y(selected.probability)}
              r="4"
              fill="#1b8d79"
              stroke="white"
              strokeWidth="2"
            />
          </>
        )}
        {[0, 6, 12, 18, 24].map((value) => (
          <text key={value} x={x(value)} y={height - 9} textAnchor="middle">
            {value}
            {value === 24 ? " mo" : ""}
          </text>
        ))}
      </svg>
      <div className="chart-periods" aria-label="Retention horizon">
        {[6, 12, 24].map((value) => (
          <button
            key={value}
            className={month === value ? "active" : ""}
            onClick={() => setMonth(value)}
            aria-pressed={month === value}
          >
            {value} months
          </button>
        ))}
      </div>
    </div>
  );
}

export function RetentionPanel({ match }: { match?: Match }) {
  const retention = match?.retention;
  const probability = retention?.completion_probability;
  const illustrative = retention?.source === "illustrative";
  return (
    <aside className="panel retention-panel">
      <div className="panel-heading">
        <span>
          <span className="step-number">03</span> Retention outlook
        </span>
        <Activity size={16} />
      </div>
      {retention && probability != null ? (
        <>
          <div className="retention-overview">
            <div className="eyebrow">COMPLETION PROBABILITY</div>
            <div className="probability">
              {(probability * 100).toFixed(1)}
              <span>%</span>
              <ArrowUpRight size={24} />
            </div>
            <span className="source-badge">
              {illustrative
                ? "Illustrative estimate"
                : retention.source === "synthetic-trained"
                  ? "Synthetic-trained model"
                  : "Cohort-trained model"}
            </span>
            <p>
              For <strong className="mono">{match?.trial.id}</strong> ·{" "}
              {match?.trial.visits_per_month} visits / month
            </p>
          </div>
          <section className="retention-section">
            <h3>
              <Activity size={14} /> RETENTION CURVE
              <span>{illustrative ? "Demo formula" : "CoxPH"}</span>
            </h3>
            <SurvivalChart retention={retention} />
          </section>
          <section className="retention-section">
            <h3>
              <ArrowDownLeft size={14} /> COMPLETION DRIVERS
              <span>{illustrative ? "Illustrative" : "SHAP"}</span>
            </h3>
            <div className="driver-legend">
              <span>
                <i className="negative-dot" /> Lowers completion
              </span>
              <span>
                <i className="positive-dot" /> Raises
              </span>
            </div>
            {retention.drivers.map((driver) => (
              <div className="driver" key={driver.feature}>
                <div>
                  <span>{driver.feature}</span>
                  <strong
                    className={driver.impact >= 0 ? "teal-text" : "amber-text"}
                  >
                    {driver.impact > 0 ? "+" : ""}
                    {illustrative
                      ? (driver.impact * 100).toFixed(1) + " pp"
                      : driver.impact.toFixed(3)}
                  </strong>
                </div>
                <div className="driver-track">
                  <span
                    className={driver.impact >= 0 ? "positive" : "negative"}
                    style={{
                      width: `${Math.min(100, (Math.abs(driver.impact) / Math.max(...retention.drivers.map((d) => Math.abs(d.impact)), 0.001)) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            ))}
            <p className="chart-footnote">
              {illustrative
                ? "Additive demo contributions, not SHAP values."
                : `Units: ${retention.driver_units}.`}
            </p>
          </section>
          <div className="model-note">
            <Info size={15} />
            <p>{retention.explanation}</p>
          </div>
        </>
      ) : (
        <div className="retention-empty">
          <Activity size={36} />
          <h3>More context, better predictions.</h3>
          <p>
            {retention?.explanation ??
              "Select an audited trial to explore its retention outlook."}
          </p>
        </div>
      )}
      {match && match.eligibility !== "ELIGIBLE" && (
        <div className="eligibility-note">
          Retention does not establish eligibility. Resolve the criterion audit
          first.
        </div>
      )}
    </aside>
  );
}

const nodeNames = [
  "FHIR Parser",
  "Hybrid Search",
  "Evaluator",
  "Protocol Critic",
  "Retention Scorer",
];
export function TraceBar({
  steps,
  running,
}: {
  steps: TraceStep[];
  running: boolean;
}) {
  return (
    <section className="trace-bar" aria-label="Pipeline execution trace">
      <div className="trace-label">
        <span className={running ? "live-dot pulse" : "live-dot"} />
        <span>
          AGENT TRACE
          <small>
            {running
              ? "Processing live"
              : steps.length === nodeNames.length
                ? "Execution complete"
                : steps.length
                  ? "Execution interrupted"
                  : "Ready to run"}
          </small>
        </span>
      </div>
      <div className="trace-steps">
        {nodeNames.map((name, index) => {
          const step = steps.find((s) => s.node === name);
          return (
            <div
              className={`trace-step ${step ? "complete" : running && index === steps.length ? "working" : ""}`}
              key={name}
              title={step?.detail}
            >
              <span className="trace-icon">
                {step ? <Check size={12} /> : index + 1}
              </span>
              <span>
                {name}
                <small>
                  {step
                    ? `${step.duration_ms.toFixed(1)} ms`
                    : running && index === steps.length
                      ? "Running…"
                      : "Waiting"}
                </small>
              </span>
            </div>
          );
        })}
      </div>
      <div className="trace-total">
        {(
          steps.reduce((sum, step) => sum + step.duration_ms, 0) / 1000
        ).toFixed(2)}
        <span>seconds</span>
      </div>
    </section>
  );
}

export function FhirModal({
  bundle,
  reference,
  onClose,
}: {
  bundle: Bundle | null;
  reference: string | null;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const resource = reference
    ? bundle?.entry?.find(
        (entry) =>
          `${entry.resource.resourceType}/${entry.resource.id}` === reference,
      )?.resource
    : bundle;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => previous?.focus();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="fhir-dialog"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
      aria-labelledby="fhir-title"
    >
      <div className="modal-heading">
        <div>
          <span className="eyebrow">EVIDENCE INSPECTOR</span>
          <h2 id="fhir-title">{reference ?? "Raw FHIR R4 bundle"}</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close evidence inspector"
        >
          <X size={20} />
        </button>
      </div>
      <div className="modal-info">
        <ShieldCheck size={14} />{" "}
        {reference
          ? "Exact resource from the current patient bundle"
          : "Synthetic data · displayed in memory only"}
      </div>
      <pre>
        {resource
          ? JSON.stringify(resource, null, 2)
          : "Resource not found in the loaded bundle."}
      </pre>
    </dialog>
  );
}
