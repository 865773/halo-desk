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
    "特别注意：\n"
    "- 提到以后 / 之后 / 明天 / 下次 / 改天 / 回头 / 到时候 / 约定 / 答应 / 记得 / "
    "每天 / 每晚 / 一直 / 你可以…这类未来或约定线索 → 存；\n"
    "- 大肥鱼自己说过的话，如果表达了喜好、承诺、计划、关系变化或情绪 → 存；\n"
    "- 发帖内容本身就值得留作创作记录 → 存。\n\n"
    "只输出一行 JSON：\n"
    '{"store": true 或 false, "reason": "为什么存：未来什么场景会触发、会怎样改变行为"}'
)

FUTURE_HINTS = (
    "以后", "之后", "明天", "下次", "改天", "回头", "到时候", "将来",
    "约定", "答应", "记得", "别忘", "每天", "每晚", "每周", "一直",
    "你可以", "以后要", "过几天", "下周", "明年", "等会", "晚点",
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
    # 明显的未来/约定线索，直接存，不再多花一次判断
    hit_word = next((w for w in FUTURE_HINTS if w in text), "")
    if hit_word:
        reason = f"出现「{hit_word}」等未来/约定线索，之后会用到"
        DBG.log("MEM", f"存入：{reason}｜{text[:40]}")
        return True, reason
    if kind == "post":
        return True, "自己发的帖子，留作创作与经历记录"
    from . import ai
    from .net import json_of
    where = "葫芦侠" if platform == "hlx" else ("灵芥" if platform == "lingjie" else "桌面")
    if kind == "reply":
        ask = (f"平台：{where}\n这是大肥鱼自己刚刚说出的一句回复：\n{text}\n\n"
               "如果这句话表达了喜好、承诺、计划、关系变化或明显情绪，就存；"
               "只是寒暄或一次性应答就不存。")
    else:
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
