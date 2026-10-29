"""自动任务：双平台消息监听（10 秒一轮）+ 大肥鱼自动回复 + 每日定时签到。

设计原则：
- 只在本地记录「已处理过的评论 id」，宁可不回也不重复回；
- 首次开启时把现有通知全部标记为已读，不翻旧账；
- 所有网络/AI 调用都在后台线程，UI 只收信号；
- 每次动作都写动态（activity）和调试日志（debug）。
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from . import ai, brain, memory
from .activity import ACT, record
from .config import CFG, FILES_DIR
from .debuglog import DBG
from .hlx import HlxClient
from .lingjie import LingjieClient
from .relations import REL

STATE_PATH = FILES_DIR / "auto_state.json"
MAX_SEEN = 800


def is_auth_error(err) -> bool:
    s = str(err or "")
    return any(k in s for k in (
        "401", "未授权", "重新登录", "登录失效", "登录已失效", "token无效",
        "token 无效", "token已过期", "token 已过期", "登录已过期"))
def reply_key(platform: str, c: dict) -> str:
    """同一帖子 + 同一句话只回一次。"""
    import hashlib
    tid = str(c.get("pid") or c.get("tid") or c.get("cid") or "")
    text = " ".join(str(c.get("text") or "").split())
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return f"{platform}:{tid}:{h}"


def _load_state() -> dict:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text("utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"hlx": [], "lj": [], "warm_hlx": False, "warm_lj": False,
            "last_signin": "", "sent": 0}


def _save_state(state: dict) -> None:
    try:
        for k in ("hlx", "lj"):
            ids = list(dict.fromkeys(state.get(k, [])))[-MAX_SEEN:]
            state[k] = ids
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def _cutoff() -> int:
    """只处理最近 24 小时的消息（毫秒时间戳，0 表示无所谓）。"""
    return int((time.time() - 24 * 3600) * 1000)


def parse_ts(v) -> int:
    """把各种时间写法转成毫秒时间戳；认不出来返回 0。"""
    if isinstance(v, (int, float)):
        return int(v if v > 1e12 else v * 1000)
    s = str(v or "").strip()
    if not s:
        return 0
    if s.isdigit():
        n = int(s)
        return n if n > 1e12 else n * 1000
    now = time.time()
    import re
    m = re.match(r"^(\d+)\s*秒前", s)
    if m:
        return int((now - int(m.group(1))) * 1000)
    m = re.match(r"^(\d+)\s*分钟前", s)
    if m:
        return int((now - int(m.group(1)) * 60) * 1000)
    m = re.match(r"^(\d+)\s*小时前", s)
    if m:
        return int((now - int(m.group(1)) * 3600) * 1000)
    m = re.match(r"^(\d+)\s*天前", s)
    if m:
        return int((now - int(m.group(1)) * 86400) * 1000)
    if s in ("刚刚", "刚才", "just now"):
        return int(now * 1000)
    if s.startswith("昨天"):
        return int((now - 86400) * 1000)
    m = re.match(r"^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", s)
    if m:
        from datetime import datetime as _dt
        mo, d, hh, mm = (int(x) for x in m.groups())
        dt = _dt(_dt.now().year, mo, d, hh, mm)
        return int(dt.timestamp() * 1000)
    return 0


def filter_hlx(datas: list[dict], my_uid: int, seen: set[int],
               since: int = 0) -> list[dict]:
    """把葫芦侠通知整理成待回复列表。since: 只处理这个时间点之后的消息。"""
    out = []
    cutoff = max(_cutoff(), int(since or 0))
    for d in datas or []:
        c = d.get("content") or {}
        if not isinstance(c, dict):
            continue
        cid = _as_int(c.get("commentID"))
        pid = _as_int(c.get("postID"))
        if not pid:
            post = c.get("post") or {}
            if isinstance(post, dict):
                pid = _as_int(post.get("postID"))
        text = (c.get("text") or "").strip()
        ct = parse_ts(c.get("createTime"))
        from_uid = _as_int(c.get("userID"))
        nick = ""
        u = c.get("user") or {}
        if isinstance(u, dict):
            if not from_uid:
                from_uid = _as_int(u.get("userID"))
            nick = u.get("nick", "") or ""
        if not cid or not pid or from_uid == my_uid:
            continue
        if not ct or ct < cutoff:
            continue        # 认不出时间 / 太老 / 接入前的消息，一律不处理
        if cid in seen:
            continue
        title = ""
        post = c.get("post") or {}
        if isinstance(post, dict):
            title = post.get("title", "") or ""
        out.append({"cid": cid, "pid": pid, "text": text, "ct": ct,
                    "uid": from_uid, "nick": nick or f"uid={from_uid}",
                    "title": title})
    out.sort(key=lambda x: x["ct"], reverse=True)
    return out


def _as_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _clean_at(text: str) -> str:
    """灵芥的 @ 通知里包着 <at uid="..">@名字</at>，去掉标签留名字。"""
    import re as _re
    t = _re.sub(r"<at[^>]*>(.*?)</at>", r"\1", text or "")
    return " ".join(t.split())


def filter_lj(records: list[dict], my_uid: int, seen: set[int],
              since: int = 0, done_keys: set[str] | None = None) -> list[dict]:
    """把灵芥通知整理成待回复列表。

    真实类型：comment（评论我帖子）、reply（回复我评论）、at_comment（@我）。
    同一条评论可能同时产生 reply 和 at_comment 两条通知，按 cid / 内容去重。
    """
    out = []
    cutoff = max(_cutoff(), int(since or 0))
    done_keys = done_keys or set()
    seen_cids: set[int] = set()
    seen_texts: set[str] = set()
    for n in records or []:
        ntype = (n.get("notification_type") or "").lower()
        if ntype not in ("comment", "reply", "at_comment", "at"):
            continue
        cid = _as_int(n.get("cid") or n.get("commentId"))
        tid = _as_int(n.get("themeId") or n.get("tid"))
        if not cid or not tid or cid in seen or cid in seen_cids:
            continue
        from_uid = _as_int(n.get("author_uid") or n.get("uid"))
        if from_uid and from_uid == my_uid:
            continue
        ct = parse_ts(n.get("create_time") or n.get("created_at"))
        if not ct or ct < cutoff:
            continue
        text = _clean_at(n.get("commentContent") or n.get("content") or "")
        text_key = f"{tid}:{text}"
        if text_key in seen_texts or text_key in done_keys:
            continue
        seen_cids.add(cid)
        seen_texts.add(text_key)
        out.append({
            "cid": cid, "tid": tid, "text": text,
            "nick": n.get("author_nickname") or f"uid={from_uid}",
            "title": n.get("themeTitle") or "",
            "ct": ct, "uid": from_uid, "kind": ntype,
            "key": text_key,
        })
    return out


def run_intents(intents: list[str], hlx=None, lj=None, max_steps: int | None = None,
                post_count: int = 0, post_limit: int | None = None,
                post_platform: str = "") -> dict:
    """执行大肥鱼自己选的动作，返回 {intents, done}。测试时可注入假客户端。"""
    from .hlx import HlxClient
    from .lingjie import LingjieClient

    limit = int(post_limit if post_limit is not None
                else (CFG.get("autopost.daily_limit", 2) or 2))

    hlx = hlx or HlxClient(CFG)
    lj = lj or LingjieClient(CFG)
    steps = max_steps if max_steps is not None else max(1, int(CFG.get("roam.max_steps", 3) or 3))
    out = {"intents": intents, "done": []}
    if "signin" in intents:
        try:
            if CFG.get("hlx.key", ""):
                hlx.signin_all()
            if CFG.get("lingjie.token", ""):
                lj.signin_all()
            from .signin_state import mark_signed
            mark_signed("hlx")
            mark_signed("lingjie")
            out["done"].append("签到")
        except Exception as e:
            out["done"].append(f"签到失败：{e}")
    if "roam" in intents and CFG.get("perm.roam", True) and (
            CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
        try:
            from .roam import roam_session
            summary = roam_session(steps, dry_run=False, log=lambda s: None)
            out["done"].append(
                f"逛{summary.get('platform')}社区({len(summary.get('actions') or [])} 个动作)")
            out["roam"] = summary
        except Exception as e:
            out["done"].append(f"逛社区失败：{e}")
    if "visit" in intents and CFG.get("perm.roam", True) and (
            CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
        try:
            from .roam import pick_interesting_user, visit_user
            platform = "hlx" if CFG.get("hlx.key", "") else "lingjie"
            if platform == "hlx" and not CFG.get("hlx.key", ""):
                platform = "lingjie"
            uid, nick = pick_interesting_user(platform)
            if uid:
                s = visit_user(platform, uid, log=lambda _m: None)
                out["done"].append(f"去 @{nick or uid} 的主页看了帖子"
                                   f"({len(s.get('actions') or [])} 个动作)")
                out["visit"] = s
            else:
                out["done"].append("还没有想去拜访的人")
        except Exception as e:
            out["done"].append(f"拜访主页失败：{e}")
    if "post" in intents and CFG.get("ai.key", ""):
        if post_count >= limit:
            out["done"].append(f"今天已经发了 {post_count} 条，到上限 {limit} 条了")
        else:
            try:
                from .autopost import auto_post
                platform = post_platform or CFG.get("autopost.platform", "hlx") or "hlx"
                if platform == "hlx" and not CFG.get("hlx.key", ""):
                    platform = "lingjie"
                res = auto_post(platform, int(CFG.get("autopost.board_id", 0) or 0),
                                CFG.get("autopost.board_name", "") or "",
                                client=hlx if platform == "hlx" else lj)
                out["done"].append(f"发帖《{res.get('title') or '—'}》"
                                   if res.get("ok") else f"发帖失败：{res.get('msg')}")
                out["post"] = res
            except Exception as e:
                out["done"].append(f"发帖失败：{e}")
    return out


class AutoPilot(QObject):
    log = Signal(str)
    replied = Signal(str, str, str)   # platform, nick, text
    incoming = Signal(str, str, str)  # platform, nick, message
    auth_failed = Signal(str)         # platform
    state_changed = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.hlx = HlxClient(CFG)
        self.lj = LingjieClient(CFG)
        self.state = _load_state()
        self._busy = False

        # 消息监听：默认 10 秒一轮（和 Android 版一致）
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_tick)
        # 慢任务：每日签到检查
        self.slow_timer = QTimer(self)
        self.slow_timer.setInterval(60_000)
        self.slow_timer.timeout.connect(self._slow_tick)
        self.last_signin_check = 0.0
        # 逛社区
        self.roam_timer = QTimer(self)
        self.roam_timer.timeout.connect(self._roam_tick)
        self._roam_busy = False
        self.last_roam = float(self.state.get("last_roam_ts", 0) or 0)
        # 自动发帖
        self.post_timer = QTimer(self)
        self.post_timer.setInterval(60_000)
        self.post_timer.timeout.connect(self._post_tick)
        self._post_busy = False
        # 大肥鱼自由行动（意图决策）
        self.intent_timer = QTimer(self)
        self.intent_timer.setInterval(60_000)
        self.intent_timer.timeout.connect(self._intent_tick)
        self._intent_busy = False
        self.last_intent = float(self.state.get("last_intent_ts", 0) or 0)

    # ---------- 生命周期 ----------
    def start(self) -> None:
        started = []
        # 总开关打开就等于启用自动任务（老的 auto.enabled 自动迁移）
        if CFG.get("fish.enabled", False) and not CFG.get("auto.enabled", False):
            CFG.set("auto.enabled", True)
            CFG.save()
        if CFG.get("auto.enabled", False):
            sec = max(5, int(CFG.get("auto.poll_sec", 10) or 10))
            self.poll_timer.setInterval(sec * 1000)
            self.poll_timer.start()
            self.slow_timer.start()
            if not self.state.get("connect_ts"):
                self.state["connect_ts"] = int(time.time() * 1000)
                _save_state(self.state)
                DBG.log("AUTO", "已记录接入时间点，之前的消息不处理")
            QTimer.singleShot(2500, self._poll_tick)
            started.append(f"消息监听 {sec}s")
        else:
            self.poll_timer.stop()
            self.slow_timer.stop()
        # 逛社区只走「自由行动」这一条路，避免两个定时器各逛一次
        self.roam_timer.stop()
        if CFG.get("autopost.enabled", False) or CFG.get("autopost.diary_enabled", False):
            self.post_timer.start()
            QTimer.singleShot(15000, self._post_tick)
            if CFG.get("autopost.enabled", False):
                started.append(f"自动发帖 {int(CFG.get('autopost.interval_hours', 6) or 6)}h")
            if CFG.get("autopost.diary_enabled", False):
                started.append(f"日记定时 {CFG.get('autopost.diary_time', '23:00')}"
                               f"（到点才生成）")
        else:
            self.post_timer.stop()
        if CFG.get("auto.enabled", False) and CFG.get("ai.key", ""):
            minutes = max(5, int(CFG.get("fish.interval_min", 20) or 20))
            self.intent_timer.start()
            QTimer.singleShot(20000, self._intent_tick)
            started.append(f"自由行动 {minutes}min")
        else:
            self.intent_timer.stop()
        if started:
            DBG.log("AUTO", "自动任务已启动：" + "，".join(started))
        # 打开就检查一次生活记忆：距上次 ≥6 小时才生成，否则跳过
        QTimer.singleShot(7000, self._life_tick)

    def stop(self) -> None:
        self.poll_timer.stop()
        self.slow_timer.stop()
        self.roam_timer.stop()
        self.post_timer.stop()
        self.intent_timer.stop()

    # ---------- 自由行动：让大肥鱼自己决定做什么 ----------
    def _intent_tick(self) -> None:
        if self._intent_busy or not CFG.get("auto.enabled", False):
            return
        if not CFG.get("ai.key", ""):
            return
        minutes = max(5, int(CFG.get("fish.interval_min", 20) or 20))
        if time.time() - self.last_intent < minutes * 60:
            return
        self._intent_busy = True
        self.last_intent = time.time()
        self.state["last_intent_ts"] = self.last_intent
        _save_state(self.state)

        def work(_emit):
            d = brain.decide_intent()
            intents = [str(x).lower() for x in (d.get("intents") or [])] or ["idle"]
            reason = (d.get("reason") or d.get("think") or "").strip()
            # 两个平台各自算额度：今天还没发够时，稍微偏向「发帖」
            post_p = self._pick_post_platform()
            limit = self._post_limit(post_p) if post_p else 0
            if post_p and "post" not in intents and random.random() < 0.2:
                intents.append("post")
            if "post" in intents and not post_p:
                intents.remove("post")
                reason = (reason + "；还没到发帖时间或额度用完了").strip("；") \
                    if reason else "还没到发帖时间或额度用完了"
            out = run_intents(intents, post_count=self._today_posts(post_p) if post_p else 0,
                              post_limit=limit, post_platform=post_p)
            out["reason"] = reason
            return out

        def done(out):
            self._intent_busy = False
            intents = out.get("intents") or []
            reason = out.get("reason") or ""
            post = out.get("post") or {}
            if post.get("ok"):
                self._bump_post_count(post.get("platform") or "hlx")
            text = ("大肥鱼想了想，决定" + "、".join(intents)
                    + (f"：{reason}" if reason else "")
                    + ("（" + "；".join(out.get("done") or []) + "）" if out.get("done") else ""))
            self.log.emit(text)
            DBG.log("INTENT", text)
            record("decision", text, "hlx" if CFG.get("hlx.key", "") else "lingjie",
                   reason=reason, intents=intents)
            self.state_changed.emit()

        def fail(msg):
            self._intent_busy = False
            self.log.emit(f"✗ 自由行动出错：{msg}")

        from .ui.common import run_bg
        run_bg(work, done, fail)

    # ---------- 消息监听 ----------
    def _poll_tick(self) -> None:
        if self._busy or not CFG.get("auto.enabled", False):
            return
        if not CFG.get("auto.reply_enabled", True):
            return
        if not (CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
            return
        self._busy = True

        def work(_emit):
            report = {"replies": [], "errors": [], "notes": []}
            self._check_reviews(record_only=report)
            self._reply_pass("hlx", report)
            self._reply_pass("lingjie", report)
            return report

        from .ui.common import run_bg
        run_bg(work, self._poll_done, self._poll_fail)

    def _poll_done(self, report: dict) -> None:
        self._busy = False
        _save_state(self.state)
        for line in report.get("notes", []):
            self.log.emit(line)
        for line in report.get("errors", []):
            self.log.emit("✗ " + line)
            DBG.log("AUTO", line, "ERROR")
        if report.get("replies"):
            self.state["sent"] = int(self.state.get("sent", 0)) + len(report["replies"])
            _save_state(self.state)
            self.state_changed.emit()

    def _poll_fail(self, msg: str) -> None:
        self._busy = False
        self.log.emit(f"✗ 消息监听出错：{msg}")
        DBG.log("AUTO", f"消息监听出错：{msg}", "ERROR")

    # ---------- 慢任务 ----------
    def _slow_tick(self) -> None:
        if time.time() - self.last_signin_check < 300:
            return
        self.last_signin_check = time.time()
        try:
            self._life_tick()   # 生活记忆：每小时一次，由 gen_life 自己判断间隔
        except Exception:
            pass
        if CFG.get("auto.enabled", False):
            self._maybe_daily_signin()

    def _maybe_daily_signin(self) -> bool:
        if not CFG.get("auto.daily_signin", True):
            return False
        from .signin_state import mark_signed, signed_today
        want = CFG.get("auto.signin_time", "08:10") or "08:10"
        if datetime.now().strftime("%H:%M") < want:
            return False
        todo_hlx = (CFG.get("hlx.key", "") and CFG.get("hlx.auto_signin", True)
                    and not signed_today("hlx"))
        todo_lj = (CFG.get("lingjie.token", "") and CFG.get("lingjie.auto_signin", True)
                   and not signed_today("lingjie"))
        if not todo_hlx and not todo_lj:
            return False

        def work(_emit):
            out = []
            if todo_hlx:
                try:
                    ok, fail, _ = self.hlx.signin_all()
                    out.append(f"葫芦侠定时签到：成功 {ok}，失败 {fail}")
                except Exception as e:
                    out.append(f"葫芦侠签到失败：{e}")
            if todo_lj:
                try:
                    ok, fail, _ = self.lj.signin_all()
                    out.append(f"灵芥定时签到：新签 {ok}，失败 {fail}")
                except Exception as e:
                    out.append(f"灵芥签到失败：{e}")
            return out

        from .ui.common import run_bg

        def done(lines):
            for ln in lines:
                self.log.emit(ln)
                DBG.log("AUTO", ln)
                record("signin", ln)
            if todo_hlx:
                mark_signed("hlx")
            if todo_lj:
                mark_signed("lingjie")
            self.state["last_signin"] = datetime.now().strftime("%Y-%m-%d")
            _save_state(self.state)
            self.state_changed.emit()

        run_bg(work, done, lambda e: self.log.emit(f"✗ 定时签到失败：{e}"))
        return True

    # ---------- 审核结果 ----------
    def _check_reviews(self, record_only: dict | None = None) -> None:
        """葫芦侠 type_id=1 会推「您的评论已审核通过/未通过」，抓出来记动态。"""
        try:
            notices = self.hlx.review_notices(10)
        except Exception:
            return
        seen = set(self.state.get("reviews", []))
        changed = False
        for text in notices:
            if text in seen:
                continue
            seen.add(text)
            changed = True
            if "审核通过" in text:
                record("system", text, "hlx")
                DBG.log("REVIEW", text)
            elif "未通过" in text or "驳回" in text:
                record("error", text, "hlx")
                DBG.log("REVIEW", text, "WARN")
        if changed:
            self.state["reviews"] = list(seen)[-200:]
            _save_state(self.state)

    # ---------- 自动回复 ----------
    def _reply_pass(self, platform: str, report: dict) -> None:
        try:
            since = int(self.state.get("connect_ts", 0) or 0)
            if platform == "hlx":
                if not CFG.get("hlx.key", ""):
                    return
                datas = self.hlx.notifications(20)
                cands = filter_hlx(datas, self.hlx.uid, set(self.state["hlx"]), since)
                warm_key, seen_key = "warm_hlx", "hlx"
            else:
                if not CFG.get("lingjie.token", ""):
                    return
                records = self.lj.notifications(1)
                cands = filter_lj(records, self.lj.uid, set(self.state["lj"]), since,
                                  done_keys=set(self.state.get("lj_keys", [])))
                warm_key, seen_key = "warm_lj", "lj"

            if not self.state.get(warm_key):
                # 接入时间点之前的消息一律不处理；这里只做一次记录
                self.state[warm_key] = True
                _save_state(self.state)
                note = (f"{'葫芦侠' if platform=='hlx' else '灵芥'}：开始监听，"
                        f"只处理接入之后的新消息（当前 {len(cands)} 条待回）")
                report.setdefault("notes", []).append(note)
                DBG.log("AUTO", note)

            # 统一去重：同一帖子+同一句话，历史上回过就不再回
            done_keys = set(self.state.get("reply_keys", []))
            fresh = []
            batch_keys = set()
            for c in cands:
                c["key"] = c.get("key") or reply_key(platform, c)
                if c["key"] in done_keys or c["key"] in batch_keys:
                    continue
                batch_keys.add(c["key"])
                fresh.append(c)
            cands = fresh

            limit = max(1, int(CFG.get("auto.max_per_pass", 3) or 3))
            done = 0
            for c in cands:
                if done >= limit:
                    break
                try:
                    self.incoming.emit(platform, c.get("nick", ""),
                                       str(c.get("text") or "")[:80])
                except Exception:
                    pass
                # 服务端二次校验：这条消息是不是已经回过了
                pid = c.get("pid") or c.get("tid")
                try:
                    if platform == "hlx":
                        already = self.hlx.has_my_comment(int(pid or 0), int(c.get("ct", 0) or 0))
                    else:
                        already = self.lj.has_my_comment(int(pid or 0), parent_cid=c["cid"])
                except Exception:
                    already = False
                if already:
                    self.state[seen_key].append(c["cid"])
                    if platform == "lingjie" and c.get("key"):
                        self.state["lj_keys"] = (list(self.state.get("lj_keys", []))
                                                 + [c["key"]])[-500:]
                    _save_state(self.state)
                    DBG.log("REPLY", f"已经回过 {c['nick']} 这条了，跳过")
                    continue

                # 让模型自己决定：只回话，还是回话 + 做一件事（动作清单里选）
                from . import capabilities
                ctx = {"post_id": c.get("pid") or c.get("tid"),
                       "author_uid": c.get("uid", 0),
                       "title": c.get("title", ""), "board": c.get("board", "")}
                # 先根据对方说的话调整心情
                try:
                    self._mood_from_text(platform, c)
                except Exception:
                    pass
                decision = capabilities.reply_with_action(
                    platform, self.hlx if platform == "hlx" else self.lj, c, ctx)
                text = decision.get("reply") or ""
                why = decision.get("reason") or ""
                act = decision.get("action") or "nothing"
                executed = decision.get("executed") or {}
                if not text and act == "nothing":
                    continue
                # 同一个帖子+同样内容，只回一次（跨轮次也记住）
                rkey = c.get("key") or reply_key(platform, c)
                if rkey in set(self.state.get("reply_keys", [])):
                    continue
                if act != "nothing" and executed and executed.get("done"):
                    why = (why + "；" if why else "") + "动作：" + "、".join(executed["done"])
                gap = brain.random_reply_gap()
                DBG.log("REPLY", f"等待 {gap:.1f} 秒再回复 {c['nick']}")
                time.sleep(gap)
                # 发送前最后再查一次服务端，特别是灵芥
                if platform == "lingjie":
                    try:
                        if self.lj.find_my_reply(c["tid"], c["cid"], text):
                            if c["cid"] not in self.state[seen_key]:
                                self.state[seen_key].append(c["cid"])
                            self.state["reply_keys"] = (
                                list(self.state.get("reply_keys", [])) + [rkey])[-800:]
                            _save_state(self.state)
                            DBG.log("REPLY", f"灵芥上已经回过 {c['nick']}，跳过")
                            continue
                    except Exception:
                        pass
                # 先乐观标记，防止并发/重入重复回复
                if c["cid"] not in self.state[seen_key]:
                    self.state[seen_key].append(c["cid"])
                self.state["reply_keys"] = (list(self.state.get("reply_keys", []))
                                            + [rkey])[-800:]
                _save_state(self.state)
                ok, msg = self._send_reply(platform, c, text or "嗯嗯")
                if ok:
                    if platform == "lingjie" and c.get("key"):
                        self.state["lj_keys"] = (list(self.state.get("lj_keys", []))
                                                 + [c["key"]])[-500:]
                    _save_state(self.state)
                    done += 1
                    report["replies"].append((platform, c["nick"], text))
                    name = "葫芦侠" if platform == "hlx" else "灵芥"
                    self.log.emit(f"↩ {name} 回复 {c['nick']}：{text}")
                    DBG.log("REPLY", f"{name} → {c['nick']}(uid={c.get('uid')})：{text}")
                    memory.remember(f"{name}上回复了 {c['nick']}：{text}",
                                    c.get("uid", 0), platform)
                    from . import names
                    names.set_name(platform, c.get("uid", 0), c.get("nick", ""))
                    favor = REL.add(platform, c.get("uid", 0), 2, c["nick"])
                    memory.nudge_mood(1)
                    try:
                        from .stats import bump
                        bump("reply", platform)
                    except Exception:
                        pass
                    record("decision",
                           f"决定回复 {c['nick']}：{text}"
                           + (f"（{act}）" if act != "nothing" else "")
                           + (f"（理由：{why}）" if why else ""),
                           platform, cid=c["cid"], uid=c.get("uid"),
                           action=act, reason=why)
                    self.replied.emit(platform, c["nick"], text)
                else:
                    # 失败：回滚乐观标记，下一轮还能重试
                    try:
                        self.state[seen_key] = [x for x in self.state[seen_key]
                                                if x != c["cid"]]
                        self.state["reply_keys"] = [x for x in self.state.get("reply_keys", [])
                                                    if x != rkey]
                        _save_state(self.state)
                    except Exception:
                        pass
                    report["errors"].append(f"{platform} 回复 {c['nick']} 失败：{msg}")
                    if is_auth_error(msg):
                        self.auth_failed.emit(platform)
        except Exception as e:  # noqa: BLE001
            report["errors"].append(f"{platform} 监听失败：{e}")
            if is_auth_error(e):
                self.auth_failed.emit(platform)

    def _compose_reply(self, platform: str, c: dict) -> tuple[str, str]:
        """返回 (回复内容, 决策理由)。"""
        if not CFG.get("ai.key", ""):
            return "", ""
        where = "葫芦侠三楼" if platform == "hlx" else "灵芥空间"
        sys = brain.system_prompt(platform, c.get("uid", 0), c["nick"], with_tools=False)
        ask = (f"在{where}，{c['nick']} 在你的帖子「{c.get('title') or ''}」下评论：\n"
               f"{c['text']}\n\n"
               "只输出一行 JSON："
               '{"think":"你为什么想这么回","reply":"15~45字的自然口语回复"}')
        from .net import json_of
        for _ in range(2):
            try:
                raw = ai.ask(sys, ask, CFG.get("ai.model_basic"))
            except Exception as e:
                DBG.log("AI", f"生成回复失败：{e}", "ERROR")
                continue
            obj = json_of(raw)
            text = " ".join((obj.get("reply") or "").split()).strip()
            why = " ".join((obj.get("think") or "").split()).strip()
            if not text:
                text = " ".join((raw or "").split()).strip()
            if text:
                return text[:120], why[:80]
        return "", ""

    def _mood_from_text(self, platform: str, c: dict) -> None:
        text = str(c.get("text") or "")
        if not text:
            return
        owner_uid = int(CFG.get(f"fish.owner_uid_{platform}", 0)
                        or CFG.get("fish.owner_uid", 0) or 0)
        owner = bool(owner_uid and int(c.get("uid", 0) or 0) == owner_uid)
        pos = any(k in text for k in (
            "夸", "可爱", "喜欢你", "好棒", "好耶", "谢谢", "开心", "乖", "摸摸",
            "抱抱", "辛苦", "爱你", "厉害", "好看"))
        neg = any(k in text for k in (
            "笨", "蠢", "凶", "骂", "滚", "烦", "讨厌", "闭嘴", "菜", "废物",
            "傻", "恶心"))
        nick = c.get("nick") or "有人"
        if pos and not neg:
            memory.nudge_mood(3, platform, f"被 {nick} 夸了", owner)
        elif neg and not pos:
            memory.nudge_mood(-4, platform, f"被 {nick} 凶了", owner)

    def _send_reply(self, platform: str, c: dict, text: str) -> tuple[bool, str]:
        from .emoji import sanitize
        text = sanitize(text, platform)
        if platform == "hlx":
            return self.hlx.comment(c["pid"], text, c["cid"])
        return self.lj.publish_comment(c["tid"], text, c["cid"])

    # ---------- 逛社区 ----------
    def _roam_tick(self) -> None:
        if self._roam_busy or not CFG.get("roam.enabled", False):
            return
        if not CFG.get("hlx.key", "") or not CFG.get("ai.key", ""):
            return
        interval = max(1, int(CFG.get("roam.interval_min", 20) or 20)) * 60
        if time.time() - self.last_roam < interval:
            return
        self.run_roam_now()

    def _post_limit(self, platform: str) -> int:
        return max(1, int(CFG.get(f"autopost.daily_limit_{platform}", 0)
                        or CFG.get("autopost.daily_limit", 2) or 2))

    def _today_posts(self, platform: str = "hlx") -> int:
        if self.state.get(f"post_day_{platform}") != datetime.now().strftime("%Y-%m-%d"):
            return 0
        return int(self.state.get(f"post_count_{platform}", 0) or 0)

    def _bump_post_count(self, platform: str = "hlx") -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get(f"post_day_{platform}") != today:
            self.state[f"post_day_{platform}"] = today
            self.state[f"post_count_{platform}"] = 0
        self.state[f"post_count_{platform}"] = \
            int(self.state.get(f"post_count_{platform}", 0) or 0) + 1
        self.state[f"last_post_ts_{platform}"] = time.time()
        _save_state(self.state)
        self.state_changed.emit()

    def _pick_post_platform(self, prefer: str = "") -> str:
        """两个平台各自独立：优先还有额度、且最久没发的那个。"""
        cands = []
        for p in ("hlx", "lingjie"):
            if not (CFG.get("hlx.key", "") if p == "hlx" else CFG.get("lingjie.token", "")):
                continue
            if self._today_posts(p) >= self._post_limit(p):
                continue
            if not self._gap_ok(p):
                continue
            cands.append((float(self.state.get(f"last_post_ts_{p}", 0) or 0), p))
        if not cands:
            return ""
        if prefer and any(p == prefer for _, p in cands):
            return prefer
        cands.sort()
        return cands[0][1]

    def _gap_ok(self, platform: str) -> bool:
        """两条帖子之间至少隔一会儿；额度在 24 小时内尽量均分。"""
        limit = self._post_limit(platform)
        base = 24 * 60 / max(1, limit) * 0.85
        gap_min = max(int(CFG.get("autopost.min_gap_min", 40) or 40), int(base))
        last = float(self.state.get(f"last_post_ts_{platform}", 0) or 0)
        return time.time() - last >= gap_min * 60

    def run_test_post(self, platform: str = "hlx") -> None:
        """测试发帖：指定平台，和大肥鱼自主发帖一样，计入该平台每日上限。"""
        if not CFG.get("ai.key", ""):
            self.log.emit("✗ 测试发帖需要先配置 DeepSeek Key")
            return
        if platform == "hlx" and not CFG.get("hlx.key", ""):
            self.log.emit("✗ 葫芦侠还没登录")
            return
        if platform == "lingjie" and not CFG.get("lingjie.token", ""):
            self.log.emit("✗ 灵芥还没登录")
            return
        limit = self._post_limit(platform)
        if self._today_posts(platform) >= limit:
            name = "葫芦侠" if platform == "hlx" else "灵芥"
            self.log.emit(f"✗ {name}今天已经发了 {limit} 条了，明天再试")
            return
        name = "葫芦侠" if platform == "hlx" else "灵芥"
        self.log.emit(f"— 测试发帖（{name}）：让大肥鱼现编一条 —")

        def work(_e):
            from .autopost import auto_post
            return auto_post(platform, 0, "",
                             client=self.hlx if platform == "hlx" else self.lj)

        def done(res):
            if not res.get("ok"):
                self.log.emit(f"✗ 测试发帖失败：{res.get('msg')}")
                DBG.log("AUTOPOST", f"测试发帖失败：{res.get('msg')}", "ERROR")
                return
            self._bump_post_count(platform)
            self.log.emit(f"📝 《{res['title']}》→ {res['board']}：{res['msg']}"
                          f"（{name}今日 {self._today_posts(platform)}/{limit}）")
            DBG.log("AUTOPOST", f"测试发帖成功：《{res['title']}》{res['msg']}")
            record("post", f"测试发帖《{res['title']}》→ {res['board']}"
                           + ("（审核中）" if res.get("review") else ""),
                   platform, reason="手动测试发帖")
            self.state_changed.emit()

        def fail(msg):
            self.log.emit(f"✗ 测试发帖出错：{msg}")

        from .ui.common import run_bg
        run_bg(work, done, fail)

    def run_roam_now(self, dry_run: bool = False) -> None:
        if self._roam_busy:
            self.log.emit("↩ 上一轮逛社区还没结束，先等等")
            return
        if not CFG.get("hlx.key", ""):
            self.log.emit("✗ 逛社区需要先登录葫芦侠")
            return
        if not CFG.get("ai.key", ""):
            self.log.emit("✗ 逛社区需要先配置 DeepSeek Key")
            return
        self._roam_busy = True
        self.last_roam = time.time()
        self.state["last_roam_ts"] = self.last_roam
        _save_state(self.state)
        steps = max(1, int(CFG.get("roam.max_steps", 3) or 3))
        self.log.emit("— 开始逛社区" + ("（试运行，不执行动作）" if dry_run else "") + " —")

        def work(_e):
            from .roam import roam_once
            return roam_once(self.hlx, steps, dry_run=dry_run,
                             log=lambda s: self.log.emit(s))

        def done(summary):
            self._roam_busy = False
            acts = summary.get("actions") or []
            msg = f"逛完了：看了 {summary.get('seen', 0)} 条帖子"
            if acts:
                msg += "，动作 " + "、".join(
                    "、".join(a["acts"]) if isinstance(a, dict) else str(a) for a in acts[:5])
            self.log.emit(msg)
            DBG.log("ROAM", msg)
            record("system", msg, "hlx")
            self.state_changed.emit()

        def fail(msg):
            self._roam_busy = False
            self.log.emit(f"✗ 逛社区出错：{msg}")
            DBG.log("ROAM", f"出错：{msg}", "ERROR")

        from .ui.common import run_bg
        run_bg(work, done, fail)

    # ---------- 自动发帖 ----------
    def _post_tick(self) -> None:
        self._diary_tick()
        self._life_tick()
        if self._post_busy or not CFG.get("autopost.enabled", False):
            return
        if not CFG.get("ai.key", ""):
            return
        # 两个平台各自独立：额度、间隔、均分都分开算
        for p in ("hlx", "lingjie"):
            if not (CFG.get("hlx.key", "") if p == "hlx" else CFG.get("lingjie.token", "")):
                continue
            if self._today_posts(p) >= self._post_limit(p):
                continue
            if not self._gap_ok(p):
                continue
            self.run_auto_post(platform=p)
            return

    def run_auto_post(self, dry_run: bool = False, platform: str = "") -> None:
        if self._post_busy:
            self.log.emit("↩ 上一条帖子还在生成中")
            return
        platform = platform or CFG.get("autopost.platform", "hlx") or "hlx"
        if not CFG.get("ai.key", ""):
            self.log.emit("✗ 自动发帖需要先配置 DeepSeek Key")
            return
        name = "葫芦侠" if platform == "hlx" else "灵芥"
        if self._today_posts(platform) >= self._post_limit(platform):
            self.log.emit(f"✗ {name}今天的发帖额度用完了")
            return
        if not self._gap_ok(platform):
            self.log.emit(f"↩ {name}离上一条帖子太近了，等会儿再发")
            return
        self._post_busy = True
        board_id = int(CFG.get("autopost.board_id", 0) or 0)
        board_name = CFG.get("autopost.board_name", "") or ""
        self.log.emit(f"— 开始自动发帖（{name}）"
                      + ("（试运行，不发布）" if dry_run else "") + " —")

        def work(_e):
            from .autopost import auto_post
            return auto_post(platform, board_id, board_name, dry_run=dry_run,
                             client=self.hlx if platform == "hlx" else self.lj)

        def done(res):
            self._post_busy = False
            if not res.get("ok"):
                self.log.emit(f"✗ 自动发帖失败：{res.get('msg')}")
                DBG.log("AUTOPOST", f"失败：{res.get('msg')}", "ERROR")
                return
            self.log.emit(f"📝 《{res['title']}》→ {res['board']}：{res['msg']}")
            DBG.log("AUTOPOST", f"成功：《{res['title']}》{res['msg']}")
            if not dry_run:
                self._bump_post_count(platform)

        def fail(msg):
            self._post_busy = False
            self.log.emit(f"✗ 自动发帖出错：{msg}")

        from .ui.common import run_bg
        run_bg(work, done, fail)

    # ---------- 每日日记 ----------
    def _diary_tick(self) -> None:
        if not CFG.get("autopost.diary_enabled", False):
            return
        from .diary import diary_due
        if not diary_due():
            return
        want = CFG.get("autopost.diary_time", "21:30") or "21:30"
        if datetime.now().strftime("%H:%M") < want:
            return
        if self._post_busy:
            return
        self.run_diary()

    def run_diary(self, dry_run: bool = False) -> None:
        if self._post_busy:
            self.log.emit("↩ 上一条帖子还在生成中")
            return
        if not CFG.get("ai.key", ""):
            self.log.emit("✗ 写日记需要先配置 DeepSeek Key")
            return
        targets = []
        if CFG.get("hlx.key", ""):
            targets.append("hlx")
        if CFG.get("lingjie.token", ""):
            targets.append("lingjie")
        if not targets:
            self.log.emit("✗ 两个平台都没登录")
            return
        self._post_busy = True
        self.log.emit("— 开始写日记（" + "、".join(
            "葫芦侠" if p == "hlx" else "灵芥" for p in targets) + "）"
            + ("（试运行，不发布）" if dry_run else "") + " —")

        def work(_e):
            from .diary import write_diary
            return [(p, write_diary(p, dry_run=dry_run,
                                    client=self.hlx if p == "hlx" else self.lj))
                    for p in targets]

        def done(results):
            self._post_busy = False
            for p, res in results or []:
                name = "葫芦侠" if p == "hlx" else "灵芥"
                if res.get("ok"):
                    self.log.emit(f"📔 {name}《{res['title']}》→ {res['board']}："
                                  f"{res['msg']}")
                    DBG.log("DIARY", f"{name}完成：《{res['title']}》")
                else:
                    self.log.emit(f"📔 {name}日记没写成：{res.get('msg')}")
            if not dry_run:
                self.state_changed.emit()

        def fail(msg):
            self._post_busy = False
            self.log.emit(f"✗ 写日记出错：{msg}")

        from .ui.common import run_bg
        run_bg(work, done, fail)

    def run_test_diary(self) -> None:
        """测试日记：两个平台各发一篇（带图），不占每日发帖额度。"""
        self.log.emit("— 测试日记：两个平台各写一篇 —")
        self.run_diary()

    # ---------- 生活记忆 ----------
    def _life_tick(self) -> None:
        if not CFG.get("ai.key", ""):
            return

        def work(_e):
            from .diary import gen_life
            return gen_life()

        common_ok = (CFG.get("auto.enabled", False) or CFG.get("roam.enabled", False)
                     or CFG.get("autopost.enabled", False)
                     or CFG.get("autopost.diary_enabled", False))
        if not common_ok:
            return
        from .ui.common import run_bg
        run_bg(work, lambda _r: None, lambda _e: None)

    # ---------- 手动触发 ----------
    def run_now(self) -> None:
        self.last_signin_check = 0
        self._poll_tick()
        self._slow_tick()
