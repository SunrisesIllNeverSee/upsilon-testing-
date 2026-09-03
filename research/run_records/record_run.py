from __future__ import annotations
import argparse, hashlib, json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def git(*args):
    try: return subprocess.check_output(["git",*args],text=True).strip()
    except Exception: return None
def sh(cmd):
    try: return subprocess.check_output(cmd,text=True).strip()
    except Exception: return None
def hash_tree(path):
    p=Path(path); out={}
    if p.exists():
        for f in sorted(p.rglob("*")):
            if f.is_file(): out[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    return out

ap=argparse.ArgumentParser()
ap.add_argument("--label",required=True)
ap.add_argument("--inputs",default="data/smoke")
ap.add_argument("--outputs",default="results")
args=ap.parse_args()

lock=Path("research/PREREGISTRATION_LOCK.json")
record={
    "label":args.label,
    "recorded_at_utc":datetime.now(timezone.utc).isoformat(),
    "platform":platform.platform(),
    "machine":platform.machine(),
    "python":sys.version,
    "git_commit":git("rev-parse","HEAD"),
    "git_status":git("status","--porcelain"),
    "pip_freeze":sh([sys.executable,"-m","pip","freeze"]),
    "protocol_lock":json.loads(lock.read_text()) if lock.exists() else None,
    "input_hashes":hash_tree(args.inputs),
    "output_hashes":hash_tree(args.outputs),
}
out=Path("research/run_records"); out.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
path=out/f"{stamp}_{args.label}.json"
path.write_text(json.dumps(record,indent=2),encoding="utf-8")
print(path)
