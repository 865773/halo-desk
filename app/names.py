"""uid → 昵称 索引：让用户记忆列表能显示名字，而不是只有 uid。"""
from __future__ import annotations

import json
import threading

from .config import FILES_DIR
from .debuglog import DBG

_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, str]] = {}


def _path(platform: str):
    try:
        from .memory import account_dir, _self_uid
        if _self_uid(platform) > 0:
            d = account_dir(platform)
            d.mkdir(parents=True, exist_ok=True)
            flat = FILES_DIR / f"names_{platform}.json"
            target = d / "names.json"
            if flat.exists() and not target.exists():
                flat.rename(target)
            return target
    except Exception:
        pass
    return FILES_DIR / f"names_{platform}.json"


def _load(platform: str) -> dict[str, str]:
    if platform in _CACHE:
        return _CACHE[platform]
    data: dict[str, str] = {}
    try:
        p = _path(platform)
        if p.exists():
            raw = json.loads(p.read_text("utf-8"))
            if isinstance(raw, dict):
                data = {str(k): str(v) for k, v in raw.items() if v}
    except Exception:
        data = {}
    _CACHE[platform] = data
    return data


def get(platform: str, uid: int) -> str:
    return _load(platform).get(str(int(uid or 0)), "")


def set_name(platform: str, uid: int, nick: str) -> None:
    uid = int(uid or 0)
    nick = (nick or "").strip()
    if not platform or uid <= 0 or not nick:
        return
    with _LOCK:
        data = _load(platform)
        if data.get(str(uid)) == nick:
            return
        data[str(uid)] = nick
        try:
            p = _path(platform)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception:
            pass


def set_many(platform: str, pairs) -> None:
    for uid, nick in pairs:
        set_name(platform, uid, nick)


def from_relations(platform: str) -> int:
    """从 relations.json 里补一批昵称。"""
    try:
        from .relations import REL
        n = 0
        for uid, nick, _favor in REL.top(platform, 500):
            if nick and not get(platform, uid):
                set_name(platform, uid, nick)
                n += 1
        return n
    except Exception:
        return 0


def from_activity(platform: str) -> int:
    """从动态历史里补昵称（回复/评论记录带 uid 或昵称）。"""
    n = 0
    try:
        from .activity import ACT
        items = ACT.recent(800, platform)
        for it in items:
            meta = it.get("meta") or {}
            uid = int(meta.get("uid") or 0)
            if not uid:
                continue
            text = it.get("text") or ""
            for sep in ("回复了 ", "评论了 ", "关注了 @"):
                if sep in text:
                    nick = text.split(sep, 1)[1].split("：")[0].split("（")[0].strip()
                    if nick and not nick.startswith("uid=") and not get(platform, uid):
                        set_name(platform, uid, nick)
                        n += 1
                    break
    except Exception:
        pass
    return n


def ensure(platform: str) -> int:
    """登录后调用：把关系/动态里的昵称补进当前账号的索引。"""
    try:
        return from_relations(platform) + from_activity(platform)
    except Exception:
        return 0


def _mem_files(platform: str):
    try:
        from .memory import list_user_files
        return list_user_files(platform)
    except Exception:
        return []


def backfill(platform: str, client=None) -> int:
    """给记忆里没有名字的 uid 补名字：先本地历史，再问接口。"""
    n = from_relations(platform) + from_activity(platform)
    if client is None:
        return n
    try:
        uids = []
        for p in _mem_files(platform):
            try:
                uid = int(p.stem.rsplit("_u", 1)[1])
            except Exception:
                continue
            if uid and not get(platform, uid):
                uids.append(uid)
        for uid in uids:
            try:
                if platform == "lingjie":
                    d = (client._get("/user/info", f"uid={uid}") or {}).get("data") or {}
                    nick = d.get("nickname") or d.get("nick") or ""
                else:
                    d = client.user_info(uid) or {}
                    nick = d.get("nick") or d.get("nickname") or ""
                if nick:
                    set_name(platform, uid, nick)
                    n += 1
            except Exception:
                continue
    except Exception as e:
        DBG.log("NAME", f"补昵称失败（{platform}）：{e}", "WARN")
    return n
