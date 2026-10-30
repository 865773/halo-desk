import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hlx import HlxClient
from app.lingjie import LingjieClient

out = {}

h = HlxClient()
try:
    items = h.notifications(3)
    out["hlx"] = []
    for d in items:
        o = {"top_keys": list(d.keys())}
        c = d.get("content")
        if isinstance(c, dict):
            o["content_keys"] = list(c.keys())
            o["content"] = {k: (str(v)[:80] if not isinstance(v, (dict, list)) else v)
                            for k, v in c.items()}
        out["hlx"].append(o)
except Exception as e:
    out["hlx_error"] = repr(e)

l = LingjieClient()
try:
    recs = l.notifications(1)
    out["lj"] = []
    for n in recs[:3]:
        out["lj"].append({k: (str(v)[:80] if not isinstance(v, (dict, list)) else v)
                          for k, v in n.items()})
except Exception as e:
    out["lj_error"] = repr(e)

(ROOT / ".uitest2" / "notif_dump.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok")
