"""Normalize AACT study-level outcomes without fabricating participant dropout labels.

AACT contains study/arm/result tables, not a generic patient-level retention cohort.
This command creates an auditable study-outcome table for protocol analytics only.
"""

import argparse
import csv
import json
from pathlib import Path


def import_studies(input_path: Path, output_path: Path):
    required = {"nct_id", "overall_status"}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        input_path.open(newline="", encoding="utf-8-sig") as source,
        output_path.open("w", newline="", encoding="utf-8") as target,
    ):
        reader = csv.DictReader(source)
        columns = {column.casefold() for column in reader.fieldnames or []}
        missing = required - columns
        if missing:
            raise ValueError(
                f"Expected AACT study export columns: {sorted(required)}; missing {sorted(missing)}"
            )
        writer = csv.DictWriter(
            target, fieldnames=["nct_id", "overall_status", "study_outcome_label", "source"]
        )
        writer.writeheader()
        for row in reader:
            nct_id = row.get("nct_id") or row.get("NCT_ID")
            status = (row.get("overall_status") or row.get("OVERALL_STATUS") or "").upper()
            if not nct_id or not status:
                continue
            if status == "COMPLETED":
                label = "COMPLETED"
            elif status in {"TERMINATED", "WITHDRAWN", "SUSPENDED"}:
                label = "STUDY_STOPPED"
            else:
                label = "OTHER_STATUS"
            writer.writerow(
                {
                    "nct_id": nct_id,
                    "overall_status": status,
                    "study_outcome_label": label,
                    "source": "AACT study-level",
                }
            )
            count += 1
    print(
        json.dumps(
            {
                "rows": count,
                "output": str(output_path),
                "warning": "Study-level outcomes are not patient-level dropout labels and must not train individual retention models.",
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="AACT studies CSV export")
    parser.add_argument("--output", type=Path, default=Path("data/local/aact/study_outcomes.csv"))
    args = parser.parse_args()
    import_studies(args.input, args.output)


if __name__ == "__main__":
    main()
