# Dependency Direction — Upsilon/MO§ES™ Semantic Authority

This document defines the controlling semantic direction for the Upsilon engine.
It reflects **semantic authority**, not merely import convenience.

## Original architectural anchor

This hardening restores an earlier intended Upsilon/MO§ES™ structure rather
than replacing working foundations with a novel architecture. The original
conceptual pipeline was approximately:

```
EDGAR
→ Agreement Chain
→ Parser
→ Commitment Extractor
→ Authoritative / validated Kernel
→ Amendment Parser
→ Authorized Change Engine
→ Commitment Lineage Graph
→ Current Authoritative Kernel
```

The target architecture makes each stage an explicit semantic home with
enforced ownership boundaries.

## Controlling semantic direction

```
INGESTION
    ↓
PARSING
    ↓
EVIDENCE
    ↓
COMMITMENT IDENTITY + KERNEL
    ↓
AUTHORIZED TRANSFORMATION
    ↓
CONSERVATION VALIDATION
    ↓
SEMANTIC PROOF
    ↓
EXECUTION
    ↓
LINEAGE EDGE / SUCCESSOR STATE
    ↓
AUTHORITY
    ↓
DOWNSTREAM PROPAGATION / COMPARISON
```

Lineage is not merely logging. It is part of the governed commitment model.
Each accepted transformation produces a lineage edge recording the
predecessor identity, successor identity, authority/source, and
transformation proof.

## Core rule

Lower-level evidence extraction may supply evidence upward.

It may **NOT** directly:

- establish authoritative commitment identity;
- mutate commitment state;
- grant semantic authority;
- bypass conservation validation.

## Per-layer import / ownership rules

### ingestion
- **may** acquire documents, discover filings, normalize text
- **may not** import `execution` or `authority`

### parsing
- **may** produce structured parse instructions and lexical evidence
- **may not** import `execution` or `authority`

### evidence
- **may** represent source evidence (section refs, aliases, spans, extracted values)
- **may not** grant semantic identity or authority

### commitments
- **owns** identity and canonical commitment state
- **may not** depend on `authority`

### transformations
- **operates** over commitment state
- **may** consume evidence
- **may not** grant authority

### conservation
- **validates** transformations and state continuity
- **may not** perform raw EDGAR parsing

### proof
- **records** validated semantic transformation evidence
- **may not** invent semantic interpretation

### execution
- **applies** already-validated structured transformations
- **may not** contain EDGAR lexical heuristics

### authority
- **consumes** execution + semantic proof + conservation status
- **may not** inspect raw EDGAR text to infer meaning

### lineage
- **owns** the append-only authoritative history of transformations
- **records** predecessor/successor identity, authority/source, transformation proof
- **may not** invent transformations or grant authority independently

### pipeline
- **orchestrates** layers
- **must not** duplicate their semantics

### audits and research
- **may** import runtime code

### runtime code
- **must NEVER** import audits or research

## Evidence vs. authority

> Global section numbers and aliases are evidence mechanisms,
> not semantic authority.

Section numbers and alias patterns may supply evidence upward to the
commitment identity and transformation layers. They may not, by themselves,
establish authoritative commitment identity or authorize a transformation.

This rule addresses a known failure mode in the current legacy layout where
`semantic_mapper._section_to_commitment_id()` resolves commitment identity
from section numbers alone without sufficient predecessor-state evidence.
