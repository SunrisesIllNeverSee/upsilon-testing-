"""Step 26B — Corrected S0 Document Selection.

This module implements the deterministic credit-agreement identification
rule and applies it to the 11 S0-failed chains.

The rule combines:
  1. Amendment cross-reference extraction (provenance resolution)
  2. EDGAR full-text search around the cross-referenced date
  3. Content-based verification (structural signals + anti-signals)
  4. Title-based amendment detection (not just any "amend" mention)

This is NOT hand-picking files. The selection mechanism is deterministic
and applies the same rule to every chain.

Usage:
    set -a && source .env && set +a
    python -m audits.step26b.corrected_s0_selection
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

MANIFEST_PATH = Path("data/held_out/manifest.json")
CORRECTED_MANIFEST_PATH = Path("data/held_out/manifest_corrected.json")
AUDIT_OUTPUT_PATH = Path("results/step26b_corrected_s0_selection.json")

# Chains that need S0 correction (the 11 S0-failed chains minus HELD-008
# which has an extractor issue, not a selection issue)
CHAINS_TO_CORRECT = {
    "HELD-011", "HELD-012", "HELD-013", "HELD-014", "HELD-015",
    "HELD-016", "HELD-018", "HELD-019", "HELD-020", "HELD-021",
    "HELD-024",
}

# ---------------------------------------------------------------------------
# Amendment cross-reference extraction (provenance resolution)
# ---------------------------------------------------------------------------

# Pattern for "that certain Credit Agreement dated as of [date]"
# This is the provenance resolution pattern — it identifies WHICH document
# is the authoritative origin, not what C0 contained.
_CROSS_REF_RE = re.compile(
    r"(?:certain\s+)?(?:Senior\s+Secured\s+)?(?:Revolving\s+)?"
    r"Credit\s+Agreement(?:\s+and\s+Guaranty)?"
    r"[,.\s]+(?:dated\s+(?:as\s+of\s+)?)"
    r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)

# Anti-pattern: "First Amendment to Credit Agreement dated as of..."
# We want the ORIGINAL credit agreement date, not amendment dates.
# The original CA date appears in "that certain Credit Agreement dated..."
# while amendment dates appear in "First/Second/Third Amendment to Credit
# Agreement dated..." or "First Amendment dated..."
_AMENDMENT_TITLE_RE = re.compile(
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|"
    r"Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth|Sixteenth|"
    r"Seventeenth|Eighteenth|Nineteenth|Twentieth)\s+Amendment",
    re.IGNORECASE,
)


def extract_original_ca_date(amendment_text: str) -> str | None:
    """Extract the original credit agreement date from amendment text.

    Provenance resolution: uses the amendment to identify WHICH document
    is the authoritative origin. Does NOT infer what C0 contained.

    Returns the earliest date that appears in a "Credit Agreement dated
    as of..." context that is NOT preceded by an amendment title.
    """
    text = amendment_text[:15000]
    candidates = []
    for m in _CROSS_REF_RE.finditer(text):
        # Check if this match is preceded by an amendment title
        # (within 100 chars before the match)
        before = text[max(0, m.start() - 100):m.start()]
        if _AMENDMENT_TITLE_RE.search(before):
            continue
        date_str = m.group(1).replace("\xa0", " ").strip()
        candidates.append((m.start(), date_str))

    if not candidates:
        return None

    # Return the first non-amendment match (closest to document start)
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Content-based credit agreement verification
# ---------------------------------------------------------------------------

# Structural signals that confirm a document IS a credit agreement.
# Must appear in the first 5000 chars.
_CA_STRUCTURAL_SIGNALS = {
    "credit_agreement": re.compile(r"credit\s+agreement", re.IGNORECASE),
    "borrower_or_lender": re.compile(
        r"(?:borrower|lender|administrative\s+agent)", re.IGNORECASE
    ),
    "commitment_or_facility": re.compile(
        r"(?:commitment|facility|revolving|term\s+loan)", re.IGNORECASE
    ),
    "section_or_article": re.compile(
        r"(?:section|article)\s+\d", re.IGNORECASE
    ),
}

# Anti-signals: if these appear in the first 300 chars, the document is
# NOT a credit agreement.
_CA_ANTI_SIGNALS = re.compile(
    r"(?:lease\s+agreement|subscription\s+agreement"
    r"|contribution\s+agreement|registration\s+rights\s+agreement"
    r"|omnibus\s+agreement|joinder\s+agreement"
    r"|stock\s+purchase\s+agreement|exchange\s+agreement"
    r"|contingent\s+value\s+rights|swap\s+transaction"
    r"|surrender\s+of\s+class\s+b\s+shares|bond\s+purchase"
    r"|term\s+loan\s+note|promissory\s+note"
    r"|manager\s+incentive\s+plan|trademark\s+license"
    r"|separation\s+and\s+shared\s+services"
    r"|registration\s+rights|warrant\s+agreement"
    r"|company\s+warrant|form\s+of\s+warrant|warrant\s+to\s+purchase)",
    re.IGNORECASE,
)

# Title-based amendment detection: checks if the document TITLE
# (first 300 chars) says it's an amendment. Matches:
#   "FIRST AMENDMENT TO CREDIT AGREEMENT"
#   "AMENDMENT NO. 2 TO CREDIT AGREEMENT"
#   "THIRD AMENDMENT TO CREDIT AGREEMENT AND GUARANTY"
_AMENDMENT_TITLE_RE_FULL = re.compile(
    r"(?:"
    r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|"
    r"SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH)\s+AMENDMENT"
    r"|AMENDMENT\s+NO\.?\s*\d+"
    r"|AMENDMENT\s+TO\s+(?:CREDIT\s+)?AGREEMENT"
    r"|WAIVER\s+AND\s+(?:\w+\s+)*AMENDMENT"
    r"|CONSENT\s+AND\s+AMENDMENT"
    r"|LIMITED\s+CONSENT\s+AND\s+\w+\s+AMENDMENT"
    r")",
    re.IGNORECASE,
)


def verify_credit_agreement_content(text: str) -> dict:
    """Verify that a document's content contains credit agreement signals.

    Returns a dict with:
      - is_credit_agreement: bool (True if >= 3 structural signals and
        no anti-signals in the first 300 chars)
      - is_amendment: bool (True if title says "Amendment to ... Agreement")
      - signals_found: list of signal names
      - has_anti_signal: bool
      - first_300_chars: preview
    """
    first_300 = text[:300]
    first_5000 = text[:5000]

    signals_found = [
        name for name, pattern in _CA_STRUCTURAL_SIGNALS.items()
        if pattern.search(first_5000)
    ]

    has_anti_signal = bool(_CA_ANTI_SIGNALS.search(first_300))
    is_amendment = bool(_AMENDMENT_TITLE_RE_FULL.search(first_300))

    is_ca = (
        len(signals_found) >= 3
        and not has_anti_signal
        and not is_amendment
    )

    return {
        "is_credit_agreement": is_ca,
        "is_amendment": is_amendment,
        "signals_found": signals_found,
        "has_anti_signal": has_anti_signal,
        "first_300_chars": first_300.replace("\n", " "),
    }


# ---------------------------------------------------------------------------
# EDGAR helpers
# ---------------------------------------------------------------------------


def get_filing_index(cik: str, accession: str, client: httpx.Client) -> list[dict]:
    # The accession number format is CCCCCCCCC-YY-NNNNNN where CCCCCCCCC
    # is the CIK of the filer. Use that CIK for the filing index URL,
    # since the filing may be under a different CIK than the chain's CIK.
    acc_cik = accession.split("-")[0]
    acc_no_dashes = accession.replace("-", "")
    cik_int = str(int(acc_cik))
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dashes}/"
        f"{accession}-index.html"
    )
    headers = {"User-Agent": SEC_USER_AGENT}
    for attempt in range(3):
        try:
            resp = client.get(index_url, headers=headers, timeout=30)
            resp.raise_for_status()
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return []
    html = resp.text
    exhibits: list[dict] = []
    for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL):
        row = row_m.group(1)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.IGNORECASE | re.DOTALL)
        if len(cells) < 4:
            continue
        type_cell = cells[3].strip()
        link_m = re.search(r'href="([^"]+)"', cells[2], re.IGNORECASE)
        if not link_m:
            continue
        doc_path = link_m.group(1).strip()
        doc_desc = re.sub(r"<[^>]+>", "", cells[1]).strip()
        if "/ix?doc=" in doc_path:
            doc_path = doc_path.split("/ix?doc=")[1]
        full_url = (
            f"https://www.sec.gov{doc_path}"
            if doc_path.startswith("/")
            else doc_path
        )
        exhibits.append({
            "type": type_cell,
            "description": doc_desc,
            "url": full_url,
        })
    return exhibits


def download_document(url: str, client: httpx.Client) -> bytes:
    headers = {"User-Agent": SEC_USER_AGENT}
    for attempt in range(3):
        try:
            resp = client.get(url, headers=headers, timeout=120, follow_redirects=True)
            resp.raise_for_status()
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            raise
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
        results.append({
            "cik": ciks_list[0],
            "file_date": src.get("file_date", ""),
            "form": src.get("form", ""),
            "accession": src.get("adsh", ""),
        })
    return results


# ---------------------------------------------------------------------------
# Deterministic S0 selection
# ---------------------------------------------------------------------------


def get_submissions(cik: str, client: httpx.Client) -> list[dict]:
    """Get all filings for a CIK using the submissions API.

    Returns a list of {accession, file_date, form} dicts.
    More reliable than EDGAR full-text search.
    """
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    headers = {"User-Agent": SEC_USER_AGENT}
    for attempt in range(3):
        try:
            resp = client.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return []
    data = resp.json()
    filings = []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    for i in range(len(forms)):
        filings.append({
            "accession": accessions[i],
            "file_date": dates[i],
            "form": forms[i],
        })
    # Also check older filings
    older = data.get("filings", {}).get("older", [])
    for bucket in older:
        bforms = bucket.get("form", [])
        bdates = bucket.get("filingDate", [])
        baccessions = bucket.get("accessionNumber", [])
        for i in range(len(bforms)):
            filings.append({
                "accession": baccessions[i],
                "file_date": bdates[i],
                "form": bforms[i],
            })
    return filings


def find_correct_s0(
    cik: str,
    ca_date: str,
    client: httpx.Client,
) -> dict | None:
    """Find the correct S0 credit agreement using the deterministic rule.

    Steps:
      1. Parse the cross-referenced CA date.
      2. Get ALL filings for the CIK via the submissions API.
      3. Filter to filings within +/- 365 days of the CA date
         (credit agreements can be filed as 10-K exhibits months later).
      4. For each filing, get all EX-10 and EX-4 exhibits.
      5. Download each exhibit and verify content.
      6. Rank candidates: mentions_cross_ref_date > EX-10 > larger text >
         earlier filing.
    """
    # Parse the date
    date_str = ca_date.replace("\xa0", " ")
    ca_dt = None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            ca_dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    if ca_dt is None:
        return None

    search_start = (ca_dt - timedelta(days=120)).date().isoformat()
    search_end = (ca_dt + timedelta(days=365)).date().isoformat()

    # Use submissions API as primary source
    all_filings = get_submissions(cik, client)
    time.sleep(SEC_DELAY)

    # Filter to filings within the date range and relevant form types
    # (credit agreements are filed as exhibits to 8-K, 10-K, S-1, S-4)
    RELEVANT_FORMS = {"8-K", "10-K", "10-K/A", "S-1", "S-1/A", "S-4", "S-4/A"}
    hits = [
        f for f in all_filings
        if search_start <= f["file_date"] <= search_end
        and f["form"] in RELEVANT_FORMS
    ]

    # Also search EDGAR full-text (some filings may be under a different
    # CIK but still associated with this issuer, e.g., subsidiary filings)
    try:
        edgar_hits = search_edgar(
            '"credit agreement"', "8-K,10-K",
            search_start, search_end, client, ciks=cik,
        )
        time.sleep(SEC_DELAY)
        # Merge, deduplicating by accession
        existing_accessions = {h["accession"] for h in hits}
        for eh in edgar_hits:
            if eh["accession"] not in existing_accessions:
                hits.append(eh)
                existing_accessions.add(eh["accession"])
    except Exception:
        pass
    # Sort by file_date (oldest first)
    hits.sort(key=lambda h: h["file_date"])

    candidates = []
    for hit in hits:
        accession = hit["accession"]
        file_date = hit["file_date"]
        exhibits = get_filing_index(cik, accession, client)
        time.sleep(SEC_DELAY)

        for ex in exhibits:
            # Check EX-10 and EX-4 exhibit types (credit agreements can
            # be filed as either)
            etype = ex["type"].upper()
            if not (etype.startswith("EX-10.") or etype.startswith("EX-4.")):
                continue

            # Download and verify
            try:
                content = download_document(ex["url"], client)
                text = html_to_text(content)
            except Exception:
                continue
            time.sleep(SEC_DELAY)

            if len(text) < 5000:
                continue  # Too short to be a credit agreement

            verification = verify_credit_agreement_content(text)
            if not verification["is_credit_agreement"]:
                continue

            # Check if the text mentions the cross-referenced date
            # (case-insensitive, handle non-breaking spaces and case)
            date_str_clean = ca_date.replace("\xa0", " ")
            date_upper = date_str_clean.upper()
            mentions_date = (
                date_str_clean in text[:10000]
                or date_upper in text[:10000]
                or date_str_clean.replace(",", ", ") in text[:10000]
            )

            is_ex10 = etype.startswith("EX-10.")

            candidate = {
                "cik": cik,
                "accession": accession,
                "file_date": file_date,
                "exhibit_type": ex["type"],
                "exhibit_description": ex["description"],
                "exhibit_url": ex["url"],
                "text_chars": len(text),
                "html_sha256": sha256(content),
                "text_sha256": sha256(text.encode("utf-8")),
                "mentions_cross_ref_date": mentions_date,
                "is_ex10": is_ex10,
                "verification": verification,
            }
            candidates.append(candidate)

    if not candidates:
        return None

    # Rank candidates using a scoring system:
    #   +100 if mentions_cross_ref_date
    #   +50 if is_ex10 (prefer EX-10 over EX-4)
    #   +1 per 10K chars (prefer larger documents)
    #   -1 per day from CA date (prefer filings closer to the CA date)
    def score(c: dict) -> int:
        s = 0
        if c["mentions_cross_ref_date"]:
            s += 100
        if c["is_ex10"]:
            s += 50
        s += c["text_chars"] // 10000
        try:
            file_dt = datetime.fromisoformat(c["file_date"])
            days_from_ca = abs((file_dt - ca_dt).days)
            s -= days_from_ca
        except Exception:
            pass
        return s

    candidates.sort(key=score, reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Step 26B — Corrected S0 Document Selection")
    print("=" * 60)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    corrections = []
    corrected_chains = []

    with httpx.Client() as client:
        for chain in manifest["chains"]:
            cid = chain["chain_id"]
            if cid not in CHAINS_TO_CORRECT:
                corrected_chains.append(chain)
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
                print(f"  No cross-referenced CA date found — keeping original S0")
                corrected_chains.append(chain)
                corrections.append({
                    "chain_id": cid,
                    "action": "NO_CROSS_REF_DATE",
                    "ca_date": None,
                })
                continue

            print(f"  Cross-referenced CA date: {ca_date} (from {ca_date_source})")

            # Step 2: Find the correct S0
            try:
                correct_s0 = find_correct_s0(cik, ca_date, client)
            except Exception as e:
                print(f"  ERROR searching for S0: {e}")
                correct_s0 = None

            if not correct_s0:
                print(f"  No correct S0 found on EDGAR — marking as UNAVAILABLE")
                corrected_chains.append(chain)
                corrections.append({
                    "chain_id": cid,
                    "action": "S0_UNAVAILABLE",
                    "ca_date": ca_date,
                    "ca_date_source": ca_date_source,
                })
                continue

            print(f"  Found correct S0:")
            print(f"    accession: {correct_s0['accession']}")
            print(f"    file_date: {correct_s0['file_date']}")
            print(f"    exhibit: {correct_s0['exhibit_type']}")
            print(f"    text_chars: {correct_s0['text_chars']}")
            print(f"    mentions_cross_ref_date: {correct_s0['mentions_cross_ref_date']}")

            # Step 3: Download the correct S0 document
            chain_dir = Path(f"data/held_out/{cid}")
            s0_html_path = chain_dir / "S0.html"
            s0_txt_path = chain_dir / "S0.txt"

            # Backup the original S0
            s0_html_bak = chain_dir / "S0_original.html"
            s0_txt_bak = chain_dir / "S0_original.txt"
            if not s0_html_bak.exists() and s0_html_path.exists():
                s0_html_path.rename(s0_html_bak)
            if not s0_txt_bak.exists() and s0_txt_path.exists():
                s0_txt_path.rename(s0_txt_bak)

            # Download the correct S0
            content = download_document(correct_s0["exhibit_url"], client)
            text = html_to_text(content)
            html_hash = sha256(content)
            text_hash = sha256(text.encode("utf-8"))

            s0_html_path.write_bytes(content)
            s0_txt_path.write_text(text, encoding="utf-8")

            # Update the chain's S0 document entry
            old_s0 = [d for d in chain["documents"] if d["role"] == "S0"][0]
            new_s0 = {
                "role": "S0",
                "accession": correct_s0["accession"],
                "file_date": correct_s0["file_date"],
                "exhibit_type": correct_s0["exhibit_type"],
                "exhibit_description": correct_s0["exhibit_description"],
                "document_url": correct_s0["exhibit_url"],
                "html_path": str(s0_html_path),
                "text_path": str(s0_txt_path),
                "html_sha256": html_hash,
                "text_sha256": text_hash,
                "html_bytes": len(content),
                "text_chars": len(text),
                "correction_applied": True,
                "original_s0_accession": old_s0["accession"],
                "original_s0_file_date": old_s0["file_date"],
                "original_s0_exhibit_description": old_s0["exhibit_description"],
                "cross_ref_ca_date": ca_date,
                "cross_ref_source": ca_date_source,
            }

            chain["documents"] = [
                new_s0 if d["role"] == "S0" else d
                for d in chain["documents"]
            ]
            chain["s0_accession"] = correct_s0["accession"]
            chain["s0_file_date"] = correct_s0["file_date"]
            chain["s0_correction_applied"] = True

            corrected_chains.append(chain)
            corrections.append({
                "chain_id": cid,
                "action": "CORRECTED",
                "ca_date": ca_date,
                "ca_date_source": ca_date_source,
                "old_s0_accession": old_s0["accession"],
                "old_s0_file_date": old_s0["file_date"],
                "old_s0_exhibit_description": old_s0["exhibit_description"],
                "new_s0_accession": correct_s0["accession"],
                "new_s0_file_date": correct_s0["file_date"],
                "new_s0_exhibit_type": correct_s0["exhibit_type"],
                "new_s0_exhibit_description": correct_s0["exhibit_description"],
                "new_s0_text_chars": correct_s0["text_chars"],
                "new_s0_html_sha256": html_hash,
                "new_s0_text_sha256": text_hash,
                "mentions_cross_ref_date": correct_s0["mentions_cross_ref_date"],
            })

    # Write corrected manifest
    corrected_manifest = dict(manifest)
    corrected_manifest["chains"] = corrected_chains
    corrected_manifest["s0_correction_applied_at"] = datetime.now(UTC).isoformat()
    corrected_manifest["s0_correction_count"] = sum(
        1 for c in corrections if c["action"] == "CORRECTED"
    )
    CORRECTED_MANIFEST_PATH.write_text(
        json.dumps(corrected_manifest, indent=2), encoding="utf-8"
    )

    # Write audit output
    AUDIT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "study": "step26b_corrected_s0_selection",
        "run_at": datetime.now(UTC).isoformat(),
        "chains_corrected": len([c for c in corrections if c["action"] == "CORRECTED"]),
        "chains_unavailable": len([c for c in corrections if c["action"] == "S0_UNAVAILABLE"]),
        "chains_no_cross_ref": len([c for c in corrections if c["action"] == "NO_CROSS_REF_DATE"]),
        "corrections": corrections,
    }
    AUDIT_OUTPUT_PATH.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"Corrections: {audit['chains_corrected']} corrected, "
          f"{audit['chains_unavailable']} unavailable, "
          f"{audit['chains_no_cross_ref']} no cross-ref")
    print(f"Corrected manifest: {CORRECTED_MANIFEST_PATH}")
    print(f"Audit output: {AUDIT_OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
