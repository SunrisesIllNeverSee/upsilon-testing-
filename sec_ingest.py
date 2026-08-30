from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

SEC_DATA = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
CREDIT_TERMS = re.compile(
    r"\b(credit agreement|loan agreement|revolving credit|term loan|credit facility|"
    r"amendment.*credit|amendment.*loan|amended and restated.*credit|waiver.*credit)\b",
    re.I,
)

def ua() -> str:
    value = os.getenv("SEC_USER_AGENT", "").strip()
    if not value:
        raise SystemExit(
            "Set SEC_USER_AGENT, e.g. 'Ello Cello LLC research@yourdomain.com'. "
            "SEC asks automated users to identify themselves."
        )
    return value

class SecClient:
    def __init__(self):
        self.delay = float(os.getenv("SEC_REQUEST_DELAY_SECONDS", "0.20"))
        self.client = httpx.Client(
            headers={
                "User-Agent": ua(),
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=45.0,
            follow_redirects=True,
        )

    def get(self, url: str) -> httpx.Response:
        r = self.client.get(url)
        r.raise_for_status()
        time.sleep(self.delay)
        return r

def cik10(cik: str) -> str:
    return str(int(cik)).zfill(10)

def cik_plain(cik: str) -> str:
    return str(int(cik))

def accession_plain(accession: str) -> str:
    return accession.replace("-", "")

def filing_index_url(cik: str, accession: str) -> str:
    return f"{SEC_ARCHIVES}/{cik_plain(cik)}/{accession_plain(accession)}/{accession}-index.html"

def filing_doc_base(cik: str, accession: str) -> str:
    return f"{SEC_ARCHIVES}/{cik_plain(cik)}/{accession_plain(accession)}/"

def submission_rows(payload: dict):
    recent = payload.get("filings", {}).get("recent", {})
    if not recent:
        return
    cols = list(recent.keys())
    n = len(recent.get("accessionNumber", []))
    for i in range(n):
        yield {c: recent[c][i] if i < len(recent[c]) else None for c in cols}

def discover_filing_exhibits(client: SecClient, cik: str, accession: str) -> list[dict]:
    index_url = filing_index_url(cik, accession)
    html = client.get(index_url).text
    soup = BeautifulSoup(html, "html.parser")
    docs = []
    for tr in soup.select("table.tableFile tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        desc = tds[1].get_text(" ", strip=True)
        link = tds[2].find("a")
        doc_name = link.get_text(" ", strip=True) if link else ""
        doc_type = tds[3].get_text(" ", strip=True)
        if not link:
            continue
        url = urljoin(filing_doc_base(cik, accession), link.get("href", ""))
        docs.append({
            "description": desc,
            "document": doc_name,
            "type": doc_type,
            "url": url,
            "candidate_credit_document": bool(
                doc_type.upper().startswith("EX-10") and
                (CREDIT_TERMS.search(desc or "") or CREDIT_TERMS.search(doc_name or ""))
            ),
        })
    return docs

def html_to_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )

def download_candidate(client: SecClient, row: dict, out_dir: Path) -> dict:
    r = client.get(row["url"])
    raw = r.content
    sha = hashlib.sha256(raw).hexdigest()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", row["document"] or sha[:16])
    source_path = out_dir / safe
    source_path.write_bytes(raw)
    text_path = out_dir / f"{safe}.txt"
    text_path.write_text(html_to_text(raw), encoding="utf-8")
    return {
        **row,
        "sha256": sha,
        "source_path": str(source_path),
        "text_path": str(text_path),
        "bytes": len(raw),
    }

def discover_company(cik: str, start_year: int, end_year: int, out_root: Path):
    client = SecClient()
    submissions_url = f"{SEC_DATA}/submissions/CIK{cik10(cik)}.json"
    payload = client.get(submissions_url).json()

    company_dir = out_root / cik10(cik)
    company_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    allowed_forms = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A"}

    for filing in submission_rows(payload):
        form = filing.get("form")
        filing_date = filing.get("filingDate") or ""
        if form not in allowed_forms or len(filing_date) < 4:
            continue
        year = int(filing_date[:4])
        if year < start_year or year > end_year:
            continue

        accession = filing["accessionNumber"]
        try:
            docs = discover_filing_exhibits(client, cik, accession)
        except Exception as exc:
            manifest.append({
                "cik": cik10(cik), "accession": accession, "filing_date": filing_date,
                "form": form, "status": "index_error", "error": str(exc)
            })
            continue

        candidates = [d for d in docs if d["candidate_credit_document"]]
        for doc in candidates:
            filing_dir = company_dir / accession_plain(accession)
            filing_dir.mkdir(parents=True, exist_ok=True)
            try:
                saved = download_candidate(client, doc, filing_dir)
                manifest.append({
                    "cik": cik10(cik),
                    "company": payload.get("name"),
                    "accession": accession,
                    "filing_date": filing_date,
                    "form": form,
                    "status": "downloaded",
                    **saved,
                })
            except Exception as exc:
                manifest.append({
                    "cik": cik10(cik), "accession": accession, "filing_date": filing_date,
                    "form": form, "status": "download_error", "url": doc["url"],
                    "error": str(exc)
                })

    out = company_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

def load_issuers(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("cik"):
                yield row

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("company")
    one.add_argument("--cik", required=True)
    one.add_argument("--start-year", type=int, default=2015)
    one.add_argument("--end-year", type=int, default=2025)
    one.add_argument("--out", default="data/raw")

    batch = sub.add_parser("batch")
    batch.add_argument("--issuers", default="issuers.csv")
    batch.add_argument("--start-year", type=int, default=2015)
    batch.add_argument("--end-year", type=int, default=2025)
    batch.add_argument("--out", default="data/raw")

    args = ap.parse_args()
    out = Path(args.out)

    if args.cmd == "company":
        rows = discover_company(args.cik, args.start_year, args.end_year, out)
        print(json.dumps({"cik": cik10(args.cik), "candidate_documents": len(rows)}, indent=2))
        return

    totals = []
    for issuer in load_issuers(Path(args.issuers)):
        cik = issuer["cik"]
        try:
            rows = discover_company(cik, args.start_year, args.end_year, out)
            totals.append({"cik": cik10(cik), "documents": len(rows), "status": "ok"})
        except Exception as exc:
            totals.append({"cik": cik10(cik), "documents": 0, "status": "error", "error": str(exc)})
    Path("data").mkdir(exist_ok=True)
    Path("data/batch_summary.json").write_text(json.dumps(totals, indent=2), encoding="utf-8")
    print(json.dumps(totals, indent=2))

if __name__ == "__main__":
    main()
