"""大肥鱼自动发帖：自己决定写什么，可选生成配图，再发到指定板块。"""
from __future__ import annotations

import random

from . import ai, imaging, memory, publishing
from .activity import record
from .config import CFG
from .debuglog import DBG
from .hlx import HlxClient
from .lingjie import LingjieClient

TOPICS = [
    "今天遇到的一件小事",
    "刚吃完一顿饭的感受",
    "看到一个好玩的东西",
    "突然想到的一个问题",
    "今天的心情",
    "半夜睡不着的时候",
]


def _pick_board(platform: str) -> tuple[int, str]:
    """发帖只去「泳池」（葫芦侠）/「闲聊」（灵芥）。"""
    from .boards import resolve_post_board
    try:
        if platform == "hlx":
            return resolve_post_board(platform, HlxClient(CFG).boards())
        return resolve_post_board(platform, LingjieClient(CFG).forums())
    except Exception:
        return (0, "")


def make_draft(platform: str, board_name: str, hint: str = "") -> tuple[str, str, str]:
    """返回 (标题, 正文, 配图提示词)。"""
    hint = hint or random.choice(TOPICS)
    title, content = publishing.compose_post(board_name, hint)
    img_prompt = ""
    from .boards import image_ready
    if image_ready():
        try:
            life = memory.recent_life(4) or "（今天还没有生活记录）"
            scene = random.choice([
                "早上刚起床在窗边伸懒腰", "在厨房煮白米饭", "下雨天在便利店门口躲雨",
                "傍晚在公园长椅上刷手机", "逛超市挑零食", "在奶茶店里发呆",
                "深夜窝在沙发上看剧", "在河边散步吹风", "书店角落翻书",
                "夜市里举着烤串", "在阳台上晒被子", "坐公交靠窗打瞌睡",
            ])
            img_prompt = ai.ask(
                "你是一个插画师。用 80 字以内写一个具体画面描述，主体是一个蓝白女仆装、"
                "蓝色长卷发、鲸鱼耳朵和尾巴的可爱女孩，清新治愈、衣着端庄。"
                "画面必须是**具体的生活场景**：要有地点、时间感、动作、天气或光线，"
                "并且和她的生活记忆一致；不要总是正脸站立、不要重复同一种构图，"
                "可以侧身/背影/局部/从窗外看进去。只输出描述本身。",
                f"她的生活记忆：\n{life}\n\n这次参考场景：{scene}\n\n"
                f"要配图的帖子标题：{title}\n正文：{content}",
                CFG.get("ai.model_basic"))
            img_prompt = " ".join((img_prompt or "").split())[:220]
        except Exception:
            img_prompt = ""
    return title, content, img_prompt


def auto_post(platform: str, board_id: int = 0, board_name: str = "",
              hint: str = "", dry_run: bool = False, client=None) -> dict:
    """写一条并发出去；dry_run=True 只生成草稿，不发布。"""
    result = {"ok": False, "msg": "", "title": "", "content": "",
              "board": board_name, "image": False, "dry": dry_run,
              "platform": platform}
    if platform not in ("hlx", "lingjie"):
        result["msg"] = "未知平台"
        return result
    if not CFG.get("ai.key", ""):
        result["msg"] = "还没配置 DeepSeek Key"
        return result
    if not board_id:
        board_id, board_name = _pick_board(platform)
        result["board"] = board_name
    if not board_id:
        result["msg"] = "拿不到板块列表"
        return result

    title, content, img_prompt = make_draft(platform, board_name, hint)
    result.update({"title": title, "content": content})
    DBG.log("AUTOPOST", f"草稿《{title}》→ {board_name}\n{content[:120]}")

    if dry_run:
        result["ok"] = True
        result["msg"] = "试运行：草稿已生成，未发布"
        return result

    ok, msg = publishing.publish_post(
        platform, board_id, board_name, title, content,
        bool(img_prompt), img_prompt, client=client)
    result["ok"] = ok
    result["msg"] = msg
    result["image"] = bool(img_prompt)
    if ok:
        # 发完查一下能不能看到；看不到就是进审核了
        review = False
        try:
            import time as _t
            from .hlx import HlxClient as _H
            from .lingjie import LingjieClient as _L
            _t.sleep(2.0)
            cli = client or (_H(CFG) if platform == "hlx" else _L(CFG))
            posts = cli.my_posts(5) if platform == "hlx" else cli.my_themes(5)
            titles = [str(p.get("title") or "") for p in (posts or [])]
            review = title not in titles
        except Exception:
            review = False
        result["review"] = review
        if review:
            result["msg"] = (msg + "（审核中）") if msg else "已提交（审核中）"
        memory.remember(f"我自己在「{board_name}」发了帖子《{title}》：{content}")
        record("post", f"自动发帖《{title}》（{board_name}）"
                       + ("（审核中）" if review else ""), platform, board=board_name)
    return result
