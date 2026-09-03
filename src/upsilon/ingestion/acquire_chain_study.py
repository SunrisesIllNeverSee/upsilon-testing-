"""Acquire 25 real EDGAR issuer chains for the Development Chain Study v1.

Each chain includes S0 (original credit agreement) + >=2 sequential
amendment filings, all downloaded from SEC EDGAR with full provenance
(URLs, accession numbers, SHA-256 hashes, file sizes).

Strategy:
  1. Search EDGAR full-text search for "amendment to credit agreement"
     in 8-K filings across a wide date range (2015-2026), paginating
     to capture more than the default 100 hits per range.
  2. Group hits by CIK — do NOT deduplicate (we want multiple filings
     per CIK to identify amendment chains).
  3. Filter to CIKs with >=2 amendment filings.
  4. For each candidate CIK, search the CIK's filing history for the
     original credit agreement (S0) — the earliest 8-K with a credit
     agreement exhibit dated before the first amendment.
  5. Download S0 + all amendments with full provenance.
  6. Write manifest to data/chain_study/manifest.json.

The 3 existing smoke-test chains (Ameresco, Amedisys, Bausch-Lomb) are
already in data/edgar_chains/ and are included as chains 1-3.  This
script acquires 22 additional chains (chains 4-25).

Usage:
    set -a && source .env && set +a
    python acquire_chain_study.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Upsilon Research test@example.com")
SEC_DELAY = float(os.getenv("SEC_REQUEST_DELAY_SECONDS", "0.20"))
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_API = "https://data.sec.gov/submissions/CIK{cik}.json"

OUTPUT_DIR = Path("data/chain_study")
MANIFEST_JSON = Path("data/chain_study/manifest.json")

# Specific query: amendment filings (not just any mention of "credit agreement")
AMENDMENT_QUERY = '"amendment to credit agreement"'
# Broader query for finding S0 (original credit agreement)
CREDIT_AGREEMENT_QUERY = '"credit agreement"'
SEARCH_FORMS = "8-K"

# Search across wide date ranges for diversity and chain depth
DATE_RANGES = [
    ("2015-01-01", "2017-12-31"),
    ("2018-01-01", "2019-12-31"),
    ("2020-01-01", "2021-06-30"),
    ("2021-07-01", "2022-12-31"),
    ("2023-01-01", "2024-06-30"),
    ("2024-07-01", "2026-08-30"),
]

PAGE_SIZE = 100  # EFTS max hits per page
MAX_PAGES = 5    # fetch up to 500 hits per date range

TARGET_NEW_CHAINS = 22  # 3 existing + 22 new = 25 total
MIN_AMENDMENTS = 2      # each chain needs >=2 amendments

# CIKs already in the smoke-test chains (exclude from new acquisition)
EXISTING_CIKS = {
    "0001488139",  # Ameresco
    "0000896262",  # Amedisys
    "0001860742",  # Bausch + Lomb
}


# ---------------------------------------------------------------------------
# EDGAR search and download helpers
# ---------------------------------------------------------------------------

def search_edgar(
    query: str,
    forms: str,
    start_date: str,
    end_date: str,
    client: httpx.Client,
    ciks: str | None = None,
    start_from: int = 0,
    retries: int = 3,
) -> list[dict]:
    """Search EDGAR full-text search API with pagination and retry."""
    params: dict[str, str | int] = {
        "q": query,
        "forms": forms,
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
        "from": str(start_from),
    }
    if ciks:
        params["ciks"] = ciks
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    for attempt in range(retries):
        try:
            resp = client.get(EDGAR_SEARCH, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            break
        except Exception:
            if attempt < retries - 1:
                time.sleep(SEC_DELAY * (attempt + 2))  # backoff
                continue
            raise
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        ciks_list = src.get("ciks", [])
        names = src.get("display_names", [])
        if not ciks_list:
            continue
        cik = ciks_list[0]
        name = names[0] if names else ""
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
        results.append({
            "cik": cik,
            "entity_name": name,
            "form": src.get("form", ""),
            "file_date": src.get("file_date", ""),
            "accession": src.get("adsh", ""),
            "items": src.get("items", []),
        })
    return results


def search_edgar_paginated(
    query: str,
    forms: str,
    start_date: str,
    end_date: str,
    client: httpx.Client,
    ciks: str | None = None,
) -> list[dict]:
    """Search EDGAR with pagination to get more than 100 hits.

    The EFTS API does not support deep pagination (returns 500 for
    high `from` values).  We catch errors and return what we have.
    """
    all_results: list[dict] = []
    for page in range(MAX_PAGES):
        start_from = page * PAGE_SIZE
        try:
            hits = search_edgar(
                query, forms, start_date, end_date, client,
                ciks=ciks, start_from=start_from,
            )
        except Exception:
            # EFTS returns 500 for deep pagination — stop and use what we have
            if page > 0:
                break
            raise
        all_results.extend(hits)
        time.sleep(SEC_DELAY)
        if len(hits) < PAGE_SIZE:
            break  # no more pages
    return all_results


def get_filing_index(cik: str, accession: str, client: httpx.Client) -> list[dict]:
    """Get the filing index page to find EX-10 exhibits.

    Parses each <tr> row individually to avoid cross-row matching.
    """
    acc_no_dashes = accession.replace("-", "")
    cik_int = str(int(cik))
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dashes}/"
        f"{accession}-index.html"
    )
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = client.get(index_url, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    exhibits: list[dict] = []
    for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL):
        row = row_m.group(1)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.IGNORECASE | re.DOTALL)
        if len(cells) < 4:
            continue
        type_cell = cells[3].strip()
        type_match = re.search(r"(EX-10[\w.\-]*)", type_cell, re.IGNORECASE)
        if not type_match:
            continue
        doc_type = type_match.group(1).strip().upper()
        link_m = re.search(r'href="([^"]+)"', cells[2], re.IGNORECASE)
        if not link_m:
            continue
        doc_path = link_m.group(1).strip()
        name_m = re.search(r">([^<]+)</a>", cells[2], re.IGNORECASE)
        doc_name = name_m.group(1).strip() if name_m else ""
        doc_desc = re.sub(r"<[^>]+>", "", cells[1]).strip()
        if "/ix?doc=" in doc_path:
            doc_path = doc_path.split("/ix?doc=")[1]
        full_url = (
            f"https://www.sec.gov{doc_path}"
            if doc_path.startswith("/")
            else doc_path
        )
        exhibits.append({
            "type": doc_type,
            "description": doc_desc,
            "url": full_url,
            "filename": doc_name,
        })
    return exhibits


def download_document(url: str, client: httpx.Client) -> bytes:
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = client.get(url, headers=headers, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def html_to_text(html: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Exhibit classification
# ---------------------------------------------------------------------------

def is_credit_agreement_exhibit(desc: str) -> bool:
    """Check if an exhibit description indicates a credit agreement document."""
    desc_lower = desc.lower()
    return (
        "credit agreement" in desc_lower
        or "credit and guaranty" in desc_lower
        or "loan agreement" in desc_lower
        or "loan and guaranty" in desc_lower
    )


def is_amendment_exhibit(desc: str) -> bool:
    """Check if an exhibit description indicates an amendment."""
    desc_lower = desc.lower()
    return "amend" in desc_lower and is_credit_agreement_exhibit(desc)


def is_composite_exhibit(desc: str) -> bool:
    """Check if an exhibit description indicates a composite/conformed/restated source.

    These are full amended-and-restated or conformed copies of the credit
    agreement — not incremental amendments.  They serve as independent
    authoritative comparison sources for the Development Chain Study.
    """
    desc_lower = desc.lower()
    return is_credit_agreement_exhibit(desc) and (
        "amended and restated" in desc_lower
        or "amended & restated" in desc_lower
        or "restated" in desc_lower
        or "conformed" in desc_lower
        or "composite" in desc_lower
    )


def find_credit_exhibit_in_filing(
    cik: str, accession: str, client: httpx.Client
) -> dict | None:
    """Find the best credit-agreement EX-10 exhibit in a filing.

    Returns the exhibit dict (with is_amendment flag) or None.
    """
    try:
        exhibits = get_filing_index(cik, accession, client)
    except Exception as e:  # noqa: BLE001
        print(f"    ERROR getting filing index for {accession}: {e}")
        return None
    time.sleep(SEC_DELAY)

    credit_exhibits = []
    for ex in exhibits:
        desc = ex["description"]
        if is_credit_agreement_exhibit(desc):
            ex["is_amendment"] = is_amendment_exhibit(desc)
            credit_exhibits.append(ex)

    if not credit_exhibits:
        return None

    # Prefer EX-10.1, then first credit exhibit
    return next(
        (e for e in credit_exhibits if e["type"] == "EX-10.1"),
        credit_exhibits[0],
    )


# ---------------------------------------------------------------------------
# S0 (original credit agreement) discovery
# ---------------------------------------------------------------------------

def find_s0_for_cik(
    cik: str,
    first_amendment_date: str,
    client: httpx.Client,
    amendment_accessions: set[str] | None = None,
) -> dict | None:
    """Find the original credit agreement (S0) for a CIK.

    Searches EDGAR for "credit agreement" 8-K filings by this CIK
    dated before the first amendment.  Returns the filing info or None.

    Amendment accessions are explicitly excluded so that an amendment
    filing is never returned as S0.  If no non-amendment credit
    agreement is found, returns None (the chain is skipped) rather
    than falling back to an amendment — an amendment mislabeled as
    S0 corrupts the chain provenance.
    """
    if amendment_accessions is None:
        amendment_accessions = set()

    # Search for credit agreement filings by this CIK before the first
    # amendment.  Use a date range ending 1 day before the first
    # amendment so the first amendment filing itself is excluded by
    # date; accession exclusion is a second safety net.
    first_amend_dt = datetime.fromisoformat(first_amendment_date + "T00:00:00")
    end_date = (first_amend_dt - timedelta(days=1)).date().isoformat()

    hits = search_edgar_paginated(
        CREDIT_AGREEMENT_QUERY,
        SEARCH_FORMS,
        "2010-01-01",  # wide start date
        end_date,
        client,
        ciks=cik,
    )

    # Sort by date ascending — earliest first
    hits.sort(key=lambda h: h["file_date"])

    # Check each filing for a credit agreement exhibit that is NOT an
    # amendment and NOT one of the amendment accessions.
    for hit in hits:
        accession = hit["accession"]
        if accession in amendment_accessions:
            continue
        ex = find_credit_exhibit_in_filing(cik, accession, client)
        if ex and not ex.get("is_amendment", False):
            return {
                "cik": cik,
                "issuer": hit["entity_name"],
                "accession": accession,
                "file_date": hit["file_date"],
                "exhibit_type": ex["type"],
                "exhibit_description": ex["description"],
                "exhibit_url": ex["url"],
                "is_amendment": False,
            }

    return None


# ---------------------------------------------------------------------------
# Composite / conformed / restated comparison source discovery
# ---------------------------------------------------------------------------

# Search query for amended-and-restated credit agreements (composites)
COMPOSITE_QUERY = '"amended and restated" "credit agreement"'


def find_comparison_source_for_cik(
    cik: str,
    last_amendment_date: str,
    client: httpx.Client,
) -> dict | None:
    """Find a composite/conformed/restated credit agreement filed AFTER the
    last amendment in the chain.

    These are full amended-and-restated or conformed copies of the credit
    agreement that serve as independent authoritative comparison sources.
    The prompt requires preferring these "where available."

    Searches EDGAR for "amended and restated" "credit agreement" 8-K filings
    by this CIK dated after the last amendment.  Falls back to a broader
    "credit agreement" search if the specific query yields nothing, then
    checks each filing's exhibits for a composite/restated/conformed
    description.

    Returns the filing info dict or None if no composite source is found.
    """
    # Primary search: "amended and restated" "credit agreement" after last amendment
    hits = search_edgar_paginated(
        COMPOSITE_QUERY,
        SEARCH_FORMS,
        last_amendment_date,
        "2026-12-31",
        client,
        ciks=cik,
    )

    # Fallback: broader "credit agreement" search after last amendment,
    # then check exhibits for composite/restated/conformed descriptions
    if not hits:
        hits = search_edgar_paginated(
            CREDIT_AGREEMENT_QUERY,
            SEARCH_FORMS,
            last_amendment_date,
            "2026-12-31",
            client,
            ciks=cik,
        )

    # Sort by date ascending — prefer the earliest composite after the chain
    hits.sort(key=lambda h: h["file_date"])

    for hit in hits:
        accession = hit["accession"]
        try:
            exhibits = get_filing_index(cik, accession, client)
        except Exception as e:  # noqa: BLE001
            print(f"    ERROR getting filing index for comparison source {accession}: {e}")
            continue
        time.sleep(SEC_DELAY)

        for ex in exhibits:
            if is_composite_exhibit(ex["description"]):
                return {
                    "cik": cik,
                    "issuer": hit["entity_name"],
                    "accession": accession,
                    "file_date": hit["file_date"],
                    "exhibit_type": ex["type"],
                    "exhibit_description": ex["description"],
                    "exhibit_url": ex["url"],
                    "source_kind": "composite_conformed_restated",
                }

    return None


# ---------------------------------------------------------------------------
# Main acquisition pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    if not SEC_USER_AGENT or "test@" in SEC_USER_AGENT:
        print("ERROR: SEC_USER_AGENT not configured. Set it in .env")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"SEC User-Agent: {SEC_USER_AGENT}")
    print(f"Target: {TARGET_NEW_CHAINS} new chains (S0 + >={MIN_AMENDMENTS} amendments)")
    print(f"Excluding {len(EXISTING_CIKS)} existing smoke CIKs")
    print()

    # Phase 1: Search EDGAR for "amendment to credit agreement" 8-K filings
    all_hits: list[dict] = []
    with httpx.Client() as client:
        for start, end in DATE_RANGES:
            print(f"Searching EDGAR: {start} to {end}...")
            hits = search_edgar_paginated(
                AMENDMENT_QUERY, SEARCH_FORMS, start, end, client,
            )
            print(f"  Found {len(hits)} hits")
            all_hits.extend(hits)

    # Group by CIK — keep ALL filings per CIK (no dedup)
    cik_hits: dict[str, list[dict]] = {}
    for hit in all_hits:
        cik = hit["cik"]
        # Deduplicate by accession within same CIK
        existing_accessions = {h["accession"] for h in cik_hits.get(cik, [])}
        if hit["accession"] not in existing_accessions:
            cik_hits.setdefault(cik, []).append(hit)

    # Filter: >=2 amendment filings, not in existing CIKs
    candidates = [
        (cik, hits)
        for cik, hits in cik_hits.items()
        if cik not in EXISTING_CIKS and len(hits) >= MIN_AMENDMENTS
    ]
    # Sort by amendment count descending (prefer longer chains)
    candidates.sort(key=lambda x: len(x[1]), reverse=True)

    print(f"\nFound {len(candidates)} candidate CIKs with >={MIN_AMENDMENTS} amendment filings")
    print()

    if len(candidates) < TARGET_NEW_CHAINS:
        print(f"WARNING: Only {len(candidates)} candidates. Will try to acquire all.")

    # Phase 2: For each candidate, verify credit-agreement exhibits and find S0
    # Resume support: load existing manifest if present
    manifest: dict = {
        "study": "development_chain_study_v1",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "sec_user_agent": SEC_USER_AGENT,
        "amendment_search_query": AMENDMENT_QUERY,
        "credit_agreement_search_query": CREDIT_AGREEMENT_QUERY,
        "search_forms": SEARCH_FORMS,
        "date_ranges": DATE_RANGES,
        "target_new_chains": TARGET_NEW_CHAINS,
        "min_amendments": MIN_AMENDMENTS,
        "existing_ciks_included": sorted(EXISTING_CIKS),
        "frozen_version": "semantic-mapper-v0.1",
        "chains": [],
    }

    already_acquired_ciks: set[str] = set()
    if MANIFEST_JSON.exists():
        try:
            old_manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
            old_chains = old_manifest.get("chains", [])
            manifest["chains"] = old_chains
            already_acquired_ciks = {c["cik"] for c in old_chains}
        except Exception:  # noqa: BLE001, S110
            pass  # corrupt manifest, start fresh

    chains_acquired = len(manifest["chains"])
    # Compute chain_num as max existing chain number + 1 to avoid
    # collisions when chains have been removed from the middle of the
    # sequence (leaving gaps in the STUDY-NNN numbering).
    existing_nums = []
    for c in manifest["chains"]:
        cid = c.get("chain_id", "")
        if cid.startswith("STUDY-"):
            try:
                existing_nums.append(int(cid.split("-")[1]))
            except (ValueError, IndexError):
                pass
    chain_num = max(existing_nums, default=3) + 1
    if already_acquired_ciks:
        print(f"Resuming: {chains_acquired} chains already acquired, {TARGET_NEW_CHAINS - chains_acquired} remaining")

    with httpx.Client() as client:
        for cik, hits in candidates:
            if chains_acquired >= TARGET_NEW_CHAINS:
                break

            if cik in already_acquired_ciks:
                continue  # already acquired in a prior run

            issuer = hits[0]["entity_name"]
            hits.sort(key=lambda h: h["file_date"])

            print(f"\n[{chains_acquired + 1}/{TARGET_NEW_CHAINS}] CIK={cik} {issuer[:50]} ({len(hits)} amendment filings)")

            # Verify each amendment filing has a credit-agreement exhibit
            amendment_filings: list[dict] = []
            for hit in hits:
                accession = hit["accession"]
                ex = find_credit_exhibit_in_filing(cik, accession, client)
                if not ex:
                    continue
                amendment_filings.append({
                    "cik": cik,
                    "issuer": issuer,
                    "accession": accession,
                    "file_date": hit["file_date"],
                    "exhibit_type": ex["type"],
                    "exhibit_description": ex["description"],
                    "exhibit_url": ex["url"],
                    "is_amendment": ex.get("is_amendment", True),
                })

            if len(amendment_filings) < MIN_AMENDMENTS:
                print(f"  Only {len(amendment_filings)} verified credit-agreement amendment exhibits (need >={MIN_AMENDMENTS}), skipping")
                continue

            # Find S0 (original credit agreement)
            first_amendment_date = amendment_filings[0]["file_date"]
            amendment_acns = {a["accession"] for a in amendment_filings}
            print(f"  Searching for S0 before {first_amendment_date}...")
            try:
                s0 = find_s0_for_cik(
                    cik, first_amendment_date, client,
                    amendment_accessions=amendment_acns,
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR searching for S0: {e}")
                s0 = None

            if not s0:
                print("  No S0 (original credit agreement) found, skipping")
                continue

            print(f"  S0: {s0['file_date']} {s0['exhibit_description'][:60]}")

            # Download all documents
            chain_id = f"STUDY-{chain_num:03d}"
            chain_dir = OUTPUT_DIR / chain_id
            chain_dir.mkdir(parents=True, exist_ok=True)

            chain_docs: list[dict] = []
            download_ok = True

            # Download S0
            try:
                content = download_document(s0["exhibit_url"], client)
                time.sleep(SEC_DELAY)
            except Exception as e:  # noqa: BLE001
                print(f"    ERROR downloading S0: {e}")
                download_ok = False
                continue

            html_hash = sha256(content)
            text = html_to_text(content)
            text_hash = sha256(text.encode("utf-8"))
            s0_html_path = chain_dir / "S0.html"
            s0_txt_path = chain_dir / "S0.txt"
            s0_html_path.write_bytes(content)
            s0_txt_path.write_text(text, encoding="utf-8")

            chain_docs.append({
                "role": "S0",
                "accession": s0["accession"],
                "file_date": s0["file_date"],
                "exhibit_type": s0["exhibit_type"],
                "exhibit_description": s0["exhibit_description"],
                "document_url": s0["exhibit_url"],
                "html_path": str(s0_html_path),
                "text_path": str(s0_txt_path),
                "html_sha256": html_hash,
                "text_sha256": text_hash,
                "html_bytes": len(content),
                "text_chars": len(text),
            })

            # Download amendments
            for i, amnd in enumerate(amendment_filings, 1):
                print(f"  A{i}: {amnd['file_date']} {amnd['exhibit_description'][:60]}")
                try:
                    content = download_document(amnd["exhibit_url"], client)
                    time.sleep(SEC_DELAY)
                except Exception as e:  # noqa: BLE001
                    print(f"    ERROR downloading A{i}: {e}")
                    download_ok = False
                    break

                html_hash = sha256(content)
                text = html_to_text(content)
                text_hash = sha256(text.encode("utf-8"))
                a_html_path = chain_dir / f"A{i}.html"
                a_txt_path = chain_dir / f"A{i}.txt"
                a_html_path.write_bytes(content)
                a_txt_path.write_text(text, encoding="utf-8")

                chain_docs.append({
                    "role": f"A{i}",
                    "accession": amnd["accession"],
                    "file_date": amnd["file_date"],
                    "exhibit_type": amnd["exhibit_type"],
                    "exhibit_description": amnd["exhibit_description"],
                    "document_url": amnd["exhibit_url"],
                    "html_path": str(a_html_path),
                    "text_path": str(a_txt_path),
                    "html_sha256": html_hash,
                    "text_sha256": text_hash,
                    "html_bytes": len(content),
                    "text_chars": len(text),
                })

            if not download_ok:
                print("  Chain acquisition incomplete, skipping")
                continue

            # Search for a composite/conformed/restated comparison source
            # filed AFTER the last amendment (prompt requirement #4:
            # "Prefer a later composite, conformed, or amended/restated
            # authoritative comparison source where available.")
            last_amend_date = amendment_filings[-1]["file_date"]
            print(f"  Searching for composite/conformed comparison source after {last_amend_date}...")
            try:
                cmp_source = find_comparison_source_for_cik(
                    cik, last_amend_date, client,
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR searching for comparison source: {e}")
                cmp_source = None

            comparison_at = last_amend_date
            final_authoritative_source = "last_amendment_filing"
            has_independent_gt = False

            if cmp_source:
                print(f"  CMP: {cmp_source['file_date']} {cmp_source['exhibit_description'][:60]}")
                try:
                    cmp_content = download_document(cmp_source["exhibit_url"], client)
                    time.sleep(SEC_DELAY)
                except Exception as e:  # noqa: BLE001
                    print(f"    ERROR downloading comparison source: {e}")
                    cmp_source = None

            if cmp_source:
                cmp_html_hash = sha256(cmp_content)
                cmp_text = html_to_text(cmp_content)
                cmp_text_hash = sha256(cmp_text.encode("utf-8"))
                cmp_html_path = chain_dir / "CMP.html"
                cmp_txt_path = chain_dir / "CMP.txt"
                cmp_html_path.write_bytes(cmp_content)
                cmp_txt_path.write_text(cmp_text, encoding="utf-8")

                chain_docs.append({
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
                comparison_at = cmp_source["file_date"]
                final_authoritative_source = (
                    f"composite_conformed_restated:{cmp_source['accession']}"
                )
                has_independent_gt = True
            else:
                print("  No composite/conformed comparison source found; using last amendment as authoritative")

            # Record chain in manifest
            chain_entry = {
                "chain_id": chain_id,
                "cik": cik,
                "issuer": issuer,
                "s0_accession": s0["accession"],
                "s0_file_date": s0["file_date"],
                "amendment_accessions": [a["accession"] for a in amendment_filings],
                "amendment_file_dates": [a["file_date"] for a in amendment_filings],
                "comparison_at": comparison_at,
                "final_authoritative_source": final_authoritative_source,
                "has_independent_ground_truth": has_independent_gt,
                "comparison_source_accession": (
                    cmp_source["accession"] if cmp_source else None
                ),
                "comparison_source_file_date": (
                    cmp_source["file_date"] if cmp_source else None
                ),
                "comparison_source_kind": (
                    cmp_source["source_kind"] if cmp_source else None
                ),
                "documents": chain_docs,
            }
            manifest["chains"].append(chain_entry)
            chains_acquired += 1
            chain_num += 1
            print(f"  OK: {len(chain_docs)} documents downloaded")

            # Write manifest incrementally so progress is not lost on crash
            MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Write manifest
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"Acquired {chains_acquired} new chains")
    print(f"Manifest: {MANIFEST_JSON}")
    print(f"Total chains in study: {3 + chains_acquired} (3 existing + {chains_acquired} new)")

    if chains_acquired < TARGET_NEW_CHAINS:
        print(f"WARNING: Only acquired {chains_acquired}/{TARGET_NEW_CHAINS} new chains.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
