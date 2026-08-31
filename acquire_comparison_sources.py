"""Acquire composite/conformed/restated comparison sources for existing chains.

This is a supplementary script that searches for and downloads
composite/conformed/restated credit agreement filings filed AFTER each
chain's last amendment.  It updates the existing manifest in-place with
comparison source fields.

This is run after acquire_chain_study.py to add comparison sources to
chains that were acquired before the comparison source search was
integrated.

Usage:
    set -a && source .env && set +a
    python acquire_comparison_sources.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

import httpx

from acquire_chain_study import (
    MANIFEST_JSON,
    OUTPUT_DIR,
    SEC_DELAY,
    SEC_USER_AGENT,
    download_document,
    find_comparison_source_for_cik,
    html_to_text,
    sha256,
)


def main() -> int:
    if not SEC_USER_AGENT or "test@" in SEC_USER_AGENT:
        print("ERROR: SEC_USER_AGENT not configured. Set it in .env")
        sys.exit(1)

    if not MANIFEST_JSON.exists():
        print(f"ERROR: {MANIFEST_JSON} not found. Run acquire_chain_study.py first.")
        sys.exit(1)

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    chains = manifest.get("chains", [])
    print(f"Loaded {len(chains)} chains from manifest")
    print()

    updated = 0
    with httpx.Client() as client:
        for entry in chains:
            chain_id = entry["chain_id"]
            cik = entry["cik"]
            issuer = entry["issuer"]

            # Skip if already has a comparison source
            if entry.get("comparison_source_accession"):
                print(f"  {chain_id}: already has comparison source, skipping")
                continue

            last_amend_date = entry["amendment_file_dates"][-1]
            print(f"  {chain_id} ({issuer[:30]}): searching after {last_amend_date}...")

            try:
                cmp_source = find_comparison_source_for_cik(
                    cik, last_amend_date, client,
                )
            except Exception as e:  # noqa: BLE001
                print(f"    ERROR: {e}")
                cmp_source = None

            if not cmp_source:
                # Ensure fields exist even when no source found
                entry["comparison_source_accession"] = None
                entry["comparison_source_file_date"] = None
                entry["comparison_source_kind"] = None
                print("    No comparison source found")
                continue

            print(f"    CMP: {cmp_source['file_date']} {cmp_source['exhibit_description'][:60]}")

            # Download the comparison source
            try:
                cmp_content = download_document(cmp_source["exhibit_url"], client)
                time.sleep(SEC_DELAY)
            except Exception as e:  # noqa: BLE001
                print(f"    ERROR downloading: {e}")
                entry["comparison_source_accession"] = None
                entry["comparison_source_file_date"] = None
                entry["comparison_source_kind"] = None
                continue

            cmp_html_hash = sha256(cmp_content)
            cmp_text = html_to_text(cmp_content)
            cmp_text_hash = sha256(cmp_text.encode("utf-8"))

            chain_dir = OUTPUT_DIR / chain_id
            cmp_html_path = chain_dir / "CMP.html"
            cmp_txt_path = chain_dir / "CMP.txt"
            cmp_html_path.write_bytes(cmp_content)
            cmp_txt_path.write_text(cmp_text, encoding="utf-8")

            # Add CMP document to the chain's documents list
            documents = entry.get("documents", [])
            # Remove any existing CMP entry (idempotent)
            documents = [d for d in documents if d.get("role") != "CMP"]
            documents.append({
                "role": "CMP",
                "accession": cmp_source["accession"],
                "file_date": cmp_source["file_date"],
                "exhibit_type": cmp_source["exhibit_type"],
                "exhibit_description": cmp_source["exhibit_description"],
                "document_url": cmp_source["exhibit_url"],
                "html_path": str(cmp_html_path),
                "text_path": str(cmp_txt_path),
                "html_sha256": cmp_html_hash,
                "text_sha256": cmp_text_hash,
                "html_bytes": len(cmp_content),
                "text_chars": len(cmp_text),
                "source_kind": cmp_source["source_kind"],
            })
            entry["documents"] = documents

            # Update chain-level fields
            entry["comparison_at"] = cmp_source["file_date"]
            entry["final_authoritative_source"] = (
                f"composite_conformed_restated:{cmp_source['accession']}"
            )
            entry["has_independent_ground_truth"] = True
            entry["comparison_source_accession"] = cmp_source["accession"]
            entry["comparison_source_file_date"] = cmp_source["file_date"]
            entry["comparison_source_kind"] = cmp_source["source_kind"]

            updated += 1
            print("    OK: comparison source downloaded")

            # Write manifest incrementally
            MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Final manifest write
    manifest["comparison_source_acquisition_at_utc"] = datetime.now(UTC).isoformat()
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print()
    print(f"{'=' * 60}")
    print(f"Updated {updated} chains with comparison sources")
    print(f"Manifest: {MANIFEST_JSON}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
