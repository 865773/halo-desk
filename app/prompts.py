"""把喂给大肥鱼的所有系统提示词集中在这里，方便查看/对照。"""
from __future__ import annotations

from . import brain
from .config import CFG


def all_prompts() -> list[tuple[str, str]]:
    """返回 [(名称, 提示词全文), ...]。"""
    out = []
    persona = CFG.get("fish.persona", "") or brain.DEFAULT_PERSONA
    out.append(("人设（共用）", persona))
    out.append(("人设补充（名字/标签/平台/心情/主人/记忆/好感）",
                brain.system_prompt("hlx", 0, "", with_tools=False)))
    from .capabilities import catalog_text
    out.append(("动作清单 + 用法教程（大肥鱼只能从中选一个）", catalog_text()))
    out.append(("主人设定", brain.owner_doc()))
    out.append(("心情上下文", brain.mood_context()))
    out.append(("自由行动（意图）提示词", brain.intent_prompt()))
    out.append(("回复消息提示词（附在用户消息里）",
                "在{平台}，{昵称} 在你的帖子「{标题}」下评论：\n{内容}\n\n"
                "你可以只回一句话，也可以顺手做一件事（比如对方让你去他主页第一个帖子"
                "点赞/收藏/评论，或者让你关注他）。\n"
                '只输出一行 JSON：{"reply":"15~45字口语回复",'
                '"action":"动作清单里的一个动作或 nothing",'
                '"target":{"kind":"known_post"},"content":"","reason":"为什么这么做"}'))
    out.append(("看帖决策提示词（附在用户消息里）",
                "{帖子上下文}\n\n从动作清单里选一个 action（看当前帖就用 target.kind=current），"
                "并给出 reason。只输出一行 JSON。"))
    out.append(("分层决策-社区", "你现在想去哪个社区逛逛？ 可选：葫芦侠三楼 / 灵芥空间"))
    out.append(("分层决策-板块", "你在{平台}，现在挑一个板块去逛。可选板块：{列表}"))
    out.append(("分层决策-看几条", "这次你打算看几个帖子？ 可选：1 / 2 / 3"))
    out.append(("分层决策-换板块", "你在「{板块}」看完一个帖子了，要换个板块继续逛吗？ 可选：换 / 不换"))
    out.append(("发帖提示词", "你正在社区「{板块}」发一条日常帖：像真人随手发动态，"
                              "口语、自然，不要 AI 腔，不要 markdown。只输出一行 JSON："
                              '{"title":"标题","content":"正文"}'))
    out.append(("日记提示词", "你在{平台}的「{板块}」版块。写一篇今天的日记帖，"
                              "像真人随手记录一天，150~300 字，口语，不要 markdown。"
                              '只输出一行 JSON：{"title":"20字内标题","content":"正文"}'))
    out.append(("生活记忆提示词", "用第一人称写一段生活记录，2~4 句，口语，像日记。"
                                  "现在是 {时间}（{时段}）。先写「{上一时段}」在做什么，"
                                  "再写现在在做什么；只能基于给你的记录。"))
    out.append(("配图提示词", "把下面这条帖子概括成一个 60 字内的画面描述，主体是一个"
                              "蓝白女仆装、蓝色长卷发、鲸鱼耳朵和尾巴的可爱女孩，"
                              "清新治愈、衣着端庄。只输出描述本身。"))
    return [(name, text.strip()) for name, text in out if text and text.strip()]
