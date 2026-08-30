from __future__ import annotations
import hashlib, json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

FILES=[
    "research/PREREGISTRATION.md",
    "research/SMOKE_TEST_PROTOCOL.md",
    "research/ANNOTATION_GUIDE.md",
    "research/RESULTS_TEMPLATE.md",
    "research/REPRODUCIBILITY_CHECKLIST.md",
    "smoke_cases.csv",
]

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    try: return subprocess.check_output(["git",*args],text=True).strip()
    except Exception: return None

record={
    "frozen_at_utc":datetime.now(timezone.utc).isoformat(),
    "python":sys.version,
    "platform":platform.platform(),
    "git_commit":git("rev-parse","HEAD"),
    "git_status":git("status","--porcelain"),
    "files":{f:sha(f) for f in FILES},
}
Path("research/PREREGISTRATION_LOCK.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
print(json.dumps(record,indent=2))
