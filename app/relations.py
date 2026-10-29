"""亲密度（好感度）系统：按「平台 + 用户」分别记，0–100，默认 50。"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import FILES_DIR

REL_PATH: Path = FILES_DIR / "relations.json"
DEFAULT_FAVOR = 50


def level(favor: int) -> str:
    if favor >= 95:
        return "特别重要"
    if favor >= 85:
        return "很喜欢"
    if favor >= 70:
        return "挺熟"
    if favor >= 55:
        return "普通朋友"
    if favor >= 40:
        return "眼熟"
    return "生疏"


class Relations:
    def __init__(self, path: Path = REL_PATH):
        self.path = path
        self._lock = threading.RLock()
        self.data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text("utf-8"))
                if isinstance(raw, dict):
                    self.data = raw
        except Exception:
            self.data = {}
        # 旧版灵芥用的是 "lj" 键，迁到 "lingjie"
        legacy = self.data.pop("lj", None)
        if isinstance(legacy, dict) and legacy:
            cur = self.data.get("lingjie")
            if not isinstance(cur, dict):
                cur = {}
            for k, v in legacy.items():
                cur.setdefault(k, v)
            self.data["lingjie"] = cur
        # 好感按「平台+当前账号」分开：把裸平台键迁到 平台@uid
        moved = False
        for platform in ("hlx", "lingjie"):
            try:
                uid = int(__import__("app.config", fromlist=["CFG"]).CFG.get(
                    f"{platform}.uid", 0) or 0)
            except Exception:
                uid = 0
            if uid <= 0:
                continue
            key = f"{platform}@{uid}"
            bare = self.data.pop(platform, None)
            if isinstance(bare, dict) and bare:
                cur = self.data.get(key)
                if not isinstance(cur, dict):
                    cur = {}
                for k, v in bare.items():
                    cur.setdefault(k, v)
                self.data[key] = cur
                moved = True
        if moved or legacy:
            self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), "utf-8")
        except Exception:
            pass

    def _key(self, platform: str) -> str:
        try:
            from .config import CFG
            uid = int(CFG.get(f"{platform}.uid", 0) or 0)
        except Exception:
            uid = 0
        return f"{platform}@{uid}" if uid else platform

    def rekey(self, platform: str) -> None:
        """登录后调用：把裸平台键（登录前写的）并进 平台@uid。"""
        try:
            from .config import CFG
            uid = int(CFG.get(f"{platform}.uid", 0) or 0)
        except Exception:
            uid = 0
        if uid <= 0:
            return
        with self._lock:
            key = f"{platform}@{uid}"
            bare = self.data.pop(platform, None)
            if isinstance(bare, dict) and bare:
                cur = self.data.get(key)
                if not isinstance(cur, dict):
                    cur = {}
                for k, v in bare.items():
                    cur.setdefault(k, v)
                self.data[key] = cur
                self._save()

    def _bucket(self, platform: str) -> dict:
        key = self._key(platform)
        b = self.data.get(key)
        if not isinstance(b, dict):
            b = {}
            self.data[key] = b
        return b

    def get(self, platform: str, uid: int, nick: str = "") -> int:
        if not uid:
            return DEFAULT_FAVOR
        with self._lock:
            b = self._bucket(platform)
            rec = b.get(str(uid))
            if isinstance(rec, dict):
                return int(rec.get("favor", DEFAULT_FAVOR))
            return int(rec) if isinstance(rec, (int, float)) else DEFAULT_FAVOR

    def nick(self, platform: str, uid: int) -> str:
        with self._lock:
            rec = self._bucket(platform).get(str(uid))
            return rec.get("nick", "") if isinstance(rec, dict) else ""

    def add(self, platform: str, uid: int, delta: int, nick: str = "") -> int:
        if not uid:
            return DEFAULT_FAVOR
        with self._lock:
            b = self._bucket(platform)
            cur = b.get(str(uid))
            favor = int(cur.get("favor", DEFAULT_FAVOR)) if isinstance(cur, dict) \
                else (int(cur) if isinstance(cur, (int, float)) else DEFAULT_FAVOR)
            nk = nick or (cur.get("nick", "") if isinstance(cur, dict) else "")
            favor = max(0, min(100, favor + delta))
            b[str(uid)] = {"favor": favor, "nick": nk}
            self._save()
            return favor

    def top(self, platform: str, n: int = 10) -> list[tuple[int, str, int]]:
        with self._lock:
            b = self._bucket(platform)
            rows = []
            for uid, rec in b.items():
                if isinstance(rec, dict):
                    rows.append((int(uid), rec.get("nick", ""), int(rec.get("favor", DEFAULT_FAVOR))))
                elif isinstance(rec, (int, float)):
                    rows.append((int(uid), "", int(rec)))
        rows.sort(key=lambda x: x[2], reverse=True)
        return rows[:n]

    def all(self, platform: str) -> dict:
        with self._lock:
            return dict(self._bucket(platform))


REL = Relations()
