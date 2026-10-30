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
    memory.reset_life_if_new_day()
    life_before = memory.recent_life(3)
    from datetime import datetime as _dt, timedelta
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
    # 生活记录只写「现实生活」，每次在上次记录基础上补「这一小时」
    scenes = random.sample([
        "去楼下便利店买喝的", "逛超市顺手拿零食", "买一杯奶茶慢慢喝",
        "在附近公园散步", "逛街试衣服", "去书店翻书",
        "和朋友吃饭", "在家追剧", "收拾房间", "取快递",
        "在河边坐着发呆", "去夜市逛逛", "看电影", "买花",
        "喂楼下的猫", "做饭", "睡了个回笼觉", "刷手机赖床",
    ], 2)
    place_hint = "、".join(scenes)
    import re as _re
    _times = _re.findall(r"\[(\d{2}:\d{2})\]", life_before or "")
    last_hm = _times[-1] if _times else (now - timedelta(minutes=60)).strftime("%H:%M")
    now_hm = now.strftime("%H:%M")
    try:
        out = ai.ask(
            "你在补写自己今天的生活时间线，不是在写社区动态。"
            f"现在是 {now.strftime('%Y-%m-%d %H:%M')}（{period}），"
            f"上一条生活记录停在 {last_hm}。"
            f"只写从 {last_hm} 到 {now_hm} 这一小时里新发生的 1~3 条，"
            "每条一行，格式 [HH:MM] 发生了什么，时间必须落在这一个小时内、按先后排列。"
            "第一人称、口语、具体，像真人日记；写这一小时在干嘛：出门、买东西、散步、宅家、"
            "追剧、和朋友相处、吃饭、休息都可以，也可以有一点点情绪和小事。"
            f"可以从这些里挑：{place_hint}。"
            "不要复述上一条，不要总结整天，不要编明天；"
            "绝对不要提社区、帖子、评论、回复、点赞、关注、发帖，也不要复述聊天内容。"
            "目标是和之前的记录拼成完整的一天。",
            ("【今天已经记录的生活（只用来衔接，不要重复）】\n" + life_before).strip()
            or f"今天是 {now.strftime('%Y-%m-%d')}，还没有生活记录。",
            None)
    except Exception as e:
        DBG.log("LIFE", f"生成生活记录失败：{e}", "WARN")
        return ""
    text = (out or "").strip()
    if not text:
        return ""
    memory.reset_life_if_new_day()
    memory.clean_life_actions()
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
        raw = ai.ask(prompt, "开始写吧。", None)
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
