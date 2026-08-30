# Prospective Study Protocol / Preregistration
## Upsilon Financial Commitment Integrity

**Protocol version:** 0.1  
**Prospective date:** 2026-08-29  
**Status:** Draft until frozen with `python freeze_study.py`

## Objective

Determine whether a structured commitment-lineage system can reconstruct the authoritative state of repeatedly amended credit agreements from public filings with traceable source authority and without silently guessing unresolved legal transformations.

Study 1 tests **mechanism and reconstruction**, not default prediction, litigation prediction, or private enterprise propagation failures.

## Research question

> Given an original credit agreement and a sequence of legally effective amendments, can Upsilon reconstruct the applicable commitment state at time T and preserve a complete authority lineage to the source documents?

## Model under test

```text
ORIGIN KERNEL C0
      ↓ authorized transformations
AUTHORITATIVE STATE K(A,T)
      ↓ projection
DOWNSTREAM REPRESENTATION R(T)
```

Study 1 directly evaluates the first two layers.

## Primary hypothesis — H1

On held-out credit-agreement chains with independently available composite, conformed, or amended-and-restated ground truth:

> Upsilon's amendment-aware reconstruction will produce greater exact agreement with the authoritative ground-truth state than a carry-forward baseline that assumes the prior agreement state did not change.

The primary comparison is performed only on fields affected by amendments.

## Secondary hypotheses

**H2 — Complexity gradient.** Supported scalar/local structural instructions will have higher exact reconstruction accuracy than instructions requiring cross-reference resolution, defined-term propagation, or full-section restatement.

**H3 — Conservative execution.** `UNRESOLVED → VALIDATION` will favor precision over recall and reduce silent incorrect authoritative-state mutations.

**H4 — Lineage completeness.** Automatically resolved state transitions will retain an unbroken authority path to the amendment instruction and source agreement version.

**H5 — Error concentration.** Remaining errors will disproportionately occur in defined-term changes, nested exceptions, cross-references, section restatements, and conditional/springing provisions.

## Prospective expectations

Recorded before testing; these are not pass thresholds.

We expect:
1. numeric replacement/deletion instructions to be easiest;
2. composite agreements to provide strong external reconstruction targets;
3. the deterministic parser to have higher precision than recall;
4. human validation demand to be material in development;
5. parser improvements to reduce unresolved complex cases rather than change the lineage architecture.

No numeric accuracy threshold is preregistered before the development corpus because the empirical difficulty distribution is not yet known.

## Study phases

### A. Smoke test — exploratory
Two fixed real SEC filings. Confirm acquisition, parsing, persistence, lineage, and ground-truth comparison. Smoke results are not the confirmatory publication result.

### B. Development corpus
25 issuers. Parser/schema/annotation changes are allowed and logged.

### C. Freeze
Before held-out evaluation, freeze code, parser, schema, taxonomy, inclusion/exclusion rules, scoring, annotation guide, and endpoints.

### D. Held-out validation
25 new issuers selected by the same rule. No tuning on this set.

## Inclusion criteria

1. Public EDGAR issuer.
2. Recoverable authoritative base credit agreement.
3. At least two later amendment events.
4. Amendment order/effective dates can be established.
5. Text/HTML is readable or reliably converted.
6. Enough source material exists to establish gold authoritative state.

For the strongest reconstruction subset, a later composite/conformed/amended-and-restated agreement must be independently available.

## Exclusion criteria

Record and exclude only for:
- missing base agreement;
- irrecoverable amendment link;
- unreadable source;
- duplicate filing artifact;
- indeterminate amendment authority/order;
- document outside the predefined contract family.

Never exclude because Upsilon performs poorly.

## Primary endpoint

**Changed-field authoritative-state exact accuracy**

Unit: `commitment × affected field × effective state`.

Compare reconstructed values against independently validated ground truth. Report exact accuracy, numerator/denominator, and agreement/issuer-clustered 95% confidence intervals.

## Primary comparator

**Carry-forward baseline:** prior authoritative state is assumed unchanged.

## Secondary endpoints

- instruction detection precision/recall/F1;
- instruction-type accuracy;
- target-section accuracy;
- numeric value exact accuracy;
- exception-set exact accuracy;
- lineage completeness;
- unresolved rate;
- incorrect automatic mutation rate;
- human-review rate;
- reconstruction accuracy by complexity class.

## Annotation

Gold annotations retain source document, accession, source span, section, instruction type, target commitment, prior state, resulting state, effective interval, reviewer, and adjudication status.

At least 20% of held-out material should receive independent double annotation.

## Deviations

Every post-freeze change must be recorded in `DEVIATION_LOG.md` with timing, reason, affected endpoint/data/code, whether results were already viewed, and expected bias direction.

## Falsification conditions

The mechanism claim is weakened if:
- authoritative states cannot be reliably reconstructed after validated amendment instructions;
- lineage cannot deterministically connect state changes to authority;
- amendment-aware results do not improve meaningfully over carry-forward on changed fields;
- unresolved routing merely hides a large incorrect-state rate.

These outcomes must be reported rather than reframed.
