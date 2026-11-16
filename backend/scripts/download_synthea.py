"""Download and safely extract Synthea's public FHIR sample bundle.

The archive contains synthetic records only. It is never sent to an external API.
"""

import argparse
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx

DEFAULT_URL = "https://synthetichealth.github.io/synthea/downloads/synthea_sample_data_fhir_latest.zip"


def safe_member_path(root: Path, name: str) -> Path:
    destination = (root / name).resolve()
    if destination != root.resolve() and root.resolve() not in destination.parents:
        raise ValueError(f"Archive path escapes destination: {name}")
    return destination


def extract_archive(content: bytes, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = safe_member_path(output, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            count += 1
    return count


def download(url: str, output: Path, sha256: str | None = None) -> None:
    response = httpx.get(url, timeout=120, follow_redirects=True, headers={"User-Agent": "TrialPulseAI/0.1"})
    response.raise_for_status()
    digest = hashlib.sha256(response.content).hexdigest()
    if sha256 and digest.casefold() != sha256.casefold():
        raise ValueError(f"SHA-256 mismatch: expected {sha256}, received {digest}")
    with tempfile.TemporaryDirectory(prefix="trialpulse-fhir-") as directory:
        temporary = Path(directory) / "sample.zip"
        temporary.write_bytes(response.content)
        extracted = Path(directory) / "fhir"
        count = extract_archive(response.content, extracted)
        output.mkdir(parents=True, exist_ok=True)
        for source in extracted.rglob("*.json"):
            relative = source.relative_to(extracted)
            target = safe_member_path(output, str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(json.dumps({"url": url, "sha256": digest, "files_extracted": count, "output": str(output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Synthea zip URL or a compatible archive URL")
    parser.add_argument("--output", type=Path, default=Path("data/local/fhir"))
    parser.add_argument("--sha256", help="Optional expected archive digest")
    args = parser.parse_args()
    download(args.url, args.output, args.sha256)


if __name__ == "__main__":
    main()
