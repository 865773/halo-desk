"""两个社区各自的表情系统（不互通）：葫芦侠 21 个，灵芥 160 个。"""
from __future__ import annotations

import json
import time
from typing import Optional

from .config import CFG, FILES_DIR
from .debuglog import DBG

# 葫芦侠：源码 FishBrain.EMOJI_LIST 写死的一套
HLX_CODES = [
    "[滑稽]", "[哈哈]", "[开心]", "[太开心]", "[笑眼]", "[呵呵]", "[乖]", "[酷]",
    "[吐]", "[真棒]", "[泪]", "[汗]", "[狂汗]", "[怒]", "[鄙视]", "[阴险]",
    "[委屈]", "[疑问]", "[勉强]", "[升起]", "[钱]",
]

HLX_MEANING = {
    "[滑稽]": "坏笑/阴阳", "[哈哈]": "大笑", "[开心]": "开心", "[太开心]": "超开心",
    "[笑眼]": "笑眯眼", "[呵呵]": "敷衍笑", "[乖]": "乖巧", "[酷]": "摆酷",
    "[吐]": "吐", "[真棒]": "夸人", "[泪]": "哭", "[汗]": "无语", "[狂汗]": "大汗",
    "[怒]": "生气", "[鄙视]": "看不起", "[阴险]": "坏主意", "[委屈]": "委屈",
    "[疑问]": "疑惑", "[勉强]": "勉强", "[升起]": "冒泡", "[钱]": "钱",
}

# 灵芥：接口 /emoji/list 的兜底子集（接口拿不到时用）
LJ_FALLBACK = [
    "[微笑]", "[哈哈]", "[吐舌]", "[惊讶]", "[酷]", "[愤怒]", "[腼腆]", "[汗]",
    "[大哭]", "[无语]", "[鄙视]", "[不爽]", "[点赞]", "[爱钱]", "[疑惑]", "[邪笑]",
    "[吐]", "[咦]", "[内向]", "[最爱]", "[呵]", "[哈]", "[咋滴]", "[好好]",
    "[滑稽]", "[尬]", "[真无语]", "[可怜]", "[睡了]", "[吓傻]", "[大怒]", "[噢]",
    "[吃瓜]", "[大笑]", "[互粉]", "[呜呜呜]", "[乖乖]", "[好耶]", "[嘻嘻]", "[好爱]",
    "[略略略]", "[笑哭]", "[哈哈哈]", "[害羞]", "[委屈]", "[我喜欢]", "[木马]", "[哼]",
    "[狗头1]", "[狗头2]", "[狗头3]", "[爱心]", "[玫瑰]", "[给力]", "[666]", "[赞]",
]

CACHE = FILES_DIR / "emoji_lingjie.json"


def lingjie_codes() -> list[str]:
    """优先读缓存（7 天有效），否则用兜底；去重、过滤非法项。"""
    data = None
    try:
        if CACHE.exists() and time.time() - CACHE.stat().st_mtime < 7 * 86400:
            data = json.loads(CACHE.read_text("utf-8"))
    except Exception:
        data = None
    raw = data if isinstance(data, list) and len(data) > 20 else LJ_FALLBACK
    out, seen = [], set()
    for c in raw:
        s = str(c).strip()
        if not (s.startswith("[") and s.endswith("]")) or len(s) > 9:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def refresh_lingjie(client) -> int:
    """从接口拉一次灵芥表情并缓存，返回数量。"""
    try:
        codes = [str(e.get("code") or "").strip() for e in client.emoji_list()]
        codes = [c for c in codes if c.startswith("[") and c.endswith("]") and len(c) <= 9]
        codes = list(dict.fromkeys(codes))
        if len(codes) > 20:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(codes, ensure_ascii=False), "utf-8")
            return len(codes)
    except Exception as e:
        DBG.log("EMOJI", f"拉灵芥表情失败：{e}", "WARN")
    return 0


def codes(platform: str) -> list[str]:
    return HLX_CODES if platform == "hlx" else lingjie_codes()


def doc(platform: str) -> str:
    """平台专属表情说明（写进系统提示词）。"""
    items = codes(platform)
    if platform == "hlx":
        detail = "；".join(f"{c}{HLX_MEANING.get(c, '')}" for c in items)
        return ("【表情（葫芦侠专用）】只认这一套，写成方括号，App 才会渲染成图；"
                "不在下面列表里的一律不要写（写了会被删掉）。\n"
                + detail + "\n一条最多 1~2 个，别堆。\n")
    lines = ["、".join(items[i:i + 16]) for i in range(0, len(items), 16)]
    return ("【表情（灵芥专用）】只认这一套，写成方括号；不在下面列表里的一律不要写"
            "（写了会被删掉），也别用葫芦侠那套（两边图案不同）。\n"
            + "\n".join(lines) + "\n一条最多 1~2 个，别堆。\n")


_EMOJI_RE = None


def sanitize(text: str, platform: str) -> str:
    """删掉不属于本平台的表情（模型自创的 [xxx]），其余原样返回。"""
    import re
    global _EMOJI_RE
    if not text:
        return text
    if _EMOJI_RE is None:
        _EMOJI_RE = re.compile(r"\[[^\[\]\r\n]{1,8}\]")
    allowed = set(codes(platform))
    removed = []

    def _sub(m):
        tok = m.group(0)
        if tok in allowed:
            return tok
        # 像表情的才删；普通方括号文字（如 [活动]）保留
        if 1 <= len(tok.strip("[]")) <= 6:
            removed.append(tok)
            return ""
        return tok

    out = _EMOJI_RE.sub(_sub, text)
    if removed:
        DBG.log("EMOJI", f"{platform} 删掉无效表情：{' '.join(removed[:6])}", "WARN")
    return out
