import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hlx import HlxClient
from app.roam import roam_once

logs = []
h = HlxClient()
try:
    summary = roam_once(h, max_steps=2, dry_run=True, log=lambda s: logs.append(s))
except Exception as e:
    summary = {"error": f"{type(e).__name__}: {e}"}

out = {"summary": summary, "logs": logs}
(ROOT / ".uitest2" / "roam_dry.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("done")
