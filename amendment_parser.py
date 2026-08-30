from __future__ import annotations
import argparse, json, re
from pathlib import Path

REPLACE = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:deleting|delete)\s+[“"](?P<old>[^”"]+)[”"].*?'
    r'(?:replacing\s+(?:it|the same)\s+with|replace(?:d)?\s+with)\s+[“"](?P<new>[^”"]+)[”"]',
    re.I | re.S,
)
DELETE_SECTION = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:is hereby )?(?:deleted|removed)\s+in\s+its\s+entirety',
    re.I | re.S,
)
RESTATE = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:is hereby )?amended\s+and\s+restated\s+in\s+its\s+entirety',
    re.I | re.S,
)
WAIVER = re.compile(
    r'(?:compliance\s+with\s+)?(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:is hereby )?waived',
    re.I | re.S,
)
ADD = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:is hereby )?amended\s+by\s+adding',
    re.I | re.S,
)

def nearby(text: str, start: int, end: int, radius: int = 450) -> str:
    return text[max(0,start-radius):min(len(text),end+radius)].strip()

def parse(text: str) -> list[dict]:
    hits = []
    specs = [
        ("REPLACE_TEXT", REPLACE),
        ("DELETE_COMMITMENT", DELETE_SECTION),
        ("RESTATE_SECTION", RESTATE),
        ("WAIVE_TEMPORARILY", WAIVER),
        ("ADD_COMMITMENT", ADD),
    ]
    seen = set()
    for typ, rx in specs:
        for m in rx.finditer(text):
            key = (m.start(), m.end(), typ)
            if key in seen:
                continue
            seen.add(key)
            row = {
                "instruction_type": typ,
                "target_section_ref": m.groupdict().get("section"),
                "target_key": None,
                "source_start": m.start(),
                "source_end": m.end(),
                "source_text": nearby(text, m.start(), m.end()),
                "old_value": m.groupdict().get("old"),
                "new_value": m.groupdict().get("new"),
                "parser": "deterministic_baseline_v0.2",
                "confidence": 1.0,
            }
            hits.append(row)
    hits.sort(key=lambda x: x["source_start"])
    for i, h in enumerate(hits, 1):
        h["instruction_order"] = i
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text_file")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = Path(args.text_file).read_text(encoding="utf-8", errors="ignore")
    result = parse(text)
    out = Path(args.out) if args.out else Path(args.text_file).with_suffix(".instructions.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"instructions": len(result), "out": str(out)}, indent=2))

if __name__ == "__main__":
    main()
