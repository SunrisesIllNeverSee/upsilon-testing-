from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

KEY = ["document_id", "instruction_id"]

def safe_div(a,b):
    return a/b if b else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", default="results/evaluation.json")
    args = ap.parse_args()

    gold = pd.read_csv(args.gold).fillna("")
    pred = pd.read_csv(args.pred).fillna("")

    for frame, name in [(gold,"gold"),(pred,"pred")]:
        missing=[c for c in KEY+["instruction_type","target_section_ref"] if c not in frame.columns]
        if missing:
            raise SystemExit(f"{name} missing columns: {missing}")

    gkeys=set(map(tuple,gold[KEY].astype(str).values.tolist()))
    pkeys=set(map(tuple,pred[KEY].astype(str).values.tolist()))
    tp=len(gkeys&pkeys); fp=len(pkeys-gkeys); fn=len(gkeys-pkeys)

    precision=safe_div(tp,tp+fp)
    recall=safe_div(tp,tp+fn)
    f1=safe_div(2*precision*recall,precision+recall)

    merged=gold.merge(pred,on=KEY,how="inner",suffixes=("_gold","_pred"))
    type_acc=(merged["instruction_type_gold"]==merged["instruction_type_pred"]).mean() if len(merged) else 0
    target_acc=(merged["target_section_ref_gold"]==merged["target_section_ref_pred"]).mean() if len(merged) else 0

    for fld in ["old_value","new_value"]:
        if f"{fld}_gold" in merged and f"{fld}_pred" in merged:
            merged[f"{fld}_exact"] = merged[f"{fld}_gold"].astype(str)==merged[f"{fld}_pred"].astype(str)

    result={
        "gold_instructions": int(len(gold)),
        "predicted_instructions": int(len(pred)),
        "detection":{"precision":precision,"recall":recall,"f1":f1,"tp":tp,"fp":fp,"fn":fn},
        "classification":{"instruction_type_accuracy":float(type_acc)},
        "target_resolution":{"section_exact_accuracy":float(target_acc)},
    }
    for fld in ["old_value","new_value"]:
        col=f"{fld}_exact"
        if col in merged:
            result.setdefault("field_extraction",{})[f"{fld}_exact_accuracy"]=float(merged[col].mean())

    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding="utf-8")

    md = out.with_suffix(".md")
    md.write_text(
f"""# Held-Out Evaluation Results

| Metric | Result |
|---|---:|
| Instruction detection precision | {precision:.3f} |
| Instruction detection recall | {recall:.3f} |
| Instruction detection F1 | {f1:.3f} |
| Instruction type accuracy | {type_acc:.3f} |
| Target section exact accuracy | {target_acc:.3f} |

Gold instructions: {len(gold)}  
Predicted instructions: {len(pred)}
""", encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
