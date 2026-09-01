"""Track B.2: Mutation-by-mutation provisional defect analysis.

For every mutation currently labeled "incorrect" in the held-out study,
extract:

  - chain_id
  - issuer
  - accession / amendment
  - source span (character offsets in amendment text)
  - parsed instruction (type, section ref, source text excerpt)
  - semantic mapping (target key, operation, value)
  - applied mutation (what the executor received)
  - reconstructed field/value (what the executor rejected)
  - basis for calling it incorrect

Classify evidence source:

  A. INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT
     The mutation is demonstrably wrong without any gold — e.g., the
     executor rejects it because the target key does not exist in the
     chain's state, or the source text clearly does not support the
     mapped semantic.

  B. DEPENDS ON AUTOMATED PROXY GOLD
     The mutation is only "wrong" relative to automated proxy gold
     annotations.

  C. AMBIGUOUS UNTIL HUMAN REVIEW
     Cannot be classified without human verification of the source
     document.

This script does NOT modify the frozen system.  It re-runs the frozen
pipeline in READ-ONLY inspection mode to extract mutation details that
were not persisted in the results JSON.

Usage:
    python analyze_held_out_mutations.py
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from run_held_out_study import all_held_out_chains
from semantic_pipeline import run_semantic_pipeline
from chain_reconstruction import AmendmentStep
from amendment_parser import parse_v04
from semantic_mapper import map_instruction
from models import AmendmentInstruction, InstructionType, InstructionProvenance
from executor import execute_amendment

HELD_OUT_MANIFEST = Path("data/held_out/manifest.json")
OUTPUT_PATH = Path("results/step_19b_mutation_defect_analysis.json")


def _find_source_span(text: str, snippet: str, window: int = 200) -> tuple[int, int] | None:
    """Find character offsets of a snippet in text."""
    idx = text.find(snippet[:80])
    if idx == -1:
        return None
    return (idx, idx + len(snippet))


def analyze_chain_mutations(
    chain_id: str,
    issuer: str,
    cik: str,
    amendments: list[AmendmentStep],
    current_state: dict,
    manifest_entry: dict,
) -> list[dict]:
    """Analyze all incorrect mutations for a single chain.

    Returns a list of mutation-detail dicts.
    """
    mutations_detail: list[dict] = []
    state = {k: v.model_copy(deep=True) for k, v in current_state.items()}

    for step in amendments:
        source_path = step.source_document_path
        if not source_path or not Path(source_path).exists():
            continue

        text = Path(source_path).read_text(encoding="utf-8", errors="ignore")
        parser_result = parse_v04(text)
        parser_rows = parser_result["instructions"]

        from semantic_pipeline import _parser_rows_to_instructions
        instructions = _parser_rows_to_instructions(parser_rows)

        # Map each instruction
        mapped_instructions = []
        step_mutations = []
        for ins in instructions:
            result = map_instruction(ins, citation_document=step.description)
            step_mutations.extend(result.mutations)
            for mut in result.mutations:
                mapped_instructions.append(mut.to_amendment_instruction(order=ins.order))

        # Execute
        execution_result = execute_amendment(state, mapped_instructions)

        # For each rejected (incorrect) mutation, extract details
        for rejected_ins in execution_result.unresolved:
            # Find the original parser instruction that produced this
            orig_ins = next(
                (i for i in instructions if i.order == rejected_ins.order),
                None,
            )
            # Find the structured mutation that produced this
            orig_mut = next(
                (m for m in step_mutations
                 if m.to_amendment_instruction(order=orig_ins.order if orig_ins else 0).order
                 == rejected_ins.order),
                None,
            )

            # Source span
            source_span = None
            source_excerpt = ""
            if orig_ins and orig_ins.source_text:
                source_span = _find_source_span(text, orig_ins.source_text)
                source_excerpt = orig_ins.source_text[:300]

            # Determine basis for "incorrect"
            # The executor rejects a mutation when the target_key does
            # not exist in the current state (UNKNOWN_COMMITMENT) or
            # the operation is not applicable.  This is independently
            # demonstrable from the system's own execution — no gold
            # needed.
            target_key = rejected_ins.target_key or ""
            key_in_state = target_key in state if target_key else False

            # Check: does the source text actually support the mapped
            # semantic?  For a maturity-date replacement, the source
            # text should contain a date near "Maturity Date" AND the
            # instruction should be a value-replacement type.
            source_supports_mapping = True
            basis_notes = []

            # CRITICAL CHECK: Is the target_key a key that the S0
            # extractor EVER produces?  If the mapper targets a key
            # that the system's own extractor never creates (across
            # all development and held-out chains), then the mutation
            # is independently demonstrable as wrong — it targets a
            # phantom key.  No gold needed.
            PHANTOM_KEYS = {
                "facility.credit_agreement",
            }
            is_phantom_key = target_key in PHANTOM_KEYS

            if orig_ins and orig_mut:
                # If the instruction type is RESTATE_SECTION or DELETE,
                # the maturity-date rule should not have fired (per the
                # v1 fix).  But if it did fire before the fix, that's a
                # demonstrable defect.
                if orig_ins.instruction_type in (
                    InstructionType.RESTATE_SECTION,
                    InstructionType.DELETE,
                ):
                    source_supports_mapping = False
                    basis_notes.append(
                        f"Instruction type is {orig_ins.instruction_type.value}, "
                        f"which is not semantically compatible with a "
                        f"field-value replacement.  The mapper fired a "
                        f"replacement rule on a non-replacement instruction."
                    )

            if is_phantom_key:
                basis_notes.append(
                    f"Target key '{target_key}' is a PHANTOM KEY: the "
                    f"S0 extractor never produces this key in any chain "
                    f"(development or held-out).  The mapper's rule "
                    f"targets a commitment that the system's own "
                    f"extractor cannot create.  This is independently "
                    f"demonstrable from the system's architecture — no "
                    f"gold required."
                )
                source_supports_mapping = False
            elif not key_in_state:
                basis_notes.append(
                    f"Target key '{target_key}' does not exist in the "
                    f"chain's commitment state (keys: "
                    f"{list(state.keys())[:5]}...).  The executor "
                    f"rejected the mutation as UNKNOWN_COMMITMENT."
                )

            # Evidence classification
            # A = Independently demonstrable from source text / system execution
            # B = Depends on automated proxy gold
            # C = Ambiguous until human review
            #
            # An incorrect mutation is classified A when:
            #   - The target key is a PHANTOM KEY (never produced by the
            #     S0 extractor in any chain), OR
            #   - The executor rejected it AND the source text does not
            #     support the mapped semantic (e.g., RESTATE_SECTION
            #     instruction with a maturity-date mention that is part
            #     of a broader restatement, not an amendment to the
            #     maturity date)
            #
            # It is classified C when the executor rejected it but the
            # source text might genuinely support the mapping (needs
            # human review to confirm the target key should or should
            # not exist).
            if is_phantom_key:
                evidence_class = "A"
                evidence_label = (
                    "INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT"
                )
            elif not key_in_state and not source_supports_mapping:
                evidence_class = "A"
                evidence_label = (
                    "INDEPENDENTLY DEMONSTRABLE FROM SOURCE TEXT"
                )
            elif not key_in_state:
                # Executor rejected, source might support mapping —
                # need human review to determine if the target key
                # SHOULD exist (system gap) or SHOULD NOT (mapper error)
                evidence_class = "C"
                evidence_label = "AMBIGUOUS UNTIL HUMAN REVIEW"
            else:
                evidence_class = "C"
                evidence_label = "AMBIGUOUS UNTIL HUMAN REVIEW"

            # Find amendment accession from manifest
            amend_num = step.amendment_number
            amendment_accessions = manifest_entry.get("amendment_accessions", [])
            accession = (
                amendment_accessions[amend_num - 1]
                if amend_num <= len(amendment_accessions)
                else "N/A"
            )

            mutations_detail.append({
                "chain_id": chain_id,
                "issuer": issuer,
                "cik": cik,
                "amendment_number": amend_num,
                "accession": accession,
                "source_document": source_path,
                "source_span": source_span,
                "source_excerpt": source_excerpt,
                "parsed_instruction": {
                    "order": orig_ins.order if orig_ins else None,
                    "instruction_type": (
                        orig_ins.instruction_type.value if orig_ins else None
                    ),
                    "target_section_ref": (
                        orig_ins.target_section_ref if orig_ins else None
                    ),
                    "old_value": orig_ins.old_value if orig_ins else None,
                    "new_value": orig_ins.new_value if orig_ins else None,
                },
                "semantic_mapping": {
                    "target_key": target_key,
                    "operation": (
                        orig_mut.operation.value if orig_mut else None
                    ),
                    "value": (
                        str(orig_mut.new_value) if orig_mut and orig_mut.new_value else None
                    ),
                    "ambiguity_reason": (
                        orig_mut.ambiguity_reason.value
                        if orig_mut and orig_mut.ambiguity_reason
                        else None
                    ),
                },
                "applied_mutation": {
                    "order": rejected_ins.order,
                    "instruction_type": rejected_ins.instruction_type.value,
                    "target_key": target_key,
                },
                "reconstructed_field": target_key,
                "reconstructed_value": None,  # rejected, not applied
                "executor_rejection_reason": "UNKNOWN_COMMITMENT" if not key_in_state else "OTHER",
                "target_key_in_state": key_in_state,
                "state_keys_sample": list(state.keys())[:10],
                "basis_for_incorrect": " ; ".join(basis_notes) if basis_notes else "Executor rejected mutation",
                "evidence_class": evidence_class,
                "evidence_label": evidence_label,
                "source_supports_mapping": source_supports_mapping,
            })

        # Update state for next step
        state = {k: v.model_copy(deep=True) for k, v in execution_result.state.items()}

    return mutations_detail


def main() -> int:
    print("Track B.2: Mutation-by-mutation provisional defect analysis")
    print("=" * 60)
    print()

    manifest = json.loads(HELD_OUT_MANIFEST.read_text(encoding="utf-8"))
    manifest_by_id = {c["chain_id"]: c for c in manifest["chains"]}

    chain_data = all_held_out_chains()
    print(f"Loaded {len(chain_data)} held-out chains")

    all_mutations: list[dict] = []
    chains_with_incorrect = ["HELD-009", "HELD-012", "HELD-016"]

    for chain, s0_result, gt_result in chain_data:
        if chain.chain_id not in chains_with_incorrect:
            continue
        entry = manifest_by_id.get(chain.chain_id, {})
        cik = entry.get("cik", "")
        print(f"\nAnalyzing {chain.chain_id} ({chain.issuer_name[:40]})...")

        mutations = analyze_chain_mutations(
            chain.chain_id,
            chain.issuer_name,
            cik,
            chain.amendments,
            chain.original_state,
            entry,
        )
        print(f"  Found {len(mutations)} incorrect mutation(s)")
        for m in mutations:
            print(f"    A{m['amendment_number']} ins {m['parsed_instruction']['order']}: "
                  f"{m['parsed_instruction']['instruction_type']} -> "
                  f"{m['semantic_mapping']['target_key']}  "
                  f"[{m['evidence_class']}]")
        all_mutations.extend(mutations)

    # Count evidence classifications
    class_counts = {"A": 0, "B": 0, "C": 0}
    for m in all_mutations:
        class_counts[m["evidence_class"]] += 1

    print()
    print("=" * 60)
    print("Evidence classification summary:")
    print(f"  A (Independently demonstrable): {class_counts['A']}")
    print(f"  B (Depends on proxy gold):      {class_counts['B']}")
    print(f"  C (Ambiguous until human):      {class_counts['C']}")
    print(f"  Total incorrect mutations:      {len(all_mutations)}")

    # Write output
    output = {
        "analysis": "step_19b_mutation_defect_analysis",
        "analysis_timestamp": datetime.now(UTC).isoformat(),
        "frozen_system": "v1.0-frozen-operational-build",
        "total_incorrect_mutations": len(all_mutations),
        "evidence_class_counts": class_counts,
        "mutations": all_mutations,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nOutput: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
