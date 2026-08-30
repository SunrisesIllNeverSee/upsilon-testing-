# Amendment Instruction Grammar v0.1

The amendment parser is split into two layers:

1. **Language interpretation**
   - identifies target section/commitment
   - classifies instruction type
   - extracts before/after values
   - records exact source span
   - assigns confidence

2. **Formal executor**
   - applies only validated/supported instructions
   - checks prior-state guards
   - creates a new commitment version
   - records lineage and authority
   - refuses ambiguous instructions

## Instruction families

### 1. Scalar replacement

Example:
> Section 6.11(a) is amended by deleting "4.00 to 1.00" and replacing it with "5.00 to 1.00".

Normalized:
```json
{
  "instruction_type": "REPLACE_VALUE",
  "target_key": "financial_covenant.total_leverage_ratio",
  "field": "threshold",
  "old_value": 4.0,
  "new_value": 5.0
}
```

### 2. Add

Example:
> Section 6.11 is amended by adding the following clause (c)...

Emit:
`ADD_COMMITMENT`

### 3. Delete

Example:
> Section 6.11(b) is hereby deleted in its entirety.

Emit:
`DELETE_COMMITMENT`

### 4. Exception expansion / contraction

Example:
> The definition of Permitted Indebtedness is amended to include...

Emit:
`ADD` with `domain_effect: exception_expansion`, or `DELETE` with
`domain_effect: exception_removal`, or explicit replacement of normalized
exception set.

### 5. Temporal waiver

Example:
> Compliance with Section 6.11(a) is waived for the fiscal quarters ending...

Emit:
`WAIVE_TEMPORARILY` with `effective_start` and `effective_end`.

The underlying covenant remains in lineage. It is not deleted.

### 6. Suspension / reinstatement

Emit:
`SUSPEND`
`REINSTATE`

### 7. Full section restatement

Example:
> Section 6.11 is hereby amended and restated in its entirety as follows...

Emit:
`RESTATE_SECTION` at parse time, then decompose the restated section against the prior section into explicit commitment-level changes before execution.

**Never blindly replace the whole kernel.**

### 8. Cross-reference / renumbering

Emit:
`RENUMBER_REFERENCE`.

This is normally non-economic but can cause downstream propagation failures if internal systems bind to section identifiers.

## Hard rule

If target resolution, authority, prior state, or effective period cannot be determined with sufficient confidence:

```text
UNRESOLVED → VALIDATION QUEUE
```

No best-effort mutation of authoritative state.
