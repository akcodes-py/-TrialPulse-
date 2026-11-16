import io
import zipfile

from backend.app.fhir_store import bundle_paths, read_bundle
from backend.scripts.download_synthea import extract_archive
from backend.scripts.import_aact import import_studies


def test_synthea_archive_extraction_is_bounded_and_discoverable(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "synthea/fhir/Patient-abc.json",
            '{"resourceType":"Bundle","entry":[{"resource":{"resourceType":"Patient","id":"abc"}}]}',
        )
    output = tmp_path / "fhir"
    assert extract_archive(archive.getvalue(), output) == 1
    assert len(bundle_paths(output)) == 1
    assert read_bundle("abc", output)["resourceType"] == "Bundle"


def test_aact_import_preserves_study_level_boundary(tmp_path, capsys):
    source = tmp_path / "studies.csv"
    source.write_text("nct_id,overall_status\nNCT1,COMPLETED\nNCT2,TERMINATED\n", encoding="utf-8")
    target = tmp_path / "out.csv"
    import_studies(source, target)
    assert "STUDY_STOPPED" in target.read_text(encoding="utf-8")
    assert "not patient-level dropout" in capsys.readouterr().out
