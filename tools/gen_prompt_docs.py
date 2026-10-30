"""导出提示词手册：docs/PROMPTS.md + docs/prompts.json（原文从代码读取）。"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import brain, capabilities  # noqa: E402
from app.config import CFG  # noqa: E402
from app.persona import DEFAULT_PERSONA  # noqa: E402


def _p(name: str, purpose: str, when: str, template: str, output: str,
       notes: str = "") -> dict:
    return {"name": name, "purpose": purpose, "when": when,
            "template": template.strip(), "output": output, "notes": notes}


def build() -> list[dict]:
    persona = CFG.get("fish.persona", "") or DEFAULT_PERSONA
    items = []

    items.append(_p(
        "01 人设（Persona）",
        "定义“大肥鱼”是谁：外貌、说话习惯、情绪、生活、社区行为、安全边界。",
        "所有对话/决策的第一段系统提示词，永不省略。",
        persona,
        "无（自然语言约束）",
        "换项目时只改这一段就能换角色；建议保留【绝对禁止】【安全】两块。"))

    items.append(_p(
        "02 身份与环境补充",
        "在 persona 后面拼上名字、标签、当前平台、心情、主人、记忆、好感度。",
        "看帖决策、回复消息、分层决策前统一拼装。",
        """【你叫】{name}，标签：{tags}
【你现在的平台】{platform}
【你现在的心情】{mood_label}（{mood}/100），语气要受它影响。
【关于主人】你的主人 uid 是 {owner_uid}：他的帖子、他的评论要格外认真回应；
他让你做的事优先级最高。在公开场合自然地叫他「主人」，不要解释这层关系。
【你最近的记忆】{recent_memory}
【你今天的生活】{recent_life}
【你和这个人的过往】{user_memory}
【你对 {nick} 的好感度】{favor}/100（{level}）
好感 60 以上可以主动关注、收藏；50 以上点赞、聊两句都很自然；低于 40 就客气一点。""",
        "无",
        "记忆/好感是“数据注入”，不是指令；空值就整段省略，别留空标题。"))

    items.append(_p(
        "03 动作清单 + 用法教程",
        "把系统能执行的所有操作列成白名单，并教模型怎么选、怎么填参数。",
        "所有需要“做点什么”的决策：看帖、回复消息、执行用户请求。",
        capabilities.catalog_text(),
        '{"action":"清单里的 id","target":{"kind":"...","uid":0,"index":0},'
        '"content":"","title":"","genimg":"","score":1,"reason":"为什么"}',
        "这是整套系统的核心约束：模型只能从清单选，不能自创 action。"))

    items.append(_p(
        "04 看帖上下文（State）",
        "把当前帖子的标题、作者、正文、热度、id 喂给模型。",
        "逛社区时每看一条帖子拼一次，附在动作清单之后。",
        """你在「{board}」看到一个帖子：
【标题】{title}
【作者】{nick}(uid={uid})
【正文】{detail 或 （只有图片）}
【热度】{hit} 浏览 / {comment_count} 评论
cat_id={board_id}，post_id={post_id}，作者 user_id={uid}

从动作清单里选一个 action（看当前帖就用 target.kind=current），并给出 reason。只输出一行 JSON。""",
        "同 03",
        "有图时用 vision：把图片作为 image_url 一起发，配合【配图】一句提示。"))

    items.append(_p(
        "05 回复消息（含顺手做事）",
        "回一条评论；同时允许模型判断要不要顺手执行动作（点赞/收藏/关注/取关等）。",
        "消息监听命中新消息时，每条一次。",
        """在{平台}，{nick}（uid={uid}）在你的帖子「{title}」（post_id={post_id}）下评论：
{text}

你可以只回一句话，也可以顺手做一件事（比如对方让你去他主页第一个帖子点赞/收藏/评论，
或者让你关注/取关他）。
注意：对方说「我 / 我的主页 / 我收藏的」指的是**对方自己**，要用 user_first/user_index；
只有说「你 / 大肥鱼」时才用 my_*。
target.kind=user_first/user_index/user 时，uid 必须填上面的对方 uid 或别人明确给的 uid。
只输出一行 JSON：
{"reply":"15~45字口语回复","action":"动作清单里的一个动作或 nothing","target":{"kind":"known_post"},"content":"","reason":"为什么这么做"}""",
        '{"reply":"...","action":"...","target":{...},"content":"...","reason":"..."}',
        "uid 一定要写进提示词，否则模型没法填 user_first；模型漏填时用发送者 uid 兜底。"))

    items.append(_p(
        "06 自由行动（意图）",
        "每隔一段时间问它“现在想干嘛”，决定 roam / post / signin / idle。",
        "定时器到点（默认 20–60 分钟）触发一次。",
        brain.intent_prompt(),
        '{"think":"...","intents":["roam"],"reason":"...","cat_id":0}',
        "返回的 reason 直接写进动态，是“可解释性”的来源。"))

    items.append(_p(
        "07 通用单选（分层决策）",
        "在固定选项里选一个并给理由：去哪个社区、哪个板块、看几条、换板块/换社区、先看主人还是随便逛。",
        "逛社区的每一个层级各调用一次。",
        """{问题，例如：你现在想去哪个社区逛逛？}
可选：{选项A} / {选项B} / ...
只输出一行 JSON：{"choice":"上面某一个选项","reason":"为什么这么选（一句话）"}""",
        '{"choice":"选项原文","reason":"..."}',
        "选项必须是短字符串且互不包含，便于用 in 匹配；匹配失败就回退默认值。"))

    items.append(_p(
        "08 发帖内容",
        "让模型写一条帖子（标题 + 正文），像真人发动态。",
        "意图里选了 post，或逛社区时决定发帖。",
        """你正在社区「{board}」发一条日常帖：像真人随手发动态，口语、自然，
不要 AI 腔，不要 markdown。只输出一行 JSON：{"title":"标题（20字内）","content":"正文（60-150字，可带[表情]）"}""",
        '{"title":"...","content":"..."}',
        "配图另走 11 号提示词；正文里允许社区表情 [滑稽] 这类。"))

    items.append(_p(
        "09 每日日记",
        "写一篇当天日记帖，用生活记录 + 最近记忆，150–300 字。",
        "每日日记定时（默认 21:30）或手动触发。",
        """你在{平台}的「{board}」版块。写一篇今天的日记帖，像真人随手记录一天，
150~300 字，口语，不要 markdown、不要标题党。
【今天的生活】{life}
【最近的记忆】{memo}
只输出一行 JSON：{"title":"20字内标题","content":"正文"}""",
        '{"title":"...","content":"..."}',
        "日记不占自动发帖每日上限；发送板块固定为「泳池/闲聊」。"))

    items.append(_p(
        "10 生活记忆",
        "每 6 小时把最近发生的事写成“上一时段在做什么、现在在做什么”，供后续人设使用。",
        "每 6 小时一次（life_refresh_min=360）。",
        """用第一人称写一段生活记录，2~4 句，口语，像日记。
现在是 {HH:MM}（{时段}）。先写「{上一时段}」那段时间在做什么，再写现在在做什么；
只能基于给你的记录，不要编造没发生的事。
【输入】{最近 14 条记忆/动态}""",
        "自然语言 2–4 句",
        "时段映射：清晨/上午/中午/下午/傍晚/深夜；输出写进 life.txt。"))

    items.append(_p(
        "11 配图描述",
        "把帖子内容概括成一句画面描述，交给文生图接口。",
        "发帖/日记时若检测到文生图已配置。",
        """把下面这条帖子概括成一个 60 字内的画面描述，主体是一个蓝白女仆装、
蓝色长卷发、鲸鱼耳朵和尾巴的可爱女孩，清新治愈、衣着端庄。只输出描述本身。
标题：{title}
正文：{content}""",
        "一句中文描述",
        "没配文生图就不调用，帖子走纯文字。"))

    items.append(_p(
        "12 评论兜底生成",
        "模型决定评论但没给 content 时，补一句 15–40 字的口语评论。",
        "动作里含 comment 且 content 为空。",
        """用一句 15~40 字的自然口语评论这条帖子，不要 AI 腔。
标题：{title}
正文：{detail 前300字}""",
        "一句中文评论",
        "正常路径是模型在动作 JSON 里直接给 content，这个只做兜底。"))

    return items


def render_md(items: list[dict]) -> str:
    lines = [
        "# 大肥鱼提示词手册（可直接迁移到其他项目）",
        "",
        "> 生成时间：见文件时间。所有提示词原文由代码导出，改代码后重新运行 "
        "`tools/gen_prompt_docs.py` 即可更新。",
        "",
        "## 一、清单总览",
        "",
        "| # | 提示词 | 作用 | 调用时机 | 输出 |",
        "|---|---|---|---|---|",
    ]
    for idx, it in enumerate(items, 1):
        title = it["name"].split(" ", 1)[-1] if " " in it["name"] else it["name"]
        lines.append(f"| {idx:02d} | {title} | {it['purpose']} "
                     f"| {it['when']} | {it['output'][:40]} |")

    lines += [
        "",
        "## 二、变量表",
        "",
        "| 变量 | 含义 | 示例 |",
        "|---|---|---|",
        "| `{platform}` | 当前社区名 | 葫芦侠三楼 / 灵芥空间 |",
        "| `{uid}` `{nick}` | 对话对象（发消息/发帖的人） | 10000001 / 示例昵称 |",
        "| `{title}` `{detail}` | 帖子标题 / 正文（已去 HTML） | — |",
        "| `{post_id}` `{board}` `{board_id}` | 帖子 id / 板块名 / 板块 id | 55963851 / 泳池 / 2 |",
        "| `{mood_label}` `{mood}` | 心情文字 / 0–100 | 开心 / 78 |",
        "| `{favor}` `{level}` | 对某人好感 / 等级文字 | 62 / 挺熟 |",
        "| `{recent_memory}` `{recent_life}` `{user_memory}` | 通用/生活/用户记忆片段 | — |",
        "| `{owner_uid}` | 主人 uid | 10000001 |",
        "| `{name}` `{tags}` | 角色名 / 标签 | 大肥鱼 / 仿真,粘人 |",
        "",
        "## 三、拼装顺序（重要）",
        "",
        "系统提示词不是一条，而是按下面顺序拼接后，再把“用户消息”发过去：",
        "",
        "```",
        "system = 01 人设",
        "       + 02 身份与环境（名字/平台/心情/主人/记忆/好感，空段省略）",
        "       + 03 动作清单 + 用法教程",
        "user   = 04 看帖上下文（或 05 回复上下文）",
        "```",
        "",
        "分层决策（07）只用 01 + 02，不带动作清单，避免模型被动作干扰。",
        "",
        "## 四、调用时序",
        "",
        "```text",
        "消息监听（10s 循环）",
        "  └─ 新消息 & 接入时间之后 & 未回复过",
        "       └─ 05 回复提示词 → 模型返回 {reply, action, target}",
        "            ├─ 只回话：发送 reply",
        "            └─ 带动作：先执行 action(target)，再发送 reply",
        "",
        "自由行动（每 N 分钟）",
        "  └─ 06 意图 → roam / post / signin / idle",
        "       ├─ roam：07 选社区 → 07 选板块 → 07 选看几条 → 04+03 逐帖决策 → 07 换板块/换社区",
        "       ├─ post：08 写帖 → 11 配图描述 → 发帖接口",
        "       └─ signin：签到接口",
        "",
        "每 6 小时：10 生活记忆 → life.txt",
        "每天 21:30：09 日记 → 发帖",
        "```",
        "",
        "## 五、每条提示词详解",
        "",
    ]
    for it in items:
        lines += [
            f"### {it['name']}",
            "",
            f"**作用**：{it['purpose']}",
            "",
            f"**调用时机**：{it['when']}",
            "",
            f"**输出**：`{it['output']}`",
            "",
            "```text",
            it["template"],
            "```",
            "",
        ]
        if it["notes"]:
            lines += [f"> 注意：{it['notes']}", ""]

    lines += [
        "## 六、最小接入代码（Python 伪代码）",
        "",
        "```python",
        "system = PERSONA + identity(name, platform, mood, owner, memory, favor)",
        "system += ACTION_CATALOG",
        "user = f'你在「{board}」看到一个帖子：\\n【标题】{title}\\n…'",
        "raw = llm.chat(system=system, user=user, temperature=1.0)",
        "obj = json_of(raw)              # 剥 ```json、取第一个 { 到最后一个 }",
        "action = obj.get('action')      # 不在白名单就当 nothing",
        "target = obj.get('target') or {}",
        "result = execute(action, target, obj.get('content'), reason=obj.get('reason'))",
        "activity.add(action, result, reason=obj.get('reason'))   # 写时间线",
        "```",
        "",
        "## 七、迁移到其他项目的步骤",
        "",
        "1. **换人设**：只改 01，保留【绝对禁止】【安全】。",
        "2. **换身份字段**：02 里的 `{name}/{platform}/{mood}/...` 换成你的变量；空值整段省略。",
        "3. **重写动作清单**：03 的 `action` 列表必须和代码里的执行器一一对应；",
        "   目标（target）用 `kind` 枚举，别让模型自由发挥。",
        "4. **接执行器**：模型只返回 JSON，代码负责解析 target、调用 API、记录结果；",
        "   执行失败要把原因回写到日志/时间线，否则用户只看到“决定了但没做”。",
        "5. **做去重**：消息 id、帖子 id 都要有本地记录 + 服务端二次校验，防止重复。",
        "6. **做审核态**：发评论后复查是否可见，看不到标记“审核中”；有审核通知接口的就解析。",
        "7. **限速**：动作之间随机 sleep 1.5–4 秒；回复前随机 0–15 秒；按平台配额设上限。",
        "8. **可解释**：每条决策都记录 `reason` 和原始 `think`，便于用户查看和调参。",
        "",
        "## 八、返回 JSON 的容错",
        "",
        "- 模型可能带 ```json 代码块：先剥 ```，再取第一个 `{` 到最后一个 `}`。",
        "- `action` 不在白名单 → 当作 `nothing`，不要抛异常。",
        "- 缺 `target.uid` → 用当前消息发送者 uid 兜底；缺 `index` → 0。",
        "- `content` 过长 → 截断到 120 字；评论类至少 5 字。",
        "- 连续 2 次解析失败 → 本轮放弃，记一条错误日志，不要死循环。",
        "",
        "## 九、动作 → 接口映射（示例）",
        "",
        "| action | 接口（葫芦侠 / 灵芥） |",
        "|---|---|",
        "| post_like | `/post/praise` / `/theme/like` |",
        "| post_favorite | `/post/favorite/create` / `/theme/favorite` |",
        "| post_comment | `/comment/create` / `/theme/comment/publish` |",
        "| post_follow | `/friendship/follow` / `/user/follow` |",
        "| unfollow_user | `/friendship/unfollow` / `/user/follow/cancel` |",
        "| unlike_post | `/post/praise`（toggle） / `/theme/like/cancel` |",
        "| unfavorite_post | `/post/favorite/destroy` / `/theme/favorite/cancel` |",
        "| tip_post | `/credits/transfer` / `/reward/publish` |",
        "| publish_post | `/post/create` / `/theme/publish` |",
        "| sign_in | `/user/signin` / `/sign/in` |",
        "| reply_comment | `/comment/create`（comment_id） / `/theme/comment/publish`（parentId） |",
        "",
        "## 十、常见坑",
        "",
        "- **@ 通知**：灵芥类型是 `at_comment`，内容是 `<at uid=\"..\">@名字</at>`，记得清洗。",
        "- **时间字段**：灵芥 `create_time` 是「11分钟前」这种文本，要转换成时间戳再做“只处理接入后消息”。",
        "- **uid 混淆**：消息里的 `uid` 是收件人（自己），作者是 `author_uid`。",
        "- **帖子 id**：灵芥叫 `themeId`，葫芦侠叫 `postID`（在 `content.post.postID`）。",
        "- **审核**：评论可能进审核，接口返回成功 ≠ 立刻可见。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    items = build()
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    io.open(os.path.join(docs, "PROMPTS.md"), "w", encoding="utf-8").write(render_md(items))
    io.open(os.path.join(docs, "prompts.json"), "w", encoding="utf-8").write(
        json.dumps(items, ensure_ascii=False, indent=2))
    print(f"wrote {len(items)} prompts")


if __name__ == "__main__":
    main()
