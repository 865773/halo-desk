"""动态系统：大肥鱼做过的事都按时间线记下来（签到/回复/发帖/生图/聊天…）。

动态跟着「平台 + 当前账号」走：data/账号/<平台>/<uid>/activity.jsonl。
没有账号时写到公共 files/activity.jsonl。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from .config import FILES_DIR

ACTIVITY_PATH = FILES_DIR / "activity.jsonl"

KIND_LABEL = {
    "decision": "决策",
    "signin": "签到",
    "reply": "回复",
    "post": "发帖",
    "comment": "评论",
    "like": "点赞",
    "favorite": "收藏",
    "follow": "关注",
    "tip": "打赏",
    "chat": "聊天",
    "genimg": "生图",
    "message": "消息",
    "error": "出错",
    "system": "系统",
}

PLATFORM_LABEL = {"hlx": "葫芦侠", "lingjie": "灵芥", "": "大肥鱼"}


def _account_path(platform: str):
    try:
        from .memory import account_dir, _self_uid
        if platform and _self_uid(platform) > 0:
            d = account_dir(platform)
            d.mkdir(parents=True, exist_ok=True)
            return d / "activity.jsonl"
    except Exception:
        pass
    return ACTIVITY_PATH


def _all_paths():
    paths = [ACTIVITY_PATH]
    for p in ("hlx", "lingjie"):
        try:
            q = _account_path(p)
            if q != ACTIVITY_PATH:
                paths.append(q)
        except Exception:
            pass
    return paths


class Activity(QObject):
    added = Signal(dict)

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._items: list[dict] = []
        self._load()

    def _load(self) -> None:
        self._items = []
        seen = set()
        for path in _all_paths():
            try:
                if not path.exists():
                    continue
                for ln in path.read_text("utf-8", "replace").splitlines()[-500:]:
                    try:
                        it = json.loads(ln)
                    except Exception:
                        continue
                    key = (it.get("ts"), it.get("kind"), it.get("text"))
                    if key in seen:
                        continue
                    seen.add(key)
                    self._items.append(it)
            except Exception:
                continue
        self._items.sort(key=lambda x: x.get("ts", ""))

    def reload(self) -> None:
        with self._lock:
            self._load()

    def add(self, kind: str, text: str, platform: str = "", meta: dict | None = None) -> dict:
        item = {
            "ts": datetime.now().strftime("%m-%d %H:%M:%S"),
            "kind": kind,
            "platform": platform,
            "text": text,
            "meta": meta or {},
        }
        path = _account_path(platform)
        with self._lock:
            self._items.append(item)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            except Exception:
                pass
        self.added.emit(item)
        return item

    def recent(self, n: int = 200, platform: str = "", kind: str = "") -> list[dict]:
        with self._lock:
            items = self._items[-800:]
        if platform:
            items = [x for x in items if x.get("platform") == platform]
        if kind:
            items = [x for x in items if x.get("kind") == kind]
        return items[-n:][::-1]

    def today_counts(self, platform: str = "") -> dict:
        today = datetime.now().strftime("%m-%d")
        out: dict[str, int] = {}
        for it in self.recent(500, platform):
            if not str(it.get("ts", "")).startswith(today):
                continue
            k = it.get("kind", "")
            out[k] = out.get(k, 0) + 1
        return out

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            for path in _all_paths():
                try:
                    path.write_text("", "utf-8")
                except Exception:
                    pass


ACT = Activity()


def record(kind: str, text: str, platform: str = "", **meta) -> None:
    ACT.add(kind, text, platform, meta)
    try:
        from .stats import bump
        bump(kind, platform)
    except Exception:
        pass
