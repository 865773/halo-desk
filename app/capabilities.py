"""动作能力表：把两个社区的所有操作整理成「固定动作 + 目标」，供提示词和代码共用。

大肥鱼只能从 ACTIONS 里选一个 action，并给出 target；代码负责解析目标并执行。
"""
from __future__ import annotations

import json
import random
import time
from typing import Optional

from . import ai, memory
from .activity import record
from .config import CFG
from .debuglog import DBG
from .relations import REL

BITS = [("like", "点赞"), ("favorite", "收藏"), ("comment", "评论"), ("follow", "关注")]

# ---------- 动作表 ----------
ACTIONS: dict[str, dict] = {}


def _add(action_id: str, desc: str, bits: list[str] | None = None, **extra) -> None:
    ACTIONS[action_id] = {"id": action_id, "desc": desc, "bits": bits or [], **extra}


for mask in range(1, 16):
    chosen = [BITS[i] for i in range(4) if mask & (1 << i)]
    aid = "post_" + "_".join(k for k, _ in chosen)
    names = "、".join(v for _, v in chosen)
    need_content = any(k == "comment" for k, _ in chosen)
    _add(aid, f"对目标帖子：{names}", [k for k, _ in chosen],
         need_content=need_content, need_post=True)

_add("follow_user", "只关注目标用户，不动帖子", ["follow"], need_post=False)
_add("unfollow_user", "取消关注目标用户（需要 target.uid）", [], need_post=False)
_add("unlike_post", "取消点赞目标帖子", [], need_post=True)
_add("unfavorite_post", "取消收藏目标帖子", [], need_post=True)
_add("tip_post", "给目标帖子送葫芦（score 1~5，content 至少 5 字）",
     [], need_post=True, need_tip=True)
_add("publish_post", "发一条新帖子（title/content，可选 genimg 配图描述）",
     [], need_post=False, need_publish=True)
_add("sign_in", "签到（两个平台都签）", [], need_post=False)
_add("reply_comment", "回复某条评论（content 为回复内容）", [], need_post=False,
     need_reply=True)
_add("nothing", "什么都不做", [], need_post=False)

# ---------- 目标 ----------
TARGETS = {
    "current": "当前正在看的帖子（逛社区时）",
    "known_post": "消息通知里那条帖子的 id（回复消息时）",
    "user_first": "某个用户主页的第一个（最新）帖子，需要 uid",
    "user_index": "某个用户的第 N 个帖子，需要 uid 和 index（从 0 开始）",
    "my_first": "我自己主页的第一个帖子",
    "my_index": "我自己的第 N 个帖子，需要 index",
    "my_favorite_first": "我收藏列表里的第一个帖子",
    "my_favorite_index": "我收藏列表里的第 N 个帖子，需要 index",
    "user": "某个用户（只关注/取关时用），需要 uid",
}


def catalog_text() -> str:
    """给模型看的详细教程（动作 + 目标 + 示例）。"""
    lines = ["【动作清单】你必须从下面选一个 action，不能自创："]
    combos = [a for a in ACTIONS if a.startswith("post_") and a != "post_tip"]
    for aid in combos:
        need = "，需要 content（15~40字口语评论）" if ACTIONS[aid]["need_content"] else ""
        lines.append(f"- {aid}：{ACTIONS[aid]['desc']}{need}")
    for aid in ("follow_user", "unfollow_user", "unlike_post", "unfavorite_post",
                "tip_post", "publish_post", "sign_in", "reply_comment", "nothing"):
        lines.append(f"- {aid}：{ACTIONS[aid]['desc']}")
    lines.append("")
    lines.append("【目标 target.kind】")
    for k, v in TARGETS.items():
        lines.append(f"- {k}：{v}")
    lines.append("")
    lines.append("【返回格式】只输出一行 JSON：")
    lines.append('{"action":"上面某一个动作","target":{"kind":"current"},"content":"",'
                 '"title":"","genimg":"","score":1,"reason":"为什么这么做"}')
    lines.append("需要 uid 的目标要写 target.uid；第 N 个帖子再写 target.index。")
    lines.append("")
    lines.append("【示例】")
    lines.append('- 给当前帖点赞+评论：{"action":"post_like_comment","target":{"kind":"current"},'
                 '"content":"这条也太真实了哈哈哈","reason":"看着有意思"}')
    lines.append('- 取消点赞：{"action":"unlike_post","target":{"kind":"current"},"reason":"点错了"}')
    lines.append('- 取消收藏：{"action":"unfavorite_post","target":{"kind":"my_favorite_first"},'
                 '"reason":"清理收藏"}')
    lines.append('- 评论我收藏的第一个帖子：'
                 '{"action":"post_like_comment","target":{"kind":"my_favorite_first"},'
                 '"content":"收藏夹里翻出来的好帖，补个赞","reason":"想回访收藏"}')
    lines.append('- 取消关注：{"action":"unfollow_user","target":{"kind":"user","uid":123},'
                 '"reason":"不想关注了"}')
    lines.append('- 给某人主页第一个帖子点赞+收藏+评论：'
                 '{"action":"post_like_favorite_comment","target":{"kind":"user_first","uid":123},'
                 '"content":"翻到你第一条帖子啦，来踩踩","reason":"主人让我去给他捧场"}')
    lines.append('- 关注楼主再评论：{"action":"post_comment_follow","target":{"kind":"current"},'
                 '"content":"关注了，常来玩呀","reason":"聊得来"}')
    lines.append('- 只关注某人：{"action":"follow_user","target":{"kind":"user","uid":123},'
                 '"reason":"他让我关注"}')
    lines.append('- 回复消息：{"action":"reply_comment","content":"在的在的","reason":"他找我"}')
    lines.append('- 什么都不做：{"action":"nothing","reason":"没兴趣"}')
    return "\n".join(lines)


# ---------- 目标解析 ----------
def _posts_of(platform: str, client, uid: int) -> list[dict]:
    try:
        if platform == "hlx":
            return client.user_posts(uid, 20)
        return client.user_themes(uid, 20)
    except Exception as e:
        DBG.log("ACT", f"取 {uid} 的帖子失败：{e}", "WARN")
        return []


def _favorites_of(platform: str, client, uid: int) -> list[dict]:
    try:
        return client.favorites(uid, 1) if platform == "hlx" else client.favorites(uid, 1)
    except Exception as e:
        DBG.log("ACT", f"取 {uid} 的收藏失败：{e}", "WARN")
        return []


def resolve_target(platform: str, client, target: dict | None,
                   ctx: dict | None = None) -> Optional[dict]:
    """把 target 解析成 {post_id, author_uid, author, title, board}；失败返回 None。"""
    target = target or {}
    ctx = ctx or {}
    kind = (target.get("kind") or "current").lower()
    out = {"post_id": 0, "author_uid": int(target.get("uid", 0) or 0),
           "author": target.get("nick", "") or "", "title": ctx.get("title", ""),
           "board": ctx.get("board", ""), "board_id": int(ctx.get("board_id", 0) or 0)}
    if kind in ("current", "known_post"):
        out["post_id"] = int(ctx.get("post_id", ctx.get("pid", 0)) or 0)
        out["author_uid"] = out["author_uid"] or int(ctx.get("author_uid", 0) or 0)
        return out if out["post_id"] else None
    uid = int(target.get("uid", 0) or 0)
    if kind.startswith("my_"):
        uid = uid or int(getattr(client, "uid", 0) or 0)
    if not uid:
        return None
    posts = _favorites_of(platform, client, uid) if "favorite" in kind \
        else _posts_of(platform, client, uid)
    if not posts:
        return None
    idx = 0 if kind.endswith("first") else max(0, int(target.get("index", 0) or 0))
    if idx >= len(posts):
        return None
    p = posts[idx]
    out["post_id"] = int(p.get("postID", 0) or p.get("tid", 0) or 0)
    u = p.get("user") or {}
    out["author_uid"] = out["author_uid"] or int(
        (u or {}).get("userID", 0) or (u or {}).get("uid", 0) or uid)
    out["author"] = out["author"] or ((u or {}).get("nick") or (u or {}).get("nickname") or "")
    out["title"] = out["title"] or (p.get("title") or "")
    return out if out["post_id"] else None


# ---------- 执行 ----------
def _do_like(platform, client, pid) -> bool:
    if platform == "hlx":
        return (not client.is_praised(pid)) and client.praise(pid)
    return client.like(pid)


def _do_favorite(platform, client, pid) -> bool:
    if platform == "hlx":
        return (not client.is_favorited(pid)) and client.favorite(pid)
    return client.favorite(pid)


def _do_comment(platform, client, pid, text) -> tuple[bool, str]:
    if platform == "hlx":
        return client.comment(pid, text)
    return client.publish_comment(pid, text)


def _do_follow(platform, client, uid) -> bool:
    if platform == "hlx":
        return client.follow_safe(uid)
    return client.follow(uid)[0]


def _perm(name: str, default: bool = True) -> bool:
    return bool(CFG.get(f"perm.{name}", default))


def execute(action: str, platform: str, client, target: dict | None,
            payload: dict | None = None, ctx: dict | None = None,
            log=print) -> dict:
    """执行一个动作，返回 {ok, done, target}。"""
    payload = payload or {}
    spec = ACTIONS.get(action)
    if not spec:
        return {"ok": False, "done": [], "msg": f"未知动作 {action}"}
    reason = (payload.get("reason") or "").strip()
    res = {"ok": False, "done": [], "target": None, "msg": ""}

    if action == "nothing":
        res.update(ok=True, msg="什么都没做")
        return res

    bits = [b for b in spec["bits"] if _perm(b)]
    if spec["bits"] and not bits:
        res["msg"] = "相关权限都关着"
        return res
    if spec.get("need_tip") and not _perm("tip", False):
        res["msg"] = "送葫芦权限关着"
        return res
    if action == "publish_post" and not _perm("post", True):
        res["msg"] = "发帖权限关着"
        return res
    if action == "sign_in" and not _perm("signin", True):
        res["msg"] = "签到权限关着"
        return res

    if action == "sign_in":
        ok = False
        try:
            if platform == "hlx":
                client.signin_all()
            else:
                client.signin_all()
            ok = True
        except Exception as e:
            res["msg"] = str(e)
        res.update(ok=ok, done=["签到"] if ok else [])
        if ok:
            record("signin", "自主签到", platform, reason=reason)
        return res

    if action == "publish_post":
        from .autopost import auto_post
        r = auto_post(platform, ctx.get("board_id", 0) if ctx else 0,
                      (ctx or {}).get("board", ""), hint=payload.get("content", ""),
                      client=client)
        res.update(ok=bool(r.get("ok")), done=["发帖"] if r.get("ok") else [],
                   msg=r.get("msg", ""))
        return res

    tgt = resolve_target(platform, client, target, ctx)
    if action == "follow_user":
        uid = int((target or {}).get("uid", 0) or 0)
        if not uid:
            res["msg"] = "缺少 uid"
            return res
        ok = _do_follow(platform, client, uid)
        if ok:
            REL.add(platform, uid, 3, (target or {}).get("nick", ""))
            record("follow", f"关注了 uid={uid}", platform, uid=uid, reason=reason)
        res.update(ok=ok, done=["关注"] if ok else [])
        return res

    if action == "unfollow_user":
        uid = int((target or {}).get("uid", 0) or 0)
        if not uid:
            res["msg"] = "缺少 uid"
            return res
        if platform == "hlx":
            ok = client.unfollow(uid)
        else:
            ok, _m = client.unfollow(uid)
        if ok:
            REL.add(platform, uid, -3, "")
            record("system", f"取关了 uid={uid}", platform, uid=uid, reason=reason)
        res.update(ok=ok, done=["取关"] if ok else [], msg="" if ok else "取关失败")
        return res

    if action in ("unlike_post", "unfavorite_post"):
        tgt = resolve_target(platform, client, target, ctx)
        if not tgt:
            res["msg"] = "找不到目标帖子"
            return res
        pid = tgt["post_id"]
        res["target"] = tgt
        if action == "unlike_post":
            ok = client.unlike(pid) if platform == "hlx" else client.like(pid, cancel=True)
            label = "取消点赞"
        else:
            ok = client.unfavorite(pid) if platform == "hlx" else client.favorite(pid, cancel=True)
            label = "取消收藏"
        if ok:
            record("system", f"{label}《{tgt.get('title') or ''}》", platform,
                   pid=pid, uid=tgt.get("author_uid"), reason=reason)
        res.update(ok=ok, done=[label] if ok else [], msg="" if ok else f"{label}失败")
        return res

    if not tgt:
        res["msg"] = "找不到目标帖子"
        return res
    pid = tgt["post_id"]
    res["target"] = tgt
    done: list[str] = []
    title = tgt.get("title", "") or ""

    if "like" in bits:
        if _do_like(platform, client, pid):
            done.append("点赞")
            record("like", f"点赞《{title}》", platform, pid=pid,
                   uid=tgt.get("author_uid"), reason=reason)
            REL.add(platform, tgt.get("author_uid", 0), 1, tgt.get("author", ""))
    if "favorite" in bits:
        if _do_favorite(platform, client, pid):
            done.append("收藏")
            record("favorite", f"收藏《{title}》", platform, pid=pid,
                   uid=tgt.get("author_uid"), reason=reason)
            REL.add(platform, tgt.get("author_uid", 0), 1, tgt.get("author", ""))
    if "comment" in bits:
        try:
            if client.has_my_comment(pid):
                res["msg"] = "这个帖子我已经评论过了（可能还在审核）"
                log("这个帖子已经评论过，跳过")
                bits = [b for b in bits if b != "comment"]
        except Exception:
            pass
    if "comment" in bits:
        text = " ".join((payload.get("content") or "").split())
        if not text:
            try:
                text = ai.ask("用一句 15~40 字的自然口语评论这条帖子，不要 AI 腔。",
                              f"标题：{title}", CFG.get("ai.model_basic"))
                text = " ".join((text or "").split())[:120]
            except Exception:
                text = ""
        time.sleep(random.uniform(2.0, 5.0))
        if text:
            from .emoji import sanitize as _san_emoji
            text = _san_emoji(text, platform)
            ok, _m = _do_comment(platform, client, pid, text)
            if ok:
                # 发完查一下是否立刻可见；看不到就是进审核了
                visible = True
                try:
                    time.sleep(2.0)
                    visible = bool(client.has_my_comment(pid))
                except Exception:
                    visible = True
                label = "评论" if visible else "评论（审核中）"
                done.append(label)
                record("comment", f"评论《{title}》：{text}"
                                  + ("" if visible else "（审核中）"),
                       platform, pid=pid, uid=tgt.get("author_uid"), reason=reason)
                memory.remember(f"在{'葫芦侠' if platform == 'hlx' else '灵芥'}评论了 "
                                f"{tgt.get('author') or ''} 的帖子：{text}",
                                tgt.get("author_uid", 0), platform)
                REL.add(platform, tgt.get("author_uid", 0), 2, tgt.get("author", ""))
    if "follow" in bits and tgt.get("author_uid"):
        if _do_follow(platform, client, tgt["author_uid"]):
            done.append("关注")
            record("follow", f"关注了 @{tgt.get('author') or ''}", platform,
                   uid=tgt.get("author_uid"), reason=reason)
            REL.add(platform, tgt.get("author_uid", 0), 3, tgt.get("author", ""))

    if spec.get("need_tip"):
        owner_uid = int(CFG.get(f"fish.owner_uid_{platform}", 0)
                        or CFG.get("fish.owner_uid", 0) or 0)
        favor = REL.get(platform, tgt.get("author_uid", 0)) if tgt.get("author_uid") else 50
        tip_min = int(CFG.get("roam.tip_favor_min", 90) or 90)
        if tgt.get("author_uid") and tgt["author_uid"] != owner_uid and favor < tip_min:
            res.update(done=done, ok=bool(done), msg=f"好感只有 {favor}，不送葫芦")
            return res
        score = max(1, min(5, int(payload.get("score", 1) or 1)))
        why = (payload.get("content") or "").strip()
        if len(why) < 5:
            why = "谢谢你一直陪我说话"
        if platform == "hlx":
            ok, _m = client.tip(pid, score, why)
        else:
            ok, _m = client.reward_publish("theme", pid, score, why)
        if ok:
            done.append(f"送葫芦×{score}")
            record("tip", f"给《{title}》送了 {score} 个葫芦", platform, pid=pid,
                   uid=tgt.get("author_uid"), reason=reason)

    if done:
        memory.nudge_mood(1)
    res["done"] = done
    res["ok"] = bool(done)
    if not done and not res["msg"]:
        res["msg"] = "动作没有生效"
    return res


def reply_with_action(platform: str, client, message: dict, ctx: dict) -> dict:
    """回复消息时用：让模型自己决定「只回话」还是「回话 + 做动作」。"""
    from .brain import system_prompt
    sys = system_prompt(platform, message.get("uid", 0), message.get("nick", ""))
    ask = (f"在{'葫芦侠三楼' if platform == 'hlx' else '灵芥空间'}，"
           f"{message.get('nick') or '对方'}（uid={message.get('uid', 0)}）"
           f"在你的帖子「{message.get('title') or ''}」（post_id={ctx.get('post_id', 0)}）"
           f"下评论：\n{message.get('text') or ''}\n\n"
           "你可以只回一句话，也可以顺手做一件事（比如对方让你去他主页第一个帖子"
           "点赞/收藏/评论，或者让你关注/取关他）。\n"
           "注意：对方说「我 / 我的主页 / 我收藏的」指的是**对方自己**，要用 user_first/"
           "user_index（收藏类目标另说）；只有说「你 / 大肥鱼」时才用 my_*。\n"
           "target.kind=user_first/user_index/user 时，uid 必须填上面的对方 uid 或别人明确给的 uid。\n"
           "只输出一行 JSON："
           '{"reply":"15~45字口语回复","action":"动作清单里的一个动作或 nothing",'
           '"target":{"kind":"known_post"},"content":"","reason":"为什么这么做"}')
    from .net import json_of
    for _ in range(2):
        try:
            raw = ai.ask(sys, ask, CFG.get("ai.model_basic"))
        except Exception as e:
            DBG.log("ACT", f"回复决策失败：{e}", "ERROR")
            continue
        obj = json_of(raw)
        if not obj:
            continue
        reply = " ".join((obj.get("reply") or "").split())[:120]
        action = str(obj.get("action") or "nothing").strip()
        if action not in ACTIONS:
            action = "nothing"
        executed = None
        if action != "nothing":
            tgt = obj.get("target") or {}
            if isinstance(tgt, dict):
                kind = str(tgt.get("kind") or "")
                txt = str(message.get("text") or "")
                # 对方说「我的…」时把 my_* 纠正成 user_*（别去操作自己的主页）
                if kind.startswith("my_") and ("我" in txt and "你" not in txt):
                    tgt["kind"] = "user_" + kind[3:]
                    tgt["uid"] = message.get("uid", 0)
                    kind = tgt["kind"]
                if kind.startswith("user") and not tgt.get("uid"):
                    tgt["uid"] = message.get("uid", 0)   # 模型没写 uid 时用消息发送者
                if kind.startswith("user") and int(tgt.get("uid") or 0) == int(
                        getattr(client, "uid", 0) or 0):
                    tgt["uid"] = message.get("uid", 0)   # 别把「我」当成鱼自己
            executed = execute(action, platform, client, tgt,
                               {"content": obj.get("content", ""),
                                "reason": obj.get("reason", "")}, ctx)
            if executed and not executed.get("ok"):
                record("error", f"决定做 {action} 但没执行成功："
                                f"{executed.get('msg') or '未知原因'}",
                       platform, cid=message.get("cid"), action=action,
                       reason=obj.get("reason", ""))
        return {"reply": reply, "action": action,
                "reason": obj.get("reason", ""), "executed": executed}
    return {"reply": "", "action": "nothing", "executed": None}
