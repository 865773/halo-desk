"""发帖：可选让大肥鱼先生成配图，再上传到对应社区发布。"""
from __future__ import annotations

import time
from typing import Optional

from . import ai, imaging, memory
from .activity import record
from .config import CFG
from .debuglog import DBG
from .hlx import HlxClient
from .lingjie import LingjieClient
from .net import json_of
from .relations import REL


def compose_post(board_name: str, hint: str) -> tuple[str, str]:
    """让模型写一条帖子，返回 (标题, 正文)。"""
    from .persona import DEFAULT_PERSONA
    persona = CFG.get("fish.persona", "") or DEFAULT_PERSONA
    sys = (persona + "\n"
           "你正在社区「" + board_name + "」发一条日常帖：像真人随手发动态，"
           "口语、自然，不要 AI 腔，不要 markdown。只输出一行 JSON："
           '{"title":"标题（20字内）","content":"正文（60-150字，可带[表情]）"}')
    text = ai.ask(sys, hint or "发一条今天的日常吧", CFG.get("ai.model_basic"))
    obj = json_of(text)
    title = (obj.get("title") or "").strip()
    content = (obj.get("content") or "").strip()
    if not title:
        title = hint[:20] or "今天的小事"
    if not content:
        content = text.strip()[:200]
    return title[:40], content[:1000]


def publish_post(platform: str, board_id: int, board_name: str,
                 title: str, content: str, make_image: bool = False,
                 img_prompt: str = "", client=None) -> tuple[bool, str]:
    """发帖入口。platform: hlx / lingjie。client 可注入（测试用）。"""
    title = (title or "").strip()
    content = (content or "").strip()
    if not board_id:
        return False, "请选择板块"
    if not title:
        return False, "标题不能为空"

    png: Optional[bytes] = None
    if make_image:
        prompt = (img_prompt or "").strip() or \
            f"和「{title}」相关的生活场景，{content[:60]}"
        DBG.log("POST", f"生成配图：{prompt}")
        png = imaging.generate(prompt)
        if png:
            imaging.save_last(png, "last_post_image.png")
            record("genimg", f"生成配图（{len(png) // 1024} KB）", platform)
        else:
            DBG.log("POST", "配图生成失败，改为纯文字发帖", "WARN")

    if platform == "hlx":
        hlx = client if client is not None else HlxClient(CFG)
        if not hlx.key:
            return False, "请先登录葫芦侠"
        fids = ""
        if png:
            fid = hlx.upload_image(png)
            if fid:
                fids = fid + ","
                DBG.log("POST", f"图片上传成功：{fid}")
            else:
                DBG.log("POST", "图片上传失败，改为纯文字", "WARN")
        ok, msg = hlx.create_post(board_id, title, content, fids)
        if ok:
            record("post", f"在「{board_name}」发帖《{title}》" +
                   ("（带图）" if fids else ""), platform)
            memory.remember(f"我在葫芦侠「{board_name}」发了帖子《{title}》：{content}")
            return True, "发帖成功" + ("（带图）" if fids else "")
        return False, msg

    lj = client if client is not None else LingjieClient(CFG)
    if not lj.token:
        return False, "请先登录灵芥"
    urls: list[str] = []
    if png:
        url = lj.upload_image(png)
        if url:
            urls = [url]
            DBG.log("POST", f"图片上传成功：{url}")
        else:
            DBG.log("POST", "图片上传失败，改为纯文字", "WARN")
    ok, msg = lj.publish_theme(board_id, title, content, 0, urls)
    if ok:
        record("post", f"在「{board_name}」发帖《{title}》" +
               ("（带图）" if urls else ""), platform)
        memory.remember(f"我在灵芥「{board_name}」发了帖子《{title}》：{content}")
        return True, "发帖成功" + ("（带图）" if urls else "")
    return False, msg
