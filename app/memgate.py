"""让大肥鱼自己判断：这条内容值不值得写进长期记忆。"""
from __future__ import annotations

import hashlib
import threading

from .config import CFG
from .debuglog import DBG

_CACHE: dict[str, tuple[bool, str]] = {}
_LOCK = threading.Lock()
_MAX = 400

PROMPT = (
    "你是大肥鱼，拥有持久记忆。每次交互后，先自主判断当前内容是否值得存入记忆，"
    "不要等用户说「记住」。\n\n"
    "对每条候选信息自问：未来会不会复用？是否稳定？用户是否明确要求或隐含长期约定？"
    "是不是纠正/反馈？存下来的收益是否大于噪声成本？\n\n"
    "满足「长期复用 + 稳定」或属于明确纠正/约定 → 存入；"
    "一次性任务、临时状态、敏感未授权信息 → 不存；拿不准优先不存。\n\n"
    "只输出一行 JSON：\n"
    '{"store": true 或 false, "reason": "为什么存：未来什么场景会触发、会怎样改变行为"}'
)


def should_store(text: str, platform: str = "", uid: int = 0,
                 kind: str = "general") -> tuple[bool, str]:
    text = (text or "").strip()
    if not text:
        return False, "空内容"
    if not CFG.get("fish.mem_gate", True):
        return True, "记忆判断已关闭，默认保存"
    key = hashlib.md5((kind + "|" + text).encode("utf-8")).hexdigest()
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return hit
    if not CFG.get("ai.key", ""):
        # 没有模型时宁可保存，避免丢信息
        return True, "没有配置模型，先保存"
    from . import ai
    from .net import json_of
    where = "葫芦侠" if platform == "hlx" else ("灵芥" if platform == "lingjie" else "桌面")
    ask = (f"平台：{where}\n对象 uid：{uid or '无'}\n类型：{kind}\n"
           f"候选内容：\n{text}\n\n请判断是否值得存入长期记忆。")
    try:
        raw = ai.ask(PROMPT, ask)
        obj = json_of(raw)
        store = bool(obj.get("store"))
        reason = str(obj.get("reason") or "").strip()
        if not reason:
            reason = "模型未给出理由"
    except Exception as e:  # noqa: BLE001
        DBG.log("MEM", f"记忆判断失败，先保存：{e}", "WARN")
        return True, f"判断失败：{e}"
    with _LOCK:
        if len(_CACHE) > _MAX:
            _CACHE.clear()
        _CACHE[key] = (store, reason)
    DBG.log("MEM", f"{'存入' if store else '不存'}：{reason}｜{text[:40]}")
    return store, reason
