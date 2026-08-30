# Annotation Guide v0.1

Annotate what the legal source states. Do not infer commercial intent beyond textual authority.

## Fields

- document_id
- instruction_id
- source_start / source_end
- source_text
- instruction_type
- target_section_ref
- target_commitment_key
- old_value / new_value
- effective_start / effective_end
- changes_commitment: yes / no / uncertain
- complexity_class
- reviewer
- adjudicated

## Complexity

**L1 Local scalar:** direct numeric/text replacement.  
**L2 Local structural:** add/delete obligation, explicit waiver, deadline, party, frequency.  
**L3 Referential:** depends on another definition, clause, schedule, or exhibit.  
**L4 Restatement:** whole section/definition replaced.  
**L5 Conditional:** springing covenant, step-down, temporal/calculated applicability.

## Ambiguity rule

If reasonable reviewers cannot identify one authoritative structured mutation from the source alone, label `UNRESOLVED`. Do not force a guess.

## Adjudication

Preserve original reviewer labels. The adjudicated gold label is separate and never overwrites the original record.
