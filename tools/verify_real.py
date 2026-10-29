"""真实数据 + 本地拦截验证。

读接口走真实网络（板块、帖子、通知、用户信息），
写接口（签到/评论/发帖/上传/打赏）在本地拦下，只校验参数，不发往服务器。

用法：
    set HALODESK_HOME=...\\dist\\data
    python tools/verify_real.py
"""
import json
import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop")
sys.path.insert(0, str(ROOT))

# 默认在数据副本上跑，绝不碰用户真实数据；加 --inplace 才用原目录
_src = os.environ.get("HALODESK_HOME", "")
if _src and "--inplace" not in sys.argv:
    _dst = ROOT / ".verify_data"
    shutil.rmtree(_dst, ignore_errors=True)
    _dst.mkdir(parents=True, exist_ok=True)
    cfg = Path(_src) / "config.json"
    if cfg.exists():
        shutil.copy(cfg, _dst / "config.json")
    os.environ["HALODESK_HOME"] = str(_dst)

import app.net as net  # noqa: E402

COMMUNITY_HOSTS = ("floor.huluxia.com", "api.lingjie888.cn", "qn.lingjie888.cn",
                   "up-z2.qiniup.com")
RECORDS: list[dict] = []
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))


def _fake_body(url: str) -> str:
    if "/user/signin/" in url:
        return json.dumps({"status": 1, "msg": "已签到"})
    if "/comment/create/" in url:
        return json.dumps({"status": 1})
    if "/post/create/" in url:
        return json.dumps({"status": 1, "postID": 1})
    if "/credits/transfer/" in url:
        return json.dumps({"iscredits": 1})
    if "/theme/comment/publish" in url:
        return json.dumps({"code": 200, "msg": "ok"})
    if "/theme/publish" in url:
        return json.dumps({"code": 200, "msg": "ok"})
    if "/upload/v3/image" in url:
        return json.dumps({"fid": "g4/verify/fake.png"})
    if "qiniup.com" in url:
        return json.dumps({"key": "verify/fake.jpg"})
    return json.dumps({"status": 1, "code": 200})


_orig_http = net.http

WRITE_HINTS = ("/user/signin/", "/comment/create/", "/post/create/", "/credits/transfer/",
               "/post/praise/", "/post/favorite/", "/friendship/follow", "/moderator/",
               "/theme/comment/publish", "/theme/publish", "/upload/v3/image",
               "qiniup.com", "/post/destroy/")


def _is_write(url: str) -> bool:
    if "/check/" in url or "/list" in url:
        return False
    return any(h in url for h in WRITE_HINTS)


def _patched_http(url, method="GET", body=None, headers=None, timeout=20, retries=2):
    community = any(h in url for h in COMMUNITY_HOSTS)
    if community and (method.upper() == "POST" or _is_write(url)):
        RECORDS.append({
            "url": url,
            "method": method,
            "body": body if isinstance(body, str) else repr(body)[:200],
            "headers": {k: v for k, v in (headers or {}).items()
                        if k.lower() in ("content-type", "authorization")},
            "at": time.strftime("%H:%M:%S"),
        })
        return _fake_body(url)
    return _orig_http(url, method, body, headers, timeout, retries)


net.http = _patched_http

# 先确认导入的客户端拿到的是打过补丁的 net
from app import ai, autopost, publishing  # noqa: E402
from app.activity import ACT  # noqa: E402
from app.automation import filter_hlx, filter_lj  # noqa: E402
from app.config import CFG  # noqa: E402
from app.debuglog import DBG  # noqa: E402
from app.hlx import HlxClient  # noqa: E402
from app.lingjie import LingjieClient  # noqa: E402
from app.relations import REL  # noqa: E402
from app.roam import roam_once  # noqa: E402
from app.signin_state import mark_signed, reset, signed_today  # noqa: E402

report = {"checks": CHECKS, "records": RECORDS, "sample": {}, "errors": []}


def _params(url: str) -> dict:
    q = url.split("?", 1)[1] if "?" in url else ""
    out = {}
    for part in q.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def _body_params(body: str) -> dict:
    out = {}
    for part in (body or "").split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def main() -> int:
    hlx = HlxClient(CFG)
    lj = LingjieClient(CFG)

    # ---------- 0. 账号 ----------
    check("葫芦侠已登录", bool(hlx.key), f"uid={hlx.uid}")
    check("灵芥已登录", bool(lj.token), f"uid={lj.uid}")

    # ---------- 1. 真实读数据 ----------
    try:
        boards = hlx.boards()
        check("葫芦侠板块", len(boards) > 0, f"{len(boards)} 个")
        report["sample"]["hlx_board"] = boards[0][1] if boards else ""
    except Exception as e:
        check("葫芦侠板块", False, str(e))
        boards = []

    try:
        posts = hlx.posts(boards[1][0] if len(boards) > 1 else 2, 0, 5)
        check("葫芦侠帖子", len(posts) > 0, f"{len(posts)} 条")
        report["sample"]["hlx_post"] = (posts[0].get("title") or "")[:30] if posts else ""
    except Exception as e:
        check("葫芦侠帖子", False, str(e))

    hlx_notifs = []
    try:
        hlx_notifs = hlx.notifications(10)
        check("葫芦侠通知", len(hlx_notifs) > 0, f"{len(hlx_notifs)} 条")
    except Exception as e:
        check("葫芦侠通知", False, str(e))

    lj_notifs = []
    try:
        lj_notifs = lj.notifications(1)
        check("灵芥通知", len(lj_notifs) > 0, f"{len(lj_notifs)} 条")
    except Exception as e:
        check("灵芥通知", False, str(e))

    # ---------- 2. 签到（拦截） ----------
    try:
        cat = boards[1][0] if len(boards) > 1 else 2
        ok, msg = hlx.signin(cat)
        check("葫芦侠签到请求已生成", ok, f"板块 {cat}")
        rec = RECORDS[-1]
        p = _params(rec["url"])
        b = _body_params(rec["body"])
        sign = b.get("sign", "")
        check("葫芦侠签到参数完整",
              bool(p.get("cat_id")) and bool(p.get("time")) and bool(p.get("_key")),
              f"cat_id={p.get('cat_id')} time={p.get('time')}")
        check("葫芦侠签到签名是32位大写", bool(re.fullmatch(r"[0-9A-F]{32}", sign)),
              sign[:8] + "…")
    except Exception as e:
        check("葫芦侠签到", False, repr(e))

    # ---------- 3. 回复（拦截） ----------
    try:
        cands = filter_hlx(hlx_notifs, hlx.uid, set())
        check("葫芦侠通知可解析", len(cands) > 0, f"{len(cands)} 条待回")
        if cands:
            c = cands[0]
            text = ai.ask("用一句 15~40 字自然口语回复这条评论。",
                          f"{c['nick']} 评论：{c['text']}", CFG.get("ai.model_basic"))
            text = " ".join((text or "").split())[:120]
            check("AI 生成回复非空", bool(text), text[:30])
            ok, msg = hlx.comment(c["pid"], text, c["cid"])
            check("葫芦侠回复请求已生成", ok, f"pid={c['pid']} cid={c['cid']}")
            body = _body_params(RECORDS[-1]["body"])
            check("回复携带 post_id/comment_id/text",
                  body.get("post_id") == str(c["pid"])
                  and body.get("comment_id") == str(c["cid"])
                  and len(body.get("text", "")) > 0,
                  f"text={body.get('text','')[:20]}")
    except Exception as e:
        report["errors"].append(f"hlx reply: {e}")
        check("葫芦侠回复", False, repr(e))

    try:
        cands = filter_lj(lj_notifs, lj.uid, set())
        check("灵芥通知可解析", len(cands) > 0, f"{len(cands)} 条待回")
        if cands:
            c = cands[0]
            ok, msg = lj.publish_comment(c["tid"], "在的在的，刚看到～", c["cid"])
            check("灵芥回复请求已生成", ok, f"tid={c['tid']} parent={c['cid']}")
    except Exception as e:
        report["errors"].append(f"lj reply: {e}")
        check("灵芥回复", False, repr(e))

    # ---------- 4. 发帖（拦截） ----------
    try:
        board_id, board_name = (boards[1] if len(boards) > 1 else (2, "闲聊"))
        res = autopost.auto_post("hlx", board_id, board_name, dry_run=False)
        check("自动发帖草稿", bool(res.get("title")), res.get("title", "")[:24])
        check("自动发帖请求已生成", bool(res.get("ok")), res.get("msg", ""))
        body = _body_params(RECORDS[-1]["body"]) if RECORDS else {}
        check("发帖携带 cat_id/title/detail",
              bool(body.get("cat_id")) and bool(body.get("title")) and bool(body.get("detail")),
              f"title={body.get('title','')[:16]}")
        check("发帖签名是32位小写", bool(re.fullmatch(r"[0-9a-f]{32}", body.get("sign", ""))),
              str(body.get("sign", ""))[:8] + "…")
    except Exception as e:
        report["errors"].append(f"autopost: {e}")
        check("自动发帖", False, repr(e))

    # ---------- 5. 逛社区（拦截写操作） ----------
    try:
        before = len(RECORDS)
        summary = roam_once(hlx, max_steps=1, dry_run=False, log=lambda s: None)
        check("逛社区跑通", summary.get("seen", 0) >= 1 or bool(summary.get("board")),
              f"板块={summary.get('board')} 动作={summary.get('actions')}")
        report["sample"]["roam"] = summary
        report["sample"]["roam_writes"] = len(RECORDS) - before
    except Exception as e:
        report["errors"].append(f"roam: {e}")
        check("逛社区", False, repr(e))

    # ---------- 6. 每日日记（只生成草稿） ----------
    try:
        from app.diary import write_diary
        board_id2, board_name2 = (boards[1] if len(boards) > 1 else (2, "闲聊"))
        res = write_diary("hlx", board_id2, board_name2, dry_run=True)
        check("日记草稿生成", bool(res.get("title")) and bool(res.get("content")),
              res.get("title", "")[:24])
        check("日记试运行不发布", bool(res.get("dry")), res.get("msg", ""))
    except Exception as e:
        report["errors"].append(f"diary: {e}")
        check("日记草稿", False, repr(e))

    # ---------- 7. 删除帖/评论（拦截） ----------
    try:
        ok, _ = hlx.delete_post(1)
        check("葫芦侠删帖请求已生成", ok and "/post/destroy/" in RECORDS[-1]["url"],
              RECORDS[-1]["url"].split("?")[0][-40:])
        ok, _ = hlx.delete_comment(1)
        check("葫芦侠删评论请求已生成", ok and "deleteComment" in RECORDS[-1]["url"],
              RECORDS[-1]["url"].split("?")[0][-40:])
        ok, _ = lj.delete_theme(1)
        check("灵芥删帖请求已生成", ok and "/moderator/delete" in RECORDS[-1]["url"],
              RECORDS[-1]["url"].split("?")[0][-30:])
    except Exception as e:
        report["errors"].append(f"delete: {e}")
        check("删除接口", False, repr(e))

    # ---------- 8. 统计 ----------
    try:
        from app.stats import today_counts
        counts = today_counts()
        check("今日统计有记录", sum(counts.values()) > 0, str(counts))
    except Exception as e:
        check("今日统计", False, repr(e))

    # ---------- 9. 看图解析 / 权限开关 ----------
    try:
        from app.roam import _images
        imgs = _images({"detail": "<text>hi</text><image>http://x/a.png</image>",
                        "images": ["http://y/b.jpg"]}, "hlx")
        check("帖子配图解析", len(imgs) >= 2, str(imgs))
    except Exception as e:
        check("帖子配图解析", False, repr(e))

    try:
        from app.capabilities import execute as cap_execute
        CFG.set("perm.like", False)
        before = len(RECORDS)
        r = cap_execute("post_like", "hlx", hlx, {"kind": "current"}, {"reason": "t"},
                        ctx={"post_id": 1, "author_uid": 0})
        check("权限关闭后不点赞", len(RECORDS) == before, f"{before}->{len(RECORDS)}")
        CFG.set("perm.like", True)
    except Exception as e:
        check("权限开关", False, repr(e))

    # ---------- 9. 真实用户请求解析 + 双方首个帖子 ----------
    try:
        from app.capabilities import ACTIONS, catalog_text, resolve_target
        combos = [a for a in ACTIONS if a.startswith("post_")]
        check("动作组合固定 15 种", len(combos) == 15, len(combos))
        txt = catalog_text()
        check("教程覆盖主页目标", "user_first" in txt and "user_index" in txt,
              "user_first/user_index" in txt)
        hposts = hlx.user_posts(hlx.uid, 5)
        check("葫芦侠-我的帖子可读", isinstance(hposts, list), f"{len(hposts)} 条")
        if hposts:
            check("葫芦侠-帖子字段完整",
                  bool(hposts[0].get("postID")) and bool(hposts[0].get("title")),
                  str(hposts[0].get("title"))[:20])
            t = resolve_target("hlx", hlx, {"kind": "my_first"}, {})
            check("目标解析-我的第一个帖子", bool(t) and t["post_id"] > 0,
                  t and t["post_id"])
        lthemes = lj.user_themes(lj.uid, 5)
        check("灵芥-我的帖子可读", isinstance(lthemes, list), f"{len(lthemes)} 条")
        if lthemes:
            check("灵芥-帖子字段完整",
                  bool(lthemes[0].get("tid")) and bool(lthemes[0].get("title")),
                  str(lthemes[0].get("title"))[:20])
    except Exception as e:
        report["errors"].append(f"capabilities: {e}")
        check("动作能力表", False, repr(e))

    # ---------- 10. 灵芥逛社区（只看不执行） ----------
    try:
        from app.roam import roam_once as roam_any
        s = roam_any(lj, max_steps=1, dry_run=True, platform="lingjie",
                     log=lambda _m: None)
        check("灵芥逛社区跑通", bool(s.get("board")), f"板块={s.get('board')}")
        check("灵芥决策带理由",
              bool(s.get("decisions")) and any(d.get("reason") for d in s["decisions"]),
              s.get("decisions", [{}])[:1])
    except Exception as e:
        report["errors"].append(f"lj roam: {e}")
        check("灵芥逛社区", False, repr(e))

    # ---------- 10.5 @通知 / 审核通知 / 收藏列表 ----------
    try:
        ats = [c for c in filter_lj(lj_notifs, lj.uid, set(), 0)
               if c.get("kind") == "at_comment"]
        check("灵芥 @ 通知能解析", len(ats) >= 1,
              ats[0]["text"][:20] if ats else "没有 @ 通知")
        if ats:
            check("@ 通知已去掉标签", "<at" not in ats[0]["text"], ats[0]["text"][:30])
    except Exception as e:
        check("灵芥 @ 通知", False, repr(e))

    try:
        notices = hlx.review_notices(10)
        check("葫芦侠审核通知可读", isinstance(notices, list), f"{len(notices)} 条")
        if notices:
            check("审核通知文本合理", "评论" in notices[0], notices[0][:24])
    except Exception as e:
        check("审核通知", False, repr(e))

    try:
        hfav = hlx.favorites(hlx.uid, 1)
        check("葫芦侠收藏列表可读", isinstance(hfav, list), f"{len(hfav)} 条")
        lfav = lj.favorites(lj.uid, 1)
        check("灵芥收藏列表可读", isinstance(lfav, list), f"{len(lfav)} 条")
        from app.capabilities import resolve_target
        if hfav:
            t = resolve_target("hlx", hlx, {"kind": "my_favorite_first"}, {})
            check("收藏目标可解析", bool(t) and t["post_id"] > 0, t and t["post_id"])
    except Exception as e:
        check("收藏列表", False, repr(e))

    # ---------- 11. 签到去重 ----------    try:
        reset("hlx")
        today_before = signed_today("hlx")
        mark_signed("hlx")
        today_after = signed_today("hlx")
        check("签到日期标记生效", today_after and not today_before, f"{today_before} → {today_after}")
    except Exception as e:
        check("签到日期标记", False, repr(e))

    # ---------- 7. 动态/日志 ----------
    try:
        hlx_items = ACT.recent(200, "hlx")
        lj_items = ACT.recent(200, "lj")
        check("动态里有三楼记录", len(hlx_items) > 0, f"hlx={len(hlx_items)} lj={len(lj_items)}")
        check("调试日志有 HLX 请求",
              any("[HLX]" in ln for ln in DBG.tail(500)),
              f"日志 {len(DBG.tail(500))} 行")
    except Exception as e:
        check("动态/日志", False, repr(e))

    # ---------- 输出 ----------
    report["checks"] = [{"name": n, "ok": o, "detail": d} for n, o, d in CHECKS]
    report["record_count"] = len(RECORDS)
    (ROOT / "verify_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ok_n = sum(1 for _, o, _ in CHECKS if o)
    print(f"{ok_n}/{len(CHECKS)} 通过，拦截写请求 {len(RECORDS)} 个")
    for n, o, d in CHECKS:
        print(("PASS " if o else "FAIL ") + n + ("  " + d if d else ""))
    return 0 if ok_n == len(CHECKS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
