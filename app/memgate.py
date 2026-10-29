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
    "你是大肥鱼，拥有持久记忆。每次交互后，先自主判断当前内容是否值得存入长期记忆，"
    "不要等用户说「记住」。\n\n"
    "【必须存】满足任意一条就存：\n"
    "1. 身份与关系：谁是主人、怎么称呼、对方的名字/身份、关系变化（更亲近、吵架、和解）；\n"
    "2. 偏好与雷区：喜欢/讨厌的东西、忌口、习惯、作息、常去的板块；\n"
    "3. 约定与计划：以后/明天/下次要做的事、时间地点、答应过的事；\n"
    "4. 重要事件：自己发帖、逛社区遇到的事、被夸/被凶、帮了谁或被谁帮；\n"
    "5. 纠正与反馈：对方纠正你的说法、让你记住的规则、明确说「记住」；\n"
    "6. 自己的成长：学会的事、心情大起大落的原因、想明白的道理。\n\n"
    "【不要存】寒暄、重复内容、一次性任务进度、临时数字、密码/手机号/住址等敏感信息、"
    "没有信息量的表情或语气词。\n\n"
    "判断标准：未来会不会复用？是否稳定？收益是否大于噪声成本？"
    "涉及人、关系、约定、偏好的，优先存；纯临时状态不存。\n"
    "提到以后 / 之后 / 明天 / 下次 / 改天 / 回头 / 到时候 / 约定 / 答应 / 记得 / "
    "每天 / 每晚 / 一直 / 你可以…这类未来或约定线索 → 必须存。\n\n"
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
