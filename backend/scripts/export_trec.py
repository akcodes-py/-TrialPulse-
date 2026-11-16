"""Export a supported Clinical Trials track from ir_datasets to local TSV files."""

import argparse
import json
from pathlib import Path

SUPPORTED = {
    "2021": "clinicaltrials/2021/trec-ct-2021",
    "2022": "clinicaltrials/2021/trec-ct-2022",
}


def export(dataset_name: str, output: Path):
    try:
        import ir_datasets
    except ImportError as exc:
        raise SystemExit(
            "Install the benchmark extra first: python -m pip install -e '.[benchmark]'"
        ) from exc
    dataset = ir_datasets.load(dataset_name)
    output.mkdir(parents=True, exist_ok=True)
    docs = output / "docs.jsonl"
    queries = output / "queries.tsv"
    qrels = output / "qrels.txt"
    with docs.open("w", encoding="utf-8") as handle:
        for doc in dataset.docs_iter():
            handle.write(
                json.dumps(
                    {
                        "id": doc.doc_id,
                        "title": doc.title,
                        "condition": doc.condition,
                        "summary": doc.summary,
                        "detailed_description": doc.detailed_description,
                        "eligibility": doc.eligibility,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    with queries.open("w", encoding="utf-8") as handle:
        for query in dataset.queries_iter():
            text = getattr(query, "text", " ".join(str(value) for value in query[1:]))
            handle.write(f"{query.query_id}\t{text}\n")
    with qrels.open("w", encoding="utf-8") as handle:
        for judgment in dataset.qrels_iter():
            handle.write(
                f"{judgment.query_id} {getattr(judgment, 'iteration', 0)} {judgment.doc_id} {judgment.relevance}\n"
            )
    print(
        json.dumps(
            {
                "dataset": dataset_name,
                "output": str(output),
                "docs": str(docs),
                "queries": str(queries),
                "qrels": str(qrels),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(SUPPORTED) + list(SUPPORTED.values()), default="2021")
    parser.add_argument("--output", type=Path, default=Path("data/local/trec/2021"))
    args = parser.parse_args()
    export(SUPPORTED.get(args.dataset, args.dataset), args.output)


if __name__ == "__main__":
    main()
