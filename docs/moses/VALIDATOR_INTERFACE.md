# Validator Interface — MVP Specification

## Internal-first, product-ready

The validator should be built as part of the architecture, not treated as a temporary spreadsheet.

### Queue view

Each task shows:

- issuer / agreement
- amendment number
- instruction type
- parser confidence
- exact source text
- target commitment
- current authoritative state
- proposed new state
- structured diff
- materiality flag

Actions:

- Approve
- Correct and approve
- Reject
- Mark unresolved
- Require second review

### Evidence view

Three panes:

**Left:** prior authoritative clause / commitment  
**Center:** amendment instruction and source span  
**Right:** proposed resulting commitment state

### Review policy

Automatic execution is allowed only when:

- target resolves uniquely;
- instruction type is supported;
- prior-state guard matches;
- parser confidence meets configured threshold;
- instruction is below configured materiality threshold OR explicitly approved for auto-apply.

All other cases go to human review.

### Gold corpus

Every approved/corrected decision becomes training/evaluation data for:

- target resolution
- instruction classification
- structured extraction
- materiality classification

Do not train directly from unreviewed production guesses.
