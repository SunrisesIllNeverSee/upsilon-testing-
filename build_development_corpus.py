"""Build the 25-issuer development corpus.

Searches EDGAR for 8-K filings containing "amendment to credit agreement",
selects 25 diverse issuers, finds EX-10 exhibits in each filing, downloads
the amendment documents, and records metadata for classification.

Usage:
    set -a && source .env && set +a
    python build_development_corpus.py
"""
from __future__ import annotations
import csv, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Upsilon Research test@example.com")
SEC_DELAY = float(os.getenv("SEC_REQUEST_DELAY_SECONDS", "0.15"))
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_API = "https://data.sec.gov/submissions/CIK{cik}.json"

OUTPUT_DIR = Path("data/development")
MANIFEST_JSON = Path("data/development/manifest.json")

SEARCH_QUERY = '"amendment to credit agreement"'
SEARCH_FORMS = "8-K"

# Search across multiple date ranges for diversity
DATE_RANGES = [
    ("2020-01-01", "2021-06-30"),
    ("2021-07-01", "2022-12-31"),
    ("2023-01-01", "2024-06-30"),
    ("2024-07-01", "2026-08-30"),
]

TARGET_COUNT = 25

# Smoke-case CIKs to exclude (already in data/smoke/)
SMOKE_CIKS = {"0001132105", "0001089063"}


# ---------------------------------------------------------------------------
# EDGAR search
# ---------------------------------------------------------------------------

def search_edgar(query: str, forms: str, start_date: str, end_date: str,
                 client: httpx.Client) -> list[dict]:
    """Search EDGAR full-text search API."""
    params = {
        "q": query,
        "forms": forms,
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
    }
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    resp = client.get(EDGAR_SEARCH, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        ciks = src.get("ciks", [])
        names = src.get("display_names", [])
        if not ciks:
            continue
        cik = ciks[0]  # Already 10-digit with leading zeros
        name = names[0] if names else ""
        # Clean up the display name (remove ticker/CIK suffix)
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
        results.append({
            "cik": cik,
            "entity_name": name,
            "form": src.get("form", ""),
            "file_date": src.get("file_date", ""),
            "accession": src.get("adsh", ""),
            "items": src.get("items", []),
            "file_type": src.get("file_type", ""),
        })
    return results


def get_filing_index(cik: str, accession: str,
                     client: httpx.Client) -> list[dict]:
    """Get the filing index page to find EX-10 exhibits.

    Fetches the <accession>-index.html page which has a tableFile table
    with columns: Seq, Description, Document (link), Type, Size.
    Parses each <tr> row individually to avoid cross-row matching.
    """
    acc_no_dashes = accession.replace("-", "")
    cik_int = str(int(cik))  # Remove leading zeros for URL
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dashes}/"
        f"{accession}-index.html"
    )
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = client.get(index_url, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    exhibits = []
    # Parse each table row individually
    # Each row: <td>seq</td><td>description</td><td><a href="...">filename</a></td><td>TYPE</td><td>size</td>
    for row_m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.I | re.S):
        row = row_m.group(1)
        # Extract all <td> cells in this row
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.I | re.S)
        if len(cells) < 4:
            continue
        # Cell 3 = Document (has the link), Cell 3 = Type
        # Actually: cells[0]=seq, cells[1]=desc, cells[2]=doc link, cells[3]=type
        type_cell = cells[3].strip()
        # Check if this row is an EX-10 exhibit
        type_match = re.search(r'(EX-10[\w.\-]*)', type_cell, re.I)
        if not type_match:
            continue
        doc_type = type_match.group(1).strip().upper()
        # Extract the link from cells[2]
        link_m = re.search(r'href="([^"]+)"', cells[2], re.I)
        if not link_m:
            continue
        doc_path = link_m.group(1).strip()
        # Extract filename from link text
        name_m = re.search(r'>([^<]+)</a>', cells[2], re.I)
        doc_name = name_m.group(1).strip() if name_m else ""
        # Extract description from cells[1]
        doc_desc = re.sub(r'<[^>]+>', '', cells[1]).strip()
        # Handle iXBRL links that use /ix?doc=/Archives/...
        if "/ix?doc=" in doc_path:
            doc_path = doc_path.split("/ix?doc=")[1]
        full_url = f"https://www.sec.gov{doc_path}" if doc_path.startswith("/") else doc_path
        exhibits.append({
            "type": doc_type,
            "description": doc_desc,
            "url": full_url,
            "filename": doc_name,
        })

    return exhibits


# ---------------------------------------------------------------------------
# Document download
# ---------------------------------------------------------------------------

def download_document(url: str, client: httpx.Client) -> bytes:
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = client.get(url, headers=headers, timeout=60, follow_redirects=True)
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
    import hashlib
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    if not SEC_USER_AGENT or "test@" in SEC_USER_AGENT:
        print("ERROR: SEC_USER_AGENT not configured. Set it in .env")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"SEC User-Agent: {SEC_USER_AGENT}")
    print(f"Target: {TARGET_COUNT} development issuers")
    print()

    # Phase 1: Search EDGAR across date ranges
    all_hits = []
    with httpx.Client() as client:
        for start, end in DATE_RANGES:
            print(f"Searching EDGAR: {start} to {end}...")
            hits = search_edgar(SEARCH_QUERY, SEARCH_FORMS, start, end, client)
            print(f"  Found {len(hits)} hits")
            all_hits.extend(hits)
            time.sleep(SEC_DELAY)

    # Deduplicate by CIK — one filing per issuer for diversity
    seen_ciks = set(SMOKE_CIKS)
    all_hits.sort(key=lambda h: (h["file_date"], h["cik"]))

    selected = []
    for hit in all_hits:
        cik = hit["cik"]
        if cik in seen_ciks:
            continue
        seen_ciks.add(cik)
        selected.append(hit)
        if len(selected) >= TARGET_COUNT:
            break

    print(f"\nSelected {len(selected)} unique issuers (excluding smoke cases)")
    print()

    if len(selected) < TARGET_COUNT:
        print(f"WARNING: Only found {len(selected)} issuers. Need {TARGET_COUNT}.")

    # Phase 2: Download documents
    manifest = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "sec_user_agent": SEC_USER_AGENT,
        "search_query": SEARCH_QUERY,
        "date_ranges": DATE_RANGES,
        "target_count": TARGET_COUNT,
        "smoke_ciks_excluded": sorted(SMOKE_CIKS),
        "documents": [],
    }

    with httpx.Client() as client:
        for i, hit in enumerate(selected, 1):
            cik = hit["cik"]
            accession = hit["accession"]
            issuer = hit["entity_name"]
            file_date = hit["file_date"]

            case_id = f"DEV-{i:03d}"
            case_dir = OUTPUT_DIR / case_id
            case_dir.mkdir(parents=True, exist_ok=True)

            print(f"[{i}/{len(selected)}] {case_id} {issuer[:45]:45s} CIK={cik} date={file_date}")

            # Get filing index to find EX-10 exhibits
            try:
                exhibits = get_filing_index(cik, accession, client)
                time.sleep(SEC_DELAY)
            except Exception as e:
                print(f"  ERROR getting filing index: {e}")
                continue

            if not exhibits:
                print(f"  No EX-10 exhibits found, skipping")
                continue

            # Prefer EX-10.1, then first EX-10
            ex = next((e for e in exhibits if e["type"] == "EX-10.1"), exhibits[0])
            url = ex["url"]

            try:
                content = download_document(url, client)
                time.sleep(SEC_DELAY)
            except Exception as e:
                print(f"  ERROR downloading: {e}")
                continue

            # Save raw HTML
            html_path = case_dir / "source.html"
            html_path.write_bytes(content)

            # Convert to text
            text = html_to_text(content)
            text_path = case_dir / "source.txt"
            text_path.write_text(text, encoding="utf-8")

            # Compute hashes
            html_hash = sha256(content)
            text_hash = sha256(text.encode("utf-8"))

            # Write metadata
            meta = {
                "case_id": case_id,
                "cik": cik,
                "issuer": issuer,
                "accession": accession,
                "filing_date": file_date,
                "exhibit_type": ex["type"],
                "exhibit_description": ex["description"],
                "document_url": url,
                "html_sha256": html_hash,
                "text_sha256": text_hash,
                "html_bytes": len(content),
                "text_chars": len(text),
            }
            meta_path = case_dir / "source_meta.json"
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            manifest["documents"].append(meta)
            print(f"  {ex['type']}: {len(content)} bytes, {len(text)} chars, SHA={html_hash[:12]}")

    # Write manifest
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest: {MANIFEST_JSON}")
    print(f"Downloaded: {len(manifest['documents'])} documents")


if __name__ == "__main__":
    main()
