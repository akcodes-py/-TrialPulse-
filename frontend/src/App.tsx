import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCheck,
  ChevronDown,
  CircleHelp,
  Clock3,
  Download,
  FlaskConical,
  LayoutDashboard,
  LoaderCircle,
  Play,
  Search,
  SlidersHorizontal,
  Upload,
  X,
} from "lucide-react";
import { jsonPost, request, streamPipeline } from "./api";
import {
  FhirModal,
  PatientInspector,
  RetentionPanel,
  TraceBar,
  TrialCard,
} from "./components";
import { BenchmarkView, SandboxView } from "./SecondaryViews";
import type { Bundle, Patient, PipelineResult, TraceStep } from "./types";

type Tab = "matching" | "benchmark" | "sandbox";

export default function App() {
  const [tab, setTab] = useState<Tab>("matching");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState("P-4092");
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [selected, setSelected] = useState("");
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modal, setModal] = useState<{ reference: string | null } | null>(null);
  const [help, setHelp] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const trialList = useRef<HTMLDivElement>(null);
  const uploaded = useRef<Bundle | null>(null);

  useEffect(() => {
    const list = trialList.current;
    const card = document.getElementById(`trial-${selected}`);
    if (list && card && window.matchMedia("(min-width: 1001px)").matches) {
      list.scrollTop +=
        card.getBoundingClientRect().top - list.getBoundingClientRect().top;
    }
  }, [selected]);

  const run = useCallback(async (id: string) => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setRunning(true);
    setSteps([]);
    setError("");
    setResult(null);
    setBundle(null);
    setModal(null);
    try {
      let next: PipelineResult;
      let nextBundle: Bundle;
      if (uploaded.current) {
        nextBundle = uploaded.current;
        next = await request<PipelineResult>(
          "/pipeline/fhir",
          jsonPost(
            { bundle: nextBundle, synthetic_acknowledged: true },
            current.signal,
          ),
        );
        if (!current.signal.aborted) setSteps(next.trace);
      } else {
        const results = await Promise.all([
          streamPipeline(
            id,
            (step) => {
              if (!current.signal.aborted)
                setSteps((previous) => [...previous, step]);
            },
            current.signal,
          ),
          request<Bundle>(`/patients/${id}/fhir`, { signal: current.signal }),
        ]);
        next = results[0];
        nextBundle = results[1];
      }
      if (current.signal.aborted) return;
      setResult(next);
      setBundle(nextBundle);
      setSelected(next.matches[0]?.trial.id ?? "");
    } catch (err) {
      if (!current.signal.aborted)
        setError(
          err instanceof Error ? err.message : "An unexpected error occurred.",
        );
    } finally {
      if (!current.signal.aborted) setRunning(false);
    }
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    request<Patient[]>("/patients", { signal: abort.signal })
      .then(setPatients)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    void run(patientId);
    return () => controller.current?.abort();
  }, [patientId, run]);

  const matches =
    result?.matches.filter(
      (match) =>
        (statusFilter === "all" || match.eligibility === statusFilter) &&
        `${match.trial.title} ${match.trial.id}`
          .toLowerCase()
          .includes(filter.toLowerCase()),
    ) ?? [];
  const activeMatch = result?.matches.find(
    (match) => match.trial.id === selected,
  );
  const displayedPatient =
    result?.patient ?? patients.find((patient) => patient.id === patientId);
  const evidence =
    result?.matches.flatMap((match) =>
      match.verdicts.flatMap((verdict) => verdict.fhir_evidence_ids),
    ) ?? [];
  const uniqueEvidence = new Set(evidence).size;
  const totalMs = steps.reduce((sum, step) => sum + step.duration_ms, 0);

  async function upload(file?: File) {
    if (!file) return;
    try {
      if (file.size > 5_000_000)
        throw new Error(
          "Please choose a synthetic FHIR bundle smaller than 5 MB.",
        );
      const parsed = JSON.parse(await file.text()) as Bundle;
      if (parsed.resourceType !== "Bundle")
        throw new Error("The file must be a FHIR R4 Bundle.");
      uploaded.current = parsed;
      await run(patientId);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not read the JSON file.",
      );
    }
    if (fileInput.current) fileInput.current.value = "";
  }

  function exportAudit() {
    if (!result) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `trialpulse-${result.patient.id}-audit.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <header className="app-header">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("matching");
          }}
        >
          <span className="brand-icon">
            <Activity size={24} strokeWidth={2} />
          </span>
          <span>
            TrialPulse<span className="brand-ai">AI</span>
            <small>CLINICAL INTELLIGENCE</small>
          </span>
        </a>
        <nav className="main-nav" aria-label="Workspace views">
          {(
            [
              ["matching", LayoutDashboard, "Patient matching"],
              ["benchmark", BarChart3, "Benchmark lab"],
              ["sandbox", SlidersHorizontal, "Protocol sandbox"],
            ] as const
          ).map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={tab === id ? "active" : ""}
              aria-current={tab === id ? "page" : undefined}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
        <div className="header-tools">
          <span className="workspace-status">
            <span />
            Research workspace
          </span>
          <button
            className="icon-button help-button"
            onClick={() => setHelp(!help)}
            aria-label="About this workspace"
            aria-expanded={help}
          >
            <CircleHelp size={19} />
          </button>
          <div className="user-avatar" aria-label="Research workspace">
            RC
          </div>
        </div>
      </header>
      {help && (
        <div className="help-popover">
          <button
            className="icon-button"
            onClick={() => setHelp(false)}
            aria-label="Close help"
          >
            <X size={16} />
          </button>
          <strong>Welcome to TrialPulse AI</strong>
          <p>
            Screen synthetic FHIR patients, inspect exact evidence, and explore
            research estimates. Use the benchmark lab for measured ranking
            metrics and the sandbox to compare protocol thresholds.
          </p>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
            Open API documentation ↗
          </a>
        </div>
      )}
      <main id="main">
        {tab === "matching" ? (
          <>
            <section className="workspace-intro">
              <div>
                <div className="eyebrow">
                  <span className="tiny-diamond" /> EVIDENCE-GROUNDED MATCHING
                </div>
                <h1>
                  Every match, backed by evidence<span>.</span>
                </h1>
                <p>
                  From patient context to trial confidence. All in one
                  workspace.
                </p>
              </div>
              <div className="intro-stamp">
                <ShieldGraphic />
                <span>
                  Built for clarity.
                  <br />
                  <strong>Designed for research.</strong>
                </span>
              </div>
            </section>
            <div className="demo-banner">
              <FlaskConical size={15} />
              <span>
                <strong>Synthetic research demo</strong>
                <span className="banner-divider">/</span>
                {result?.retrieval_mode === "qdrant"
                  ? "BioLORD + BM25 retrieval"
                  : "Local demo retrieval"}{" "}
                · Illustrative retention unless model artifacts are loaded
              </span>
              <span className="demo-badge">NO REAL PHI</span>
            </div>
            <section className="workspace-toolbar">
              <div className="patient-selector-wrap">
                <span className="field-label">PATIENT RECORD</span>
                <div className="select-wrapper">
                  <select
                    aria-label="Patient record"
                    value={uploaded.current ? "uploaded" : patientId}
                    disabled={running}
                    onChange={(e) => {
                      uploaded.current = null;
                      if (e.target.value === patientId) void run(patientId);
                      else setPatientId(e.target.value);
                    }}
                  >
                    {uploaded.current && (
                      <option value="uploaded">
                        Imported · {result?.patient.name ?? "synthetic bundle"}
                      </option>
                    )}
                    {patients.length ? (
                      patients.map((patient) => (
                        <option key={patient.id} value={patient.id}>
                          {patient.name} · {patient.id}
                        </option>
                      ))
                    ) : (
                      <option value="P-4092">Loading patient records…</option>
                    )}
                  </select>
                  <ChevronDown size={14} />
                </div>
              </div>
              <div className="toolbar-actions">
                <input
                  ref={fileInput}
                  type="file"
                  accept=".json,application/json"
                  hidden
                  onChange={(e) => void upload(e.target.files?.[0])}
                />
                <button
                  className="secondary-button upload-button"
                  onClick={() => fileInput.current?.click()}
                  disabled={running}
                  title="Import synthetic FHIR JSON only; processed in memory"
                >
                  <Upload size={15} />
                  Import synthetic FHIR
                </button>
                <button
                  className="secondary-button"
                  onClick={exportAudit}
                  disabled={!result || running}
                >
                  <Download size={15} />
                  <span>Export audit</span>
                </button>
                <button
                  className="primary-button"
                  onClick={() => void run(patientId)}
                  disabled={running}
                >
                  {running ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <Play size={15} fill="currentColor" />
                  )}
                  {running ? "Running pipeline" : "Run pipeline"}
                  {!running && <ArrowRight size={16} />}
                </button>
              </div>
            </section>
            {error && (
              <div className="error-banner" role="alert">
                <span>{error}</span>
                <button onClick={() => void run(patientId)}>Retry</button>
              </div>
            )}
            <div className="workspace-stats">
              <div>
                <span className="stat-icon">
                  <Search size={17} />
                </span>
                <strong>{result?.total_candidates ?? "—"}</strong>
                <span>candidate trials</span>
              </div>
              <div>
                <span className="stat-icon">
                  <CheckCheck size={18} />
                </span>
                <strong>{result ? uniqueEvidence : "—"}</strong>
                <span>cited resources</span>
              </div>
              <div>
                <span className="stat-icon">
                  <Clock3 size={17} />
                </span>
                <strong>
                  {steps.length ? `${(totalMs / 1000).toFixed(2)}s` : "—"}
                </strong>
                <span>pipeline time</span>
              </div>
              <span className="screening-date">
                {result
                  ? `Screened ${new Date(result.as_of + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`
                  : running
                    ? "Processing current patient…"
                    : "Ready for screening"}
              </span>
            </div>
            <div className="command-center">
              {displayedPatient ? (
                <PatientInspector
                  patient={displayedPatient}
                  onRaw={() => bundle && setModal({ reference: null })}
                  onEvidence={(reference) => bundle && setModal({ reference })}
                />
              ) : (
                <div className="panel skeleton-panel">
                  <div className="skeleton circle" />
                  <div className="skeleton" />
                  <div className="skeleton" />
                </div>
              )}
              <section className="matches-panel">
                <div className="matches-heading">
                  <h2>
                    <span className="step-number">02</span> Ranked trial matches{" "}
                    <span className="count-badge">{matches.length}</span>
                  </h2>
                  <span className="muted">Eligibility first</span>
                </div>
                <div className="match-filters">
                  <div className="search-box">
                    <Search size={14} />
                    <input
                      aria-label="Search trials"
                      placeholder="Search trials or protocol ID…"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    />
                  </div>
                  <select
                    aria-label="Filter eligibility status"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">All statuses</option>
                    <option value="ELIGIBLE">Criteria met</option>
                    <option value="NEEDS_REVIEW">Needs review</option>
                    <option value="INELIGIBLE">Not eligible</option>
                  </select>
                </div>
                {running ? (
                  <div className="pipeline-loading">
                    <div className="loading-orbit">
                      <Activity size={28} />
                    </div>
                    <h3>Connecting evidence to opportunity.</h3>
                    <p>
                      {steps.at(-1)?.detail ?? "Preparing the patient context…"}
                    </p>
                    <div className="loading-line" />
                  </div>
                ) : matches.length ? (
                  <div className="trial-list" ref={trialList}>
                    {matches.map((match) => (
                      <TrialCard
                        key={match.trial.id}
                        match={match}
                        rank={(result?.matches.indexOf(match) ?? 0) + 1}
                        selected={selected === match.trial.id}
                        onSelect={() =>
                          setSelected(
                            selected === match.trial.id ? "" : match.trial.id,
                          )
                        }
                        onEvidence={(reference) => setModal({ reference })}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    <Search size={30} />
                    <h3>
                      {error ? "Unable to load matches" : "No trials to show"}
                    </h3>
                    <p>
                      {error
                        ? "Check the connection and retry the pipeline."
                        : "Try a different search or eligibility filter."}
                    </p>
                  </div>
                )}
                <div className="matches-footnote">
                  <span /> RRF is a ranking score, not a probability of
                  eligibility.
                </div>
              </section>
              <RetentionPanel match={activeMatch} />
            </div>
            <TraceBar steps={steps} running={running} />
          </>
        ) : tab === "benchmark" ? (
          <BenchmarkView />
        ) : (
          <SandboxView />
        )}
        <footer className="page-footer">
          <span>
            <Activity size={13} /> TrialPulse AI{" "}
            <span className="muted">/</span> Research, with a clearer pulse.
          </span>
          <span>Synthetic data · Auditable decisions · v0.1.0</span>
        </footer>
      </main>
      {modal && (
        <FhirModal
          bundle={bundle}
          reference={modal.reference}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

function ShieldGraphic() {
  return (
    <div className="intro-mark">
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path
          d="M24 4 40 11v13c0 11-16 20-16 20S8 35 8 24V11L24 4Z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path
          d="m16 24 5 5 11-12"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}
