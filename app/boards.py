"""发帖板块策略：只发「泳池」（葫芦侠）和「闲聊」（灵芥），并检测文生图是否可用。"""
from __future__ import annotations

from .config import CFG

# 名称 -> 平台默认板块
POST_BOARD_NAMES = {"hlx": ("泳池",), "lingjie": ("闲聊",)}
DEFAULT_IDS = {"hlx": 2, "lingjie": 2}


def resolve_post_board(platform: str, boards: list[tuple[int, str]]) -> tuple[int, str]:
    """在真实板块列表里找「泳池 / 闲聊」；找不到退回默认 id，再不行取第一个非公告板块。"""
    names = POST_BOARD_NAMES.get(platform, ())
    for want in names:
        for bid, name in boards:
            if want in name:
                return bid, name
    default_id = DEFAULT_IDS.get(platform, 0)
    for bid, name in boards:
        if bid == default_id:
            return bid, name
    for bid, name in boards:
        if bid not in (1, 4, 6) and "公告" not in name and "反馈" not in name:
            return bid, name
    return (0, "")


def is_allowed_board(platform: str, name: str) -> bool:
    return any(w in (name or "") for w in POST_BOARD_NAMES.get(platform, ()))


def forced_board(platform: str, client) -> tuple[int, str]:
    """发帖只允许泳池/闲聊：每次都按真实板块列表重新解析，忽略调用方传的 id。"""
    try:
        boards = client.boards() if platform == "hlx" else client.forums()
    except Exception:
        boards = []
    return resolve_post_board(platform, boards)


def image_ready() -> bool:
    """文生图配置是否可用（有地址或 Key，SD 只要有地址）。"""
    proto = (CFG.get("fish.img_proto", "openai") or "openai").strip()
    url = (CFG.get("fish.img_url", "") or "").strip()
    key = (CFG.get("fish.img_key", "") or "").strip()
    model = (CFG.get("fish.img_model", "") or "").strip()
    if proto == "sd":
        return bool(url)
    return bool(key or (url and model))
