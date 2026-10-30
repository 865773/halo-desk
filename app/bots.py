"""疑似机器人标记：高频互刷过的账号，后续默认不回复。"""
from __future__ import annotations

import json
import time

from .config import CFG, FILES_DIR

_PATH = FILES_DIR / "suspected_bots.json"


def _load() -> dict:
    try:
        if _PATH.exists():
            data = json.loads(_PATH.read_text("utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    try:
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    except Exception:
        pass


def _key(platform: str, uid: int) -> str:
    return f"{platform}:{int(uid or 0)}"


def mark(platform: str, uid: int, nick: str = "", reason: str = "") -> None:
    if not uid:
        return
    data = _load()
    data[_key(platform, uid)] = {
        "nick": nick or "",
        "reason": reason or "高频互刷",
        "ts": time.time(),
    }
    _save(data)


def info(platform: str, uid: int) -> dict:
    return _load().get(_key(platform, uid)) or {}


def is_bot(platform: str, uid: int) -> bool:
    rec = info(platform, uid)
    if not rec:
        return False
    days = float(CFG.get("auto.bot_skip_days", 30) or 30)
    return time.time() - float(rec.get("ts", 0) or 0) < days * 86400


def unmark(platform: str, uid: int) -> None:
    data = _load()
    if data.pop(_key(platform, uid), None) is not None:
        _save(data)


def all_bots() -> dict:
    return _load()
