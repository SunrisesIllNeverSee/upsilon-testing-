"""Test that .gitignore frozen-source exceptions admit only source evidence.

Step 23G.1 requirement: the .gitignore exceptions for ``data/edgar_chains/``
must track only the authoritative frozen source artifacts (``.txt`` source
evidence and ``manifest.json``) and must not admit derived parser/processing
output (``.html``, ``.v04.json``).

The distinction is::

    SOURCE EVIDENCE (.txt)       = version-controlled, hashed by manifest
    DERIVED OUTPUT (.html/.json) = gitignored, regenerable

These tests use ``git check-ignore`` to verify the tracking boundary without
actually staging files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _is_ignored(path: str) -> bool:
    """Return True if ``path`` is git-ignored, False if it would be tracked."""
    result = subprocess.run(
        ["git", "check-ignore", path],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    # git check-ignore exits 0 if the path IS ignored, 1 if NOT ignored
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Source evidence (.txt) must be trackable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rel_path", [
    "data/edgar_chains/ameresco/S0_fifth_AR_2022.txt",
    "data/edgar_chains/ameresco/A1_amend_2023_08.txt",
    "data/edgar_chains/ameresco/A2_amend_2023_12.txt",
    "data/edgar_chains/ameresco/A3_sixth_amend_2024.txt",
    "data/edgar_chains/amedisys/S0_AR_2018.txt",
    "data/edgar_chains/amedisys/A1_first_amend_2019.txt",
    "data/edgar_chains/amedisys/A2_second_amend_2021.txt",
    "data/edgar_chains/amedisys/A3_third_amend_2023.txt",
    "data/edgar_chains/amedisys/A4_fourth_amend_2025.txt",
    "data/edgar_chains/bausch_lomb/S0_credit_agreement_2022.txt",
    "data/edgar_chains/bausch_lomb/A1_first_incremental_2023.txt",
    "data/edgar_chains/bausch_lomb/A2_second_incremental_2024.txt",
    "data/edgar_chains/bausch_lomb/A3_third_amend_2025.txt",
    "data/edgar_chains/bausch_lomb/A4_fourth_amend_2026.txt",
])
def test_txt_source_evidence_is_trackable(rel_path):
    """Every .txt source document in the frozen manifest must be trackable."""
    assert not _is_ignored(rel_path), f"{rel_path} is ignored but should be tracked"


def test_edgar_chain_manifest_is_trackable():
    """The chain manifest.json must be trackable (it provides URL provenance)."""
    assert not _is_ignored("data/edgar_chains/manifest.json")


# ---------------------------------------------------------------------------
# Derived output (.html, .v04.json) must be ignored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rel_path", [
    "data/edgar_chains/ameresco/A1_amend_2023_08.html",
    "data/edgar_chains/ameresco/A1_amend_2023_08.v04.json",
    "data/edgar_chains/amedisys/A1_first_amend_2019.html",
    "data/edgar_chains/amedisys/A1_first_amend_2019.v04.json",
    "data/edgar_chains/bausch_lomb/A1_first_incremental_2023.html",
    "data/edgar_chains/bausch_lomb/A1_first_incremental_2023.v04.json",
])
def test_derived_output_is_ignored(rel_path):
    """Derived .html and .v04.json artifacts must not be tracked."""
    assert _is_ignored(rel_path), f"{rel_path} is not ignored but should be"


# ---------------------------------------------------------------------------
# Hypothetical new chain directory is handled by the general pattern
# ---------------------------------------------------------------------------


def test_hypothetical_new_chain_txt_is_trackable():
    """A .txt file in a hypothetical new chain directory should be trackable.

    The .gitignore pattern uses wildcards (``data/edgar_chains/*/``) so new
    chain directories are handled without per-chain exceptions.
    """
    assert not _is_ignored("data/edgar_chains/new_chain_hypothetical/S0_test.txt")


def test_hypothetical_new_chain_derived_is_ignored():
    """Derived output in a hypothetical new chain directory must be ignored."""
    assert _is_ignored("data/edgar_chains/new_chain_hypothetical/A1_test.html")
    assert _is_ignored("data/edgar_chains/new_chain_hypothetical/A1_test.v04.json")
