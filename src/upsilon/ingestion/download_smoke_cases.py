from __future__ import annotations
import csv, hashlib, os, time, json
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

def main():
    ua=os.getenv("SEC_USER_AGENT","").strip()
    if not ua:
        raise SystemExit("Set SEC_USER_AGENT in your environment first.")
    out=Path("data/smoke"); out.mkdir(parents=True,exist_ok=True)
    with open("smoke_cases.csv",newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    client=httpx.Client(headers={"User-Agent":ua,"Accept-Encoding":"gzip, deflate"},
                        timeout=60.0,follow_redirects=True)
    for row in rows:
        case=out/row["case_id"]; case.mkdir(exist_ok=True)
        r=client.get(row["document_url"]); r.raise_for_status()
        raw=r.content
        (case/"source.html").write_bytes(raw)
        soup=BeautifulSoup(raw,"html.parser")
        for tag in soup(["script","style"]): tag.decompose()
        text="\n".join(x.strip() for x in soup.get_text("\n").splitlines() if x.strip())
        (case/"source.txt").write_text(text,encoding="utf-8")
        sha=hashlib.sha256(raw).hexdigest()
        (case/"source_meta.json").write_text(json.dumps({**row,"sha256":sha,"bytes":len(raw)},indent=2),encoding="utf-8")
        print(row["case_id"],row["issuer"],sha[:12],len(raw))
        time.sleep(0.25)

if __name__=="__main__":
    main()
