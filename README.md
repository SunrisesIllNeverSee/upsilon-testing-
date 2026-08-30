
## Repository testing

Automated tests run on pushes and pull requests. For formal empirical work, use
`GITHUB_TESTING_PROTOCOL.md` together with the prospective protocol under
`research/`.

**CI passing is not the research result.** Formal test runs must be frozen,
tagged, hashed, and documented separately.


# Upsilon Financial Commitment Integrity — MVP

## Locked architecture

**Commercial product line:** Upsilon  
**Underlying architecture/protocol:** MO§E§  
**Initial domain module:** Financial Commitment Integrity

### Stack

- Python 3.12+
- FastAPI
- PostgreSQL 16+
- SQLAlchemy / psycopg
- Pydantic
- Alembic
- Background jobs: simple worker first; Temporal/Celery only when needed
- Object storage for source documents
- Optional later projection: Neo4j for advanced graph exploration

### Why PostgreSQL first

The core system is not primarily a graph browser. It is an **auditable state-transition engine**:

1. ingest authoritative documents;
2. extract commitments;
3. freeze an authoritative state;
4. parse amendment instructions;
5. apply instructions deterministically;
6. preserve lineage;
7. compare downstream representations against current authoritative state;
8. record validation decisions.

PostgreSQL handles this cleanly with relational integrity, JSONB payloads, recursive CTEs, transactions, and mature enterprise operations.


### Bitemporal authority

Authoritative state is temporal, not a permanent boolean flag.

Each commitment version records:
- **valid time**: half-open interval `[valid_from, valid_to)`;
- **recorded time**: when Upsilon stored the state;
- **applicability**: conditions for springing/conditional terms.

Temporary waivers are represented as bounded effective states and can schedule a
restored state at the waiver end.

---

## Core state model

```text
ORIGIN KERNEL C0
      |
      | authorized amendment
      v
AUTHORITATIVE CURRENT KERNEL C*t
      |
      +------> downstream representation A
      +------> downstream representation B
      +------> downstream representation C

AUTHORIZED CHANGE    = change supported by valid amendment lineage
UNEXPLAINED DRIFT    = change lacking valid authority/lineage
PROPAGATION FAILURE  = authoritative state changed, downstream state did not
```

---

## Product objects

- `agreement`
- `agreement_version`
- `source_document`
- `source_span`
- `commitment`
- `commitment_version`
- `amendment_instruction`
- `lineage_edge`
- `downstream_representation`
- `representation_commitment`
- `propagation_check`
- `validation_task`
- `validation_decision`

---

## Amendment instruction types

The deterministic executor separates **transformation type** (how the legal
document transformed) from **domain effect** (what changed in the commitment
domain). A single transformation (e.g., `REPLACE_VALUE`) can produce different
domain effects (e.g., `commitment_amount_change`, `covenant_threshold_change`)
depending on which field changed.

**Instruction types** (transformation operations):

- `REPLACE_VALUE`
- `REPLACE_TEXT`
- `ADD`
- `ADD_COMMITMENT`
- `DELETE`
- `DELETE_COMMITMENT`
- `WAIVE_TEMPORARILY`
- `SUSPEND`
- `REINSTATE`
- `RESTATE_SECTION`
- `RENUMBER_REFERENCE`
- `FIND_REPLACE_REFERENCE`

**Domain effects** (semantic impact on the commitment domain):

- `covenant_threshold_change`
- `commitment_amount_change`
- `deadline_change`
- `exception_expansion`
- `exception_removal`
- `party_change`
- `frequency_change`
- `scope_change`
- `definition_change`
- `unknown`

Anything outside the supported grammar is stored as `UNRESOLVED` and routed to validation rather than guessed.

---

## Validation policy

The validator is **part of the product architecture**, but internal-first.

Phase 1:
- operator/admin validation UI
- legal reviewer queue
- gold-corpus creation
- unresolved-instruction review
- high-materiality commitment review

Phase 2:
- customer-facing evidence/approval workflow
- reviewer role controls
- dual approval for high-risk changes
- exportable audit trail

The system should never silently convert uncertain legal language into authoritative state.

---

## Commercial positioning

### Upsilon
Enterprise operating intelligence product line.

### Upsilon Financial Commitment Integrity
Measures whether binding financial commitments remain authorized, traceable, and correctly propagated as agreements change.

### MO§E§
Underlying architecture for commitment continuity, lineage, state, and governed execution.

---

## MVP build target

25 issuers  
2–5 amendments per issuer  
~75–100 amendment events

First success criterion:

> Given an original agreement and its amendment chain, reconstruct the authoritative current commitment state and match a filed amended/restated or composite agreement where one exists.

Second success criterion:

> Detect a stale downstream representation after an authoritative commitment changes.

Prediction of defaults or covenant breaches is deliberately **not** an MVP requirement.


---

## Persistence bridge

`persistence.py` connects the in-memory formal executor to PostgreSQL.

It:
- writes commitment versions;
- closes prior validity intervals;
- writes lineage edges;
- records reference renumberings separately;
- marks instructions APPLIED or UNRESOLVED;
- binds every state transition to the amendment agreement-version authority;
- schedules restoration after a temporary waiver.

This closes the prior gap between `executor.py` and the database lineage model.

---

## Parser status

`amendment_parser.py` is a reproducible deterministic baseline, not the finished
legal parser. It currently recognizes common replace/delete/add/waive/restate
patterns. Cross-reference resolution and dense defined-term propagation remain
the critical parser work and are intentionally routed to validation when unresolved.


---

## Academic testing workflow

On macOS, start with `RESEARCH_WORKFLOW_MAC.md`.

The `research/` directory contains the prospective preregistration, smoke-test
protocol, hypotheses, annotation guide, lab notebook, deviation log, results
template, and reproducibility checklist.

Run `freeze_study.py` before downloading the fixed smoke-test documents.
