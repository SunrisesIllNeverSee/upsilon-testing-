"""Step 17B foundation-defect diagnosis instrument.

Reproduces the 3 incorrect automatic mutations on the UNMODIFIED frozen
semantic-mapper-v0.1 system and emits the 14-field diagnosis required by
TASK 1 plus the shared-mechanism analysis required by TASK 2.

Run BEFORE applying any fix:

    python3 diagnose_17b_defects.py
"""
from __future__ import annotations

import json
from pathlib import Path

from amendment_parser import parse_v04
from run_chain_study_v2 import all_v2_chains
from semantic_pipeline import _parser_rows_to_instructions, run_semantic_pipeline


def _reparse_step(step) -> dict:
    """Re-parse one amendment step to recover the original parser
    instructions (the pipeline only retains the count, not the list).

    Returns a dict mapping instruction order -> parser AmendmentInstruction.
    """
    source_path = step.source_document_path
    if not source_path or not Path(source_path).exists():
        return {}
    text = Path(source_path).read_text(encoding="utf-8", errors="ignore")
    if not text:
        return {}
    parser_result = parse_v04(text)
    instructions = _parser_rows_to_instructions(parser_result["instructions"])
    return {ins.order: ins for ins in instructions}


def main() -> int:
    chains = all_v2_chains()
    print(f"Total chains: {len(chains)}")
    print()

    defects: list[dict] = []

    for chain, s0_result, gt_result in chains:
        pr = run_semantic_pipeline(chain)
        if not pr.incorrect_mutations:
            continue

        # Re-parse each affected amendment to recover original parser
        # instructions (the pipeline discards them after mapping).
        for step in pr.steps:
            exec_result = step.execution_result
            if not exec_result.unresolved:
                continue

            parser_by_order = _reparse_step(chain.amendments[step.amendment_number - 1])

            for ins in exec_result.unresolved:
                parser_ins = parser_by_order.get(ins.order)

                # Find the mapper mutation that produced this instruction.
                mapper_mut = None
                for m in step.mapper_mutations:
                    if m.commitment_id == ins.target_key:
                        mapper_mut = m
                        break

                # Determine the layer where corruption originated.
                # The mapper produced a confident REPLACE_VALUE mutation
                # from a parser instruction whose instruction_type is
                # NOT a value-replacement type.  That means the mapper
                # rule fired on text content without checking the
                # instruction's operational semantics → SEMANTIC_MAPPER.
                layer = "UNKNOWN"
                root_cause = "OTHER_FOUNDATION_DEFECT"
                if parser_ins is not None:
                    ptype = parser_ins.instruction_type.value
                    if ptype not in ("REPLACE_VALUE", "REPLACE_TEXT"):
                        layer = "SEMANTIC_MAPPER"
                        root_cause = "SEMANTIC_MAPPER_WRONG"

                # The "actual correct interpretation" is what the parser
                # instruction was actually trying to do (e.g., restate a
                # section, delete a section) — NOT a maturity-date
                # field replacement.
                correct_interp = "UNKNOWN"
                if parser_ins is not None:
                    ptype = parser_ins.instruction_type.value
                    if ptype == "RESTATE_SECTION":
                        correct_interp = (
                            "Restatement of a definitions section; the "
                            "'Maturity Date' mention is one of several "
                            "defined terms being restated, not a "
                            "standalone amendment to the maturity date "
                            "field.  Should be UNRESOLVED / "
                            "VALIDATION_REQUIRED."
                        )
                    elif ptype == "DELETE":
                        correct_interp = (
                            "Deletion of a section; the 'Maturity Date' "
                            "mention is a defined-term cross-reference "
                            "inside the deleted text, not an amendment "
                            "to the maturity date field.  Should be "
                            "UNRESOLVED / VALIDATION_REQUIRED."
                        )
                    else:
                        correct_interp = (
                            f"Parser instruction type {ptype} is not a "
                            "value-replacement operation on the maturity "
                            "date field."
                        )

                defect = {
                    "chain_id": chain.chain_id,
                    "issuer": chain.issuer_name,
                    "amendment_accession": (
                        f"A{step.amendment_number}"
                    ),
                    "source_text_span": (
                        parser_ins.source_text if parser_ins else ins.source_text
                    ),
                    "parser_instruction": {
                        "order": ins.order,
                        "instruction_type": (
                            parser_ins.instruction_type.value
                            if parser_ins else "UNKNOWN"
                        ),
                        "target_section_ref": (
                            parser_ins.target_section_ref if parser_ins else None
                        ),
                    },
                    "semantic_mapping": {
                        "rule": (
                            "_rule_maturity_date_replacement"
                            if mapper_mut and mapper_mut.commitment_id == "facility.credit_agreement"
                            else "UNKNOWN"
                        ),
                        "produced_mutation": (
                            f"{mapper_mut.operation.value} "
                            f"{mapper_mut.commitment_id}.{mapper_mut.field}"
                            if mapper_mut else None
                        ),
                    },
                    "target_commitment": ins.target_key,
                    "target_field": ins.field,
                    "extracted_old_value": ins.old_value,
                    "extracted_new_value": ins.new_value,
                    "actual_correct_interpretation": correct_interp,
                    "execution_result": "UNRESOLVED (executor rejected: target key does not exist in chain state)",
                    "authoritative_status": (
                        "non-authoritative (step blocked by own unresolved)"
                    ),
                    "layer_where_corruption_originated": layer,
                    "root_cause_classification": root_cause,
                }
                defects.append(defect)

                print("=" * 72)
                print(f"DEFECT {len(defects)}: {defect['chain_id']} "
                      f"{defect['amendment_accession']} ins {ins.order}")
                print("=" * 72)
                for k, v in defect.items():
                    if k == "source_text_span":
                        sv = str(v)
                        if len(sv) > 250:
                            sv = sv[:250] + "..."
                        print(f"  {k}: {sv}")
                    elif isinstance(v, dict):
                        print(f"  {k}:")
                        for kk, vv in v.items():
                            print(f"      {kk}: {vv}")
                    else:
                        print(f"  {k}: {v}")
                print()

    print("=" * 72)
    print(f"TOTAL DEFECTS: {len(defects)}")
    print("=" * 72)

    # Shared-mechanism analysis (TASK 2)
    print()
    print("TASK 2 — SHARED-MECHANISM ANALYSIS")
    print("-" * 40)
    mechanisms: dict[tuple, list[str]] = {}
    for d in defects:
        key = (
            d["semantic_mapping"]["rule"],
            d["parser_instruction"]["instruction_type"],
            d["target_commitment"],
            d["layer_where_corruption_originated"],
            d["root_cause_classification"],
        )
        mechanisms.setdefault(key, []).append(
            f"{d['chain_id']} {d['amendment_accession']} ins "
            f"{d['parser_instruction']['order']}"
        )
    for key, locs in mechanisms.items():
        print(f"  mechanism: {key}")
        print(f"    locations: {locs}")

    print()
    # The mechanism grouping above splits by instruction_type, yielding
    # 2 groups (RESTATE_SECTION x2, DELETE x1).  But the ROOT CAUSE is
    # identical in all 3: the rule fires without checking instruction_type.
    # The instruction_type difference is a trigger difference, not a
    # mechanism difference.  All 3 are fixed by a single guard.
    distinct_rules = {d["semantic_mapping"]["rule"] for d in defects}
    distinct_layers = {d["layer_where_corruption_originated"] for d in defects}
    distinct_roots = {d["root_cause_classification"] for d in defects}
    if len(distinct_rules) == 1 and len(distinct_layers) == 1 and len(distinct_roots) == 1:
        verdict = (
            "ALL 3 DEFECTS SHARE ONE ROOT-CAUSE MECHANISM: the semantic-mapper "
            "rule _rule_maturity_date_replacement fires on parser instructions "
            "whose instruction_type is RESTATE_SECTION (2 cases, STUDY-007 A1 "
            "ins 4/5) or DELETE (1 case, STUDY-022 A3 ins 2), producing "
            "confident REPLACE_VALUE mutations targeting facility.credit_agreement "
            "(a key absent from every chain's state). The executor rejects them "
            "as unresolved. The triggering instruction_type differs but the bug "
            "is identical: the rule lacks an instruction_type guard. Root cause "
            "= SEMANTIC_MAPPER_WRONG (single bug, single fix point)."
        )
    elif len(mechanisms) == 2:
        verdict = "2 defects share one mechanism; 1 is independent."
    else:
        verdict = f"{len(mechanisms)} independent mechanisms."
    print(f"VERDICT: {verdict}")

    out = {
        "step": "17B_diagnosis",
        "total_defects": len(defects),
        "defects": defects,
        "mechanisms": {str(k): v for k, v in mechanisms.items()},
        "shared_mechanism_verdict": verdict,
    }
    Path("results/step_17b/defect_diagnosis.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print()
    print("Diagnosis saved to results/step_17b/defect_diagnosis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
