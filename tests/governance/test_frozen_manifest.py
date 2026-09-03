"""Regression tests for frozen ground-truth manifest idempotency (Step 23G.1).

These tests prove:

- ``verify`` does not mutate ``manifest.json`` (the core principle:
  ``Verify(FrozenArtifact) must not mutate FrozenManifest``).
- Running ``verify`` twice against unchanged inputs produces zero manifest
  changes.
- ``freeze`` reuses persisted ``created_at`` / ``frozen_at`` for existing
  artifacts — only ``generated_at`` (manifest metadata) changes.
- SHA-256 hashes are stable across re-freeze (no artifact identity change).
- ``verify`` reports PASS against the current frozen inputs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "ground_truth" / "frozen" / "manifest.json"
GENERATOR = REPO_ROOT / "data" / "ground_truth" / "frozen" / "generate_manifest.py"


def _run(mode: str) -> tuple[int, str, str]:
    """Run the manifest generator in ``mode`` and return (rc, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR), mode],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture(scope="module")
def _restored_manifest():
    """Ensure the manifest is restored to its committed state after tests."""
    original = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else None
    yield
    if original is not None:
        MANIFEST_PATH.write_text(original, encoding="utf-8")


# ---------------------------------------------------------------------------
# verify does not mutate the manifest
# ---------------------------------------------------------------------------


def test_verify_does_not_mutate_manifest(_restored_manifest):
    """``verify`` must not write to manifest.json."""
    before = MANIFEST_PATH.read_text(encoding="utf-8")
    rc, stdout, _stderr = _run("verify")
    after = MANIFEST_PATH.read_text(encoding="utf-8")
    assert rc == 0, f"verify failed:\n{stdout}"
    assert before == after, "verify mutated manifest.json — violates idempotency"


def test_verify_twice_produces_zero_manifest_changes(_restored_manifest):
    """Running verify twice against unchanged inputs produces zero manifest changes."""
    before = MANIFEST_PATH.read_text(encoding="utf-8")
    rc1, _, _ = _run("verify")
    rc2, _, _ = _run("verify")
    after = MANIFEST_PATH.read_text(encoding="utf-8")
    assert rc1 == 0 and rc2 == 0
    assert before == after, "manifest changed after two verify runs"


def test_verify_reports_pass_against_current_inputs(_restored_manifest):
    """verify must report PASS against the current frozen inputs."""
    rc, stdout, _stderr = _run("verify")
    assert rc == 0, f"verify did not PASS:\n{stdout}"
    assert "VERIFY: PASS" in stdout


# ---------------------------------------------------------------------------
# freeze reuses persisted timestamps
# ---------------------------------------------------------------------------


def test_freeze_reuses_persisted_timestamps(_restored_manifest):
    """freeze must reuse created_at/frozen_at for existing artifacts.

    Only ``generated_at`` (manifest metadata) may change.  All artifact
    ``created_at``, ``frozen_at``, and ``sha256`` values must be stable.
    """
    m1 = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rc, _, _ = _run("freeze")
    assert rc == 0
    m2 = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    ts_keys = ["created_at", "frozen_at", "sha256"]
    for field in ("source_documents", "embedded_states"):
        list1 = m1.get(field, [])
        list2 = m2.get(field, [])
        assert len(list1) == len(list2), f"{field}: length changed"
        for a, b in zip(list1, list2):
            for k in ts_keys:
                assert a.get(k) == b.get(k), (
                    f"{field} {a.get('artifact_path', a.get('artifact_id'))}: "
                    f"{k} changed from {a.get(k)!r} to {b.get(k)!r}"
                )


def test_freeze_does_not_change_artifact_sha256(_restored_manifest):
    """SHA-256 hashes must be stable across re-freeze (no identity change)."""
    m1 = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    _run("freeze")
    m2 = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for a, b in zip(m1.get("source_documents", []), m2.get("source_documents", [])):
        assert a["sha256"] == b["sha256"], (
            f"sha256 changed for {a['artifact_path']}"
        )
