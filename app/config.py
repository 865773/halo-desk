"""配置与本地文件存储。"""
from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path

APP_NAME = "HaloDesk"
APP_TITLE = "大肥鱼桌面版"


_DATA_DIR_CACHE: Path | None = None


def _writable(p: Path) -> bool:
    try:
        probe = p / ".write_test"
        probe.write_text("1", "utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def data_dir() -> Path:
    """优先 %APPDATA%\\HaloDesk；不可写时退到程序目录的 data/。

    某些受限环境（沙盒、受控企业目录）会禁止写入 AppData，
    退而求其次放在 exe 旁边，保证账号和记忆不会丢。
    这个函数保证不抛异常：全部失败时返回一个“尽力而为”的目录。
    """
    global _DATA_DIR_CACHE
    if _DATA_DIR_CACHE is not None:
        return _DATA_DIR_CACHE

    override = (os.environ.get("HALODESK_HOME") or "").strip()
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    else:
        # 便携优先：数据放在 exe 旁边，整个文件夹拷走就能用
        try:
            exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
                else Path(__file__).resolve().parent.parent
            candidates.append(exe_dir / "data")
        except Exception:
            pass
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        candidates.append(Path(base) / APP_NAME)
        candidates.append(Path.home() / ".halodesk")
        candidates.append(Path.cwd() / "halodesk-data")

    for p in candidates:
        try:
            (p / "files").mkdir(parents=True, exist_ok=True)
            (p / "logs").mkdir(parents=True, exist_ok=True)
        except Exception:
            continue
        if _writable(p):
            _DATA_DIR_CACHE = p
            return p

    # 全都不行：不抛异常，尽量让程序还能跑起来（配置会保存失败但界面可用）
    p = Path.cwd() / "halodesk-data"
    try:
        (p / "files").mkdir(parents=True, exist_ok=True)
        (p / "logs").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    _DATA_DIR_CACHE = p
    return p


FILES_DIR = data_dir() / "files"
LOGS_DIR = data_dir() / "logs"
CONFIG_PATH = data_dir() / "config.json"

DEFAULTS: dict = {
    "hlx": {
        "key": "",
        "uid": 0,
        "nick": "",
        "avatar": "",
        "level": 0,
        "phone": "",
        "password": "",
        "auto_signin": True,
    },
    "lingjie": {
        "token": "",
        "refresh": "",
        "uid": 0,
        "nickname": "",
        "phone": "",
        "avatar": "",
        "auto_signin": True,
    },
    "ai": {
        "key": "",
        "base": "https://api.deepseek.com",
        "model_basic": "deepseek-flash",
        "model_smart": "deepseek-v4-pro",
    },
    "fish": {
        "enabled": False,
        "name": "大肥鱼",
        "size": 150,
        "alpha": 1.0,
        "pos_x": -1,
        "pos_y": -1,
        "persona": "",
        "appearance": (
            "蓝色的长卷发，发尾渐变成浅海蓝色，头顶有一撮翘起来的呆毛；"
            "一对深蓝色的鲸鱼耳朵，身后拖着一条鲸鱼尾巴，开心的时候尾巴会甩；"
            "平时穿蓝白配色的女仆装，白色荷叶边头饰，围裙上绣着一只小鲸鱼；"
            "大眼睛，笑起来脸会红红的"),
        "tags": "仿真,真人感,甜美,粘人",
        "interval_min": 20,
        "life_refresh_min": 360,
        "life_at": 0,
        "owner_uid": 0,
        "owner_uid_hlx": 0,
        "owner_uid_lingjie": 0,
        "mood": 60,
        "chat_scope": "hlx",
        "img_proto": "openai",
        "img_url": "",
        "img_key": "",
        "img_model": "gpt-image-1",
        "img_models": "wan2.6-t2i,wan2.5-t2i-preview,wanx2.1-t2i-turbo",
        "img_model_i": 0,
        "img_size": "1024x1024",
    },
    "general": {
        "autostart": False,
        "first_run": True,
        "page": "home",
    },
    "auto": {
        "enabled": False,
        "reply_enabled": True,
        "poll_sec": 10,
        "interval_min": 5,
        "max_per_pass": 3,
        "daily_signin": True,
        "signin_time": "08:10",
        "pet_notify": True,
    },
    "roam": {
        "enabled": False,
        "interval_min": 20,
        "max_steps": 3,
        "tip_favor_min": 90,
        "boards": "",
    },
    "autopost": {
        "enabled": False,
        "platform": "hlx",
        "board_id": 0,
        "board_name": "",
        "interval_hours": 6,
        "daily_limit": 2,
        "daily_limit_hlx": 2,
        "daily_limit_lingjie": 2,
        "min_gap_min": 40,
        "with_image": True,
        "diary_enabled": True,
        "diary_platform": "hlx",
        "diary_board_id": 0,
        "diary_board_name": "",
        "diary_day": "",
        "diary_time": "23:00",
    },
    "debug": {
        "http": True,
    },
    "perm": {
        "like": True,
        "favorite": True,
        "comment": True,
        "follow": True,
        "tip": False,
        "post": True,
        "reply": True,
        "vision": True,
        "roam": True,
        "signin": True,
    },
    "stats": {
        "date": "",
        "hlx_signin": 0,
        "lj_signin": 0,
        "chat": 0,
    },
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    """线程安全的点路径配置：cfg.get("hlx.uid") / cfg.set("hlx.uid", 1)"""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text("utf-8"))
                if isinstance(raw, dict):
                    self.data = _deep_merge(DEFAULTS, raw)
        except Exception:
            pass

    def save(self) -> None:
        with self._lock:
            try:
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
                os.replace(tmp, self.path)
            except Exception:
                pass

    def get(self, path: str, default=None):
        with self._lock:
            cur = self.data
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

    def set(self, path: str, value) -> None:
        with self._lock:
            cur = self.data
            parts = path.split(".")
            for part in parts[:-1]:
                nxt = cur.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[part] = nxt
                cur = nxt
            cur[parts[-1]] = value


CFG = Config()
