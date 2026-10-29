"""亲密度到阈值自动关注。"""
from __future__ import annotations

from .config import CFG
from .debuglog import DBG


def auto_follow_if_close(platform: str, client, uid: int, nick: str = "",
                         log=None) -> bool:
    """亲密度 >= 阈值且还没关注，就替大肥鱼关注一下。"""
    if not CFG.get("fish.auto_follow", True):
        return False
    try:
        uid = int(uid or 0)
    except Exception:
        uid = 0
    if uid <= 0:
        return False
    try:
        if uid == int(getattr(client, "uid", 0) or 0):
            return False
    except Exception:
        pass
    threshold = int(CFG.get("fish.auto_follow_favor", 70) or 70)
    from .relations import REL
    favor = REL.get(platform, uid)
    if favor < threshold:
        return False
    try:
        ok, msg = client.follow_once(uid)
    except Exception as e:  # noqa: BLE001
        DBG.log("FOLLOW", f"自动关注失败：{e}", "WARN")
        return False
    if not ok:
        return False
    name = "葫芦侠" if platform == "hlx" else "灵芥"
    try:
        from .activity import record
        record("follow", f"亲密度 {favor} 自动关注 @{nick or uid}",
               platform, uid=uid, reason=f"亲密度到 {threshold}")
    except Exception:
        pass
    try:
        from . import memory
        memory.remember(f"在{name}关注了 @{nick or uid}（亲密度 {favor}）",
                        uid, platform)
    except Exception:
        pass
    if log:
        try:
            log(f"亲密度 {favor}，自动关注 @{nick or uid}")
        except Exception:
            pass
    DBG.log("FOLLOW", f"{name} 亲密度 {favor} 自动关注 {nick or uid}")
    return True
