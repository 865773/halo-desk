"""动态系统：大肥鱼做过的事都按时间线记下来（签到/回复/发帖/生图/聊天…）。"""
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
    "chat": "聊天",
    "genimg": "生图",
    "message": "消息",
    "error": "出错",
    "system": "系统",
}

PLATFORM_LABEL = {"hlx": "葫芦侠", "lingjie": "灵芥", "": "大肥鱼"}


class Activity(QObject):
    added = Signal(dict)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            if ACTIVITY_PATH.exists():
                lines = ACTIVITY_PATH.read_text("utf-8", "replace").splitlines()[-500:]
                for ln in lines:
                    try:
                        self._items.append(json.loads(ln))
                    except Exception:
                        continue
        except Exception:
            pass

    def add(self, kind: str, text: str, platform: str = "", meta: dict | None = None) -> dict:
        item = {
            "ts": datetime.now().strftime("%m-%d %H:%M:%S"),
            "kind": kind,
            "platform": platform,
            "text": text,
            "meta": meta or {},
        }
        with self._lock:
            self._items.append(item)
            try:
                ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
                with ACTIVITY_PATH.open("a", encoding="utf-8") as f:
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

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            try:
                ACTIVITY_PATH.write_text("", "utf-8")
            except Exception:
                pass


ACT = Activity()


def record(kind: str, text: str, platform: str = "", **meta) -> None:
    ACT.add(kind, text, platform, meta)
    try:
        from .stats import bump
        bump(kind)
    except Exception:
        pass
