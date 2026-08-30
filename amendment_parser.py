"""Upsilon amendment parser — v0.3

v0.3 adds structure-aware document segmentation, composite ground-truth
detection, bounded instruction extraction, and tightened waiver regexes.

Key changes from v0.2:
- Document segmentation divides a filing into AMENDMENT_BODY, SIGNATURES,
  COMPOSITE_AGREEMENT, and OTHER segments before instruction extraction.
- Instructions are extracted ONLY from the amendment body, eliminating
  false positives from the composite agreement body.
- Composite ground-truth detection records Annex A as a CompositeTarget
  (a ground-truth document), NOT as an amendment instruction. This
  prevents metrics from accidentally counting "we found the composite"
  as "we found an amendment instruction."
- Waiver regex requires imperative amendment language ("is hereby waived")
  and excludes cross-reference contexts ("waived in accordance with").
- Restatement spans are bounded to a 500-char context window.

Architecture:
    AMENDMENT BODY → AmendmentInstruction[]
    ANNEX A / COMPOSITE → CompositeTarget (ground truth)

The v0.2 `parse()` function is preserved for backward compatibility and
regression comparison. The new `parse_v03()` function returns a richer
result with segments, composite target, and instructions.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

# ---------------------------------------------------------------------------
# v0.2 regexes (preserved for backward compatibility)
# ---------------------------------------------------------------------------

REPLACE = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+).*?'
    r'(?:deleting|delete)\s+[\u201c"](?P<old>[^\u201c"]+)[\u201d"].*?'
    r'(?:replacing\s+(?:it|the same)\s+with|replace(?:d)?\s+with)\s+[\u201c"](?P<new>[^\u201c"]+)[\u201d"]',
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

# ---------------------------------------------------------------------------
# v0.3 regexes — tightened and bounded
# ---------------------------------------------------------------------------

# Bounded replace: limit the gap between section and delete/replace to 200 chars
REPLACE_V03 = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
    r'(?:deleting|delete)\s+[\u201c"](?P<old>[^\u201c"]+)[\u201d"].*?'
    r'(?:replacing\s+(?:it|the same)\s+with|replace(?:d)?\s+with)\s+[\u201c"](?P<new>[^\u201c"]+)[\u201d"]',
    re.I | re.S,
)

# Bounded delete: limit gap to 200 chars
DELETE_V03 = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
    r'(?:is hereby )?(?:deleted|removed)\s+in\s+its\s+entirety',
    re.I | re.S,
)

# Bounded restate: limit gap to 200 chars
RESTATE_V03 = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
    r'(?:is hereby )?amended\s+and\s+restated\s+in\s+its\s+entirety',
    re.I | re.S,
)

# Tightened waiver: require imperative amendment language.
# Must match "is hereby waived" or "is waived" as an instruction, NOT
# "waived in accordance with" or "has been waived" (cross-reference / notice).
WAIVER_V03 = re.compile(
    r'(?:compliance\s+with\s+|the\s+requirement\s+(?:contained\s+in\s+|of\s+))?'
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+)\s*'
    r'(?:is\s+hereby\s+waived|is\s+waived)',
    re.I,
)

# Bounded add: limit gap to 200 chars
ADD_V03 = re.compile(
    r'(?P<section>Section\s+[A-Za-z0-9.\-()]+)[^\n]{0,200}?'
    r'(?:is hereby )?amended\s+by\s+adding',
    re.I | re.S,
)

# Composite restatement: detects the "Composite Credit Agreement" format
# where the entire credit agreement is amended via an Annex A redline.
COMPOSITE_RESTATEMENT_RX = re.compile(
    r'(?:The\s+Credit\s+Agreement\s+is\s+hereby\s+amended\s+to\s+'
    r'delete\s+(?:the\s+)?(?:bold,?\s+)?(?:stricken|strikethrough)\s+text'
    r'.*?'
    r'(?:attached|annexed)\s+(?:hereto\s+)?as\s+Annex\s+(?P<annex>[A-Z]))',
    re.I | re.S,
)

# Also match the "Composite Credit Agreement" named pattern
COMPOSITE_NAMED_RX = re.compile(
    r'(?:Composite\s+Credit\s+Agreement\s*[\.\)].*?'
    r'(?:attached|annexed)\s+(?:hereto\s+)?as\s+Annex\s+(?P<annex>[A-Z]))',
    re.I | re.S,
)

# ---------------------------------------------------------------------------
# Document segmentation
# ---------------------------------------------------------------------------

# Markers for finding the end of the amendment body
SIGNATURE_PAGES_FOLLOW = re.compile(
    r'\[?signature\s+pages?\s+follow\]?', re.I
)
IN_WITNESS_WHEREOF = re.compile(r'IN\s+WITNESS\s+WHEREOF', re.I)

# Markers for finding the start of Annex A / composite agreement
ANNEX_A_HEADER = re.compile(
    r'ANNEX\s+A\s*\n+\s*(?:AMENDED\s+AND\s+RESTATED\s+)?CREDIT\s+AGREEMENT',
    re.I,
)
ANNEX_A_COMPOSITE = re.compile(
    r'ANNEX\s+A\s*\n+\s*Composite\s+Amended\s+and\s+Restated\s+Credit\s+Agreement',
    re.I,
)

# Marker for the start of the amendment instruction section
NOW_THEREFORE = re.compile(r'NOW,?\s+THEREFORE', re.I)


def segment_document(text: str) -> dict:
    """Divide a filing into structural segments.

    Returns a dict with:
        amendment_body: {start, end} — the section containing amendment
            instructions (from NOW, THEREFORE to signatures)
        signatures: {start, end} — signature pages and schedules
        composite_agreement: {start, end} or None — the Annex A composite
        other: {start, end} — header, recitals, WHEREAS clauses
    """
    total = len(text)

    # Find amendment body start (NOW, THEREFORE)
    now_match = NOW_THEREFORE.search(text)
    body_start = now_match.start() if now_match else 0

    # Find amendment body end (first [SIGNATURE PAGES FOLLOW] or
    # IN WITNESS WHEREOF after the body start)
    sig_match = SIGNATURE_PAGES_FOLLOW.search(text, body_start)
    witness_match = IN_WITNESS_WHEREOF.search(text, body_start)

    # Use whichever comes first
    body_end_candidates = [p for p in [sig_match, witness_match] if p]
    if body_end_candidates:
        body_end = min(m.start() for m in body_end_candidates)
    else:
        body_end = total

    # Find composite agreement start (ANNEX A ... CREDIT AGREEMENT)
    annex_match = ANNEX_A_HEADER.search(text, body_end)
    annex_composite_match = ANNEX_A_COMPOSITE.search(text, body_end)
    annex_candidates = [m for m in [annex_match, annex_composite_match] if m]

    if annex_candidates:
        comp_start = min(m.start() for m in annex_candidates)
        comp_end = total
    else:
        # Fallback: look for "ANNEX A" anywhere after body_end
        annex_fallback = re.search(r'ANNEX\s+A\b', text[body_end:], re.I)
        if annex_fallback:
            comp_start = body_end + annex_fallback.start()
            comp_end = total
        else:
            comp_start = None
            comp_end = None

    # Assemble segments
    segments = {
        "other": {"start": 0, "end": body_start},
        "amendment_body": {"start": body_start, "end": body_end},
        "signatures": {"start": body_end, "end": comp_start if comp_start else total},
        "composite_agreement": (
            {"start": comp_start, "end": comp_end}
            if comp_start is not None
            else None
        ),
    }
    return segments


# ---------------------------------------------------------------------------
# Composite ground-truth detection
# ---------------------------------------------------------------------------

def detect_composite(text: str, segments: dict) -> dict | None:
    """Detect whether the filing contains a composite/conformed agreement
    as a ground-truth target.

    This is NOT an amendment instruction. The composite agreement is the
    authoritative post-amendment state of the credit agreement. The parser
    detects its presence and location; downstream comparison uses it as
    ground truth.

    Returns a CompositeTarget-shaped dict with:
        annex: "A" (or other letter)
        start_offset: start of the composite agreement
        end_offset: end of the composite agreement
        source_format: "html_redline"
    or None if no composite is found.
    """
    comp = segments.get("composite_agreement")
    if comp is None:
        return None

    # Verify it's actually a composite/restated agreement
    comp_text = text[comp["start"]:comp["end"]]

    # Check for composite/restated language
    is_composite = bool(
        re.search(r'(?:AMENDED\s+AND\s+RESTATED|Composite)', comp_text[:500], re.I)
    )

    if not is_composite:
        return None

    # Determine annex letter
    annex_match = re.search(r'ANNEX\s+([A-Z])', text[comp["start"]:comp["start"]+50], re.I)
    annex = annex_match.group(1).upper() if annex_match else "A"

    return {
        "annex": annex,
        "start_offset": comp["start"],
        "end_offset": comp["end"],
        "source_format": "html_redline",
    }


# ---------------------------------------------------------------------------
# v0.3 instruction extraction
# ---------------------------------------------------------------------------

# Maximum context window for source_text in instructions
MAX_CONTEXT = 500


def nearby_v03(text: str, start: int, end: int, radius: int = MAX_CONTEXT) -> str:
    """Bounded context extraction — never more than 2*radius chars."""
    return text[max(0, start - radius):min(len(text), end + radius)].strip()


def _extract_instructions(text: str, body_start: int, body_end: int) -> list[dict]:
    """Extract instructions from the amendment body only, using v0.3
    tightened regexes."""
    body_text = text[body_start:body_end]

    hits = []
    specs = [
        ("REPLACE_TEXT", REPLACE_V03),
        ("DELETE_COMMITMENT", DELETE_V03),
        ("RESTATE_SECTION", RESTATE_V03),
        ("WAIVE_TEMPORARILY", WAIVER_V03),
        ("ADD_COMMITMENT", ADD_V03),
    ]
    seen = set()
    for typ, rx in specs:
        for m in rx.finditer(body_text):
            key = (m.start(), m.end(), typ)
            if key in seen:
                continue
            seen.add(key)
            # Convert body-relative offsets to document-absolute offsets
            abs_start = body_start + m.start()
            abs_end = body_start + m.end()
            row = {
                "instruction_type": typ,
                "target_section_ref": m.groupdict().get("section"),
                "target_key": None,
                "source_start": abs_start,
                "source_end": abs_end,
                "source_text": nearby_v03(text, abs_start, abs_end),
                "old_value": m.groupdict().get("old"),
                "new_value": m.groupdict().get("new"),
                "parser": "deterministic_baseline_v0.3",
                "confidence": 1.0,
            }
            hits.append(row)
    hits.sort(key=lambda x: x["source_start"])

    for i, h in enumerate(hits, 1):
        h["instruction_order"] = i
    return hits


def parse_v03(text: str) -> dict:
    """Parse a filing with v0.3 structure-aware segmentation.

    Returns:
        {
            "instructions": [...],
            "segments": {...},
            "composite_ground_truth": {...} | None,
            "parser": "deterministic_baseline_v0.3",
        }
    """
    segments = segment_document(text)
    composite = detect_composite(text, segments)

    body = segments["amendment_body"]
    instructions = _extract_instructions(text, body["start"], body["end"])

    return {
        "instructions": instructions,
        "segments": segments,
        "composite_target": composite,
        "parser": "deterministic_baseline_v0.3",
    }


# ---------------------------------------------------------------------------
# v0.2 backward-compatible parse (preserved for regression comparison)
# ---------------------------------------------------------------------------

def nearby(text: str, start: int, end: int, radius: int = 450) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)].strip()


def parse(text: str) -> list[dict]:
    """v0.2 backward-compatible parse. Runs regexes over the entire document
    without segmentation. Preserved for regression comparison."""
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Upsilon amendment parser")
    ap.add_argument("text_file", help="Path to the source text file")
    ap.add_argument("--out", help="Output JSON path (default: <input>.instructions.json)")
    ap.add_argument("--v2", action="store_true", help="Use v0.2 parser (no segmentation)")
    args = ap.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8", errors="ignore")

    if args.v2:
        result = parse(text)
        out = Path(args.out) if args.out else Path(args.text_file).with_suffix(".instructions.json")
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"instructions": len(result), "parser": "v0.2", "out": str(out)}, indent=2))
    else:
        result = parse_v03(text)
        out = Path(args.out) if args.out else Path(args.text_file).with_suffix(".instructions.json")
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        comp = result["composite_target"]
        print(json.dumps({
            "instructions": len(result["instructions"]),
            "parser": "v0.3",
            "composite_target": comp if comp else None,
            "segments": {
                k: v if v else None
                for k, v in result["segments"].items()
            },
            "out": str(out),
        }, indent=2))


if __name__ == "__main__":
    main()
