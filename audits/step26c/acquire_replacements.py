"""Step 26C — Replacement Chain Acquisition.

Acquires two replacement credit-agreement chains (HELD-R01, HELD-R02)
to replace HELD-018 and HELD-019, whose authoritative predecessor
credit agreements are unavailable from EDGAR.

Selection criteria (same as the original held-out study):
  1. Search EDGAR for "amendment to credit agreement" 8-K filings
  2. Exclude all CIKs already in the held-out or development corpora
  3. Require at least 2 amendments in the filing history
  4. Require a publicly available original credit agreement on EDGAR
  5. Do NOT inspect semantic reconstruction performance before inclusion

The deterministic S0 selector from Step 26B is used to find and verify
the original credit agreement for each replacement chain.

Usage:
    set -a && source .env && set +a
    python -m audits.step26c.acquire_replacements
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from audits.step26b.corrected_s0_selection import (
    download_document,
    extract_original_ca_date,
    find_correct_s0,
    get_filing_index,
    get_submissions,
    html_to_text,
    search_edgar,
    sha256,
    verify_credit_agreement_content,
)

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Upsilon Research test@example.com")
SEC_DELAY = float(os.getenv("SEC_REQUEST_DELAY_SECONDS", "0.20"))

MANIFEST_PATH = Path("data/held_out/manifest.json")
REPLACEMENT_AUDIT_PATH = Path("results/step26c_replacement_acquisition.json")

# Replacement chain IDs
REPLACEMENTS = [
    {"chain_id": "HELD-R01", "replaces": "HELD-018"},
    {"chain_id": "HELD-R02", "replaces": "HELD-019"},
]


def get_excluded_ciks(manifest: dict) -> set[str]:
    """Get all CIKs that are already in the held-out or dev corpora."""
    excluded = set()
    for chain in manifest.get("chains", []):
        excluded.add(chain["cik"])
    for cik in manifest.get("dev_ciks_excluded", []):
        excluded.add(cik)
    return excluded


def find_replacement_candidates(
    excluded_ciks: set[str],
    client: httpx.Client,
    target_count: int = 2,
) -> list[dict]:
    """Find replacement chain candidates using the same selection criteria
    as the original held-out study.

    Searches EDGAR for "amendment to credit agreement" 8-K filings,
    excludes already-used CIKs, and requires:
      - At least 2 amendment filings
      - A valid original credit agreement findable on EDGAR

    Does NOT inspect semantic reconstruction performance.
    """
    # Search EDGAR for amendment filings (broader date range to find
    # candidates with enough amendments)
    hits = search_edgar(
        '"amendment to credit agreement"', "8-K",
        "2018-01-01", "2024-12-31", client,
    )
    time.sleep(SEC_DELAY)

    # Group by CIK
    cik_filings: dict[str, list[dict]] = {}
    for hit in hits:
        cik = hit["cik"]
        if cik in excluded_ciks:
            continue
        cik_filings.setdefault(cik, []).append(hit)

    # Filter to CIKs with at least 2 amendment filings
    candidates = []
    for cik, filings in cik_filings.items():
        if len(filings) < 2:
            continue
        # Sort by date
        filings.sort(key=lambda f: f["file_date"])
        candidates.append({"cik": cik, "amendment_filings": filings})

    print(f"Found {len(candidates)} CIKs with >= 2 amendment filings")

    # For each candidate, try to find the original credit agreement
    # using the deterministic S0 selector
    selected = []
    for cand in candidates:
        if len(selected) >= target_count:
            break

        cik = cand["cik"]
        filings = cand["amendment_filings"]

        # Get issuer name from submissions
        try:
            cik_padded = cik.lstrip("0").zfill(10)
            url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
            resp = client.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=30)
            if resp.status_code != 200:
                continue
            issuer_name = resp.json().get("name", cik)
            time.sleep(SEC_DELAY)
        except Exception:
            continue

        # Download the first amendment to extract the cross-referenced CA date
        first_amendment = filings[0]
        try:
            exhibits = get_filing_index(cik, first_amendment["accession"], client)
            time.sleep(SEC_DELAY)
        except Exception:
            continue

        ca_date = None
        amendment_exhibit_url = None
        for ex in exhibits:
            etype = ex["type"].upper()
            if not etype.startswith("EX-10."):
                continue
            try:
                content = download_document(ex["url"], client)
                text = html_to_text(content)
                time.sleep(SEC_DELAY)
            except Exception:
                continue

            # Check if this is an amendment
            verification = verify_credit_agreement_content(text)
            if not verification["is_amendment"]:
                continue

            # Extract the cross-referenced CA date
            date = extract_original_ca_date(text)
            if date:
                ca_date = date
                amendment_exhibit_url = ex["url"]
                break

        if not ca_date:
            print(f"  {cik} ({issuer_name[:30]}): no cross-ref CA date found — skipping")
            continue

        # Find the correct S0 using the deterministic selector
        try:
            correct_s0 = find_correct_s0(cik, ca_date, client)
        except Exception as e:
            print(f"  {cik} ({issuer_name[:30]}): S0 search error: {e}")
            continue

        if not correct_s0:
            print(f"  {cik} ({issuer_name[:30]}): no valid S0 found — skipping")
            continue

        print(f"  {cik} ({issuer_name[:30]}): FOUND S0 accession={correct_s0['accession']} exhibit={correct_s0['exhibit_type']}")

        selected.append({
            "cik": cik,
            "issuer": issuer_name,
            "ca_date": ca_date,
            "s0": correct_s0,
            "amendment_filings": filings,
            "first_amendment_exhibit_url": amendment_exhibit_url,
        })

    return selected


def acquire_chain(
    chain_id: str,
    replaces: str,
    candidate: dict,
    client: httpx.Client,
) -> dict:
    """Acquire a full replacement chain: S0 + all amendments."""
    cik = candidate["cik"]
    issuer = candidate["issuer"]
    ca_date = candidate["ca_date"]
    s0_info = candidate["s0"]
    amendment_filings = candidate["amendment_filings"]

    chain_dir = Path(f"data/held_out/{chain_id}")
    chain_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Acquiring {chain_id} ({issuer[:40]}) ---")
    print(f"  Replaces: {replaces}")
    print(f"  CIK: {cik}")
    print(f"  CA date: {ca_date}")

    # Download S0
    s0_content = download_document(s0_info["exhibit_url"], client)
    s0_text = html_to_text(s0_content)
    s0_html_path = chain_dir / "S0.html"
    s0_txt_path = chain_dir / "S0.txt"
    s0_html_path.write_bytes(s0_content)
    s0_txt_path.write_text(s0_text, encoding="utf-8")

    s0_doc = {
        "role": "S0",
        "accession": s0_info["accession"],
        "file_date": s0_info["file_date"],
        "exhibit_type": s0_info["exhibit_type"],
        "exhibit_description": s0_info["exhibit_description"],
        "document_url": s0_info["exhibit_url"],
        "html_path": str(s0_html_path),
        "text_path": str(s0_txt_path),
        "html_sha256": sha256(s0_content),
        "text_sha256": sha256(s0_text.encode("utf-8")),
        "html_bytes": len(s0_content),
        "text_chars": len(s0_text),
    }
    print(f"  S0: {s0_info['accession']} {s0_info['exhibit_type']} ({len(s0_text)} chars)")
    time.sleep(SEC_DELAY)

    # Download amendments
    documents = [s0_doc]
    amendment_accessions = []
    amendment_file_dates = []

    for i, filing in enumerate(amendment_filings, 1):
        role = f"A{i}"
        accession = filing["accession"]
        file_date = filing["file_date"]

        # Find the amendment exhibit in this filing
        try:
            exhibits = get_filing_index(cik, accession, client)
            time.sleep(SEC_DELAY)
        except Exception as e:
            print(f"  {role}: ERROR getting filing index: {e}")
            continue

        for ex in exhibits:
            etype = ex["type"].upper()
            if not etype.startswith("EX-10."):
                continue

            try:
                content = download_document(ex["url"], client)
                text = html_to_text(content)
                time.sleep(SEC_DELAY)
            except Exception:
                continue

            verification = verify_credit_agreement_content(text)
            if not verification["is_amendment"]:
                continue

            html_path = chain_dir / f"{role}.html"
            txt_path = chain_dir / f"{role}.txt"
            html_path.write_bytes(content)
            txt_path.write_text(text, encoding="utf-8")

            doc = {
                "role": role,
                "accession": accession,
                "file_date": file_date,
                "exhibit_type": ex["type"],
                "exhibit_description": ex["description"],
                "document_url": ex["url"],
                "html_path": str(html_path),
                "text_path": str(txt_path),
                "html_sha256": sha256(content),
                "text_sha256": sha256(text.encode("utf-8")),
                "html_bytes": len(content),
                "text_chars": len(text),
            }
            documents.append(doc)
            amendment_accessions.append(accession)
            amendment_file_dates.append(file_date)
            print(f"  {role}: {accession} {ex['type']} ({len(text)} chars)")
            break

    chain_entry = {
        "chain_id": chain_id,
        "cik": cik,
        "issuer": issuer,
        "s0_accession": s0_info["accession"],
        "s0_file_date": s0_info["file_date"],
        "amendment_accessions": amendment_accessions,
        "amendment_file_dates": amendment_file_dates,
        "comparison_at": amendment_file_dates[-1] if amendment_file_dates else None,
        "final_authoritative_source": "last_amendment_filing",
        "has_independent_ground_truth": False,
        "comparison_source_accession": None,
        "comparison_source_file_date": None,
        "comparison_source_kind": None,
        "documents": documents,
        "replaces": replaces,
        "replacement_reason": "S0_SOURCE_UNAVAILABLE",
        "replacement_selection_rule": "Same criteria as original held-out study: amendment to credit agreement 8-K filings, >= 2 amendments, valid S0 on EDGAR. Selected before semantic performance inspection.",
        "replacement_acquired_at": datetime.now(UTC).isoformat(),
        "cross_ref_ca_date": ca_date,
    }

    return chain_entry


def main() -> int:
    print("Step 26C — Replacement Chain Acquisition")
    print("=" * 60)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    excluded_ciks = get_excluded_ciks(manifest)

    print(f"Excluded CIKs: {len(excluded_ciks)} (held-out + dev)")
    print(f"Need {len(REPLACEMENTS)} replacement chains")

    with httpx.Client() as client:
        # Find candidates
        candidates = find_replacement_candidates(excluded_ciks, client, target_count=len(REPLACEMENTS))

        if len(candidates) < len(REPLACEMENTS):
            print(f"WARNING: Only found {len(candidates)} candidates, need {len(REPLACEMENTS)}")

        # Acquire each replacement chain
        new_chains = []
        acquisition_records = []

        for i, (repl, cand) in enumerate(zip(REPLACEMENTS, candidates)):
            chain_entry = acquire_chain(
                repl["chain_id"], repl["replaces"], cand, client,
            )
            new_chains.append(chain_entry)

            acquisition_records.append({
                "chain_id": repl["chain_id"],
                "replaces": repl["replaces"],
                "cik": cand["cik"],
                "issuer": cand["issuer"],
                "ca_date": cand["ca_date"],
                "s0_accession": cand["s0"]["accession"],
                "s0_file_date": cand["s0"]["file_date"],
                "s0_exhibit_type": cand["s0"]["exhibit_type"],
                "s0_text_chars": cand["s0"]["text_chars"],
                "s0_html_sha256": cand["s0"]["html_sha256"],
                "s0_text_sha256": cand["s0"]["text_sha256"],
                "amendment_count": len(chain_entry["amendment_accessions"]),
                "selection_rule": "Same criteria as original held-out study. Selected before semantic performance inspection.",
            })

        # Update manifest: remove HELD-018 and HELD-019, add replacements
        old_chains = manifest["chains"]
        excluded_ids = {"HELD-018", "HELD-019"}
        kept_chains = [c for c in old_chains if c["chain_id"] not in excluded_ids]

        # Mark excluded chains
        for c in old_chains:
            if c["chain_id"] in excluded_ids:
                c["status"] = "S0_SOURCE_UNAVAILABLE"
                c["excluded_reason"] = "authoritative predecessor agreement unavailable from EDGAR"

        # Add replacement chains
        kept_chains.extend(new_chains)

        # Sort by chain_id for consistency
        kept_chains.sort(key=lambda c: c["chain_id"])

        manifest["chains"] = kept_chains
        manifest["replacement_applied_at"] = datetime.now(UTC).isoformat()
        manifest["replacement_count"] = len(new_chains)
        manifest["excluded_chains"] = list(excluded_ids)

        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Write audit
        audit = {
            "study": "step26c_replacement_acquisition",
            "run_at": datetime.now(UTC).isoformat(),
            "replacements": acquisition_records,
            "excluded_chains": [
                {"chain_id": "HELD-018", "reason": "S0_SOURCE_UNAVAILABLE", "detail": "Credit agreement never filed on EDGAR (Nuo Therapeutics was private)"},
                {"chain_id": "HELD-019", "reason": "S0_SOURCE_UNAVAILABLE", "detail": "Credit agreement never filed on EDGAR (Oaktree Fund Administration as administrative agent)"},
            ],
        }
        REPLACEMENT_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPLACEMENT_AUDIT_PATH.write_text(json.dumps(audit, indent=2), encoding="utf-8")

        print(f"\n{'=' * 60}")
        print(f"Replacements acquired: {len(new_chains)}")
        for r in acquisition_records:
            print(f"  {r['chain_id']} (replaces {r['replaces']}): {r['issuer'][:30]} CIK={r['cik']} amendments={r['amendment_count']}")
        print(f"Manifest updated: {MANIFEST_PATH}")
        print(f"Audit: {REPLACEMENT_AUDIT_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
