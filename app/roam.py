"""逛社区：社区 → 板块 → 看几条 → 每帖做什么 → 换板块/换社区，全部由大肥鱼决策。

每一层决策都写进动态（带理由）；执行统一交给 capabilities。
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from . import brain, memory
from .activity import record
from .config import CFG, FILES_DIR
from .debuglog import DBG
from .hlx import HlxClient
from .lingjie import LingjieClient
from .relations import REL

PLATFORM_NAME = {"hlx": "葫芦侠三楼", "lingjie": "灵芥空间"}

_VISITING = {"on": False}


def in_visit() -> bool:
    return bool(_VISITING.get("on"))


def _seen_path(platform: str) -> Path:
    return FILES_DIR / f"roam_seen_{platform}.json"


def _commented_path(platform: str) -> Path:
    return FILES_DIR / f"roam_commented_{platform}.json"


def _load_ids(path: Path) -> list[int]:
    try:
        if path.exists():
            data = json.loads(path.read_text("utf-8"))
            if isinstance(data, list):
                return [int(x) for x in data][-800:]
    except Exception:
        pass
    return []


def _save_ids(path: Path, ids: list[int]) -> None:
    try:
        path.write_text(json.dumps(list(dict.fromkeys(ids))[-800:]), "utf-8")
    except Exception:
        pass


def _strip(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())


def _boards(client, platform: str) -> list[tuple[int, str]]:
    try:
        return client.boards() if platform == "hlx" else client.forums()
    except Exception:
        return []


def _posts(client, platform: str, board_id: int) -> list[dict]:
    try:
        return client.posts(board_id, 0, 12) if platform == "hlx" \
            else client.themes(board_id, 1, 12)
    except Exception:
        return []


def _posts_of(client, platform: str, uid: int) -> list[dict]:
    try:
        return client.user_posts(uid, 10) if platform == "hlx" \
            else client.user_themes(uid, 10)
    except Exception:
        return []


def _post_id(post: dict, platform: str) -> int:
    if platform == "hlx":
        return int(post.get("postID", 0) or 0)
    return int(post.get("tid", 0) or post.get("themeId", 0) or 0)


def _author(post: dict, platform: str) -> tuple[int, str]:
    u = post.get("user") or {}
    uid = int((u or {}).get("userID", 0) or (u or {}).get("uid", 0)
              or post.get("uid", 0) or 0)
    nick = ((u or {}).get("nick") or (u or {}).get("nickname")
            or post.get("nickname") or "这位")
    return uid, nick


def _clean_img(u: str) -> str:
    """灵芥的 <image> 标签会带 ",宽,高"，要截掉，否则 404。"""
    u = (u or "").strip()
    if "," in u:
        u = u.split(",", 1)[0].strip()
    return u if u.startswith("http") else ""


def _images(post: dict, platform: str) -> list[str]:
    out: list[str] = []
    imgs = post.get("images")
    if isinstance(imgs, str):
        try:
            imgs = json.loads(imgs)
        except Exception:
            imgs = []
    if isinstance(imgs, list):
        for u in imgs:
            if isinstance(u, str):
                u = _clean_img(u)
                if u and u not in out:
                    out.append(u)
    detail = post.get("detail") or post.get("content") or ""
    for m in re.finditer(r"<image>([^<]+)</image>", detail):
        u = _clean_img(m.group(1))
        if u and u not in out:
            out.append(u)
    return out[:3]


def _post_context(post: dict, platform: str, board: str) -> str:
    pid = _post_id(post, platform)
    uid, nick = _author(post, platform)
    title = post.get("title", "") or ""
    detail = _strip(post.get("detail") or post.get("content") or "")[:500]
    return (f"你在「{board}」看到一个帖子：\n【标题】{title}\n【作者】{nick}(uid={uid})\n"
            f"【正文】{detail or '（只有图片）'}\n"
            f"【热度】{post.get('hit', 0)} 浏览 / {post.get('commentCount', 0)} 评论\n"
            f"cat_id={post.get('_cat_id', 0)}，post_id={pid}，作者 user_id={uid}")


def _record(summary: dict, platform: str, text: str, reason: str, meta: dict, log) -> None:
    record("decision", text, platform, reason=reason, **meta)
    summary["decisions"].append({"text": text, "reason": reason})
    DBG.log("ROAM", f"[{platform}] {text}")
    log(text)


def _process(client, platform: str, post: dict, board_id: int, board_name: str,
             summary: dict, seen: list[int], commented: list[int],
             dry_run: bool, log) -> list[str]:
    """看一条帖子并执行决策，返回执行了哪些动作。"""
    pid = _post_id(post, platform)
    if not pid:
        return []
    author_uid, author = _author(post, platform)
    if author_uid == int(getattr(client, "uid", 0) or 0) or pid in commented:
        return []
    post["_cat_id"] = board_id
    seen.append(pid)
    _save_ids(_seen_path(platform), seen)

    ctx = _post_context(post, platform, board_name)
    images = _images(post, platform)
    decision = brain.decide(platform, ctx, author_uid, author, images)
    if not decision:
        summary["errors"].append("模型没有给出决策")
        return []
    action = str(decision.get("action") or "nothing").strip()
    reason = (decision.get("reason") or decision.get("think") or "").strip()
    content = " ".join((decision.get("content") or "").split())
    extra = f"，评论：{content}" if ("comment" in action and content) else ""
    _record(summary, platform,
            f"看《{post.get('title', '')}》→ 决定 {action}{extra}"
            + (f"（理由：{reason}）" if reason else ""),
            reason, {"post": pid, "action": action, "board": board_name}, log)
    summary["seen"] += 1
    summary.setdefault("titles", []).append(post.get("title", "") or "")

    if dry_run:
        summary["actions"].append({"post": pid, "action": action, "dry": True,
                                   "reason": reason})
        return [action]

    from . import capabilities
    res = capabilities.execute(
        action, platform, client, decision.get("target") or {"kind": "current"},
        {"content": content, "reason": reason, "score": decision.get("score", 1)},
        ctx={"post_id": pid, "author_uid": author_uid,
             "title": post.get("title", ""), "board": board_name,
             "board_id": board_id},
        log=log)
    done = res.get("done") or []
    if done:
        summary["actions"].extend(done)
        if "评论" in done:
            commented.append(pid)
            _save_ids(_commented_path(platform), commented)
    return done


def roam_session(max_steps: int = 3, dry_run: bool = False, log=print,
                 hlx=None, lj=None) -> dict:
    """先决定去哪个社区，再看主人主页，最后逛板块；支持中途「换社区」。"""
    avail = []
    if CFG.get("hlx.key", ""):
        avail.append("hlx")
    if CFG.get("lingjie.token", ""):
        avail.append("lingjie")
    if not avail:
        return {"errors": ["两个平台都没登录"]}
    platform, why = brain.choose_community(avail)
    # 平衡：如果连续多次都偏向同一个社区，强制换另一个逛一次
    if len(avail) > 1:
        from datetime import datetime as _dt
        today = _dt.now().strftime("%Y-%m-%d")
        if CFG.get("fish.roam_count_day", "") != today:
            CFG.set("fish.roam_count_day", today)
            CFG.set("fish.roam_count_hlx", 0)
            CFG.set("fish.roam_count_lingjie", 0)
        ch = int(CFG.get(f"fish.roam_count_{platform}", 0) or 0)
        other = "lingjie" if platform == "hlx" else "hlx"
        co = int(CFG.get(f"fish.roam_count_{other}", 0) or 0)
        if ch - co >= 2:
            why = (why + "；" if why else "") + "最近老在一个社区，换个地方逛逛"
            platform = other
        CFG.set(f"fish.roam_count_{platform}",
                int(CFG.get(f"fish.roam_count_{platform}", 0) or 0) + 1)
        CFG.save()
    name = PLATFORM_NAME.get(platform, platform)
    record("decision", f"决定去{name}逛逛" + (f"：{why}" if why else ""),
           platform, reason=why)
    log(f"决定去{name}逛逛" + (f"（{why}）" if why else ""))

    total = {"platform": platform, "board": "", "seen": 0, "actions": [],
             "errors": [], "decisions": [], "segments": []}
    rounds = 0
    clients = {"hlx": hlx, "lingjie": lj}
    while rounds < 2:
        rounds += 1
        client = clients.get(platform) or (
            HlxClient(CFG) if platform == "hlx" else LingjieClient(CFG))
        s = roam_once(client, max_steps, dry_run, log, platform)
        for k in ("actions", "decisions", "errors"):
            total[k].extend(s.get(k) or [])
        total["seen"] += s.get("seen", 0)
        total["board"] = s.get("board") or total["board"]
        total["segments"].append({"platform": platform, "board": s.get("board", "")})
        nxt = s.get("next_platform")
        others = [p for p in avail if p != platform]
        if nxt and others and rounds == 1:
            target = nxt if nxt in others else others[0]
            tname = PLATFORM_NAME.get(target, target)
            why2 = s.get("next_reason", "")
            record("decision", f"换到{tname}看看" + (f"：{why2}" if why2 else ""),
                   target, reason=why2)
            log(f"换到{tname}看看" + (f"（{why2}）" if why2 else ""))
            total["platform"] = target
            platform = target
            continue
        break
    # 把今天逛社区的事记进通用记忆（只记概要，不写用户记忆）
    if total.get("seen"):
        pname = PLATFORM_NAME.get(total.get("platform") or platform, "社区")
        titles = [t for t in (s.get("titles") or []) if t][:5]
        txt = f"在{pname}逛了 {total['seen']} 条帖子，做了 {len(total.get('actions') or [])} 个动作"
        if titles:
            txt += "；看了" + "".join(f"《{t}》" for t in titles)
        memory.remember(txt, platform=total.get("platform") or platform)
    return total


def roam_once(client, max_steps: int = 3, dry_run: bool = False, log=print,
              platform: str = "hlx", prefer_board: int = 0) -> dict:
    summary = {"platform": platform, "board": "", "seen": 0, "actions": [],
               "errors": [], "decisions": [], "next_platform": None}
    boards = _boards(client, platform)
    if not boards:
        summary["errors"].append("拿不到板块列表")
        return summary

    seen = _load_ids(_seen_path(platform))
    commented = _load_ids(_commented_path(platform))

    # 先看主人有没有发新帖（每个平台的主人各自独立）
    owner = int(CFG.get(f"fish.owner_uid_{platform}", 0) or 0) \
        or int(CFG.get("fish.owner_uid", 0) or 0)
    if owner:
        focus, why_f = brain.choose_focus(platform, owner)
        if focus == "owner":
            _record(summary, platform, f"先看看主人有没有发新帖"
                    + (f"：{why_f}" if why_f else ""), why_f, {"owner": owner}, log)
            for p in _posts_of(client, platform, owner)[:5]:
                pid = _post_id(p, platform)
                if not pid or pid in seen:
                    continue
                try:
                    if pid in commented or client.has_my_comment(pid):
                        seen.append(pid)
                        _save_ids(_seen_path(platform), seen)
                        continue
                except Exception:
                    pass
                _process(client, platform, p, 0, "主人的主页", summary,
                         seen, commented, dry_run, log)
                break

    board_id, board_name, why = brain.choose_board(platform, boards)
    if not board_id:
        summary["errors"].append("没有可用板块")
        return summary
    summary["board"] = board_name
    _record(summary, platform, f"决定逛「{board_name}」" + (f"：{why}" if why else ""), why,
            {"board": board_name, "board_id": board_id}, log)

    count, why_n = brain.choose_count()
    _record(summary, platform, f"打算看 {count} 个帖子" + (f"：{why_n}" if why_n else ""),
            why_n, {"count": count}, log)

    viewed = 0
    tries = 0
    while viewed < count and tries < count * 5:
        tries += 1
        posts = _posts(client, platform, board_id)
        target = None
        for p in posts:
            pid = _post_id(p, platform)
            if not pid or pid in seen:
                continue
            # 已经评论过的帖子：不再重复看，也不再重复评论
            try:
                if pid in commented or client.has_my_comment(pid):
                    seen.append(pid)
                    _save_ids(_seen_path(platform), seen)
                    continue
            except Exception:
                if pid in commented:
                    continue
            target = p
            break
        if target is None:
            board_id, board_name, why = brain.choose_board(
                platform, boards, exclude=[board_id])
            summary["board"] = board_name
            _record(summary, platform, f"这板块没新帖了，换到「{board_name}」"
                    + (f"：{why}" if why else ""), why,
                    {"board": board_name, "board_id": board_id}, log)
            continue

        _process(client, platform, target, board_id, board_name, summary,
                 seen, commented, dry_run, log)
        viewed += 1

        nxt, why_s = brain.choose_switch(board_name)
        if nxt == "switch_community":
            other = "lingjie" if platform == "hlx" else "hlx"
            logged = CFG.get("lingjie.token", "") if other == "lingjie" else CFG.get("hlx.key", "")
            if logged:
                _record(summary, platform,
                        f"想换到{PLATFORM_NAME[other]}看看" + (f"：{why_s}" if why_s else ""),
                        why_s, {"switch_to": other}, log)
                summary["next_platform"] = other
                summary["next_reason"] = why_s
                break
            why_s = (why_s + "；" if why_s else "") + "另一个社区没登录，继续逛这个板块"
        if nxt == "switch_board":
            board_id, board_name, why_b = brain.choose_board(
                platform, boards, exclude=[board_id])
            if board_id:
                summary["board"] = board_name
                _record(summary, platform, f"换到「{board_name}」"
                        + (f"：{why_b}" if why_b else ""), why_b,
                        {"board": board_name, "board_id": board_id}, log)
        else:
            _record(summary, platform,
                    f"继续逛「{board_name}」" + (f"：{why_s}" if why_s else ""),
                    why_s, {"switch": "stay"}, log)
        time.sleep(random.uniform(1.5, 4.0))
    return summary


def pick_interesting_user(platform: str) -> tuple[int, str]:
    """从好感度/互动记录里挑一个“有意思的人”。"""
    try:
        rows = REL.top(platform, 20)
    except Exception:
        rows = []
    owner = int(CFG.get(f"fish.owner_uid_{platform}", 0)
                or CFG.get("fish.owner_uid", 0) or 0)
    me = 0
    try:
        from .names import get as _name_of  # noqa: F401
    except Exception:
        pass
    cands = [(uid, nick, favor) for uid, nick, favor in rows
             if uid and uid != owner]
    if not cands:
        return 0, ""
    cands.sort(key=lambda x: x[2], reverse=True)
    uid, nick, _favor = cands[0]
    return uid, nick


def visit_user(platform: str, uid: int = 0, dry_run: bool = False, log=print,
               client=None) -> dict:
    """去某人的主页看帖子，由大肥鱼自己决定看哪个、做什么、怎么评论。"""
    from . import names
    client = client or (HlxClient(CFG) if platform == "hlx" else LingjieClient(CFG))
    summary = {"platform": platform, "uid": uid, "seen": 0, "actions": [],
               "errors": [], "decisions": [], "titles": []}
    if not uid:
        uid, nick = pick_interesting_user(platform)
        if not uid:
            summary["errors"].append("还没有值得拜访的人")
            return summary
    else:
        nick = names.get(platform, uid)
    if not nick:
        try:
            d = client.user_info(uid) if platform == "hlx" else \
                (client._get("/user/info", f"uid={uid}") or {}).get("data") or {}
            nick = (d or {}).get("nick") or (d or {}).get("nickname") or f"uid={uid}"
        except Exception:
            nick = f"uid={uid}"
    names.set_name(platform, uid, nick)
    _record(summary, platform, f"去 @{nick} 的主页看看" + ("（试运行）" if dry_run else ""),
            "对这个人有点好奇", {"visit_uid": uid}, log)

    posts = _posts_of(client, platform, uid)
    if not posts:
        summary["errors"].append("他主页没有帖子")
        return summary
    if len(posts) > 1:
        try:
            pick = brain._choose(  # noqa: SLF001
                f"你在 @{nick} 的主页，看到他发的这些帖子：",
                [p.get("title", "")[:20] or "无标题" for p in posts[:6]],
                posts[0].get("title", "") or "无标题")
            for p in posts[:6]:
                if (p.get("title", "") or "无标题").startswith(pick[:6]):
                    posts = [p] + [x for x in posts if x is not p]
                    break
        except Exception:
            pass
    seen = _load_ids(_seen_path(platform))
    commented = _load_ids(_commented_path(platform))
    # 拜访频率限制：全局 1 分钟最多一次；同一个人 30 分钟内不重复拜访
    now = time.time()
    last_any = float(CFG.get("fish.last_visit_any", 0) or 0)
    last_uid = float(CFG.get(f"fish.last_visit_{platform}_{uid}", 0) or 0)
    if now - last_any < 60:
        summary["errors"].append("刚去过主页，先等一分钟")
        return summary
    if now - last_uid < 1800:
        summary["errors"].append(f"半小时内已经去过 @{nick} 的主页了")
        return summary
    CFG.set("fish.last_visit_any", now)
    CFG.set(f"fish.last_visit_{platform}_{uid}", now)
    CFG.save()
    _VISITING["on"] = True
    try:
        for p in posts[:1]:
            pid = _post_id(p, platform)
            if not pid or pid in seen or pid in commented:
                summary["errors"].append("这个帖子已经看过/评论过了")
                continue
            post = dict(p)
            post["_cat_id"] = 0
            _process(client, platform, post, 0, f"@{nick} 的主页", summary,
                     seen, commented, dry_run, log)
            summary["titles"].append(post.get("title", ""))
            if dry_run:
                break
    finally:
        _VISITING["on"] = False
    if summary["actions"]:
        memory.remember(f"去 @{nick} 的主页看了帖子，做了 "
                        f"{len(summary['actions'])} 个动作", platform=platform)
        REL.add(platform, uid, 1, nick)
    return summary
