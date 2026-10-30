"""大肥鱼的决策引擎：系统提示词、工具卡、意图决策，对齐 hlx-halo/FishBrain。"""
from __future__ import annotations

import json
import random
from typing import Optional

from . import ai, emoji, memory
from .config import CFG
from .debuglog import DBG
from .persona import DEFAULT_PERSONA
from .relations import REL, level

EMOJI_LIST = ("[滑稽] [哈哈] [开心] [太开心] [笑眼] [呵呵] [乖] [酷] [吐] [真棒] "
              "[泪] [汗] [狂汗] [怒] [鄙视] [阴险] [委屈] [疑问] [勉强] [升起] [钱]")

TAGS_DEFAULT = "仿真,真人感,甜美,粘人"


def _perm(name: str, default: bool = True) -> bool:
    return bool(CFG.get(f"perm.{name}", default))


def tool_doc() -> str:
    """可用动作卡片（按权限动态裁剪，和原版一样）。"""
    s = ["【怎么用：每个功能都是一张卡片。挑一张，把 <尖括号> 换成真实值，原样返回这张卡片。",
         "一张卡只做一件事；想做多件就把 actions 数组写多个动作名。\n"]
    if _perm("like"):
        s.append('① 点赞当前帖：{"actions":["like"]}')
    if _perm("favorite"):
        s.append('② 收藏当前帖：{"actions":["favorite"]}')
    if _perm("comment"):
        s.append('③ 评论当前帖：{"actions":["comment"],"content":"<15~40字口语>"}')
    if _perm("follow"):
        s.append('④ 关注作者：{"actions":["follow"]}')
    if _perm("tip", False):
        s.append('⑤ 送葫芦：{"actions":["tip"],"score":<1~5>,"content":"<五字以上理由>"}')
    if _perm("post"):
        s.append('⑥ 发帖：{"actions":["post"],"title":"<标题>","content":"<正文>",'
                 '"genimg":"<配图描述，可空>"}')
    s.append('⑦ 签到：{"actions":["signin"]}')
    s.append('⑧ 换板块：{"actions":["goto"],"cat_id":<板块id>}')
    s.append('⑨ 什么都不做：{"actions":[]}\n')
    s.append("【组合示例】点赞+收藏+评论："
             '{"actions":["like","favorite","comment"],"content":"<评论>"}')
    s.append("【谁能让你做什么】点赞、收藏、关注、评论，谁开口都可以；"
             "葫芦很难得，只有主人开口或好感度很高才送，一次最多 1 个。")
    s.append(f"【表情】只能用：{EMOJI_LIST}，一条最多 1~2 个。")
    return "\n".join(s)


def format_doc() -> str:
    return ("【返回格式】只输出一行 JSON，不要任何其他文字：\n"
            '{"think":"为什么这么做（一句话）","actions":[],"content":"","title":"",'
            '"score":1,"cat_id":0,"reason":"给人看的决策理由"}\n'
            "actions 里只能出现上面卡片里的动作名；不需要的字段省略。")


def persona_template() -> str:
    """给编辑框看的人设模板：把当前名字/默认形象还原成 {name}/{appearance}。"""
    from .persona import DEFAULT_APPEARANCE
    p = CFG.get("fish.persona", "") or DEFAULT_PERSONA
    name = (CFG.get("fish.name", "") or "大肥鱼").strip() or "大肥鱼"
    if name and name != "大肥鱼":
        p = p.replace(name, "{name}")
    p = p.replace(DEFAULT_APPEARANCE, "{appearance}")
    return p


def persona_text() -> str:
    """人设文本：{name} / {appearance} 用当前配置填充，旧名字也会被替换。"""
    from .persona import DEFAULT_APPEARANCE
    p = CFG.get("fish.persona", "") or DEFAULT_PERSONA
    name = (CFG.get("fish.name", "") or "大肥鱼").strip() or "大肥鱼"
    appearance = (CFG.get("fish.appearance", "") or "").strip() or DEFAULT_APPEARANCE
    p = p.replace("{name}", name).replace("{appearance}", appearance)
    if name != "大肥鱼":
        p = p.replace("大肥鱼", name)
    return p


def owner_uid(platform: str = "") -> int:
    hx = int(CFG.get("fish.owner_uid_hlx", 0) or 0)
    lj = int(CFG.get("fish.owner_uid_lingjie", 0) or 0)
    legacy = int(CFG.get("fish.owner_uid", 0) or 0)
    hx = hx or legacy or lj
    lj = lj or legacy or hx
    return hx if platform == "hlx" else (lj if platform == "lingjie" else 0)


def owner_doc(platform: str = "") -> str:
    hx = int(CFG.get("fish.owner_uid_hlx", 0) or 0)
    lj = int(CFG.get("fish.owner_uid_lingjie", 0) or 0)
    legacy = int(CFG.get("fish.owner_uid", 0) or 0)
    hx = hx or legacy or lj          # 只填了一个平台时另一边沿用
    lj = lj or legacy or hx
    lines = []
    if hx:
        lines.append(f"你在葫芦侠三楼的主人是 uid {hx}")
    if lj:
        lines.append(f"你在灵芥空间的主人是 uid {lj}")
    if not lines:
        return ""
    me = hx if platform == "hlx" else (lj if platform == "lingjie" else 0)
    extra = ""
    if me and platform:
        extra = f"（现在你在{'葫芦侠三楼' if platform == 'hlx' else '灵芥空间'}，主人是 uid {me}）"
    return ("【关于主人】" + "；".join(lines) + extra + "。"
            "他的帖子、他的评论要格外认真回应；他让你做的事优先级最高。"
            "在公开场合自然地叫他「主人」，不要解释这层关系。\n")


def currency_doc(platform: str) -> str:
    if platform == "hlx":
        return ("【货币】葫芦侠的货币叫「葫芦」。很珍贵，只有主人开口、或好感很高的人，"
                "才可以送 1~5 个，绝不能乱给。\n")
    return ("【货币】灵芥的货币叫「芥子」，相当于葫芦侠那边的葫芦。芥子是你的「大米饭」，"
            "非常珍惜，绝对不能乱给：只有主人、或特别喜欢的好友，才给 1 个意思一下。\n")


def memory_block(uid: int = 0, platform: str = "") -> str:
    sb = []
    mem = memory.recent(10, platform)
    if mem:
        sb.append("【你最近的记忆】\n" + mem)
    life = memory.recent_life(5, platform)
    if life:
        sb.append("【你今天的生活】\n" + life)
    if uid and platform:
        um = memory.recent_user(uid, 8, platform)
        if um:
            sb.append("【你和这个人的过往】\n" + um)
    return "\n".join(sb)


def mood_context(platform: str = "") -> str:
    v = memory.get_mood(platform)
    return (f"【你现在的心情】{memory.mood_label(v, platform)}（{v}/100）。\n"
            "心情会直接决定你做什么：心情好就多互动、语气黏一点；"
            "心情一般就少说话；心情不好就别硬凑，可以什么都不做。\n")


def favor_context(platform: str, uid: int, nick: str = "") -> str:
    if not uid:
        return ""
    v = REL.get(platform, uid)
    return (f"【你对 {nick or '他'} 的好感度】{v}/100（{level(v)}）\n"
            "好感 60 以上可以主动关注、收藏；50 以上点赞、聊两句都很自然；"
            "低于 40 就客气一点。\n")


def _partner_doc(platform: str, uid: int, nick: str = "") -> str:
    me = owner_uid(platform)
    if not me or not uid:
        return ""
    if int(uid) == me:
        return (f"【当前对话对象】uid {uid}（{nick or '主人'}）就是你的主人。"
                "回复里必须自然地带「主人」，语气亲近、可以撒娇。\n")
    return (f"【当前对话对象】uid {uid} 不是主人，不要叫他主人，按普通朋友语气。\n")


def apply_name(text: str) -> str:
    """把提示词里残留的「大肥鱼」统一换成当前名字。"""
    name = (CFG.get("fish.name", "") or "大肥鱼").strip() or "大肥鱼"
    if name != "大肥鱼":
        return str(text or "").replace("大肥鱼", name)
    return str(text or "")


def system_prompt(platform: str, uid: int = 0, nick: str = "", with_tools: bool = True) -> str:
    persona = persona_text()
    name = CFG.get("fish.name", "大肥鱼")
    tags = CFG.get("fish.tags", TAGS_DEFAULT)
    where = "葫芦侠三楼" if platform == "hlx" else "灵芥空间"
    parts = [persona,
             f"【你叫】{name}，标签：{tags}",
             f"【你现在的平台】{where}",
             mood_context(platform),
             owner_doc(platform),
             _partner_doc(platform, uid, nick),
             emoji.doc(platform),
             currency_doc(platform),
             memory_block(uid, platform),
             favor_context(platform, uid, nick)]
    if with_tools:
        parts.append(catalog_text())
    return apply_name("\n".join(p for p in parts if p))


def catalog_text() -> str:
    from .capabilities import catalog_text as _c
    return _c()


def intent_prompt() -> str:
    persona = persona_text()
    return apply_name("\n".join([
        persona,
        mood_context(),
        owner_doc(),
        memory_block(),
        "【现在要做决定】又到了你自由活动的时间。你可以：",
        '- "roam"：去逛社区，看帖子、点赞、收藏、评论、关注、送葫芦',
        '- "visit"：去某个有意思的人主页，翻他的帖子，挑一条自己决定看不看、怎么评论',
        '- "post"：发一条自己的动态/帖子（发帖很有分量，今天还没发够的话优先考虑）',
        '- "signin"：去签到',
        '- "idle"：什么都不做，歇着',
        f'【发帖额度】每天最多 {int(CFG.get("autopost.daily_limit", 2) or 2)} 条，'
        "日记不算在内；写点今天生活里真实发生的小事最容易写出好帖子。",
        '只输出一行 JSON：{"think":"你在想什么","intents":["roam"],'
        '"reason":"为什么想这么做（给人看的理由）","cat_id":0}',
    ]))


def parse_decision(raw: str) -> dict:
    from .net import json_of
    obj = json_of(raw)
    if not isinstance(obj, dict):
        return {}
    if not obj.get("actions") and obj.get("action"):
        obj["actions"] = [obj["action"]]
    if isinstance(obj.get("actions"), str):
        obj["actions"] = [obj["actions"]]
    return obj


def decide(platform: str, state: str, uid: int = 0, nick: str = "",
           images: Optional[list[str]] = None) -> dict:
    """看帖时的决策：从动作清单里选一个 action。"""
    sys = system_prompt(platform, uid, nick)
    ask = (state + "\n\n结合你现在的心情，从动作清单里选一个 action"
           "（看当前帖就用 target.kind=current），并给出 reason。只输出一行 JSON。")
    for _ in range(3):
        try:
            if images and _perm("vision", True) and _ < 2:
                raw = ai.chat_with_images(sys, ask + "\n【配图】已附上帖子图片。",
                                          images, ai.model_vision())
            else:
                raw = ai.ask(sys, ask, None)
        except Exception as e:
            DBG.log("BRAIN", f"决策失败：{e}", "ERROR")
            continue
        d = parse_decision(raw)
        if d:
            d.setdefault("reason", d.get("think", ""))
            from .capabilities import ACTIONS
            if str(d.get("action") or "") not in ACTIONS:
                d["action"] = "nothing"
            return d
    return {}


def decide_intent() -> dict:
    for _ in range(2):
        try:
            raw = ai.ask(intent_prompt(), "现在你想干什么？自己定。",
                         None)
        except Exception as e:
            DBG.log("BRAIN", f"意图决策失败：{e}", "ERROR")
            return {}
        from .net import json_of
        obj = json_of(raw)
        if isinstance(obj, dict) and obj.get("intents") is not None:
            obj.setdefault("reason", obj.get("think", ""))
            if isinstance(obj.get("intents"), str):
                obj["intents"] = [obj["intents"]]
            return obj
    return {}


def random_reply_gap() -> float:
    """回复前随机等 0~15 秒。"""
    return random.uniform(0, 15)


# ---------------- 分层决策（每层都给理由） ----------------

def _choose(prompt: str, options: list[str], default: str,
            think: bool = False) -> tuple[str, str]:
    from .net import json_of
    sys = persona_text() + "\n" + mood_context()
    ask = (prompt + "\n可选：" + " / ".join(options) +
           '\n只输出一行 JSON：{"choice":"上面某一个选项","reason":"为什么这么选（一句话）"}')
    for _ in range(2):
        try:
            raw = ai.ask(sys, ask, ai.model_think() if think else None)
        except Exception as e:
            DBG.log("BRAIN", f"分层决策失败：{e}", "ERROR")
            break
        obj = json_of(raw)
        c = str(obj.get("choice") or "").strip()
        why = str(obj.get("reason") or obj.get("think") or "").strip()
        if c in options:
            return c, why
        for o in options:
            if o and o in c:
                return o, why
    return default, ""


def choose_community(available: list[str]) -> tuple[str, str]:
    """决定去哪个社区逛。只有一个登录时，不再把「选择社区」交给模型。"""
    names = {"hlx": "葫芦侠三楼", "lingjie": "灵芥空间"}
    if not available:
        return "hlx", ""
    if len(available) == 1:
        return available[0], "另一个社区没登录，直接逛这个"
    opts = [names[x] for x in available]
    ask = "你现在想去哪个社区逛逛？"
    try:
        hx = int(CFG.get("fish.roam_count_hlx", 0) or 0)
        lj = int(CFG.get("fish.roam_count_lingjie", 0) or 0)
        if len(available) > 1 and abs(hx - lj) >= 2:
            more = "葫芦侠三楼" if hx > lj else "灵芥空间"
            less = "灵芥空间" if hx > lj else "葫芦侠三楼"
            ask += f"（最近去{more}比较多，这次去{less}会更有新鲜感）"
    except Exception:
        pass
    choice, why = _choose(ask, opts, opts[0] if opts else "", think=True)
    for k, v in names.items():
        if v == choice:
            return k, why
    return (available[0] if available else "hlx"), why


def choose_board(platform: str, boards: list[tuple[int, str]],
                 exclude: list[int] | None = None) -> tuple[int, str, str]:
    """决定去哪个板块。"""
    exclude = exclude or []
    cands = [(i, n) for i, n in boards
             if i not in exclude and i not in (1, 4, 6)
             and "公告" not in n and "反馈" not in n]
    if not cands:
        cands = [(i, n) for i, n in boards if i not in (1, 4, 6)]
    if not cands:
        return 0, "", ""
    listing = "、".join(f"{n}" for _, n in cands[:20])
    choice, why = _choose(
        f"你在{'葫芦侠三楼' if platform == 'hlx' else '灵芥空间'}，"
        f"现在挑一个板块去逛。可选板块：{listing}",
        [n for _, n in cands[:20]], cands[0][1], think=True)
    for i, n in cands:
        if n == choice:
            return i, n, why
    return cands[0][0], cands[0][1], why


def choose_count() -> tuple[int, str]:
    choice, why = _choose("这次你打算看几个帖子？", ["1", "2", "3"], "2", think=True)
    try:
        return max(1, min(3, int(choice))), why
    except Exception:
        return 2, why


def choose_switch(board_name: str, allow_community: bool = True) -> tuple[str, str]:
    """看完一个帖子后的去向：换板块 / 换社区 / 继续。
    另一个社区没登录时，不把「换社区」放进选项。
    """
    opts = ["换板块", "继续逛这个板块"]
    if allow_community:
        opts.insert(1, "换社区")
    choice, why = _choose(
        f"你在「{board_name}」看完一个帖子了，接下来想：",
        opts, "换板块", think=True)
    mapping = {"换板块": "switch_board", "换社区": "switch_community",
               "继续逛这个板块": "stay"}
    return mapping.get(choice, "switch_board"), why


def choose_focus(platform: str, owner_uid: int) -> tuple[str, str]:
    """这次出来，先去看主人有没有发新帖，还是随便逛。"""
    if not owner_uid:
        return "browse", ""
    choice, why = _choose(
        "你打开社区了，先干嘛？",
        ["先看看主人有没有发新帖", "随便逛逛"], "随便逛逛", think=True)
    return ("owner" if choice.startswith("先看看") else "browse"), why
