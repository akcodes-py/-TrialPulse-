"""Evaluate standard qrels and TREC run files on the same judged topic set."""

import argparse
import json
import math
from pathlib import Path


def read_qrels(path: Path) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        topic, _, document, grade = line.split()
        qrels.setdefault(topic, {})[document] = int(grade)
    if not qrels:
        raise ValueError("Qrels must contain at least one judged topic")
    return qrels


def read_run(path: Path) -> dict[str, list[str]]:
    rows: dict[str, list[tuple[float, str]]] = {}
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        topic, _, document, rank, score, _tag = line.split()
        if (topic, document) in seen:
            raise ValueError(f"Duplicate document {document} for topic {topic}")
        seen.add((topic, document))
        numeric_score = float(score)
        if not math.isfinite(numeric_score) or int(rank) < 1:
            raise ValueError("Run scores must be finite and ranks positive")
        rows.setdefault(topic, []).append((numeric_score, document))
    # Match trec_eval's score-first ordering, with descending document id for ties.
    return {topic: [doc for _, doc in sorted(values, reverse=True)] for topic, values in rows.items()}


def topic_metrics(judgments: dict[str, int], ranking: list[str], relevant_grade: int = 2) -> dict[str, float]:
    def precision(k):
        return sum(judgments.get(doc, 0) >= relevant_grade for doc in ranking[:k]) / k

    # Linear graded gain, consistent with trec_eval ndcg_cut. Unjudged/negative grades have zero gain.
    gains = [max(0, judgments.get(doc, 0)) for doc in ranking[:10]]
    ideal = sorted((max(0, grade) for grade in judgments.values()), reverse=True)[:10]
    dcg = sum(gain / math.log2(i + 2) for i, gain in enumerate(gains))
    idcg = sum(gain / math.log2(i + 2) for i, gain in enumerate(ideal))
    return {
        "precision_5": precision(5),
        "precision_10": precision(10),
        "ndcg_10": dcg / idcg if idcg else 0.0,
    }


def evaluate_files(qrels_path: Path, runs: dict[str, Path], dataset: str, relevant_grade: int = 2) -> dict:
    qrels = read_qrels(qrels_path)
    results = []
    for name, path in runs.items():
        run = read_run(path)
        per_topic = {
            topic: topic_metrics(judgments, run.get(topic, []), relevant_grade)
            for topic, judgments in qrels.items()
        }
        metrics = {
            key: sum(row[key] for row in per_topic.values()) / len(per_topic)
            for key in ["precision_5", "precision_10", "ndcg_10"]
        }
        results.append(
            {"name": name, **metrics, "per_topic": per_topic, "missing_topics": sorted(set(qrels) - set(run))}
        )
    return {
        "dataset": dataset,
        "topic_count": len(qrels),
        "relevant_grade": relevant_grade,
        "gain": "linear",
        "unjudged_policy": "nonrelevant",
        "results": results,
        "targets": {"ndcg_10": 0.68, "precision_5": 0.8},
        "note": "Targets are aspirations, not measured results. TREC labels: 2 eligible; 1 partially relevant; 0 irrelevant. P@K uses grade ≥ 2 by default.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qrels", required=True, type=Path)
    parser.add_argument(
        "--run", action="append", required=True, help="LABEL=path/to/run.txt (repeat for each baseline)"
    )
    parser.add_argument("--dataset", required=True, help="Dataset name, year and split")
    parser.add_argument("--relevant-grade", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation_results.json"))
    args = parser.parse_args()
    report = evaluate_files(
        args.qrels,
        {label: Path(path) for label, path in (value.split("=", 1) for value in args.run)},
        args.dataset,
        args.relevant_grade,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
