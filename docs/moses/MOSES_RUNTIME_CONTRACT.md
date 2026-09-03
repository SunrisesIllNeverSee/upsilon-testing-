# MOSES Runtime Contract

**Step 23M design document.** This is the governing contract for the
MOSES semantic control layer inside Upsilon.  It defines the formal
state model, the controlling runtime sequence, and the layer contracts
that separate responsibilities.

No runtime code is modified by this document.  It is a specification
that future implementation steps (Step 23S safety, Step 24 coverage)
must conform to.

---

## 1. Formal governing state model

The preferred formulation is:

```
C_t = C_{t-1} ⊕ Δ_t_authorized
```

subject to:

```
Δ_t_actual = Δ_t_authorized
```

and, for every field outside the authorized transformation:

```
C_t[f] = C_{t-1}[f]   for all f not in affected(Δ_t)
```

Conservation does NOT mean preventing legitimate amendment changes.
It means:

- no unauthorized semantic change;
- no unexplained semantic loss;
- no unsupported semantic gain.

### Current behavior (forensic finding)

The forensic evidence (`forensic_qa/001_moses_commitment_theory_audit.md`
Q6) indicates that current Upsilon behaves approximately as:

```
C_t = Execute(Extract(Text_t))
```

The resolver rediscovers commitment identity from amendment text at
every step (`semantic_resolver_v2.py:482`), re-extracts values from
text regex (`semantic_resolver_v2.py:650-745`), and the predecessor
`CommitmentState` is passed as a dead parameter that is never read.
This is the behavior the present contract supersedes.

### Why this matters

Of the 86 IN_SCOPE instructions audited in Step 23R:

- 6 were accepted with incorrect values (wrong value, wrong class, or
  wrong unit) because the resolver did not use predecessor state to
  validate the transformation.
- 4 OUT_OF_SCOPE instructions produced unauthorized mutations because
  the resolver matched a facility alias in debt-incurrence context
  without establishing that the amendment actually targets a conserved
  commitment.
- 1 false authoritative promotion occurred because authority
  determination checks structural completeness only, not semantic
  correctness.

All 10 incorrect accepted mutations and the 1 false promotion are
traceable to the absence of the governing state model at runtime.

---

## 2. Controlling runtime sequence

This sequence supersedes any design that treats the core runtime as
merely `Text → Alias → Field → Value → Mutation`.  It is the
controlling target from the Step 23M addendum:

```
SOURCE AGREEMENT
      │
      ▼
AUTHORITATIVE PREDECESSOR KERNEL
      │
      ▼
PERSISTENT IDENTITY
      │
      ▼
AMENDMENT EVIDENCE
      │
      ▼
TARGET DETERMINATION
      │
      ▼
AUTHORIZED TRANSFORMATION Δ
      │
      ▼
SEMANTIC PROOF
      │
      ▼
CONSERVATION VALIDATION
      │
      ▼
EXECUTION
      │
      ▼
SUCCESSOR KERNEL
      │
      ▼
LINEAGE EDGE
      │
      ▼
SEMANTIC AUTHORITY GATE
      │
      ▼
AUTHORITATIVE C*t
      │
      ▼
PROPAGATION / DOWNSTREAM COMPARISON
```

The lineage edge represents an **executed successor**.  Authority
determines whether that executed state is promotable to authoritative
status.  The successor is not authoritative until the authority gate
grants promotion.

### Semantic proof precedes execution

A `SemanticTransformationProof` is NOT a post-hoc explanation of
executor behavior.  It is the precondition that justifies allowing a
transformation to execute.  The conceptual ordering is:

```
Evidence
  → Target Identity
  → Predecessor State
  → Authorized Transformation
  → Semantic Proof
  → Conservation Validation
  → EXECUTION
  → Lineage
  → Authority
```

The executor may not apply a transformation that lacks a valid proof
record.  The authority gate may not promote a step whose proof record
has failed conservation validation.

### Three integrity domains

| Domain | Question | Current status |
|--------|----------|----------------|
| Transformation Integrity | Did authorized amendment evidence produce the correct successor state? | Primary focus of Step 23S/24 |
| Lineage Integrity | Can the current commitment be traced through valid authorized transformations? | Scaffolded, not enforced |
| Propagation Integrity | Do downstream representations match the current authoritative kernel? | Not yet addressed |

These three domains must not be collapsed.  Current Step 23/24 work is
primarily Transformation Integrity.  Lineage and Propagation are
future phases.

---

## 3. Contracts before migration

Step 23M defines semantic contracts before any Phase-2 source
migration is authorized.  The required sequence is:

```
define semantic ownership/contracts
  → review contracts
  → implement runtime enforcement
  → only then migrate responsibilities into target modules
```

The prohibited sequence is:

```
move files → fix imports → green tests
```

No runtime modules are moved during Step 23M.  The target package
layout (`src/upsilon/` with `commitments/`, `transformations/`,
`conservation/`, `proof/`, `execution/`, `authority/`, `lineage/`,
`pipeline/`) is the destination, not the starting point.
Migration is authorized only after the contracts in this package are
reviewed and runtime enforcement is implemented.

---

## 4. Evaluation truth must never become production logic

The Step 23R independently adjudicated labels are:

```
TEST / DIAGNOSTIC ORACLES
```

They must never become production lookup data.  Future semantic
authority must not depend on:

```
ground_truth_correct = true
```

or any equivalent answer-key information.  Production runtime must
establish validity using operational evidence and MOSES invariants
alone.

The dependency direction rule from `.devin/rules.md` is reinforced
here: audit and research modules may import runtime code, but runtime
code must never import audit or research modules.  The Step 23R
diagnostic set (`results/step23r_audit.json`,
`results/step23r_instruction_ledger.csv`, etc.) is frozen evidence
for evaluation, not a production data source.

---

## 5. Layer contracts

The runtime is explicitly separated into seven layers.  These
responsibilities must not collapse into a single resolver.  The
current legacy architecture violates this: `semantic_resolver_v2.py`
performs evidence extraction, semantic interpretation, transformation
construction, and validation in one 10-step function, and
`semantic_pipeline_v2.py:247-251` reduces authority to a completeness
check.

### Layer A — Evidence extraction

| | |
|---|---|
| **Inputs** | Source documents (amendment text, section references, defined-term tables), parser instructions |
| **Outputs** | Evidence objects: text spans, alias matches, section references, defined-term expansions, model-assisted candidates, extracted value candidates |
| **May do** | Text matching, regex extraction, alias lookup, section-reference resolution, defined-term expansion, model-assisted candidate generation |
| **Must not do** | Establish authoritative commitment identity; construct transformations; mutate commitment state; grant authority; bypass conservation validation |
| **Failure behavior** | If no evidence is found, produce an empty evidence set.  Empty evidence does NOT default to a guess.  The downstream layers fail closed. |

Evidence extraction mechanisms (text matching, aliases, section
references, regex, model-assisted candidates, defined-term lookup)
remain useful but become subordinate evidence sources.  They may not
independently establish semantic authority.

### Layer B — Semantic interpretation (Authorized Transformation Engine)

| | |
|---|---|
| **Inputs** | Evidence objects (from Layer A), authoritative predecessor commitment `C_{t-1}`, authority/lineage context `A_t` |
| **Outputs** | Authorized semantic transformation `Δ_t` (or rejection with reason) |
| **May do** | Establish transformation target identity from evidence + predecessor state; determine transformation type; determine affected fields; determine old/new values from predecessor state + evidence |
| **Must not do** | Raw document parsing; mutate commitment state; grant authority; execute the transformation |
| **Failure behavior** | If target identity cannot be established with sufficient evidence, reject (fail closed).  If transformation type cannot be determined, reject.  If old-value consistency cannot be verified, reject.  Rejection produces an UNRESOLVED instruction, not a best-guess mutation. |

This layer is the `AuthorizedTransformationEngine` from the original
MOSES architecture.  Its contract is:

```
(C_{t-1}, E_t, A_t) → Δ_t
```

It owns transformation interpretation and authorization reasoning,
not raw document parsing.  It must be distinct from evidence
extraction (Layer A) and from execution (Layer F).

**Authoritative predecessor objects (Constraint #2):** The engine
must treat the independently established predecessor commitment/kernel
as a real semantic input.  It must not reconstruct identity from
amendment text when authoritative predecessor identity already
exists.  However, predecessor state is context and constraint
evidence — it is NOT automatically proof that the amendment targets
that commitment.  Target identity must be established by affirmative
evidence, not by predecessor existence alone.

**Prohibit tautological old-value validation (Constraint #3):** The
engine must NOT simply copy `old_value = predecessor[field]` and then
treat an executor check that `old_value == predecessor[field]` as
evidence that the semantic interpretation was correct.  That only
proves `x = x`.  Old-value consistency is a conservation check AFTER
target/transformation evidence has been established.  The engine must
first establish (1) the amendment targets the commitment, (2) the
amendment targets the field, (3) the extracted transformation is
authorized — and only then verify old-value consistency as a
conservation guard.

### Layer C — Commitment transformation

| | |
|---|---|
| **Inputs** | Authorized transformation `Δ_t`, predecessor commitment `C_{t-1}` |
| **Outputs** | Candidate successor state `C_t_candidate` (not yet executed) |
| **May do** | Apply the transformation to produce a candidate successor; compute the semantic delta |
| **Must not do** | Grant authority; execute against the live commitment store; invent transformation semantics not in `Δ_t` |
| **Failure behavior** | If the transformation cannot be applied (e.g., required predecessor field is missing), produce a PARTIAL result.  Partial results do not proceed to execution. |

### Layer D — Conservation validation

| | |
|---|---|
| **Inputs** | Candidate successor `C_t_candidate`, predecessor `C_{t-1}`, authorized transformation `Δ_t` |
| **Outputs** | Validation results: pass/fail per invariant, with failure reasons |
| **May do** | Check identity persistence, old-value consistency, unchanged-field preservation, no unsupported semantic gain, no silent semantic loss, target/reference separation, temporal validity, OUT_OF_SCOPE isolation, transformation completeness |
| **Must not do** | Perform raw EDGAR parsing; construct transformations; grant authority |
| **Failure behavior** | If any invariant fails, the candidate is rejected.  Rejection prevents execution.  The failure is recorded in the proof record. |

See `CONSERVATION_INVARIANTS.md` for the full invariant list and
which invariants apply to which transformation family.

### Layer E — Semantic proof

| | |
|---|---|
| **Inputs** | Authorized transformation `Δ_t`, validation results (from Layer D), evidence objects, predecessor/successor versions |
| **Outputs** | `SemanticTransformationProof` record |
| **May do** | Assemble the proof record with all required fields; record evidence status and uncertainty status |
| **Must not do** | Invent semantic interpretation; perform validation; execute |
| **Failure behavior** | If required proof fields cannot be populated, the proof is INCOMPLETE.  An incomplete proof does not proceed to execution. |

The proof record is the precondition that justifies execution.  See
`SEMANTIC_PROOF_RECORD.md` for the schema.

### Layer F — Execution

| | |
|---|---|
| **Inputs** | Validated candidate successor with a complete proof record |
| **Outputs** | Execution result: applied/unresolved instructions, successor state |
| **May do** | Apply the validated transformation to the commitment store; deep-copy state before mutation; record the lineage edge |
| **Must not do** | Contain EDGAR lexical heuristics; perform semantic interpretation; grant authority; inspect raw EDGAR text |
| **Failure behavior** | If execution fails (e.g., state conflict), produce an UNRESOLVED result.  The state is not mutated. |

The executor applies already-validated structured transformations.
It must not contain EDGAR lexical heuristics or text-based semantic
interpretation (`.devin/rules.md` prohibited action #1).

### Layer G — Authority promotion

| | |
|---|---|
| **Inputs** | Execution result, proof record, conservation validation results, inherited unresolved state |
| **Outputs** | Authority decision: AUTHORITY_GRANTED / AUTHORITY_BLOCKED / VALIDATION_REQUIRED / PARTIAL / UNRESOLVED |
| **May do** | Consume execution + proof + conservation + lineage status; determine if the step may be promoted to authoritative |
| **Must not do** | Inspect raw EDGAR text to infer meaning; perform validation; construct transformations |
| **Failure behavior** | If any required input is missing or failed, authority is BLOCKED.  No path may promote a step with a failed proof record or failed conservation validation. |

Authority must no longer be reducible to `execution complete + nothing
unresolved`.  See `SEMANTIC_AUTHORITY_GATE.md` for the full authority
contract.

---

## 6. Current legacy architecture vs. target

The current legacy architecture collapses layers A–E into
`semantic_resolver_v2.py` and `semantic_mapper.py`, and reduces Layer
G to a completeness check in `semantic_pipeline_v2.py:247-251`.

| Target layer | Current legacy location | Gap |
|--------------|------------------------|-----|
| A. Evidence extraction | `commitment_registry.py`, `semantic_resolver_v2.py` (interleaved) | Not separated from interpretation |
| B. Semantic interpretation | `semantic_resolver_v2.py:458-557` (10-step resolver) | No predecessor-state use; no AuthorizedTransformationEngine |
| C. Commitment transformation | `semantic_resolver_v2.py` (candidate construction) | Not separated from evidence |
| D. Conservation validation | `semantic_resolver_v2.py:788` (`_validate_candidate` — `hasattr` check only) | `current_state` is a dead parameter; no real validation |
| E. Semantic proof | (does not exist) | No proof records produced |
| F. Execution | `executor.py:17-179` | Old-value guard exists but never activated (`old_value` always `None`) |
| G. Authority promotion | `semantic_pipeline_v2.py:247-251` | Completeness-only; no correctness gate |

Migration of these responsibilities into the target `src/upsilon/`
package layout is NOT authorized in Step 23M.  The contracts in this
document are the precondition for that migration.

---

## 7. References

- `forensic_qa/001_moses_commitment_theory_audit.md` — forensic evidence
- `docs/architecture/DEPENDENCY_DIRECTION.md` — per-layer import rules
- `docs/architecture/ARCHITECTURE_INDEX.md` — architecture navigation
- `.devin/rules.md` — agent governance rules
- `.devin/prompts/STEP_23M.md` — base prompt
- `.devin/prompts/STEP_23M_ADDENDUM.md` — original architecture anchor
- `.devin/prompts/STEP_23M_CONSTRAINTS.md` — six controlling constraints
