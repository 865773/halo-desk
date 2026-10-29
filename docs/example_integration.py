"""最小接入示例：把提示词搬到任意 OpenAI 兼容接口的项目里。

不依赖本仓库，只演示「拼 system + user → 解析 JSON → 执行动作」这条链。
"""
from __future__ import annotations

import json
import os
import re

import requests


PERSONA = """你是「你的角色名」，一个真实存在的人。不是AI，不是助手。
【最重要】你在「打字聊天」，不是写文章。
【绝对禁止】不用Markdown；不说「作为AI」。
【安全】不评论政治、色情、暴力、辱骂、歧视、引战、广告、谣言。
"""

# 动作白名单：id -> 说明。执行器必须覆盖这里每一个 id。
ACTIONS = {
    "post_like": "给目标帖子点赞",
    "post_favorite": "收藏目标帖子",
    "post_comment": "评论目标帖子（需要 content）",
    "post_like_comment": "点赞 + 评论",
    "follow_user": "关注某个用户",
    "unfollow_user": "取消关注",
    "unlike_post": "取消点赞",
    "unfavorite_post": "取消收藏",
    "nothing": "什么都不做",
}

TARGETS = {
    "current": "当前帖子",
    "user_first": "某人主页第一个帖子（需要 uid）",
    "my_first": "我自己主页第一个帖子",
    "my_favorite_first": "我收藏的第一个帖子",
    "user": "某个用户（关注/取关用，需要 uid）",
}


def catalog() -> str:
    lines = ["【动作清单】只能从下面选一个 action："]
    lines += [f"- {k}：{v}" for k, v in ACTIONS.items()]
    lines.append("【目标 target.kind】")
    lines += [f"- {k}：{v}" for k, v in TARGETS.items()]
    lines.append('【返回格式】只输出一行 JSON：')
    lines.append('{"action":"...","target":{"kind":"current"},"content":"",'
                 '"reason":"为什么"}')
    lines.append("【示例】")
    lines.append('- 点赞+评论：{"action":"post_like_comment","target":{"kind":"current"},'
                 '"content":"哈哈哈太真实了","reason":"看着有意思"}')
    lines.append('- 去某人主页第一个帖子收藏：'
                 '{"action":"post_favorite","target":{"kind":"user_first","uid":123},'
                 '"reason":"对方让我收藏"}')
    return "\n".join(lines)


def identity(platform: str, nick: str, uid: int, mood: int = 70,
             favor: int = 50, memory: str = "") -> str:
    parts = [f"【你现在的平台】{platform}",
             f"【你现在的心情】{mood}/100",
             f"【对方】{nick}（uid={uid}），你对他的好感度 {favor}/100"]
    if memory:
        parts.append("【你最近的记忆】\n" + memory)
    return "\n".join(parts)


def chat(system: str, user: str, model: str = "deepseek-chat") -> str:
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"},
        json={"model": model, "temperature": 1.0,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def json_of(text: str) -> dict:
    """剥掉 ```json、取第一个 { 到最后一个 }。"""
    if not text:
        return {}
    t = re.sub(r"```(?:json)?", "", text)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        return json.loads(t[a:b + 1])
    except Exception:
        return {}


def execute(action: str, target: dict, content: str = "") -> bool:
    """这里换成你的业务接口。"""
    print("执行动作:", action, target, content)
    return True


def main() -> None:
    system = PERSONA + "\n" + identity("某某社区", "小明", 123) + "\n" + catalog()
    user = ("你在「闲聊」看到一个帖子：\n【标题】今天吃了白米饭\n"
            "【作者】小明(uid=123)\n【正文】好香\n\n"
            "从动作清单里选一个 action（看当前帖就用 target.kind=current），"
            "并给出 reason。只输出一行 JSON。")

    obj = json_of(chat(system, user))
    action = obj.get("action") or "nothing"
    if action not in ACTIONS:
        action = "nothing"
    if execute(action, obj.get("target") or {}, obj.get("content") or ""):
        print("完成:", action, "理由:", obj.get("reason"))


if __name__ == "__main__":
    main()
