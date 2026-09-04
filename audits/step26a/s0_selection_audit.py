"""Step 26A — S0 Document Selection Audit.

For each of the 11 S0-failed chains, this script:
  1. Extracts the cross-referenced original credit agreement date from
     the amendment text (provenance resolution, NOT value inference).
  2. Searches EDGAR for 8-K filings around that date for the same CIK.
  3. Downloads candidate exhibits and verifies content contains
     credit-agreement structural signals.
  4. Records the findings to results/step26a_s0_selection_audit.json.

This does NOT modify the frozen manifest or any runtime code.
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Upsilon Research test@example.com")
SEC_DELAY = float(os.getenv("SEC_REQUEST_DELAY_SECONDS", "0.20"))
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_API = "https://data.sec.gov/submissions/CIK{cik}.json"

MANIFEST_PATH = Path("data/held_out/manifest.json")
OUTPUT_PATH = Path("results/step26a_s0_selection_audit.json")

FAILED_CHAINS = {
    "HELD-011", "HELD-012", "HELD-013", "HELD-014", "HELD-015",
    "HELD-016", "HELD-018", "HELD-019", "HELD-020", "HELD-021",
    "HELD-024",
}

# ---------------------------------------------------------------------------
# Amendment cross-reference extraction
# ---------------------------------------------------------------------------

# Patterns for extracting the original credit agreement date from
# amendment text.  These look for phrases like:
#   "that certain Credit Agreement dated as of July 8, 2014"
#   "Credit Agreement, dated as of December 17, 2020"
#   "Credit Agreement and Guaranty, dated as of April 19, 2022"
_CROSS_REF_PATTERNS = [
    re.compile(
        r"(?:certain\s+)?(?:Senior\s+Secured\s+)?(?:Revolving\s+)?"
        r"Credit\s+Agreement(?:\s+and\s+Guaranty)?"
        r"[,.\s]+(?:dated\s+(?:as\s+of\s+)?)"
        r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:certain\s+)?(?:Senior\s+Secured\s+)?(?:Revolving\s+)?"
        r"Credit\s+Agreement(?:\s+and\s+Guaranty)?"
        r"[,.\s]+(?:dated\s+(?:as\s+of\s+)?)"
        r"(\d{1,2}/\d{1,2}/\d{4})",
        re.IGNORECASE,
    ),
]


def extract_original_ca_date(amendment_text: str) -> str | None:
    """Extract the original credit agreement date from amendment text.

    This is provenance resolution: we use the amendment to identify
    WHICH document is the authoritative origin, not to infer what C0
    contained.
    """
    # Search in the first 10000 chars — the cross-reference is
    # typically in the recitals/whereas section near the start.
    text = amendment_text[:10000]
    dates = []
    for pat in _CROSS_REF_PATTERNS:
        for m in pat.finditer(text):
            date_str = m.group(1).strip()
            # Normalize: remove non-breaking spaces
            date_str = date_str.replace("\xa0", " ")
            dates.append(date_str)
    if not dates:
        return None
    # The original CA date is typically the EARLIEST date referenced
    # (amendments reference the original and prior amendments).
    # But we need to be careful — some amendments reference multiple
    # prior amendments.  The original CA date is the one that appears
    # in the "that certain Credit Agreement dated as of..." phrase,
    # not in "First Amendment dated as of..." phrases.
    # Our patterns are specific enough to capture only the CA date.
    # Return the first match (closest to the start of the document).
    return dates[0] if dates else None


# ---------------------------------------------------------------------------
# Credit agreement content verification
# ---------------------------------------------------------------------------

# Structural signals that confirm a document is actually a credit agreement
_CA_STRUCTURAL_SIGNALS = [
    re.compile(r"credit\s+agreement", re.IGNORECASE),
    re.compile(r"(?:borrower|lender|administrative\s+agent)", re.IGNORECASE),
    re.compile(r"(?:commitment|facility|loan|revolving|term\s+loan)", re.IGNORECASE),
    re.compile(r"(?:section|article)\s+\d", re.IGNORECASE),
]

# Anti-signals: if these appear in the first 500 chars, the document is
# likely NOT a credit agreement
_CA_ANTI_SIGNALS = [
    re.compile(r"^.{0,200}(?:lease\s+agreement|subscription\s+agreement"
               r"|contribution\s+agreement|registration\s+rights\s+agreement"
               r"|omnibus\s+agreement|joinder\s+agreement"
               r"|stock\s+purchase\s+agreement|exchange\s+agreement"
               r"|contingent\s+value\s+rights|swap\s+transaction"
               r"|surrender\s+of\s+class\s+b\s+shares|bond\s+purchase"
               r"|term\s+loan\s+note|promissory\s+note)", re.IGNORECASE),
]


def verify_credit_agreement_content(text: str) -> dict:
    """Verify that a document's content contains credit agreement signals.

    Returns a dict with:
      - is_credit_agreement: bool
      - signals_found: list of signal names
      - anti_signals_found: list of anti-signal names
      - first_200_chars: preview
    """
    first_500 = text[:500]
    signals_found = []
    for i, sig in enumerate(_CA_STRUCTURAL_SIGNALS):
        if sig.search(text[:5000]):
            signals_found.append(f"signal_{i}")

    anti_signals_found = []
    for i, anti in enumerate(_CA_ANTI_SIGNALS):
        if anti.search(first_500):
            anti_signals_found.append(f"anti_{i}")

    is_ca = (
        len(signals_found) >= 3
        and len(anti_signals_found) == 0
    )

    return {
        "is_credit_agreement": is_ca,
        "signals_found": signals_found,
        "anti_signals_found": anti_signals_found,
        "first_200_chars": first_500[:200].replace("\n", " "),
    }


# ---------------------------------------------------------------------------
# EDGAR search helpers
# ---------------------------------------------------------------------------


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


def search_edgar(
    query: str,
    forms: str,
    start_date: str,
    end_date: str,
    client: httpx.Client,
    ciks: str | None = None,
) -> list[dict]:
    params: dict[str, str | int] = {
        "q": query,
        "forms": forms,
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
    }
    if ciks:
        params["ciks"] = ciks
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    resp = client.get(EDGAR_SEARCH, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        ciks_list = src.get("ciks", [])
        if not ciks_list:
            continue
        cik = ciks_list[0]
        name = src.get("display_names", [""])[0]
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
        results.append({
            "cik": cik,
            "entity_name": name,
            "form": src.get("form", ""),
            "file_date": src.get("file_date", ""),
            "accession": src.get("adsh", ""),
        })
    return results


def get_submissions(cik: str, client: httpx.Client) -> dict:
    """Get the full submission history for a CIK."""
    cik_padded = cik.lstrip("0").zfill(10)
    url = SUBMISSIONS_API.format(cik=cik_padded)
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = client.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------


def main() -> int:
    print("Step 26A — S0 Document Selection Audit")
    print("=" * 60)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results = []

    with httpx.Client() as client:
        for chain in manifest["chains"]:
            cid = chain["chain_id"]
            if cid not in FAILED_CHAINS:
                continue

            print(f"\n--- {cid} ({chain['issuer']}) ---")
            cik = chain["cik"]

            # Step 1: Extract cross-referenced CA date from amendments
            amendments = [d for d in chain["documents"] if d["role"].startswith("A")]
            ca_date = None
            ca_date_source = None
            for amnd in amendments:
                text = Path(amnd["text_path"]).read_text(
                    encoding="utf-8", errors="ignore"
                )
                date = extract_original_ca_date(text)
                if date:
                    ca_date = date
                    ca_date_source = amnd["role"]
                    break

            if not ca_date:
                print(f"  No cross-referenced CA date found in amendments")
                # Try to find it by searching for "Credit Agreement" in all amendments
                for amnd in amendments:
                    text = Path(amnd["text_path"]).read_text(
                        encoding="utf-8", errors="ignore"
                    )
                    if re.search(r"credit\s+agreement", text[:5000], re.IGNORECASE):
                        print(f"    {amnd['role']} mentions Credit Agreement but no date extracted")
                ca_date = "UNKNOWN"

            print(f"  Cross-referenced CA date: {ca_date} (from {ca_date_source})")

            # Step 2: Search EDGAR for 8-K filings around that date
            # Parse the date and search a window of +/- 60 days
            edgar_candidates = []
            if ca_date != "UNKNOWN":
                try:
                    # Parse date (handle both "July 8, 2014" and "9/25/2014")
                    date_str = ca_date.replace("\xa0", " ")
                    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
                        try:
                            ca_dt = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        ca_dt = None

                    if ca_dt:
                        search_start = (ca_dt - timedelta(days=90)).date().isoformat()
                        search_end = (ca_dt + timedelta(days=90)).date().isoformat()
                        print(f"  Searching EDGAR: {search_start} to {search_end}")

                        hits = search_edgar(
                            '"credit agreement"', "8-K",
                            search_start, search_end, client, ciks=cik,
                        )
                        time.sleep(SEC_DELAY)

                        print(f"  Found {len(hits)} 8-K filings with 'credit agreement'")
                        for hit in hits:
                            accession = hit["accession"]
                            file_date = hit["file_date"]
                            print(f"    {file_date} {accession}")

                            # Get filing index
                            try:
                                exhibits = get_filing_index(cik, accession, client)
                            except Exception as e:
                                print(f"      ERROR: {e}")
                                continue
                            time.sleep(SEC_DELAY)

                            # Find EX-10 exhibits
                            for ex in exhibits:
                                if not ex["type"].startswith("EX-10"):
                                    continue
                                desc = ex["description"]
                                # Check if description mentions credit agreement
                                desc_lower = desc.lower()
                                has_ca_in_desc = (
                                    "credit agreement" in desc_lower
                                    or "credit and guaranty" in desc_lower
                                    or "loan agreement" in desc_lower
                                    or "loan and guaranty" in desc_lower
                                )
                                # Download and verify content
                                try:
                                    content = download_document(ex["url"], client)
                                    text = html_to_text(content)
                                except Exception as e:
                                    print(f"      ERROR downloading: {e}")
                                    continue
                                time.sleep(SEC_DELAY)

                                verification = verify_credit_agreement_content(text)
                                is_ca = verification["is_credit_agreement"]

                                # Check if it's an amendment
                                is_amendment = bool(
                                    re.search(r"amend", text[:2000], re.IGNORECASE)
                                )

                                # Check if it mentions the cross-referenced date
                                mentions_date = False
                                if ca_date != "UNKNOWN":
                                    date_str_clean = ca_date.replace("\xa0", " ")
                                    mentions_date = date_str_clean in text[:5000]

                                candidate = {
                                    "accession": accession,
                                    "file_date": file_date,
                                    "exhibit_type": ex["type"],
                                    "exhibit_description": desc,
                                    "exhibit_url": ex["url"],
                                    "text_chars": len(text),
                                    "has_ca_in_desc": has_ca_in_desc,
                                    "is_credit_agreement": is_ca,
                                    "is_amendment": is_amendment,
                                    "mentions_cross_ref_date": mentions_date,
                                    "verification": verification,
                                    "text_sha256": hashlib.sha256(
                                        text.encode("utf-8")
                                    ).hexdigest(),
                                }
                                edgar_candidates.append(candidate)

                                status = "CA" if is_ca else "NOT-CA"
                                amend = "AMEND" if is_amendment else "ORIG"
                                print(f"      {ex['type']}: {status} {amend} "
                                      f"desc={desc[:60]} chars={len(text)}")

                except Exception as e:
                    print(f"  ERROR searching EDGAR: {e}")

            # Step 3: Select the best S0 candidate
            # Criteria:
            #   1. is_credit_agreement = True
            #   2. is_amendment = False
            #   3. mentions_cross_ref_date = True (if date available)
            #   4. Earliest file_date
            best_s0 = None
            for cand in edgar_candidates:
                if not cand["is_credit_agreement"]:
                    continue
                if cand["is_amendment"]:
                    continue
                if best_s0 is None:
                    best_s0 = cand
                elif cand["mentions_cross_ref_date"] and not best_s0["mentions_cross_ref_date"]:
                    best_s0 = cand
                elif (cand["mentions_cross_ref_date"] == best_s0["mentions_cross_ref_date"]
                      and cand["file_date"] < best_s0["file_date"]):
                    best_s0 = cand

            if best_s0:
                print(f"\n  BEST S0 CANDIDATE:")
                print(f"    accession: {best_s0['accession']}")
                print(f"    file_date: {best_s0['file_date']}")
                print(f"    exhibit: {best_s0['exhibit_type']}")
                print(f"    desc: {best_s0['exhibit_description'][:80]}")
                print(f"    text_chars: {best_s0['text_chars']}")
                print(f"    mentions_cross_ref_date: {best_s0['mentions_cross_ref_date']}")
            else:
                print(f"\n  NO VALID S0 CANDIDATE FOUND")
                # Check if any candidate is a credit agreement at all
                ca_candidates = [c for c in edgar_candidates if c["is_credit_agreement"]]
                if ca_candidates:
                    print(f"  (Found {len(ca_candidates)} CA candidates but all are amendments)")
                else:
                    print(f"  (Found {len(edgar_candidates)} EX-10 candidates, none are CA)")

            # Record results
            current_s0 = [d for d in chain["documents"] if d["role"] == "S0"][0]
            results.append({
                "chain_id": cid,
                "issuer": chain["issuer"],
                "cik": cik,
                "current_s0": {
                    "accession": current_s0["accession"],
                    "file_date": current_s0["file_date"],
                    "exhibit_description": current_s0["exhibit_description"],
                    "text_chars": current_s0["text_chars"],
                },
                "cross_ref_ca_date": ca_date,
                "cross_ref_source": ca_date_source,
                "edgar_candidates": edgar_candidates,
                "best_s0_candidate": best_s0,
                "verdict": "FOUND" if best_s0 else "NOT_FOUND",
            })

    # Write results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "study": "step26a_s0_selection_audit",
        "run_at": datetime.now(UTC).isoformat(),
        "failed_chains": sorted(FAILED_CHAINS),
        "results": results,
        "summary": {
            "total_failed": len(FAILED_CHAINS),
            "found": sum(1 for r in results if r["verdict"] == "FOUND"),
            "not_found": sum(1 for r in results if r["verdict"] == "NOT_FOUND"),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"Results: {output['summary']}")
    print(f"Output: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
