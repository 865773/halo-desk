"""大肥鱼的记忆 / 心情 / 生活记录，落盘为本地文本。

- 通用记忆 memory.txt：两个社区共用（大肥鱼自己的事、对主人的了解）
- 用户记忆 mem_<平台>_u<uid>.txt：按平台分开，避免两个社区 uid 撞车串味
- 生活记忆 life.txt：共用，跨天自动清空
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from .config import FILES_DIR, CFG

MEMORY_FILE = FILES_DIR / "memory.txt"
LIFE_FILE = FILES_DIR / "life.txt"
MOOD_FILE = FILES_DIR / "mood.json"
LOG_FILE = FILES_DIR / "log.txt"

PLATFORM_TAG = {"hlx": "葫芦侠", "lingjie": "灵芥", "": ""}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now().strftime("%m-%d %H:%M")


ACCOUNTS_DIR = FILES_DIR.parent / "账号"
ACCOUNT_NAME = {"hlx": "葫芦侠", "lingjie": "灵芥"}


def _self_uid(platform: str) -> int:
    """当前登录账号的 uid（切换账号后用户记忆按账号分目录）。"""
    if not platform:
        return 0
    try:
        return int(CFG.get(f"{platform}.uid", 0) or 0)
    except Exception:
        return 0


def account_dir(platform: str):
    uid = _self_uid(platform)
    if not platform or uid <= 0:
        return FILES_DIR
    return ACCOUNTS_DIR / ACCOUNT_NAME.get(platform, platform) / str(uid)


def _user_file(uid: int, platform: str = ""):
    if platform:
        return account_dir(platform) / f"mem_{platform}_u{uid}.txt"
    return FILES_DIR / f"mem_u{uid}.txt"


def list_user_files(platform: str = "") -> list:
    """当前账号下的用户记忆文件。"""
    d = account_dir(platform) if platform else FILES_DIR
    pat = f"mem_{platform}_u*.txt" if platform else "mem_u*.txt"
    try:
        return sorted(d.glob(pat))
    except Exception:
        return []


def ensure_account(platform: str) -> None:
    """登录后调用：把旧数据迁进该账号目录。"""
    _migrate_legacy()


def _migrate_legacy() -> None:
    """旧命名 mem_lj_u* → mem_lingjie_u*；旧平铺文件 → 当前账号目录。"""
    try:
        for p in FILES_DIR.glob("mem_lj_u*.txt"):
            target = FILES_DIR / p.name.replace("mem_lj_", "mem_lingjie_")
            if not target.exists():
                p.rename(target)
    except Exception:
        pass
    for platform in ("hlx", "lingjie"):
        try:
            d = account_dir(platform)
            if d == FILES_DIR:
                continue
            d.mkdir(parents=True, exist_ok=True)
            # 旧平铺文件
            for p in FILES_DIR.glob(f"mem_{platform}_u*.txt"):
                target = d / p.name
                if not target.exists():
                    p.rename(target)
            # 旧 accounts/<platform>_<uid> 目录
            old = FILES_DIR / "accounts" / f"{platform}_{_self_uid(platform)}"
            if old.exists() and old != d:
                for p in old.glob("mem_*.txt"):
                    target = d / p.name
                    if not target.exists():
                        p.rename(target)
                for p in old.glob("names.json"):
                    target = d / "names.json"
                    if not target.exists():
                        p.rename(target)
        except Exception:
            pass


_migrate_legacy()


def append_line(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{_now()}] {text.strip()}\n")


def read_lines(path, n: int = 10) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = [ln.strip() for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except Exception:
        return []
    return lines[-n:]


def remember(text: str, uid: int = 0, platform: str = "") -> None:
    """记一条通用记忆；给了 uid 就同时记到该平台的用户记忆里。"""
    if not text.strip():
        return
    append_line(MEMORY_FILE, text)
    if uid:
        uf = _user_file(uid, platform)
        append_line(uf, text)
        maybe_compress(uf, "user")
    _trim(MEMORY_FILE, int(CFG.get("fish.memory_max", 1500) or 1500))
    maybe_compress(MEMORY_FILE, "general")


def _trim(path, max_chars: int) -> None:
    try:
        raw = path.read_text("utf-8")
        if len(raw) > max_chars:
            path.write_text(raw[-max_chars:], "utf-8")
    except Exception:
        pass


# ---------------- 记忆压缩 ----------------

_LIMIT_KEYS = {
    "general": ("fish.memory_max", 1500),
    "user": ("fish.user_mem_max", 800),
    "life": ("fish.life_max", 1200),
}
_COMPRESSING: set[str] = set()


def mem_limit(kind: str) -> int:
    key, default = _LIMIT_KEYS.get(kind, ("fish.memory_max", 1500))
    return max(200, int(CFG.get(key, default) or default))


def compress(path, kind: str = "general", keep_ratio: float = 0.55) -> bool:
    """超过字数上限就让大肥鱼总结一次，只留关键节点。"""
    key = str(path)
    if key in _COMPRESSING:
        return False
    try:
        raw = path.read_text("utf-8")
    except Exception:
        return False
    limit = mem_limit(kind)
    if len(raw) <= limit:
        return False
    _COMPRESSING.add(key)
    try:
        from . import ai
        keep = max(200, int(limit * keep_ratio))
        txt = ai.ask(
            "把你下面的记忆压缩成一段，最多 " + str(keep) + " 字。"
            "只保留关键节点：人物和称呼、重要事件、喜好与厌恶、约定过的事、最近发生的事；"
            "删掉重复和寒暄，用「；」分隔，不要编号、不要解释。",
            raw, CFG.get("ai.model_basic"))
        out = " ".join((txt or "").split())
        if not out:
            return False
        path.write_text("[压缩] " + out[:keep] + "\n", "utf-8")
        return True
    except Exception as e:
        from .debuglog import DBG
        DBG.log("MEM", f"压缩失败（{kind}）：{e}", "WARN")
        return False
    finally:
        _COMPRESSING.discard(key)


def compress_all() -> list[str]:
    """手动触发：压缩通用/生活/所有用户记忆。返回压缩了哪些。"""
    done = []
    if compress(MEMORY_FILE, "general"):
        done.append("通用记忆")
    if compress(LIFE_FILE, "life"):
        done.append("生活记忆")
    for p in list(FILES_DIR.glob("mem_*_u*.txt")) + list(ACCOUNTS_DIR.glob("*/mem_*_u*.txt")):
        if compress(p, "user"):
            done.append(p.stem)
    return done


def user_count(platform: str = "") -> int:
    return len(list_user_files(platform))


def maybe_compress(path, kind: str = "general") -> None:
    try:
        if path.exists() and path.stat().st_size > mem_limit(kind):
            compress(path, kind)
    except Exception:
        pass


def recent(n: int = 8) -> str:
    return "\n".join(read_lines(MEMORY_FILE, n))


def recent_user(uid: int, n: int = 6, platform: str = "") -> str:
    """读某个人的记忆：优先本平台的，其次兼容旧版不分平台的。"""
    if not uid:
        return ""
    lines = read_lines(_user_file(uid, platform), n)
    if not lines and platform:
        lines = read_lines(FILES_DIR / f"mem_u{uid}.txt", n)
    return "\n".join(lines)


def life_append(text: str) -> None:
    append_line(LIFE_FILE, text)
    maybe_compress(LIFE_FILE, "life")


def recent_life(n: int = 5) -> str:
    return "\n".join(read_lines(LIFE_FILE, n))


def reset_life_if_new_day() -> None:
    try:
        if LIFE_FILE.exists():
            first = LIFE_FILE.read_text("utf-8").splitlines()[0]
            if _today() not in first:
                LIFE_FILE.write_text("", "utf-8")
    except Exception:
        pass


# ---------------- 心情 ----------------

def get_mood() -> int:
    try:
        if MOOD_FILE.exists():
            return int(json.loads(MOOD_FILE.read_text("utf-8")).get("mood", 60))
    except Exception:
        pass
    return int(CFG.get("fish.mood", 60) or 60)


def set_mood(v: int) -> int:
    v = max(0, min(100, int(v)))
    CFG.set("fish.mood", v)
    try:
        MOOD_FILE.write_text(json.dumps({"mood": v, "at": _now()},
                                        ensure_ascii=False), "utf-8")
    except Exception:
        pass
    return v


def nudge_mood(delta: int) -> int:
    return set_mood(get_mood() + delta)


def mood_label(v: Optional[int] = None) -> str:
    v = get_mood() if v is None else v
    if v >= 85:
        return "超级开心"
    if v >= 70:
        return "开心"
    if v >= 50:
        return "还不错"
    if v >= 30:
        return "有点闷"
    return "不高兴"


def log(text: str) -> None:
    append_line(LOG_FILE, text)
