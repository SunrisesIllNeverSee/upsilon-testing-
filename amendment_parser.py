"""Upsilon amendment parser — v0.4

v0.4 broadens the instruction grammar based on the 25-document
parser-development sample census (v0.3.1 baseline).

Key changes from v0.3:
- Generalized reference targets: Section, Article, Schedule, Exhibit
  (not just Section). Lowercase structural terms (Definition, Clause,
  Paragraph, Subsection) are NOT included as targets because they appear
  as common nouns in amendment text and cause false positives. In the
  current 25-document development sample, restricting primary targets to
  Section/Article/Schedule/Exhibit reduced false positives; finer-grained
  targets remain future work.
- Broadened replace pattern: deleting...replacing, deleting...inserting,
  deleting...substituting (not just deleting...replacing).
- New "amended to read" pattern: "Section X is amended to read as follows".
- "amended as follows" is a STRUCTURAL/CONTAINER MARKER, not an instruction.
  It does NOT emit RESTATE_SECTION. Child operations beneath it are detected
  by the other regexes (ADD_V04, DELETE_BY_V04, REPLACE_V04, etc.).
- New "deleted from Section" pattern: "is hereby deleted from Section X".
- Broadened "amended by": adding, deleting, inserting, modifying (not just
  adding). "amended by deleting" maps to DELETE_COMMITMENT, not ADD_COMMITMENT.
- Overlapping match deduplication: when REPLACE_V04 and ADD_V04 match the
  same text span (e.g., "amended by deleting...inserting"), only the
  more specific match is kept.

v0.3 changes (preserved):
- Document segmentation divides a filing into AMENDMENT_BODY, SIGNATURES,
  COMPOSITE_AGREEMENT, and OTHER segments before instruction extraction.
- Instructions are extracted ONLY from the amendment body, eliminating
  false positives from the composite agreement body.
- Composite ground-truth detection records Annex A as a CompositeTarget
  (a ground-truth document), NOT as an amendment instruction.
- Waiver regex requires imperative amendment language ("is hereby waived")
  and excludes cross-reference contexts ("waived in accordance with").
- Restatement spans are bounded to a 200-char context window.

Architecture:
    AMENDMENT BODY → AmendmentInstruction[]
    ANNEX A / COMPOSITE → CompositeTarget (ground truth)

The v0.2 `parse()` function is preserved for backward compatibility and
regression comparison. `parse_v03()` returns the v0.3.1 baseline result
(using v0.3 regexes). `parse_v04()` returns the v0.4 result (using
broadened v0.4 regexes). Both share the same segmentation and composite
detection logic.
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
# v0.3 regexes — tightened and bounded (preserved for backward compat)
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

# ---------------------------------------------------------------------------
# v0.4 regexes — generalized targets + broadened transformations
# ---------------------------------------------------------------------------

# Generalized reference target: matches Section, Article, Schedule, Exhibit
# (not just Section). These are always capitalized in legal documents when
# used as section references.
# Definition, Clause, Paragraph, Subsection are intentionally excluded —
# they appear as common nouns in amendment text (e.g., "the definition of X",
# "clause (a)(v)") and cause false positives when included as targets.
# In the current 25-document development sample, restricting primary targets
# to Section/Article/Schedule/Exhibit reduced false positives; finer-grained
# targets remain future work.
_TARGET = (
    r'(?P<section>'
    r'(?:Section|Article|Schedule|Exhibit)'
    r'\s+[A-Za-z0-9.\-()]+'
    r')'
)

# v0.4 REPLACE: broadened to handle deleting...inserting, deleting...substituting,
# and deleting...in lieu thereof (not just deleting...replacing).
# Also handles "deleting the single instance of X and inserting Y in lieu thereof".
# Requires "amended by" (or "modified and amended by") between target and "deleting"
# to ensure the target is actually being amended (not a cross-reference followed by
# "deleting" in a different instruction).
# Gap between target and deleting is bounded to 200 chars.
# Gap between deleting and inserting/replacing is bounded to 500 chars
# (some definitions are long).
REPLACE_V04 = re.compile(
    _TARGET + r'.{0,200}?'
    r'(?:is\s+(?:hereby\s+)?(?:further\s+)?(?:modified\s+and\s+)?amended\s+by\s+)'
    r'(?:\(\w+\)\s+)*'
    r'(?:deleting|delete)\s+'
    r'(?:the\s+(?:single\s+instance\s+of\s+)?(?:definition\s+(?:of\s+)?[\u201c"]?)?)?'
    r'[\u201c"]?'
    r'(?P<old>[^\u201c"]{1,200})[\u201d"]?'
    r'.{0,500}?'
    r'(?:replacing\s+(?:it|the same|each)?\s*(?:with|by)|'
    r'replace(?:d)?\s+with|'
    r'inserting\s+(?:the\s+following(?:\s+new)?\s+)?|'
    r'substituting\s+in\s+its\s+place\s+(?:the\s+following(?:\s+new)?\s+)?)'
    r'[\u201c"]?(?P<new>[^\u201c"]{1,200})[\u201d"]?',
    re.I | re.S,
)

# v0.4 RESTATE: same as v0.3 but with generalized target
RESTATE_V04 = re.compile(
    _TARGET + r'.{0,200}?'
    r'(?:is hereby )?amended\s+and\s+restated\s+in\s+its\s+entirety',
    re.I | re.S,
)

# v0.4 DELETE: same as v0.3 but with generalized target
DELETE_V04 = re.compile(
    _TARGET + r'.{0,200}?'
    r'(?:is hereby )?(?:deleted|removed)\s+in\s+its\s+entirety',
    re.I | re.S,
)

# v0.4 ADD: "amended by adding" or "amended by inserting".
# Emits generic ADD (not ADD_COMMITMENT). Commitment-level resolution
# (ADD → ADD_COMMITMENT) happens downstream, not in the parser.
# "amended by modifying" is handled by MODIFIED_BY_V04 (emits UNRESOLVED).
# "amended by deleting" is handled by DELETE_BY_V04 (emits DELETE).
# Requires "of the Credit Agreement" (or similar) after the target to ensure
# the target is a Credit Agreement section, not the amendment's own section heading.
# Allows optional "[...]" or "(...)" descriptions after the section number.
# Allows optional "(i) " or "(ii) " etc. between "by" and the verb.
ADD_V04 = re.compile(
    _TARGET + r'(?:\s*\[[^\]]*\])?(?:\s*\([^)]*\))?'
    r'\s+of\s+the\s+(?:Credit|Note\s+Purchase|Loan)\s+Agreement'
    r'.{0,60}?'
    r'(?:is hereby )?(?:further\s+)?(?:modified\s+and\s+)?amended\s+by\s+'
    r'(?:\(\w+\)\s+)*'
    r'(?:adding|inserting)',
    re.I | re.S,
)

# v0.4 DELETE_BY: "amended by deleting" — emits generic DELETE.
# Commitment-level resolution (DELETE → DELETE_COMMITMENT) happens downstream.
DELETE_BY_V04 = re.compile(
    _TARGET + r'(?:\s*\[[^\]]*\])?(?:\s*\([^)]*\))?'
    r'\s+of\s+the\s+(?:Credit|Note\s+Purchase|Loan)\s+Agreement'
    r'.{0,60}?'
    r'(?:is hereby )?(?:further\s+)?(?:modified\s+and\s+)?amended\s+by\s+'
    r'(?:\(\w+\)\s+)*'
    r'deleting',
    re.I | re.S,
)

# v0.4 MODIFIED_BY: "amended by modifying" — emits UNRESOLVED.
# "modifying" is too ambiguous to classify as ADD or DELETE; the parser
# marks it UNRESOLVED for downstream validation.
MODIFIED_BY_V04 = re.compile(
    _TARGET + r'(?:\s*\[[^\]]*\])?(?:\s*\([^)]*\))?'
    r'\s+of\s+the\s+(?:Credit|Note\s+Purchase|Loan)\s+Agreement'
    r'.{0,60}?'
    r'(?:is hereby )?(?:further\s+)?(?:modified\s+and\s+)?amended\s+by\s+'
    r'(?:\(\w+\)\s+)*'
    r'modifying',
    re.I | re.S,
)

# v0.4 WAIVER: same as v0.3 but with generalized target
WAIVER_V04 = re.compile(
    r'(?:compliance\s+with\s+|the\s+requirement\s+(?:contained\s+in\s+|of\s+))?'
    + _TARGET + r'\s*'
    r'(?:is\s+hereby\s+waived|is\s+waived)',
    re.I,
)

# v0.4 AMENDED_TO_READ: "Section X is amended to read as follows"
# This is a restatement pattern — the section is being replaced entirely.
AMENDED_TO_READ_V04 = re.compile(
    _TARGET + r'.{0,200}?'
    r'(?:is\s+(?:hereby\s+)?amended\s+to\s+read\s+as\s+follows)',
    re.I | re.S,
)

# v0.4 AMENDED_AS_FOLLOWS: "Section X of the Credit Agreement is hereby amended as follows"
# This is a STRUCTURAL/CONTAINER MARKER, not an instruction. It signals that
# amendment instructions follow, typically in lettered subsections (a), (b), (c)...
# The parser does NOT emit a RESTATE_SECTION for this pattern. Child operations
# beneath it (detected by ADD_V04, DELETE_BY_V04, REPLACE_V04, DELETED_FROM_V04,
# AMENDED_TO_READ_V04, etc.) are the actual instructions.
# Requires "of the Credit Agreement" (or similar) after the target to ensure
# the target is a Credit Agreement section, not the amendment's own section number.
# Without this, "Section 2 hereof, the Credit Agreement is hereby amended as follows"
# would match "Section 2" as the target, which is the amendment's section heading.
AMENDED_AS_FOLLOWS_V04 = re.compile(
    _TARGET + r'(?:\s*\[[^\]]*\])?'
    r'\s+of\s+the\s+(?:Credit|Note\s+Purchase|Loan)\s+Agreement'
    r'.{0,200}?'
    r'is\s+(?:hereby\s+)?amended\s+as\s+follows',
    re.I | re.S,
)

# v0.4 DELETED_FROM_SECTION: "is hereby deleted from Section X in its entirety"
# This is a delete pattern where the target follows the verb.
DELETED_FROM_V04 = re.compile(
    r'is\s+hereby\s+deleted\s+from\s+'
    + _TARGET
    + r'(?:\s+in\s+its\s+entirety)?',
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


def _extract_instructions_v03(text: str, body_start: int, body_end: int) -> list[dict]:
    """Extract instructions from the amendment body only, using v0.3
    tightened regexes (Section-only targets). This is the v0.3.1 baseline."""
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


def _extract_instructions_v04(text: str, body_start: int, body_end: int) -> list[dict]:
    """Extract instructions from the amendment body only, using v0.4
    broadened regexes with generalized targets and deduplication."""
    body_text = text[body_start:body_end]

    raw_hits = []
    # v0.4.1 specs: parser emits generic transformation types.
    # ADD/DELETE are generic legal operations. ADD_COMMITMENT/DELETE_COMMITMENT
    # are only assigned after commitment-level resolution (downstream).
    # "amended by modifying" → UNRESOLVED (too ambiguous to classify).
    # AMENDED_TO_READ is mapped to RESTATE_SECTION (section is replaced entirely).
    # AMENDED_AS_FOLLOWS is a STRUCTURAL/CONTAINER MARKER — it does NOT emit an
    # instruction. Child operations beneath it are detected by the other regexes.
    specs = [
        ("REPLACE_TEXT", REPLACE_V04),
        ("DELETE", DELETE_V04),
        ("RESTATE_SECTION", RESTATE_V04),
        ("WAIVE_TEMPORARILY", WAIVER_V04),
        ("ADD", ADD_V04),
        ("DELETE", DELETE_BY_V04),
        ("UNRESOLVED", MODIFIED_BY_V04),
        ("RESTATE_SECTION", AMENDED_TO_READ_V04),
        ("DELETE", DELETED_FROM_V04),
    ]
    for typ, rx in specs:
        for m in rx.finditer(body_text):
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
                "parser": "deterministic_baseline_v0.4.1",
                # No confidence assigned to raw deterministic hits.
                # Confidence is set by downstream semantic validation,
                # not by the regex match itself.
                "_span": (abs_start, abs_end),
            }
            raw_hits.append(row)

    # Deduplicate overlapping matches.
    # When two matches overlap (e.g., REPLACE_V04 and DELETE_BY_V04 both match
    # "amended by deleting...inserting"), prefer the match that captures more
    # information (has old/new values or a longer span that includes the
    # inserting/replacing part).
    # Priority: REPLACE_TEXT > ADD_COMMITMENT/DELETE_COMMITMENT > RESTATE_SECTION
    # This ensures that "amended by deleting...inserting" is classified as
    # REPLACE_TEXT (which captures old/new values), not DELETE.
    type_priority = {
        "REPLACE_TEXT": 0,
        "ADD": 1,
        "DELETE": 1,
        "RESTATE_SECTION": 2,
        "WAIVE_TEMPORARILY": 2,
        "UNRESOLVED": 3,
    }
    raw_hits.sort(key=lambda x: (
        x["source_start"],
        type_priority.get(x["instruction_type"], 9),
        -(x["source_end"] - x["source_start"]),
    ))
    deduped = []
    for hit in raw_hits:
        s, e = hit["_span"]
        overlaps = False
        for kept in deduped:
            ks, ke = kept["_span"]
            if s < ke and ks < e:
                overlaps = True
                break
        if not overlaps:
            deduped.append(hit)

    # Sort by source_start and assign order
    deduped.sort(key=lambda x: x["source_start"])
    for i, h in enumerate(deduped, 1):
        h["instruction_order"] = i
        del h["_span"]
    return deduped


def parse_v03(text: str) -> dict:
    """Parse a filing with v0.3 structure-aware segmentation (v0.3.1 baseline).

    Uses v0.3 tightened regexes (Section-only targets, bounded gaps).
    Preserved for v0.3.1 vs v0.4 comparison on the same dataset.

    Returns:
        {
            "instructions": [...],
            "segments": {...},
            "composite_target": {...} | None,
            "parser": "deterministic_baseline_v0.3",
        }
    """
    segments = segment_document(text)
    composite = detect_composite(text, segments)

    body = segments["amendment_body"]
    instructions = _extract_instructions_v03(text, body["start"], body["end"])

    return {
        "instructions": instructions,
        "segments": segments,
        "composite_target": composite,
        "parser": "deterministic_baseline_v0.3",
    }


def parse_v04(text: str) -> dict:
    """Parse a filing with v0.4.1 broadened grammar (generic ADD/DELETE,
    generalized targets, new patterns, deduplication).

    Uses v0.4.1 regexes (Section|Article|Schedule|Exhibit targets, broadened
    transformations, overlap deduplication). Emits generic ADD/DELETE instead
    of ADD_COMMITMENT/DELETE_COMMITMENT. Commitment-level resolution happens
    downstream. "amended by modifying" emits UNRESOLVED.

    Returns:
        {
            "instructions": [...],
            "segments": {...},
            "composite_target": {...} | None,
            "parser": "deterministic_baseline_v0.4.1",
        }
    """
    segments = segment_document(text)
    composite = detect_composite(text, segments)

    body = segments["amendment_body"]
    instructions = _extract_instructions_v04(text, body["start"], body["end"])

    return {
        "instructions": instructions,
        "segments": segments,
        "composite_target": composite,
        "parser": "deterministic_baseline_v0.4.1",
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
    ap.add_argument("--v3", action="store_true", help="Use v0.3 parser (v0.3.1 baseline)")
    args = ap.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8", errors="ignore")

    if args.v2:
        result = parse(text)
        out = Path(args.out) if args.out else Path(args.text_file).with_suffix(".instructions.json")
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"instructions": len(result), "parser": "v0.2", "out": str(out)}, indent=2))
    elif args.v3:
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
    else:
        result = parse_v04(text)
        out = Path(args.out) if args.out else Path(args.text_file).with_suffix(".instructions.json")
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        comp = result["composite_target"]
        print(json.dumps({
            "instructions": len(result["instructions"]),
            "parser": "v0.4",
            "composite_target": comp if comp else None,
            "segments": {
                k: v if v else None
                for k, v in result["segments"].items()
            },
            "out": str(out),
        }, indent=2))


if __name__ == "__main__":
    main()
