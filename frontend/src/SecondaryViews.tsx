import { useEffect, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  FlaskConical,
  GitCompareArrows,
  Info,
  RotateCcw,
  SlidersHorizontal,
} from "lucide-react";
import { jsonPost, request } from "./api";
import type { Benchmark, SandboxResult } from "./types";

type Metric = "ndcg_10" | "precision_5" | "precision_10";
const metricNames = {
  ndcg_10: "NDCG@10",
  precision_5: "Precision@5",
  precision_10: "Precision@10",
};

export function BenchmarkView() {
  const [data, setData] = useState<Benchmark | null>(null);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState<Metric>("ndcg_10");
  const isFixture = data?.dataset.toLowerCase().includes("fixture") ?? true;
  useEffect(() => {
    const controller = new AbortController();
    request<Benchmark>("/benchmarks", { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, []);
  return (
    <div className="secondary-view">
      <div className="view-intro">
        <div className="eyebrow">
          <BarChart3 size={14} /> RETRIEVAL EVALUATION
        </div>
        <h1>Better retrieval. Measured.</h1>
        <p>Compare ranking quality on a shared set of relevance judgments.</p>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {!data && !error && (
        <div className="loading-panel">Loading benchmark results…</div>
      )}
      {data && (
        <>
          <div className="benchmark-banner">
            <FlaskConical size={18} />
            <div>
              <strong>{data.dataset}</strong>
              <p>
                {data.topic_count} judged topics · relevance threshold ≥{" "}
                {data.relevant_grade} · linear NDCG gain
              </p>
            </div>
            <span className="tiny-badge">
              {data.dataset.toLowerCase().includes("fixture")
                ? "FIXTURE DATA"
                : "EVALUATION RUN"}
            </span>
          </div>
          <div className="benchmark-layout">
            <section className="panel benchmark-chart-panel">
              <div className="section-title">
                <h2>Baseline comparison</h2>
                <span className="muted">Higher is better ↗</span>
              </div>
              <div className="segmented-control">
                {(Object.keys(metricNames) as Metric[]).map((key) => (
                  <button
                    key={key}
                    className={metric === key ? "active" : ""}
                    onClick={() => setMetric(key)}
                    aria-pressed={metric === key}
                  >
                    {metricNames[key]}
                  </button>
                ))}
              </div>
              <div className="benchmark-chart">
                <div className="chart-grid-labels">
                  {[1, 0.75, 0.5, 0.25, 0].map((value) => (
                    <span key={value}>{value.toFixed(2)}</span>
                  ))}
                </div>
                <div className="benchmark-bars">
                  {[0, 25, 50, 75, 100].map((bottom) => (
                    <div
                      key={bottom}
                      className="benchmark-grid-line"
                      style={{ bottom: `${bottom}%` }}
                    />
                  ))}
                  {data.results.map((result, index) => (
                    <div className="benchmark-column" key={result.name}>
                      <div
                        className={`benchmark-column-fill series-${index % 3}`}
                        style={{ height: `${result[metric] * 100}%` }}
                      >
                        <strong>{result[metric].toFixed(3)}</strong>
                      </div>
                      <span>{result.name}</span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="chart-footnote">
                {isFixture
                  ? "Fixture rankings are hand-authored to exercise the evaluator. They do not demonstrate retrieval gains on TREC."
                  : `Macro average across ${data.topic_count} judged topics. Missing topics score zero; unjudged documents have zero gain.`}
              </p>
            </section>
            <section className="panel methodology">
              <div className="method-icon">
                <BookOpen size={23} />
              </div>
              <h2>Evidence before claims.</h2>
              <p>
                Run your own BM25, dense, and hybrid rankings against the same
                TREC qrels. Missing topics score zero; unjudged documents are
                nonrelevant.
              </p>
              <div className="target-row">
                <span>NDCG@10 target</span>
                <strong>≥ 0.68</strong>
              </div>
              <div className="target-row">
                <span>Precision@5 target</span>
                <strong>≥ 0.80</strong>
              </div>
              <div className="model-note">
                <Info size={15} />
                <p>
                  {isFixture
                    ? "Targets are not achieved results. Real TREC performance has not been measured in the included fixture."
                    : "Targets are product goals. The chart and run summary show the measured values from the supplied evaluation report."}
                </p>
              </div>
              <p className="mono small">
                python -m evaluation.eval_trec --help
              </p>
            </section>
          </div>
          <section className="panel results-table-panel">
            <div className="section-title">
              <h2>Run summary</h2>
              <span className="tiny-badge">MACRO AVERAGE</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Retrieval configuration</th>
                  <th>Precision@5</th>
                  <th>Precision@10</th>
                  <th>NDCG@10</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((result, index) => (
                  <tr key={result.name}>
                    <td>
                      <i className={`table-dot series-${index % 3}`} />
                      {result.name}
                    </td>
                    <td>{result.precision_5.toFixed(3)}</td>
                    <td>{result.precision_10.toFixed(3)}</td>
                    <td>{result.ndcg_10.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

export function SandboxView() {
  const [maxAge, setMaxAge] = useState(75);
  const [minEgfr, setMinEgfr] = useState(45);
  const [data, setData] = useState<SandboxResult | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setPending(true);
    const timer = setTimeout(() => {
      request<SandboxResult>(
        "/sandbox",
        jsonPost({ max_age: maxAge, min_egfr: minEgfr }, controller.signal),
      )
        .then((result) => {
          setData(result);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setPending(false);
        });
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [maxAge, minEgfr]);
  const maximum = Math.max(
    1,
    ...(data?.bins.flatMap((bin) => [bin.baseline, bin.modified]) ?? []),
  );
  return (
    <div className="secondary-view">
      <div className="view-intro">
        <div className="eyebrow">
          <SlidersHorizontal size={14} /> PROTOCOL OPTIMIZATION
        </div>
        <h1>Small changes. More possibilities.</h1>
        <p>
          Explore how eligibility thresholds change a synthetic patient pool.
        </p>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <div className="sandbox-layout">
        <section className="panel sandbox-controls">
          <div className="section-title">
            <h2>Eligibility parameters</h2>
            <SlidersHorizontal size={18} />
          </div>
          <p className="muted">Adjust the inclusion criteria below.</p>
          <div className="slider-group">
            <label htmlFor="age">
              Maximum patient age
              <strong>
                {maxAge}
                <small>years</small>
              </strong>
            </label>
            <input
              id="age"
              type="range"
              min="18"
              max="100"
              value={maxAge}
              onChange={(e) => setMaxAge(+e.target.value)}
            />
            <div className="slider-labels">
              <span>18 years</span>
              <span>100 years</span>
            </div>
            <p>Baseline: 75 years</p>
          </div>
          <div className="slider-group">
            <label htmlFor="egfr">
              Minimum eGFR
              <strong>
                {minEgfr}
                <small>mL/min/1.73m²</small>
              </strong>
            </label>
            <input
              id="egfr"
              type="range"
              min="0"
              max="120"
              value={minEgfr}
              onChange={(e) => setMinEgfr(+e.target.value)}
            />
            <div className="slider-labels">
              <span>0</span>
              <span>120</span>
            </div>
            <p>Baseline: 45 mL/min/1.73m²</p>
          </div>
          <button
            className="secondary-button"
            onClick={() => {
              setMaxAge(75);
              setMinEgfr(45);
            }}
          >
            <RotateCcw size={14} /> Reset to baseline
          </button>
          <div className="model-note">
            <Info size={15} />
            <p>
              Two-rule simulation on 240 synthetic profiles. Other criteria,
              treatment effects, and clinical feasibility are not modeled.
            </p>
          </div>
        </section>
        <section className="panel sandbox-results" aria-busy={pending}>
          <div className="section-title">
            <h2>Patient pool impact</h2>
            <span className="tiny-badge">
              {pending ? "UPDATING…" : "SYNTHETIC COHORT"}
            </span>
          </div>
          <div className="pool-comparison">
            <div>
              <span>Baseline pool</span>
              <strong>{data?.baseline ?? "—"}</strong>
              <small>patients</small>
            </div>
            <ArrowRight size={24} />
            <div className="modified-pool">
              <span>Modified pool</span>
              <strong>{data?.modified ?? "—"}</strong>
              <small>patients</small>
            </div>
            <div
              className={`pool-delta ${(data?.delta ?? 0) < 0 ? "negative-delta" : ""}`}
            >
              <GitCompareArrows size={20} />
              <strong>
                {(data?.delta ?? 0) > 0 ? "+" : ""}
                {data?.delta ?? "—"}
              </strong>
              <span>patient difference</span>
            </div>
          </div>
          <div className="section-title">
            <h3>Eligible patients by age group</h3>
            <div className="driver-legend">
              <span>
                <i className="baseline-dot" />
                Baseline
              </span>
              <span>
                <i className="positive-dot" />
                Modified
              </span>
            </div>
          </div>
          <div className="pool-chart">
            {data?.bins.map((bin) => (
              <div key={bin.label} className="pool-column">
                <div className="pool-bar-pair">
                  <div
                    className="baseline-bar"
                    style={{ height: `${(bin.baseline / maximum) * 100}%` }}
                  >
                    <span>{bin.baseline}</span>
                  </div>
                  <div
                    className="modified-bar"
                    style={{ height: `${(bin.modified / maximum) * 100}%` }}
                  >
                    <span>{bin.modified}</span>
                  </div>
                </div>
                <span>{bin.label}</span>
              </div>
            ))}
          </div>
          <p className="chart-footnote">{data?.source}</p>
        </section>
      </div>
    </div>
  );
}
