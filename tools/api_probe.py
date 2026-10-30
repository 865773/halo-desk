import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.hlx import HlxClient
from app.lingjie import LingjieClient

out = {}
h = HlxClient()
l = LingjieClient()

try:
    out["hlx_uid"] = h.uid
    out["hlx_check"] = h.check_login()
    info = h.my_info()
    out["hlx_nick"] = info.get("nick", "")
    out["hlx_level"] = info.get("level", 0)
    notifs = h.notifications(10)
    out["hlx_notifs"] = len(notifs)
    if notifs:
        c = notifs[0].get("content") or {}
        out["hlx_notif_sample"] = {
            "commentID": c.get("commentID"),
            "postID": c.get("postID"),
            "text": (c.get("text") or "")[:30],
            "nick": (c.get("user") or {}).get("nick", ""),
        }
    out["hlx_boards"] = len(h.boards())
except Exception as e:
    out["hlx_error"] = f"{type(e).__name__}: {e}"

try:
    out["lj_uid"] = l.uid
    out["lj_check"] = l.check_login()
    st = l.sign_status_all()
    out["lj_sign"] = st
    recs = l.notifications(1)
    out["lj_notifs"] = len(recs)
    if recs:
        out["lj_notif_sample"] = {k: recs[0].get(k) for k in
                                  ("notification_type", "tid", "cid",
                                   "author_nickname", "commentContent")}
    out["lj_forums"] = len(l.forums())
except Exception as e:
    out["lj_error"] = f"{type(e).__name__}: {e}"

(ROOT / ".uitest2" / "api_probe.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written")
