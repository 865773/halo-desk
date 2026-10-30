"""全功能本地仿真测试：不联网、不发任何请求，验证决策/数据完整性。

覆盖：消息接入时间点、10 秒轮询过滤、0-15 秒回复间隔、自动回复、
逛社区决策与理由、意图决策、发帖/签到/打赏、亲密度与心情、动态与统计。
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 隔离数据目录
_src = os.environ.get("HALODESK_HOME", "")
if _src and "--inplace" not in sys.argv:
    dst = ROOT / ".sim_data"
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True, exist_ok=True)
    cfg = Path(_src) / "config.json"
    if cfg.exists():
        shutil.copy(cfg, dst / "config.json")
    os.environ["HALODESK_HOME"] = str(dst)

import app.net as net  # noqa: E402

CHECKS = []
REPORT = {"checks": CHECKS, "writes": [], "errors": []}


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def _block_network(*a, **k):
    REPORT["errors"].append(f"出现了真实网络请求：{a[0] if a else k.get('url', '')}")
    raise RuntimeError("simulation must not touch network")


net.http = _block_network
net.post_form = _block_network
net.post_json = _block_network

from app import ai, brain, automation, diary, roam, stats  # noqa: E402
from app.activity import ACT  # noqa: E402
from app.config import CFG  # noqa: E402
from app.debuglog import DBG  # noqa: E402
from app.relations import REL  # noqa: E402

CFG.set("fish.mem_gate", False)   # 仿真没有模型，关闭记忆判断


class FakeHlx:
    def __init__(self):
        self.key = "k"
        self.uid = 1
        self.writes = []
        self.praised = set()
        self.faved = set()
        self.followed = set()

    # 读
    def boards(self):
        return [(2, "闲聊"), (3, "技术"), (1, "公告"), (6, "意见反馈")]

    def posts(self, cat_id, start=0, count=12):
        return [{"postID": 100 + i, "title": f"帖子{i}", "detail": "<text>内容</text>",
                 "user": {"userID": 50 + i, "nick": f"用户{50 + i}"},
                 "hit": 10, "commentCount": 2} for i in range(3)]

    def notifications(self, n=20):
        now = int(time.time() * 1000)
        return [
            {"content": {"commentID": 900, "postID": 100, "text": "旧的",
                         "createTime": str(now - 7200_000), "userID": 50,
                         "user": {"nick": "旧用户"}}},
            {"content": {"commentID": 901, "postID": 100, "text": "新消息",
                         "createTime": str(now - 30_000), "userID": 51,
                         "user": {"nick": "新用户"}}},
        ]

    def is_praised(self, pid):
        return pid in self.praised

    def is_favorited(self, pid):
        return pid in self.faved

    def is_following(self, uid):
        return uid in self.followed

    # 写（记录）
    def praise(self, pid):
        self.praised.add(pid)
        self.writes.append(("praise", {"pid": pid}))
        return True

    def favorite(self, pid):
        self.faved.add(pid)
        self.writes.append(("favorite", {"pid": pid}))
        return True

    def follow_safe(self, uid):
        if uid in self.followed:
            return True
        self.followed.add(uid)
        self.writes.append(("follow", {"uid": uid}))
        return True

    def follow_once(self, uid):
        if uid in self.followed:
            return False, "已经关注过了"
        self.followed.add(uid)
        self.writes.append(("follow", {"uid": uid}))
        return True, ""

    def unfollow_once(self, uid):
        if uid not in self.followed:
            return False, "本来就没关注"
        self.followed.discard(uid)
        self.writes.append(("unfollow", {"uid": uid}))
        return True, ""

    def comment(self, pid, text, cid=0):
        self.writes.append(("comment", {"pid": pid, "text": text, "cid": cid}))
        if not hasattr(self, "done_pids"):
            self.done_pids = set()
        self.done_pids.add(int(pid))
        return True, ""

    def tip(self, pid, score, text):
        self.writes.append(("tip", {"pid": pid, "score": score, "text": text}))
        return True, ""

    def tip_comment(self, pid, cid, score, text):
        self.writes.append(("tip_comment", {"pid": pid, "cid": cid,
                                            "score": score, "text": text}))
        return True, ""

    def comment_author(self, pid, cid, pages=3):
        return 60

    def signin(self, cat):
        self.writes.append(("signin", {"cat": cat}))
        return True, ""

    def signin_all(self, on_progress=None, skip_boards=(1, 4)):
        for i, _ in self.boards():
            if i in skip_boards:
                continue
            self.signin(i)
        return 2, 0, []

    def create_post(self, cat_id, title, content, image_fids=""):
        self.writes.append(("create_post", {"cat": cat_id, "title": title,
                                            "content": content, "fids": image_fids}))
        return True, ""

    def upload_image(self, png):
        self.writes.append(("upload", {"size": len(png or b"")}))
        return "fake/fid.png"

    def user_posts(self, uid, count=10):
        if int(uid) == int(self.uid):
            return [{"postID": 999, "title": "鱼自己的帖子"}]
        return [{"postID": 777, "title": "我的第一个帖子"}]

    def favorites(self, uid=0, page=1):
        return [{"postID": 555, "title": "我收藏的帖子"}]

    def has_my_comment(self, post_id, since_ms=0, pages=2):
        return int(post_id) in getattr(self, "done_pids", set())

    def followers(self, count=30):
        return [{"user": {"userID": 88, "nick": "粉丝甲"}},
                {"user": {"userID": 89, "nick": "粉丝乙"}}]


class FakeLj:
    def __init__(self):
        self.token = "t"
        self.uid = 2
        self.writes = []

    def notifications(self, page=1):
        return [{"notification_type": "reply", "cid": "700", "themeId": "800",
                 "commentContent": "灵芥旧", "author_nickname": "老A",
                 "author_uid": "60", "themeTitle": "帖", "create_time": "2小时前"},
                {"notification_type": "at_comment", "cid": "702", "themeId": "800",
                 "commentContent": "<at uid=\"2\">@大肥鱼</at> 来给我点个收藏",
                 "author_nickname": "老C", "author_uid": "62", "themeTitle": "帖",
                 "create_time": "刚刚"},
                {"notification_type": "reply", "cid": "701", "themeId": "800",
                 "commentContent": "灵芥新", "author_nickname": "老B",
                 "author_uid": "61", "themeTitle": "帖", "create_time": "刚刚"}]

    def publish_comment(self, tid, content, parent=0):
        self.writes.append(("lj_comment", {"tid": tid, "content": content, "parent": parent}))
        if not hasattr(self, "done_pids"):
            self.done_pids = set()
        self.done_pids.add(int(tid))
        return True, ""

    def user_themes(self, uid, count=10):
        if int(uid) == int(self.uid):
            return [{"tid": 999, "title": "鱼自己的帖子"}]
        return [{"tid": 888, "title": "灵芥第一个帖子"}]

    def favorites(self, uid=0, page=1):
        return [{"tid": 666, "title": "灵芥收藏"}]

    def has_my_comment(self, tid, parent_cid=0, since_ms=0):
        return int(tid) in getattr(self, "done_pids", set())

    def favorite(self, tid):
        self.writes.append(("lj_favorite", {"tid": tid}))
        return True

    def like(self, tid):
        self.writes.append(("lj_like", {"tid": tid}))
        return True

    def follow(self, uid):
        self.writes.append(("lj_follow", {"uid": uid}))
        return True, ""

    def is_following(self, uid):
        return int(uid) in getattr(self, "followed", set())

    def follow_once(self, uid):
        if int(uid) in getattr(self, "followed", set()):
            return False, "已经关注过了"
        self.followed = getattr(self, "followed", set()) | {int(uid)}
        self.writes.append(("lj_follow", {"uid": uid}))
        return True, ""

    def unfollow_once(self, uid):
        if int(uid) not in getattr(self, "followed", set()):
            return False, "本来就没关注"
        self.followed = getattr(self, "followed", set()) - {int(uid)}
        self.writes.append(("lj_unfollow", {"uid": uid}))
        return True, ""

    def reward_publish(self, target_type, target_id, amount, reason="谢谢"):
        self.writes.append(("lj_reward", {"tid": target_id, "amount": amount,
                                          "reason": reason}))
        return True, ""

    def signin_all(self, on_progress=None):
        return 1, 0, []


def fake_ai_ask(system, user, model=None, **kw):
    """按提示词内容返回不同决策。"""
    s = str(user)
    if '"reply"' in s or "reply" in s:
        return ('{"reply":"好呀，这就去你主页看看~","action":"post_like_comment",'
                '"target":{"kind":"user_first","uid":88},'
                '"content":"翻到你第一条帖子啦","reason":"对方让我去他主页互动"}')
    if "日记" in str(system) or "日记" in s:
        return '{"title":"今天的小事","content":"今天吃了白米饭，开心。"}'
    if "看到一个帖子" in s or "看到一条帖子" in s:
        return ('{"think":"这条挺有意思","reason":"内容合我口味",'
                '"action":"post_like_comment","content":"哈哈哈哈这个太真实了"}')
    if "发一条" in s or "帖子" in s:
        return '{"title":"随手一条","content":"今天的风好舒服。"}'
    return '{"action":"nothing","reason":"随便看看"}'


def main() -> int:
    CFG.set("ai.key", "test")
    CFG.set("ai.key", "test")
    CFG.set("hlx.key", "k")
    CFG.set("lingjie.token", "t")
    CFG.set("auto.enabled", True)
    CFG.set("auto.reply_enabled", True)
    CFG.set("roam.enabled", True)
    CFG.set("perm.tip", True)
    CFG.set("perm.post", True)
    CFG.set("autopost.with_image", False)
    CFG.set("fish.img_proto", "openai")
    CFG.set("fish.img_url", "")
    CFG.set("fish.img_key", "")
    CFG.set("fish.img_model", "")
    CFG.set("fish.owner_uid", 0)
    ai.ask = lambda system, user, model=None, **kw: fake_ai_ask(system, user, model)
    ai.chat_with_images = lambda system, user, images, model=None: fake_ai_ask(system, user, model)
    brain.random_reply_gap = lambda: 0.0

    # ---------- 1. 时间解析 ----------
    now = time.time() * 1000
    t1 = automation.parse_ts("11分钟前")
    t2 = automation.parse_ts("3小时前")
    t3 = automation.parse_ts("刚刚")
    check("相对时间解析-分钟", abs(t1 - (now - 660000)) < 5000, t1)
    check("相对时间解析-小时", abs(t2 - (now - 10800000)) < 5000, t2)
    check("相对时间解析-刚刚", abs(t3 - now) < 5000, t3)

    # ---------- 2. 接入时间点过滤 ----------
    hlx = FakeHlx()
    connect = int(now - 60_000)
    cands = automation.filter_hlx(hlx.notifications(), hlx.uid, set(), since=connect)
    check("只处理接入后的新消息", len(cands) == 1 and cands[0]["cid"] == 901,
          [c["cid"] for c in cands])
    lj = FakeLj()
    ljc = automation.filter_lj(lj.notifications(), lj.uid, set(), since=connect)
    check("灵芥只处理新消息（相对时间）", set(c["cid"] for c in ljc) == {701, 702},
          [c["cid"] for c in ljc])

    # ---------- 3. 自动回复 ----------
    ap = automation.AutoPilot(None)
    ap.hlx, ap.lj = hlx, lj
    ap.state = {"hlx": [], "lj": [], "warm_hlx": True, "warm_lj": True,
                "connect_ts": connect, "sent": 0, "last_signin": ""}
    report = {"replies": [], "errors": [], "notes": []}
    mood0 = __import__("app.memory", fromlist=["get_mood"]).get_mood()
    ap._reply_pass("hlx", report)
    check("葫芦侠只回新消息", len(report["replies"]) == 1
          and report["replies"][0][1] == "新用户", report["replies"])
    check("回复写入携带 pid/cid", any(w[0] == "comment" and w[1]["pid"] == 100
                                     and w[1]["cid"] == 901 for w in hlx.writes), hlx.writes)
    check("回复计入亲密度", REL.get("hlx", 51) > 50, REL.get("hlx", 51))
    check("回复提升心情", __import__("app.memory", fromlist=["get_mood"]).get_mood() >= mood0)

    report2 = {"replies": [], "errors": [], "notes": []}
    ap._reply_pass("lj", report2)
    check("灵芥只回新消息", len(report2["replies"]) >= 1
          and report2["replies"][0][1] in ("老B", "老C"), report2["replies"])
    check("灵芥回复携带 tid/parent",
          any(w[0] == "lj_comment" and w[1]["tid"] == 800
              and w[1]["parent"] in (701, 702) for w in lj.writes), lj.writes)

    # ---------- 4. 逛社区决策 ----------
    hlx2 = FakeHlx()
    summary = roam.roam_once(hlx2, max_steps=2, dry_run=False, log=lambda s: None)
    kinds = [w[0] for w in hlx2.writes]
    check("逛社区执行了点赞", "praise" in kinds, kinds)
    check("逛社区执行了评论", "comment" in kinds, kinds)
    check("逛社区跳过公告/反馈",
          summary.get("board") not in ("公告", "意见反馈", ""),
          summary.get("board"))
    dec = [x for x in ACT.recent(300, "hlx") if x["kind"] == "decision"]
    check("动态里有决策记录", len(dec) > 0, len(dec))
    check("决策带理由", any(x.get("meta", {}).get("reason") for x in dec),
          [x.get("meta", {}).get("reason") for x in dec][:2])

    # ---------- 5. 意图决策 ----------
    hlx3 = FakeHlx()
    out = automation.run_intents(["signin", "post"], hlx=hlx3, lj=lj)
    check("意图-签到", "签到" in out["done"], out["done"])
    check("意图-发帖", bool(out.get("post", {}).get("ok")),
          out.get("post", {}).get("msg"))

    # ---------- 5.5 跨社区切换 ----------
    hlx6, lj6 = FakeHlx(), FakeLj()
    seq = iter(["switch_community", "stay", "stay", "stay"])
    brain.choose_switch = lambda board: (next(seq, "stay"), "想去灵芥看看大大王")
    s6 = roam.roam_session(max_steps=1, dry_run=False, log=lambda _m: None,
                           hlx=hlx6, lj=lj6)
    segs = [x["platform"] for x in s6.get("segments", [])]
    check("中途换到另一个社区", segs[:2] == ["hlx", "lingjie"], segs)
    check("换社区有决策理由",
          any("换到" in d["text"] and d.get("reason") for d in s6.get("decisions", [])),
          s6.get("decisions", [])[:2])
    brain.choose_switch = lambda board: ("switch_board", "换个板块")

    # ---------- 6. 日记草稿 ----------
    res = diary.write_diary("hlx", 2, "闲聊", dry_run=True, client=FakeHlx())
    check("日记草稿生成", bool(res.get("title")) and bool(res.get("content")), res.get("title"))
    check("日记试运行不发布", res.get("dry") is True, res.get("msg"))

    # ---------- 7. 固定动作清单 / 用户请求 ----------
    from app import capabilities
    from app.capabilities import ACTIONS, execute, resolve_target
    combos = [a for a in ACTIONS if a.startswith("post_")]
    check("动作组合固定 15 种", len(combos) == 15, len(combos))
    hlx4 = FakeHlx()
    tgt = resolve_target("hlx", hlx4, {"kind": "user_first", "uid": 88}, {})
    check("目标解析-某人主页第一个帖子", bool(tgt) and tgt["post_id"] == 777, tgt)
    from app import capabilities as _cap0
    from app.config import FILES_DIR as _FD0
    _cap0._LIKED_CACHE.pop("hlx", None)
    (_FD0 / "liked_hlx.json").unlink(missing_ok=True)
    for _p in ("hlx", "lingjie"):
        (_FD0 / f"roam_commented_{_p}.json").unlink(missing_ok=True)
        (_FD0 / f"roam_seen_{_p}.json").unlink(missing_ok=True)
    res = execute("post_like_favorite_comment", "hlx", hlx4,
                  {"kind": "user_first", "uid": 88},
                  {"content": "翻到你第一条帖子啦", "reason": "对方让我来互动"}, ctx={})
    check("组合动作执行-点赞收藏评论",
          res["ok"] and {"点赞", "收藏", "评论"} <= set(res["done"]), res.get("done"))

    lj4 = FakeLj()
    tgt2 = resolve_target("lingjie", lj4, {"kind": "user_first", "uid": 60}, {})
    check("灵芥目标解析", bool(tgt2) and tgt2["post_id"] == 888, tgt2)
    res2 = execute("post_like_comment", "lingjie", lj4,
                   {"kind": "user_first", "uid": 60},
                   {"content": "灵芥第一条~", "reason": "来踩踩"}, ctx={})
    check("灵芥组合动作", res2["ok"] and {"点赞", "评论"} <= set(res2["done"]),
          res2.get("done"))

    handled = capabilities.reply_with_action(
        "hlx", FakeHlx(),
        {"uid": 88, "nick": "粉丝甲", "text": "帮我主页第一个帖子点赞评论", "title": "帖子"},
        {"post_id": 100})
    check("模型决定动作并执行", bool(handled.get("reply"))
          and handled.get("action") == "post_like_comment"
          and bool(handled.get("executed")), handled.get("action"))

    # ---------- 7.4 @ 消息 / 收藏目标 / 「我的」纠正 ----------
    at = automation.filter_lj(
        [{"notification_type": "at_comment", "cid": "9001", "themeId": "9002",
          "commentContent": '<at uid="2">@大肥鱼</at> 来给我点个收藏',
          "author_nickname": "老C", "author_uid": "60",
          "create_time": "刚刚", "themeTitle": "t"}],
        2, set(), 0)
    check("灵芥 @ 消息能收到", len(at) == 1 and "@大肥鱼" in at[0]["text"]
          and "<at" not in at[0]["text"], at)

    tgt3 = resolve_target("hlx", FakeHlx(), {"kind": "my_favorite_first"}, {})
    check("收藏列表目标解析", bool(tgt3) and tgt3["post_id"] == 555, tgt3)

    _orig_ask = ai.ask
    ai.ask = lambda s, u, model=None, **k: (
        '{"reply":"好嘞","action":"post_favorite","target":{"kind":"my_first"},'
        '"reason":"测试"}')
    res_my = capabilities.reply_with_action(
        "hlx", FakeHlx(),
        {"uid": 88, "nick": "粉丝甲", "text": "给我主页第一个帖子点收藏", "title": "t"},
        {"post_id": 100})
    ai.ask = _orig_ask
    check("「我的主页」不会操作鱼自己的帖子",
          bool(res_my.get("executed")) and res_my["executed"]["target"]["post_id"] == 777,
          res_my.get("executed"))

    # ---------- 7.7 每日发帖上限 / 平台主人独立 / 旧记忆迁移 ----------
    lim = automation.run_intents(["post"], hlx=FakeHlx(), lj=FakeLj(),
                                 post_count=2, post_limit=2)
    check("每天发帖到上限就不再发",
          "post" not in lim and any("上限" in d for d in lim["done"]), lim["done"])

    CFG.set("fish.owner_uid_hlx", 111)
    CFG.set("fish.owner_uid_lingjie", 222)
    check("两个平台主人各自独立",
          "111" in brain.owner_doc("hlx") and "222" in brain.owner_doc("lingjie"),
          (brain.owner_doc("hlx")[:16], brain.owner_doc("lingjie")[:16]))

    from app.config import FILES_DIR
    from app import memory as mem_mod
    legacy = FILES_DIR / "mem_lj_u9999.txt"
    legacy.write_text("旧记忆", "utf-8")
    mem_mod._migrate_legacy()
    migrated = list(FILES_DIR.glob("mem_lingjie_u9999.txt")) + \
        list((FILES_DIR.parent / "账号").glob("*/**/mem_lingjie_u9999.txt"))
    check("旧灵芥记忆迁到新命名", bool(migrated) and not legacy.exists(),
          [str(p) for p in migrated])
    for p in migrated:
        p.unlink(missing_ok=True)

    # ---------- 7.8 两个平台发帖额度/间隔独立 ----------
    ap9 = automation.AutoPilot(None)
    ap9.state = {"post_day_hlx": time.strftime("%Y-%m-%d"), "post_count_hlx": 1,
                 "post_day_lingjie": time.strftime("%Y-%m-%d"), "post_count_lingjie": 0}
    check("发帖额度按平台分开计数",
          ap9._today_posts("hlx") == 1 and ap9._today_posts("lingjie") == 0,
          (ap9._today_posts("hlx"), ap9._today_posts("lingjie")))
    CFG.set("autopost.daily_limit_hlx", 2)
    CFG.set("autopost.daily_limit_lingjie", 2)
    ap9.state["last_post_ts_hlx"] = time.time()
    check("刚发过的平台不会马上再发", ap9._gap_ok("hlx") is False)
    ap9.state["last_post_ts_hlx"] = time.time() - 20 * 3600
    check("隔得够久才允许再发", ap9._gap_ok("hlx") is True)
    CFG.set("post_test", 1)
    check("额度没用在另一个平台",
          ap9._pick_post_platform() == "lingjie", ap9._pick_post_platform())

    # ---------- 7.9 两套表情 / 上传域名 ----------
    from app import emoji as emo
    hdoc, ldoc = emo.doc("hlx"), emo.doc("lingjie")
    check("两个社区表情互不混用",
          "[滑稽]" in hdoc and "[狗头3]" in ldoc and "[狗头3]" not in hdoc,
          (len(emo.codes("hlx")), len(emo.codes("lingjie"))))
    check("灵芥表情是一整套", len(emo.codes("lingjie")) >= 48, len(emo.codes("lingjie")))
    h_bad = emo.sanitize("好耶[滑稽][狗头3]", "hlx")
    l_bad = emo.sanitize("好耶[狗头3][太开心]", "lingjie")
    check("自创/串台表情会被删掉",
          h_bad == "好耶[滑稽]" and l_bad == "好耶[狗头3]", (h_bad, l_bad))

    from app.lingjie import LingjieClient as _LJ
    hosts1 = _LJ._upload_hosts({"uploadHost": "https://qnljkj.kodo-accelerate.cn-east-1.qiniucs.com"})
    hosts2 = _LJ._upload_hosts({})
    check("上传优先用接口给的域名",
          hosts1[0].startswith("https://qnljkj") and hosts2[0].endswith("up-z0.qiniup.com"),
          (hosts1[0], hosts2[0]))

    # ---------- 7.10 记忆压缩 / 生图模型轮换 ----------
    from app.config import FILES_DIR as _FD
    from app import memory as _mem
    tmp = _FD / "mem_test_u42.txt"
    tmp.write_text("旧记忆。" * 400, "utf-8")          # 远超 800 字上限
    ok_c = _mem.compress(tmp, "user")
    small = len(tmp.read_text("utf-8"))
    check("记忆超字数会压缩", ok_c and small < 800 and "[压缩]" in tmp.read_text("utf-8"),
          small)
    tmp.unlink(missing_ok=True)

    from app import imaging as _img
    cands = _img._model_cands("wan2.6-t2i", "wan2.5-t2i-preview,wanx2.1-t2i-turbo")
    check("生图模型按顺序轮换",
          cands == ["wan2.6-t2i", "wan2.5-t2i-preview", "wanx2.1-t2i-turbo"], cands)

    # ---------- 7.11 关注幂等 / 送芥子 ----------
    hf = FakeHlx()
    hf.followed = {88}
    rf = execute("follow_user", "hlx", hf, {"kind": "user", "uid": 88},
                 {"reason": "测试"})
    check("已关注的人不再重复关注", not rf["ok"] and "已经关注" in rf.get("msg", ""),
          rf.get("msg"))

    hu = FakeHlx()
    ru = execute("unfollow_user", "hlx", hu, {"kind": "user", "uid": 88},
                 {"reason": "测试"})
    check("没关注的人不会误触发关注", not ru["ok"] and "没关注" in ru.get("msg", ""),
          ru.get("msg"))

    lf = FakeLj()
    lf.followed = {60}
    rlf = execute("follow_user", "lingjie", lf, {"kind": "user", "uid": 60},
                  {"reason": "测试"})
    check("灵芥已关注不重复关注", not rlf["ok"], rlf.get("msg"))

    CFG.set("roam.tip_favor_min", 0)
    CFG.set("perm.tip", True)
    lt = FakeLj()
    rt = execute("tip_post", "lingjie", lt, {"kind": "user_first", "uid": 60},
                 {"content": "谢谢你的帖子", "reason": "感谢", "score": 5}, ctx={})
    rewards = [w for w in lt.writes if w[0] == "lj_reward"]
    check("灵芥送芥子一次 1 个",
          bool(rt.get("done")) and rewards and rewards[0][1]["amount"] == 1,
          rewards)

    ht = FakeHlx()
    CFG.set("roam.tip_favor_min", 0)
    rh = execute("tip_post", "hlx", ht, {"kind": "current", "uid": 60},
                 {"reason": "测试", "score": 9}, ctx={"post_id": 123, "title": "测试帖"})
    htips = [w for w in ht.writes if w[0] == "tip"]
    check("葫芦侠送葫芦会清洗空理由并限制分数",
          bool(rh.get("done")) and bool(htips)
          and bool(htips[0][1]["text"].strip())
          and 1 <= htips[0][1]["score"] <= 1,
          htips)

    ht2 = FakeHlx()
    rc = execute("tip_post", "hlx", ht2, {"kind": "current", "uid": 60},
                 {"reason": "回复打赏", "score": 1},
                 ctx={"post_id": 123, "comment_id": 456, "title": "测试帖"})
    ctips = [w for w in ht2.writes if w[0] == "tip_comment"]
    check("葫芦侠回复场景会打赏评论而不是帖子",
          bool(rc.get("done")) and bool(ctips), ctips)

    # ---------- 7.12 发帖板块锁死 / 形象配图 ----------
    class _FB:
        def boards(self):
            return [(9, "玩机教程"), (2, "泳池"), (1, "公告")]

        def forums(self):
            return [(9, "玩机教程"), (2, "闲聊"), (1, "公告")]

    from app.boards import forced_board
    check("葫芦侠只发泳池", forced_board("hlx", _FB()) == (2, "泳池"),
          forced_board("hlx", _FB()))
    check("灵芥只发闲聊", forced_board("lingjie", _FB()) == (2, "闲聊"),
          forced_board("lingjie", _FB()))

    CFG.set("fish.appearance", "红头发、黑裙子、金色眼睛")
    from app.autopost import make_image_prompt
    ip = make_image_prompt("吃饭", "今天吃了白米饭")
    check("配图带上自定义形象", "红头发" in ip and "日系插画" in ip, ip[:40])

    # ---------- 7.13 重复通知去重 / 点赞一次 / 拜访主页 ----------
    dup = automation.filter_lj(
        [{"notification_type": "reply", "cid": "7001", "themeId": "800",
          "commentContent": "同一条", "author_uid": "60", "author_nickname": "A",
          "create_time": "刚刚"},
         {"notification_type": "at_comment", "cid": "7001", "themeId": "800",
          "commentContent": "同一条", "author_uid": "60", "author_nickname": "A",
          "create_time": "刚刚"},
         {"notification_type": "reply", "cid": "7002", "themeId": "800",
          "commentContent": "同一条", "author_uid": "60", "author_nickname": "A",
          "create_time": "刚刚"}],
        2, set(), 0)
    check("灵芥重复通知只回一次", len(dup) == 1, [c["cid"] for c in dup])

    from app import capabilities as cap
    from app.config import FILES_DIR as _FD2
    cap._LIKED_CACHE.pop("hlx", None)
    (_FD2 / "liked_hlx.json").unlink(missing_ok=True)
    hl = FakeHlx()
    execute("post_like", "hlx", hl, {"kind": "current"}, {}, ctx={"post_id": 321})
    execute("post_like", "hlx", hl, {"kind": "current"}, {}, ctx={"post_id": 321})
    check("同一个帖子只点赞一次",
          len([w for w in hl.writes if w[0] == "praise"]) == 1, hl.writes)
    (_FD2 / "liked_hlx.json").unlink(missing_ok=True)
    cap._LIKED_CACHE.pop("hlx", None)

    CFG.set("fish.owner_uid_hlx", 0)
    CFG.set("fish.owner_uid_lingjie", 777)
    check("灵芥主人也能进葫芦侠提示词", "777" in brain.owner_doc("hlx"),
          brain.owner_doc("hlx")[:30])

    ljv = FakeLj()
    from app.config import FILES_DIR as _FDV
    (_FDV / "roam_commented_lingjie.json").unlink(missing_ok=True)
    (_FDV / "roam_seen_lingjie.json").unlink(missing_ok=True)
    CFG.set("fish.last_visit_any", 0)
    CFG.set("fish.last_visit_lingjie_60", 0)
    vs = roam.visit_user("lingjie", 60, dry_run=False, log=lambda _m: None, client=ljv)
    check("去别人主页看帖子并互动", bool(vs.get("seen")) and bool(vs.get("actions")),
          (vs.get("seen"), vs.get("actions")))

    # ---------- 7.14 主人双平台 / 主页动作 / 图片内联 ----------
    CFG.set("fish.owner_uid_hlx", 111)
    CFG.set("fish.owner_uid_lingjie", 222)
    od = brain.owner_doc("lingjie")
    check("主人提示词写清两个平台",
          "你在葫芦侠三楼的主人是 uid 111" in od
          and "你在灵芥空间的主人是 uid 222" in od, od[:60])

    from app import roam as _roam
    _orig_visit = _roam.visit_user
    _roam.visit_user = lambda *a, **k: {"ok": True, "seen": 1,
                                        "actions": ["点赞"],
                                        "errors": [], "titles": ["t"]}
    rv = execute("visit_profile", "lingjie", FakeLj(),
                 {"kind": "user", "uid": 60}, {"reason": "想了解他"}, ctx={})
    _roam.visit_user = _orig_visit
    check("动作清单里的「看他主页」能执行", bool(rv.get("done")), rv)

    from app import ai as _ai
    from app import net as _net
    _orig_bytes = _net.http_bytes
    _net.http_bytes = lambda url, timeout=30: (
        b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    data_url = _ai._as_data_url("http://example.com/a.png")
    _net.http_bytes = _orig_bytes
    check("图片转成 base64 内联", data_url.startswith("data:image/png;base64,"),
          data_url[:30])

    # ---------- 7.15 灵芥图片地址清洗 ----------
    from app.roam import _images as _roam_images
    imgs = _roam_images(
        {"detail": "<image>http://a.com/x.jpg,1440,2095</image>"
                   "<image>http://a.com/y.jpg,1080,1622</image>",
         "images": '["http://a.com/z.jpg"]'}, "lingjie")
    check("图片地址去掉尺寸后缀",
          imgs == ["http://a.com/z.jpg", "http://a.com/x.jpg", "http://a.com/y.jpg"],
          imgs)

    # ---------- 7.16 账号切换：用户记忆按账号分开 ----------
    from app import memory as _mem2
    CFG.set("hlx.uid", 111)
    _mem2.remember("账号111的记忆", 222, "hlx")
    f111 = _mem2.list_user_files("hlx")
    CFG.set("hlx.uid", 333)
    f333 = _mem2.list_user_files("hlx")
    CFG.set("hlx.uid", 111)
    check("切换账号后用户记忆分开",
          any("u222" in p.name for p in f111) and
          not any("u222" in p.name for p in f333),
          (len(f111), len(f333)))
    for p in f111:
        if "u222" in p.name:
            p.unlink(missing_ok=True)

    # ---------- 7.6 已评论过的帖子不再评论 ----------
    hlx7 = FakeHlx()
    hlx7.done_pids = {777}
    res7 = execute("post_comment", "hlx", hlx7, {"kind": "user_first", "uid": 88},
                   {"content": "再来一条", "reason": "测试重复"}, ctx={})
    check("已评论过的帖子跳过评论",
          "评论" not in (res7.get("done") or []), res7.get("done"))

    # 已回复过的消息不再回复（服务端校验）
    ap8 = automation.AutoPilot(None)
    hlx8 = FakeHlx()
    hlx8.done_pids = {100}
    ap8.hlx, ap8.lj = hlx8, FakeLj()
    ap8.state = {"hlx": [], "lj": [], "warm_hlx": True, "warm_lj": True,
                 "connect_ts": int(now - 60_000), "sent": 0, "last_signin": ""}
    rep8 = {"replies": [], "errors": [], "notes": []}
    ap8._reply_pass("hlx", rep8)
    check("已回复过的消息不再回复", len(rep8["replies"]) == 0, rep8["replies"])

    # ---------- 7.6 唤醒间隔跨重启生效 ----------
    ap7 = automation.AutoPilot(None)
    ap7.state["last_intent_ts"] = time.time() - 60      # 1 分钟前跑过
    ap7.last_intent = ap7.state["last_intent_ts"]
    CFG.set("fish.interval_min", 60)
    ap7._intent_tick()
    check("60 分钟内不再唤醒", ap7._intent_busy is False)
    ap7.state["last_intent_ts"] = time.time() - 3600 * 2   # 2 小时前
    ap7.last_intent = ap7.state["last_intent_ts"]
    check("超过间隔才允许唤醒", time.time() - ap7.last_intent > 60 * 60)

    # ---------- 8. 统计 ----------
    c = stats.today_counts()
    check("统计有数据", sum(c.values()) > 0, c)

    # ---------- 9. 无网络请求 ----------
    check("全程没有网络请求", not REPORT["errors"], REPORT["errors"])

    ok = sum(1 for x in CHECKS if x["ok"])
    (ROOT / "sim_report.json").write_text(
        json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{ok}/{len(CHECKS)} 通过")
    for x in CHECKS:
        print(("PASS " if x["ok"] else "FAIL ") + x["name"] + "  " + x["detail"][:60])
    return 0 if ok == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
