"""每日日记 + 生活记忆生成。"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta

from . import ai, imaging, memory, publishing
from .activity import record
from .config import CFG
from .debuglog import DBG
from .hlx import HlxClient
from .lingjie import LingjieClient


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ---------------- 生活记忆 ----------------

def gen_life(force: bool = False) -> str:
    """每 6 小时把最近发生的事写成生活记录（含当前时段与上一时段在做什么）。"""
    if not CFG.get("ai.key", ""):
        return ""
    interval = max(60, int(CFG.get("fish.life_refresh_min", 60) or 60)) * 60
    last = float(CFG.get("fish.life_at", 0) or 0)
    if not force and time.time() - last < interval:
        return ""
    recent = memory.recent(14, "hlx")
    life_before = memory.recent_life(3)
    from datetime import datetime, timedelta as _dt
    now = _dt.now()
    hour = now.hour
    if 5 <= hour < 9:
        period = "清晨"
    elif 9 <= hour < 12:
        period = "上午"
    elif 12 <= hour < 14:
        period = "中午"
    elif 14 <= hour < 18:
        period = "下午"
    elif 18 <= hour < 22:
        period = "傍晚"
    else:
        period = "深夜"
    # 只取上次记录之后发生的事，写成时间线，不再整天覆盖
    since = _dt.fromtimestamp(last) if last else (now - timedelta(hours=1))
    try:
        from .activity import ACT
        events = []
        for it in ACT.recent(120):
            ts = str(it.get("ts") or "")
            try:
                when = _dt.strptime(f"{now.year}-{ts}", "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if when < since:
                continue
            events.append(f"{ts[-8:-3]} {it.get('text', '')}")
        events = events[-20:]
    except Exception:
        events = []
    timeline = "\n".join(events)
    place_hint = random.choice([
        "楼下便利店", "附近公园", "常去的那家小饭馆", "商场", "书店",
        "奶茶店", "河边", "朋友家", "夜市", "电影院",
    ]) if random.random() < 0.5 else ""
    try:
        out = ai.ask(
            "根据下面这段时间真实发生的事，写 2~4 条生活时间线。"
            "每条一行，格式必须是：[HH:MM] 发生了什么（第一人称、口语、具体场景）。"
            "只写这些事，按时间先后，不要总结整天，不要复述更早的记录。"
            f"现在是 {now.strftime('%H:%M')}（{period}）。"
            + (f"可以自然补充一两句宅家/出门的细节（比如{place_hint}）。"
               if place_hint else ""),
            (timeline or recent or "这段时间没发生什么特别的事。").strip(),
            CFG.get("ai.model_basic"))
    except Exception as e:
        DBG.log("LIFE", f"生成生活记录失败：{e}", "WARN")
        return ""
    text = (out or "").strip()
    if not text:
        return ""
    memory.reset_life_if_new_day()
    lines = []
    for ln in text.splitlines():
        ln = ln.strip().lstrip("-•· ").strip()
        if not ln:
            continue
        if not ln.startswith("["):
            ln = f"[{now.strftime('%H:%M')}] {ln}"
        lines.append(ln)
    if not lines:
        lines = [f"[{now.strftime('%H:%M')}] {text[:300]}"]
    memory.life_append("\n".join(lines)[:800])
    CFG.set("fish.life_at", time.time())
    CFG.save()
    DBG.log("LIFE", f"生活记录已更新（{period}，{len(lines)} 条）")
    return text


# ---------------- 每日日记 ----------------

def diary_due() -> bool:
    return (CFG.get("autopost.diary_day", "") or "") != _today()


def write_diary(platform: str = "hlx", board_id: int = 0, board_name: str = "",
                dry_run: bool = False, client=None) -> dict:
    """写今天的日记并发出去；dry_run 只生成不发布。"""
    res = {"ok": False, "msg": "", "title": "", "content": "", "board": board_name,
           "dry": dry_run}
    if not CFG.get("ai.key", ""):
        res["msg"] = "还没配置 DeepSeek Key"
        return res
    # 日记也只发泳池 / 闲聊，忽略配置里的板块
    from .boards import forced_board
    try:
        cli = client or (HlxClient(CFG) if platform == "hlx" else LingjieClient(CFG))
    except Exception:
        cli = client
    board_id, board_name = forced_board(platform, cli) if cli else (0, "")
    res["board"] = board_name
    if not board_id:
        res["msg"] = "只允许发到「泳池 / 闲聊」，但没找到对应板块"
        return res

    life = memory.recent_life(5, platform)
    memo = memory.recent(8, platform)
    where = "葫芦侠三楼" if platform == "hlx" else "灵芥空间"
    prompt = (
        f"你在{where}的「{board_name}」版块。写一篇今天的日记帖，"
        "像真人随手记录一天，150~300 字，口语，不要 markdown、不要标题党。\n"
        f"【今天的生活】{life or '（还没有记录）'}\n"
        f"【最近的记忆】{memo or '（没有）'}\n"
        '只输出一行 JSON：{"title":"20字内标题","content":"正文"}'
    )
    try:
        raw = ai.ask(prompt, "开始写吧。", CFG.get("ai.model_basic"))
    except Exception as e:
        res["msg"] = f"生成失败：{e}"
        return res
    obj = json.loads(_extract_json(raw) or "{}")
    title = (obj.get("title") or "").strip()[:40]
    content = (obj.get("content") or "").strip()[:1200]
    if not title or not content:
        res["msg"] = "模型没写出完整日记"
        return res
    res.update({"title": title, "content": content})
    DBG.log("DIARY", f"草稿《{title}》")

    if dry_run:
        res["ok"] = True
        res["msg"] = "试运行：日记草稿已生成，未发布"
        return res

    with_image = bool(CFG.get("autopost.with_image", True))
    img_prompt = ""
    if with_image:
        from .autopost import make_image_prompt
        img_prompt = make_image_prompt(title, content, scene="晚上写日记的安静时刻")
    ok, msg = publishing.publish_post(platform, board_id, board_name, title,
                                      content, with_image, img_prompt, client=cli)
    res["ok"] = ok
    res["msg"] = msg
    if ok:
        CFG.set("autopost.diary_day", _today())
        CFG.save()
        memory.remember(f"我写了今天的日记《{title}》")
        record("post", f"日记《{title}》（{board_name}）", platform)
    return res


def _pick_diary_board(platform: str):
    from .boards import resolve_post_board
    try:
        if platform == "hlx":
            from .hlx import HlxClient
            return resolve_post_board(platform, HlxClient(CFG).boards())
        from .lingjie import LingjieClient
        return resolve_post_board(platform, LingjieClient(CFG).forums())
    except Exception:
        return (0, "")


def _extract_json(text: str) -> str:
    a = (text or "").find("{")
    b = (text or "").rfind("}")
    return text[a:b + 1] if a >= 0 and b > a else ""
