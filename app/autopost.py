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


def make_image_prompt(title: str, content: str, scene: str = "") -> str:
    """统一配图提示词：形象 + 生活记忆 + 具体场景 + 构图，避免千篇一律。"""
    appearance = (CFG.get("fish.appearance", "") or "").strip() or (
        "蓝色长卷发，发尾渐变成浅海蓝色，头顶有一撮翘起来的呆毛；"
        "一对深蓝色的鲸鱼耳朵，身后拖着一条鲸鱼尾巴；"
        "蓝白配色的女仆装，白色荷叶边头饰，围裙上绣着一只小鲸鱼；大眼睛，笑起来脸会红红的")
    life = memory.recent_life(3) or "（今天还没有生活记录）"
    scene = scene or random.choice([
        "清晨在窗边伸懒腰", "厨房里刚盛好一碗白米饭", "下雨天在便利店门口躲雨",
        "傍晚在公园长椅上刷手机", "超市货架前挑零食", "奶茶店里发呆",
        "深夜窝在沙发上看剧", "河边散步吹风", "书店角落翻书",
        "夜市里举着烤串", "阳台上晒被子", "公交车上靠窗打瞌睡",
    ])
    return (
        f"角色：{appearance}。\n"
        f"场景：{scene}，和她的生活记忆一致：{life}\n"
        f"正在做的事：{title}；{content[:80]}\n"
        "画面要求：日系插画/动画截图质感，柔和光线，浅景深，有环境细节（家具、食物、"
        "窗外的雨或光），人物是画面主体但不必正脸；构图自然，可侧身、背影、半身或局部。"
        "禁止文字、水印、logo、多个人物、变形的手；衣着端庄。"
    )


def make_draft(platform: str, board_name: str, hint: str = "") -> tuple[str, str, str]:
    """返回 (标题, 正文, 配图提示词)。"""
    hint = hint or random.choice(TOPICS)
    title, content = publishing.compose_post(board_name, hint)
    img_prompt = ""
    from .boards import image_ready
    if image_ready():
        img_prompt = make_image_prompt(title, content)
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
    # 发帖板块锁死：只允许泳池（葫芦侠）/ 闲聊（灵芥），忽略传入的 id
    from .boards import forced_board
    cli = client or (HlxClient(CFG) if platform == "hlx" else LingjieClient(CFG))
    board_id, board_name = forced_board(platform, cli)
    result["board"] = board_name
    if not board_id:
        result["msg"] = "只允许发到「泳池 / 闲聊」，但没找到对应板块"
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
        bool(img_prompt), img_prompt, client=cli)
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
        memory.remember(f"我自己在「{board_name}」发了帖子《{title}》：{content}",
                        platform=platform, kind="post")
        record("post", f"自动发帖《{title}》（{board_name}）"
                       + ("（审核中）" if review else ""), platform, board=board_name)
    return result
