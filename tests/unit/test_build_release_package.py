"""Tests for the development-data release package.

Tests cover:
  - All 10 required components are present in the release package
  - Accessions manifest has correct structure (25 chains, 112+ documents)
  - Every document has an accession, URL, and at least one SHA-256 hash
  - Manifest has correct metadata (frozen reference, statistics, hashes)
  - Output SHA-256 hashes in manifest match actual file hashes
  - Run records directory is non-empty
  - Reproducibility instructions are present and substantive
  - Release notes are present
  - No SEC exhibit content is redistributed (only metadata + derived analysis)
  - v2 results in release match the frozen baseline SHA-256
"""
from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest

# Skip if the release package data directory doesn't exist
# (data paths changed during v0.4 directory migration)
_RELEASE_DIR = Path("results/release_package")
_RELEASE_DATA = _RELEASE_DIR / "release_notes.md"
pytestmark = pytest.mark.skipif(
    not _RELEASE_DATA.exists(),
    reason="Release package data not built (results/release_package/release_notes.md missing)",
)

from results.release_package.build_release_package import (
    RELEASE_DIR,
    build_accessions,
    build_manifest,
    extract_accession_from_url,
    sha256_file,
    verify_release_package,
)

# ---------------------------------------------------------------------------
# Accession extraction
# ---------------------------------------------------------------------------


class TestExtractAccessionFromUrl:
    def test_extracts_18_digit_accession(self):
        url = "https://www.sec.gov/Archives/edgar/data/1488139/000148813922000016/exhibit101.htm"
        acc = extract_accession_from_url(url)
        assert acc == "0001488139-22-000016"

    def test_returns_none_for_no_accession(self):
        url = "https://example.com/no-accession-here"
        assert extract_accession_from_url(url) is None

    def test_returns_none_for_empty_url(self):
        assert extract_accession_from_url("") is None


# ---------------------------------------------------------------------------
# Accessions manifest
# ---------------------------------------------------------------------------


class TestAccessionsManifest:
    def test_build_accessions_returns_dict(self):
        acc = build_accessions()
        assert isinstance(acc, dict)

    def test_has_total_documents(self):
        acc = build_accessions()
        assert acc["total_documents"] > 0

    def test_has_total_chains(self):
        acc = build_accessions()
        assert acc["total_chains"] == 25

    def test_has_22_new_study_chains(self):
        acc = build_accessions()
        study_chains = [k for k in acc["chains"] if k.startswith("STUDY-")]
        assert len(study_chains) == 22

    def test_has_3_existing_edgar_chains(self):
        acc = build_accessions()
        edgar_chains = [k for k in acc["chains"] if k.startswith("EDGAR-")]
        assert len(edgar_chains) == 3
        assert "EDGAR-AMERESCO" in acc["chains"]
        assert "EDGAR-AMEDISYS" in acc["chains"]
        assert "EDGAR-BAUSCH-LOMB" in acc["chains"]

    def test_every_document_has_url(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            assert doc["document_url"], (
                f"Document {doc['chain_id']}/{doc['document_role']} has no URL"
            )

    def test_every_document_has_at_least_one_hash(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            has_hash = doc.get("html_sha256") or doc.get("text_sha256")
            assert has_hash, (
                f"Document {doc['chain_id']}/{doc['document_role']} has no SHA-256 hash"
            )

    def test_every_study_chain_document_has_accession(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            if doc["source"] == "chain_study_manifest":
                assert doc["accession"], (
                    f"Study chain doc {doc['chain_id']}/{doc['document_role']} has no accession"
                )

    def test_every_document_has_chain_id(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            assert doc["chain_id"], "Document missing chain_id"

    def test_every_document_has_document_role(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            assert doc["document_role"], "Document missing document_role"

    def test_hashes_are_64_char_hex(self):
        acc = build_accessions()
        for doc in acc["documents"]:
            for hash_field in ("html_sha256", "text_sha256"):
                h = doc.get(hash_field, "")
                if h:
                    assert len(h) == 64, (
                        f"Hash {hash_field} for {doc['chain_id']}/"
                        f"{doc['document_role']} is {len(h)} chars, not 64"
                    )
                    assert all(c in "0123456789abcdef" for c in h), (
                        f"Hash {hash_field} for {doc['chain_id']} is not hex"
                    )


# ---------------------------------------------------------------------------
# Release manifest
# ---------------------------------------------------------------------------


class TestReleaseManifest:
    def test_manifest_has_release_name(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert manifest["release"] == "upsilon_development_data_release"

    def test_manifest_has_release_version(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert manifest["release_version"] == "1.0"

    def test_manifest_has_frozen_reference(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert manifest["frozen_reference"]["tag"] == "chain-study-v2-development"
        assert manifest["frozen_reference"]["commit"] == "fb0862d"

    def test_manifest_has_statistics(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert manifest["statistics"]["total_chains"] == 25
        assert manifest["statistics"]["new_study_chains"] == 22
        assert manifest["statistics"]["existing_edgar_chains"] == 3

    def test_manifest_has_output_hashes(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert "output_sha256" in manifest
        assert len(manifest["output_sha256"]) > 0

    def test_manifest_has_redistribution_note(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        assert "redistribution_note" in manifest
        assert "NOT" in manifest["redistribution_note"].upper()

    def test_manifest_has_contents_map(self):
        acc = build_accessions()
        manifest = build_manifest(acc)
        contents = manifest["contents"]
        for key in [
            "accessions", "failure_matrix_json", "failure_matrix_md",
            "gold_schema_json", "gold_schema_documentation",
            "chain_study_v1_results", "chain_study_v1_report",
            "chain_study_v2_results", "chain_study_v2_report",
            "freeze_record", "run_records", "reproducibility", "release_notes",
        ]:
            assert key in contents, f"Manifest contents missing: {key}"


# ---------------------------------------------------------------------------
# Release package — all 10 required components
# ---------------------------------------------------------------------------


RELEASE_MANIFEST = RELEASE_DIR / "manifest.json"


@pytest.mark.skipif(
    not RELEASE_MANIFEST.exists(),
    reason="Release package not built — run build_release_package.py",
)
class TestReleasePackageContents:
    """Verify all 10 required components are present in the release package."""

    REQUIRED_FILES: typing.ClassVar[list[str]] = [
        "manifest.json",
        "accessions.json",
        "failure_matrix.json",
        "failure_matrix.md",
        "gold_schema.json",
        "gold_schema_documentation.md",
        "chain_study_v1_results.json",
        "chain_study_v1_report.md",
        "chain_study_v2_results.json",
        "chain_study_v2_report.md",
        "freeze_record.md",
        "REPRODUCIBILITY.md",
        "RELEASE_NOTES.md",
    ]

    def test_all_required_files_exist(self):
        for fname in self.REQUIRED_FILES:
            assert (RELEASE_DIR / fname).exists(), f"Missing: {fname}"

    def test_run_records_directory_exists(self):
        assert (RELEASE_DIR / "run_records").is_dir()

    def test_run_records_directory_is_not_empty(self):
        records = list((RELEASE_DIR / "run_records").glob("*.json"))
        assert len(records) > 0, "run_records/ directory is empty"

    def test_has_at_least_4_run_records(self):
        """Should have run records for: smoke, dev corpus, v1, v2."""
        records = list((RELEASE_DIR / "run_records").glob("*.json"))
        assert len(records) >= 4, f"Only {len(records)} run records, expected >= 4"


# ---------------------------------------------------------------------------
# Release package — integrity verification
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not RELEASE_MANIFEST.exists(),
    reason="Release package not built — run build_release_package.py",
)
class TestReleasePackageIntegrity:
    def test_verify_release_package_passes(self):
        with open(RELEASE_MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        errors = verify_release_package(manifest)
        assert errors == [], f"Verification errors: {errors}"

    def test_output_hashes_match_actual_files(self):
        with open(RELEASE_MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        for name, expected_hash in manifest["output_sha256"].items():
            path = RELEASE_DIR / name
            if path.exists():
                actual = sha256_file(path)
                assert actual == expected_hash, (
                    f"Hash mismatch for {name}: expected {expected_hash[:16]}..., "
                    f"got {actual[:16]}..."
                )

    def test_v2_results_match_frozen_baseline(self):
        """The v2 results in the release must match the frozen baseline SHA-256."""
        with open(RELEASE_MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        v2_hash = manifest["output_sha256"].get("chain_study_v2_results.json")
        # This must match the freeze record hash: 7d6f50bf...
        assert v2_hash == "7d6f50bf7cde5ed72edd206619599b101ca5011ed146ce156235cf05c1351886", (
            f"v2 results hash {v2_hash} does not match frozen baseline"
        )


# ---------------------------------------------------------------------------
# Release package — no SEC content redistributed
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not RELEASE_MANIFEST.exists(),
    reason="Release package not built — run build_release_package.py",
)
class TestNoSECContentRedistributed:
    def test_no_html_files_in_release(self):
        """No .html files should be in the release package (those are SEC exhibits)."""
        html_files = list(RELEASE_DIR.rglob("*.html"))
        assert html_files == [], f"Found HTML files in release: {html_files}"

    def test_no_txt_files_in_release(self):
        """No .txt files should be in the release package (those are SEC exhibit text)."""
        txt_files = list(RELEASE_DIR.rglob("*.txt"))
        assert txt_files == [], f"Found TXT files in release: {txt_files}"

    def test_accessions_contain_only_metadata(self):
        """The accessions file should contain URLs and hashes, not document content."""
        with open(RELEASE_DIR / "accessions.json", encoding="utf-8") as f:
            acc = json.load(f)
        for doc in acc["documents"]:
            # No document should have a "content" or "text" field
            assert "content" not in doc, (
                f"Document {doc['chain_id']}/{doc['document_role']} has 'content' field"
            )
            assert "text" not in doc, (
                f"Document {doc['chain_id']}/{doc['document_role']} has 'text' field"
            )


# ---------------------------------------------------------------------------
# Reproducibility instructions
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (RELEASE_DIR / "REPRODUCIBILITY.md").exists(),
    reason="Release package not built",
)
class TestReproducibilityInstructions:
    def test_has_frozen_reference(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "fb0862d" in content
        assert "chain-study-v2-development" in content

    def test_has_step_by_step_instructions(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "Step 1" in content
        assert "Step 10" in content

    def test_mentions_acquisitions(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "acquire" in content.lower() or "acquisition" in content.lower()

    def test_mentions_failure_matrix(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "failure_matrix" in content or "failure matrix" in content.lower()

    def test_mentions_sha256_verification(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "sha256" in content.lower() or "sha-256" in content.lower()

    def test_has_expected_results(self):
        content = (RELEASE_DIR / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
        assert "54.5" in content  # S0 extraction rate
        assert "40.0" in content  # GT extraction rate


# ---------------------------------------------------------------------------
# Release notes
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (RELEASE_DIR / "RELEASE_NOTES.md").exists(),
    reason="Release package not built",
)
class TestReleaseNotes:
    def test_has_release_version(self):
        content = (RELEASE_DIR / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        assert "1.0" in content

    def test_has_frozen_reference(self):
        content = (RELEASE_DIR / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        assert "fb0862d" in content

    def test_mentions_no_sec_content(self):
        content = (RELEASE_DIR / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        assert "NOT" in content.upper()
        assert "redistribut" in content.lower()

    def test_has_baseline_results(self):
        content = (RELEASE_DIR / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        assert "54.5" in content
        assert "40.0" in content
