"""Fetch recruiting ClinicalTrials.gov v2 records as normalized JSONL."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from backend.app.criteria import decompose_text, decompose_with_llm
from backend.app.schemas import Trial


def parse_study(study: dict) -> Trial:
    protocol = study["protocolSection"]
    identity = protocol["identificationModule"]
    design = protocol.get("designModule", {})
    eligibility = protocol.get("eligibilityModule", {}).get("eligibilityCriteria", "")
    return Trial(
        id=identity["nctId"],
        title=identity.get("briefTitle", identity.get("officialTitle", "Untitled")),
        phase="/".join(design.get("phases", [])) or "NA",
        conditions=protocol.get("conditionsModule", {}).get("conditions", []),
        status=protocol.get("statusModule", {}).get("overallStatus", "UNKNOWN"),
        summary=protocol.get("descriptionModule", {}).get("briefSummary", ""),
        eligibility_text=eligibility,
        criteria=decompose_text(eligibility),
        locations=[
            ", ".join(filter(None, [p.get("facility"), p.get("city"), p.get("state"), p.get("country")]))
            for p in protocol.get("contactsLocationsModule", {}).get("locations", [])
        ],
    )


async def fetch(condition: str, limit: int, output: Path, use_llm: bool = False):
    output.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": min(limit, 1000),
        "format": "json",
    }
    count = 0
    # Write atomically so a failed fetch does not replace a previously usable corpus.
    temporary = output.with_suffix(".partial")
    async with httpx.AsyncClient(
        timeout=60, headers={"User-Agent": "TrialPulseAI/0.1 research-demo"}
    ) as client:
        with temporary.open("w", encoding="utf-8") as handle:
            while count < limit:
                for attempt in range(4):
                    response = await client.get("https://clinicaltrials.gov/api/v2/studies", params=params)
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        break
                    await asyncio.sleep(2**attempt)
                response.raise_for_status()
                payload = response.json()
                for study in payload.get("studies", []):
                    trial = parse_study(study)
                    if use_llm:
                        trial.criteria = await decompose_with_llm(trial.eligibility_text)
                    handle.write(trial.model_dump_json() + "\n")
                    count += 1
                    if count >= limit:
                        break
                token = payload.get("nextPageToken")
                if not token:
                    break
                params["pageToken"] = token
    temporary.replace(output)
    print(json.dumps({"trials": count, "output": str(output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", default="non-small cell lung cancer")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--output", type=Path, default=Path("data/local/trials.jsonl"))
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use configured structured LLM decomposition with original-protocol review",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    asyncio.run(fetch(args.condition, args.limit, args.output, args.llm))


if __name__ == "__main__":
    main()
