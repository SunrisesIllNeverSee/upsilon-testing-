"""Acquire 25 completely new (held-out) EDGAR issuer chains for the
Step 19B Confirmatory Study.

This script is the held-out analog of acquire_chain_study.py.  It:

  1. Excludes EVERY CIK used in development (chain_study manifest +
     development corpus manifest + 3 EDGAR smoke-test fixtures).
  2. Searches EDGAR for "amendment to credit agreement" 8-K filings
     across wide date ranges, paginating for diversity.
  3. Filters to CIKs with >=2 amendment filings that are NOT in the
     dev-set exclusion list.
  4. For each candidate CIK, finds the original credit agreement (S0)
     filed before the first amendment.
  5. Downloads S0 + all amendments + optional composite/conformed
     comparison source (CMP) with full provenance (URLs, accessions,
     SHA-256 hashes, file sizes).
  6. Writes manifest to data/held_out/manifest.json.

NO held-out document is inspected before the frozen system runs.
This script only acquires raw documents — it does not run the frozen
parser, mapper, extractor, or reconstruction pipeline.

Usage:
    set -a && source .env && set +a
    python acquire_held_out_study.py
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

OUTPUT_DIR = Path("data/held_out")
MANIFEST_JSON = Path("data/held_out/manifest.json")

AMENDMENT_QUERY = '"amendment to credit agreement"'
CREDIT_AGREEMENT_QUERY = '"credit agreement"'
COMPOSITE_QUERY = '"amended and restated" "credit agreement"'
SEARCH_FORMS = "8-K"

# Use different date ranges than the dev study to maximize issuer
# diversity and reduce overlap risk.
DATE_RANGES = [
    ("2015-01-01", "2017-12-31"),
    ("2018-01-01", "2019-12-31"),
    ("2020-01-01", "2021-06-30"),
    ("2021-07-01", "2022-12-31"),
    ("2023-01-01", "2024-06-30"),
    ("2024-07-01", "2026-08-30"),
]

PAGE_SIZE = 100
MAX_PAGES = 5

TARGET_CHAINS = 25
MIN_AMENDMENTS = 2

# ---------------------------------------------------------------------------
# Dev-set CIK exclusion list
# ---------------------------------------------------------------------------
# Every CIK used in development: chain_study manifest (22 chains) +
# development corpus manifest (25 docs) + 3 EDGAR smoke-test fixtures.
# Total: 48 unique CIKs.  No held-out chain may use any of these.
DEV_CIKS = {
    "0000029332", "0000033185", "0000074303", "0000081318", "0000084129",
    "0000703351", "0000746598", "0000809248", "0000815556", "0000825324",
    "0000851968", "0000880266", "0000885725", "0000886128", "0000890447",
    "0000896262", "0000922864", "0001008654", "0001014052", "0001015328",
    "0001022646", "0001059142", "0001069533", "0001084991", "0001104485",
    "0001179929", "0001278027", "0001301787", "0001315257", "0001377149",
    "0001397047", "0001409269", "0001410428", "0001423902", "0001452857",
    "0001488139", "0001512077", "0001512762", "0001517175", "0001525759",
    "0001600033", "0001609253", "0001617669", "0001638833", "0001672326",
    "0001692787", "0001822145", "0001860742",
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
                time.sleep(SEC_DELAY * (attempt + 2))
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
    all_results: list[dict] = []
    for page in range(MAX_PAGES):
        start_from = page * PAGE_SIZE
        try:
            hits = search_edgar(
                query, forms, start_date, end_date, client,
                ciks=ciks, start_from=start_from,
            )
        except Exception:
            if page > 0:
                break
            raise
        all_results.extend(hits)
        time.sleep(SEC_DELAY)
        if len(hits) < PAGE_SIZE:
            break
    return all_results


def get_filing_index(cik: str, accession: str, client: httpx.Client) -> list[dict]:
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
# Exhibit classification (same heuristics as dev study)
# ---------------------------------------------------------------------------

def is_credit_agreement_exhibit(desc: str, exhibit_type: str = "") -> bool:
    """Check if an exhibit description indicates a credit agreement document.

    Many EDGAR filings have generic exhibit descriptions like "EX-10.1" or
    "EXHIBIT 10.1" without mentioning "credit agreement" in the description.
    Since we only call this on filings already matched by the full-text
    search for "amendment to credit agreement", a generic EX-10.1 exhibit
    in such a filing is very likely the credit agreement exhibit.
    """
    desc_lower = desc.lower()
    if (
        "credit agreement" in desc_lower
        or "credit and guaranty" in desc_lower
        or "loan agreement" in desc_lower
        or "loan and guaranty" in desc_lower
    ):
        return True
    # Accept generic EX-10.* descriptions (just the exhibit number, no
    # other identifying text).  This catches filings where the description
    # is literally "EX-10.1" or "EXHIBIT 10.1".
    type_clean = exhibit_type.upper().strip()
    desc_clean = desc_lower.strip()
    if type_clean.startswith("EX-10."):
        # Generic description = just the exhibit type or "exhibit" + number
        if desc_clean in (
            type_clean.lower(),
            "exhibit " + type_clean[3:].lower(),
            "ex-" + type_clean[3:].lower(),
        ):
            return True
    return False


def is_amendment_exhibit(desc: str, exhibit_type: str = "") -> bool:
    desc_lower = desc.lower()
    # If description explicitly says "amend", it's an amendment
    if "amend" in desc_lower and is_credit_agreement_exhibit(desc, exhibit_type):
        return True
    # If the description is generic (just exhibit number), we can't tell
    # from the description alone.  We assume amendment filings matched by
    # the "amendment to credit agreement" full-text search are amendments.
    # The is_amendment flag will be set to True by default in the caller.
    return False


def _is_generic_desc(desc: str, exhibit_type: str) -> bool:
    """Check if an exhibit description is generic (just the exhibit number)."""
    type_clean = exhibit_type.upper().strip()
    desc_clean = desc.lower().strip()
    return desc_clean in (
        type_clean.lower(),
        "exhibit " + type_clean[3:].lower(),
        "ex-" + type_clean[3:].lower(),
    )


def is_composite_exhibit(desc: str) -> bool:
    desc_lower = desc.lower()
    return is_credit_agreement_exhibit(desc, "") and (
        "amended and restated" in desc_lower
        or "amended & restated" in desc_lower
        or "restated" in desc_lower
        or "conformed" in desc_lower
        or "composite" in desc_lower
    )


def find_credit_exhibit_in_filing(
    cik: str, accession: str, client: httpx.Client,
    assume_amendment: bool = True,
) -> dict | None:
    """Find the best credit-agreement EX-10 exhibit in a filing.

    Args:
        assume_amendment: if True, generic-description exhibits are assumed
            to be amendments (used when searching amendment filings).  If
            False, generic-description exhibits are assumed to be non-
            amendments (used when searching for S0).
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
        etype = ex.get("type", "")
        if is_credit_agreement_exhibit(desc, etype):
            desc_lower = desc.lower()
            if "amend" in desc_lower:
                ex["is_amendment"] = True
            elif "restated" in desc_lower or "conformed" in desc_lower or "composite" in desc_lower:
                ex["is_amendment"] = False
            elif _is_generic_desc(desc, etype):
                ex["is_amendment"] = assume_amendment
            else:
                ex["is_amendment"] = is_amendment_exhibit(desc, etype)
            credit_exhibits.append(ex)
    if not credit_exhibits:
        return None
    return next(
        (e for e in credit_exhibits if e["type"] == "EX-10.1"),
        credit_exhibits[0],
    )


# ---------------------------------------------------------------------------
# S0 and CMP discovery
# ---------------------------------------------------------------------------

def find_s0_for_cik(
    cik: str,
    first_amendment_date: str,
    client: httpx.Client,
    amendment_accessions: set[str] | None = None,
) -> dict | None:
    if amendment_accessions is None:
        amendment_accessions = set()
    first_amend_dt = datetime.fromisoformat(first_amendment_date + "T00:00:00")
    end_date = (first_amend_dt - timedelta(days=1)).date().isoformat()
    hits = search_edgar_paginated(
        CREDIT_AGREEMENT_QUERY, SEARCH_FORMS, "2010-01-01", end_date, client, ciks=cik,
    )
    hits.sort(key=lambda h: h["file_date"])
    for hit in hits:
        accession = hit["accession"]
        if accession in amendment_accessions:
            continue
        ex = find_credit_exhibit_in_filing(cik, accession, client, assume_amendment=False)
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


def find_comparison_source_for_cik(
    cik: str,
    last_amendment_date: str,
    client: httpx.Client,
) -> dict | None:
    hits = search_edgar_paginated(
        COMPOSITE_QUERY, SEARCH_FORMS, last_amendment_date, "2026-12-31", client, ciks=cik,
    )
    if not hits:
        hits = search_edgar_paginated(
            CREDIT_AGREEMENT_QUERY, SEARCH_FORMS, last_amendment_date, "2026-12-31", client, ciks=cik,
        )
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
    print(f"Target: {TARGET_CHAINS} held-out chains (S0 + >={MIN_AMENDMENTS} amendments)")
    print(f"Excluding {len(DEV_CIKS)} dev-set CIKs")
    print()

    # Phase 1: Search EDGAR for amendment filings
    all_hits: list[dict] = []
    with httpx.Client() as client:
        for start, end in DATE_RANGES:
            print(f"Searching EDGAR: {start} to {end}...")
            hits = search_edgar_paginated(
                AMENDMENT_QUERY, SEARCH_FORMS, start, end, client,
            )
            print(f"  Found {len(hits)} hits")
            all_hits.extend(hits)

    # Group by CIK
    cik_hits: dict[str, list[dict]] = {}
    for hit in all_hits:
        cik = hit["cik"]
        existing_accessions = {h["accession"] for h in cik_hits.get(cik, [])}
        if hit["accession"] not in existing_accessions:
            cik_hits.setdefault(cik, []).append(hit)

    # Filter: >=2 amendment filings, NOT in dev CIKs
    candidates = [
        (cik, hits)
        for cik, hits in cik_hits.items()
        if cik not in DEV_CIKS and len(hits) >= MIN_AMENDMENTS
    ]
    candidates.sort(key=lambda x: len(x[1]), reverse=True)

    print(f"\nFound {len(candidates)} candidate CIKs with >={MIN_AMENDMENTS} amendment filings (excluding dev set)")
    print()

    if len(candidates) < TARGET_CHAINS:
        print(f"WARNING: Only {len(candidates)} candidates. Will try to acquire all.")

    # Phase 2: Acquire chains
    manifest: dict = {
        "study": "held_out_confirmatory_study_19b",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "sec_user_agent": SEC_USER_AGENT,
        "amendment_search_query": AMENDMENT_QUERY,
        "credit_agreement_search_query": CREDIT_AGREEMENT_QUERY,
        "search_forms": SEARCH_FORMS,
        "date_ranges": DATE_RANGES,
        "target_chains": TARGET_CHAINS,
        "min_amendments": MIN_AMENDMENTS,
        "dev_ciks_excluded": sorted(DEV_CIKS),
        "dev_ciks_excluded_count": len(DEV_CIKS),
        "frozen_version": "v1.0-frozen-operational-build",
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
            pass

    chains_acquired = len(manifest["chains"])
    existing_nums = []
    for c in manifest["chains"]:
        cid = c.get("chain_id", "")
        if cid.startswith("HELD-"):
            try:
                existing_nums.append(int(cid.split("-")[1]))
            except (ValueError, IndexError):
                pass
    chain_num = max(existing_nums, default=0) + 1
    if already_acquired_ciks:
        print(f"Resuming: {chains_acquired} chains already acquired, {TARGET_CHAINS - chains_acquired} remaining")

    with httpx.Client() as client:
        for cik, hits in candidates:
            if chains_acquired >= TARGET_CHAINS:
                break
            if cik in already_acquired_ciks:
                continue

            issuer = hits[0]["entity_name"]
            hits.sort(key=lambda h: h["file_date"])

            print(f"\n[{chains_acquired + 1}/{TARGET_CHAINS}] CIK={cik} {issuer[:50]} ({len(hits)} amendment filings)")

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

            # Find S0
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
            chain_id = f"HELD-{chain_num:03d}"
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

            # Search for composite/conformed comparison source
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

            # Write manifest incrementally
            MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Write final manifest
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"Acquired {chains_acquired} held-out chains")
    print(f"Manifest: {MANIFEST_JSON}")

    if chains_acquired < TARGET_CHAINS:
        print(f"WARNING: Only acquired {chains_acquired}/{TARGET_CHAINS} held-out chains.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
