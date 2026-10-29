"""互动统计：本地按天计数，不上传（原版的上报仓库不再使用）。"""
from __future__ import annotations

import json
import threading
from datetime import datetime

from .config import FILES_DIR

STATS_PATH = FILES_DIR / "stats.json"

KIND_LABEL = {
    "signin": "签到",
    "reply": "回复",
    "comment": "评论",
    "post": "发帖",
    "like": "点赞",
    "favorite": "收藏",
    "follow": "关注",
    "tip": "送葫芦",
    "genimg": "生图",
    "chat": "聊天",
    "roam": "逛社区",
}

_LOCK = threading.RLock()


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        if STATS_PATH.exists():
            data = json.loads(STATS_PATH.read_text("utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"day": _today(), "counts": {}, "total": {}}


def bump(kind: str, n: int = 1) -> None:
    if kind not in KIND_LABEL:
        return
    with _LOCK:
        data = _load()
        if data.get("day") != _today():
            data = {"day": _today(), "counts": {}, "total": data.get("total", {})}
        data.setdefault("counts", {})
        data.setdefault("total", {})
        data["counts"][kind] = int(data["counts"].get(kind, 0)) + n
        data["total"][kind] = int(data["total"].get(kind, 0)) + n
        try:
            STATS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        except Exception:
            pass


def today_counts() -> dict:
    data = _load()
    if data.get("day") != _today():
        return {}
    return dict(data.get("counts", {}))


def summary() -> str:
    c = today_counts()
    if not c:
        return "今天还没有互动"
    return " · ".join(f"{KIND_LABEL.get(k, k)} {v}" for k, v in c.items() if v)
