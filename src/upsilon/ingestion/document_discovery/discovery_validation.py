"""Discovery validation for acquired S0 and GT documents.

V02-005 / V02-006: Validates that documents acquired by the acquisition
pipeline are the correct type (full credit agreements, not exhibit
covers or amendment documents). This does NOT improve extraction logic
— it correctly attributes discovery failures and enables re-acquisition.

The acquisition pipeline (acquire_chain_study.py) selects EX-10 exhibits
from 8-K filings. Sometimes the wrong exhibit is selected:
  - S0_DISCOVERY_FAILURE: a short document, exhibit cover, or summary
    is acquired as S0 instead of the full credit agreement
  - GT_DISCOVERY_FAILURE: an amendment document is acquired as CMP
    instead of a composite/conformed/restated copy

This module provides validation functions that detect these cases so
the failure matrix can correctly attribute them as discovery failures
rather than extraction failures.

Usage:
    from upsilon.ingestion.document_discovery.discovery_validation import validate_s0_document, validate_gt_document
    s0_status = validate_s0_document("data/chain_study/STUDY-006/S0.txt")
    gt_status = validate_gt_document("data/chain_study/STUDY-016/CMP.txt")
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiscoveryValidationResult:
    """Result of validating an acquired document.

    Fields:
        is_valid: True if the document passes validation (is the correct
            type for its role).
        failure_cause: The failure cause if invalid, or "" if valid.
            One of: "S0_DISCOVERY_FAILURE", "GT_DISCOVERY_FAILURE", "".
        reason: Human-readable explanation of the validation result.
        text_length: Character count of the document text.
        checks: Dict of check name -> bool (passed/failed).
    """

    is_valid: bool
    failure_cause: str
    reason: str
    text_length: int
    checks: dict[str, bool]


# ---------------------------------------------------------------------------
# S0 discovery validation (V02-005)
# ---------------------------------------------------------------------------

# Minimum character count for a full credit agreement. Documents shorter
# than this are likely exhibit covers, summaries, or incorrectly acquired
# documents. The threshold is set conservatively at 15K chars (the same
# threshold used by build_failure_matrix.py).
S0_MIN_CHARS = 15000


def validate_s0_document(s0_path: str | Path) -> DiscoveryValidationResult:
    """Validate that an S0 document is a full credit agreement.

    V02-005: Checks that the acquired S0 document is:
      (a) >= 15K chars (not a short exhibit cover or summary)
      (b) contains "credit agreement" language
      (c) contains covenant-like content (ratio thresholds, dollar
          amounts with loan language, or covenant section headers)

    If validation fails, the chain should be flagged as
    S0_DISCOVERY_FAILURE at acquisition time, not misattributed to the
    extractor.

    Args:
        s0_path: path to the S0 document text file.

    Returns:
        DiscoveryValidationResult with is_valid=True if the document
        passes all checks, or is_valid=False with failure_cause=
        "S0_DISCOVERY_FAILURE" if any check fails.
    """
    p = Path(s0_path)
    if not p.exists():
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="S0_DISCOVERY_FAILURE",
            reason="S0.txt file missing",
            text_length=0,
            checks={"file_exists": False, "min_chars": False, "credit_agreement": False, "covenant_content": False},
        )

    text = p.read_text(encoding="utf-8", errors="ignore")
    chars = len(text)

    checks: dict[str, bool] = {
        "file_exists": True,
        "min_chars": chars >= S0_MIN_CHARS,
        "credit_agreement": bool(re.search(r"(?i)credit agreement", text)),
        "covenant_content": _has_covenant_content(text),
    }

    if not checks["min_chars"]:
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="S0_DISCOVERY_FAILURE",
            reason=(
                f"Document too short ({chars} chars) — likely not a full "
                f"credit agreement. May be an exhibit cover, summary, or "
                f"incorrectly acquired document."
            ),
            text_length=chars,
            checks=checks,
        )

    if not checks["credit_agreement"]:
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="S0_DISCOVERY_FAILURE",
            reason=(
                "No 'credit agreement' language found — likely the wrong "
                "document type acquired as S0."
            ),
            text_length=chars,
            checks=checks,
        )

    if not checks["covenant_content"]:
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="S0_DISCOVERY_FAILURE",
            reason=(
                "No covenant-like content found (no ratio thresholds, "
                "no covenant section headers, no loan/facility language). "
                "The document may not be a credit agreement."
            ),
            text_length=chars,
            checks=checks,
        )

    return DiscoveryValidationResult(
        is_valid=True,
        failure_cause="",
        reason="S0 document passes discovery validation.",
        text_length=chars,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# GT discovery validation (V02-006)
# ---------------------------------------------------------------------------

def validate_gt_document(cmp_path: str | Path) -> DiscoveryValidationResult:
    """Validate that a CMP document is a composite/conformed/restated copy.

    V02-006: Checks that the acquired CMP document is NOT an amendment
    document. The key signal is "AMENDMENT TO ... AGREEMENT" in the
    first 500 chars — a composite/conformed/restated copy would not
    have "AMENDMENT TO" in its title.

    If validation fails, the chain should be flagged as
    GT_DISCOVERY_FAILURE at acquisition time, not misattributed to the
    extractor.

    Args:
        cmp_path: path to the CMP document text file.

    Returns:
        DiscoveryValidationResult with is_valid=True if the document
        passes all checks, or is_valid=False with failure_cause=
        "GT_DISCOVERY_FAILURE" if any check fails.
    """
    p = Path(cmp_path)
    if not p.exists():
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="GT_DISCOVERY_FAILURE",
            reason="CMP.txt file missing",
            text_length=0,
            checks={"file_exists": False, "not_amendment": False, "credit_agreement": False},
        )

    text = p.read_text(encoding="utf-8", errors="ignore")
    chars = len(text)

    # Check if this is actually an amendment document (wrong acquisition).
    # Matches "AMENDMENT TO CREDIT AGREEMENT", "FIFTH AMENDMENT TO SECOND
    # AMENDED AND RESTATED CREDIT AGREEMENT", etc. The [^.] character
    # class matches newlines, so this handles titles that wrap across
    # lines.
    is_amendment = bool(
        re.search(
            r"(?i)\bamendment\s+to\s+[^.]{0,120}?\bagreement\b",
            text[:500],
        )
    )

    has_credit_agreement = bool(re.search(r"(?i)credit agreement", text))

    checks: dict[str, bool] = {
        "file_exists": True,
        "not_amendment": not is_amendment,
        "credit_agreement": has_credit_agreement,
    }

    if is_amendment:
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="GT_DISCOVERY_FAILURE",
            reason=(
                "CMP document appears to be an amendment document (title "
                "contains 'AMENDMENT TO ... AGREEMENT' in first 500 chars), "
                "not a composite/conformed/restated copy. The acquisition "
                "pipeline selected the wrong exhibit as the comparison source."
            ),
            text_length=chars,
            checks=checks,
        )

    if not has_credit_agreement:
        return DiscoveryValidationResult(
            is_valid=False,
            failure_cause="GT_DISCOVERY_FAILURE",
            reason=(
                "CMP document does not contain 'credit agreement' language — "
                "likely the wrong document type acquired as CMP."
            ),
            text_length=chars,
            checks=checks,
        )

    return DiscoveryValidationResult(
        is_valid=True,
        failure_cause="",
        reason="GT document passes discovery validation.",
        text_length=chars,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Shared covenant content detection
# ---------------------------------------------------------------------------

# Ratio threshold pattern: "X.XX to 1.00" or "X.XX : 1.0"
_RATIO_THRESHOLD_RE = re.compile(
    r"[\d.]+\s*(?:to|:)\s*1\.0+", re.IGNORECASE,
)
# Covenant section header pattern
_COVENANT_SECTION_RE = re.compile(
    r"(?i)(?:section|article)\s+[\d.]+\s+"
    r"(?:financial\s+)?(?:covenants|condition)",
)
# Loan/facility language pattern
_LOAN_LANGUAGE_RE = re.compile(
    r"(?i)(?:term\s+loan|revolving\s+(?:loan|facility|credit|commitment)"
    r"|delayed\s+draw|credit\s+agreement)",
)


def _has_covenant_content(text: str) -> bool:
    """Check if a document contains covenant-like content.

    Returns True if any of the following are found:
      - Ratio thresholds ("X.XX to 1.00", "X.XX : 1.0")
      - Covenant section headers ("Financial Covenants", "Financial Condition")
      - Loan/facility language ("Term Loan", "Revolving Credit", etc.)
    """
    if _RATIO_THRESHOLD_RE.search(text):
        return True
    if _COVENANT_SECTION_RE.search(text):
        return True
    return bool(_LOAN_LANGUAGE_RE.search(text))
