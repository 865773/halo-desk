"""葫芦侠三楼（floor.huluxia.com）客户端，移植自 hlx-halo/HlxClient.java。"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Callable, Optional

from . import net
from .authwords import is_login_bad
from .config import CFG
from .debuglog import DBG

BASE = "http://floor.huluxia.com"
UPLOAD_HOST = "http://upload.huluxia.com"
SECRET = "fa1c28a5b62e79c3e63d9030b6142e4b"
APP_VER = "4.4.0.6"
VER_CODE = "20141528"
MARKET = "floor_web"
HLX_UA = "okhttp/3.8.1"
DEV_RAW = "[d]5125c3c6-f456-4c6b-81cf-9bc467522d61"
DEV_ENC = "%5Bd%5D5125c3c6-f456-4c6b-81cf-9bc467522d61"


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _log_http(method: str, url: str, t0: float, text: str) -> None:
    """把每次请求记进调试日志（不记录 _key/token 等敏感参数）。"""
    try:
        if not CFG.get("debug.http", True):
            return
        path = url.split("?")[0].replace(BASE, "")
        ms = int((time.time() - t0) * 1000)
        obj = net.json_of(text) if text else {}
        st = obj.get("status")
        msg = str(obj.get("msg") or "")[:40]
        extra = f"status={st}" + (f" msg={msg}" if msg else "")
        DBG.log("HLX", f"{method} {path} {ms}ms {extra} len={len(text or '')}")
    except Exception:
        pass


class HlxError(Exception):
    pass


class HlxClient:
    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.auth_issue = ""

    # ---------- 基础 ----------
    @property
    def key(self) -> str:
        return self.cfg.get("hlx.key", "") or ""

    @property
    def uid(self) -> int:
        return int(self.cfg.get("hlx.uid", 0) or 0)

    @property
    def logged_in(self) -> bool:
        return bool(self.key)

    def common(self) -> str:
        return (f"platform=2&gkey=000000&app_version={APP_VER}"
                f"&versioncode={VER_CODE}&market_id={MARKET}")

    def auth(self) -> str:
        return (f"{self.common()}&_key={self.key}&device_code={DEV_ENC}"
                f"&phone_brand_type=MI")

    def _get(self, url: str) -> str:
        t0 = time.time()
        text = net.http(url, headers={"User-Agent": HLX_UA}, timeout=18)
        _log_http("GET", url, t0, text)
        return text

    def _post(self, url: str, body: str) -> str:
        t0 = time.time()
        text = net.http(url, "POST", body,
                        {"User-Agent": HLX_UA,
                         "Content-Type": "application/x-www-form-urlencoded"},
                        timeout=22)
        _log_http("POST", url, t0, text)
        return text

    def _json(self, text: str) -> dict:
        obj = net.json_of(text)
        msg = str(obj.get("msg") or "")
        if is_login_bad(msg):
            self.auth_issue = msg
        return obj

    # ---------- 登录 ----------
    def login(self, account: str, password: str) -> dict:
        pwd = md5(password)
        raw = f"account{account}device_code{DEV_RAW}password{pwd}voice_code"
        sign = md5(raw + SECRET)
        url = (f"{BASE}/account/login/ANDROID/4.1.8?{self.common()}"
               f"&device_code={DEV_ENC}&account={net.enc(account)}&login_type=2"
               f"&password={pwd}&voice_code=&sign={sign}")
        obj = self._json(self._get(url))
        key = obj.get("_key", "")
        if not key:
            raise HlxError(obj.get("msg") or "登录失败：账号或密码不正确")
        user = obj.get("user") or {}
        self.cfg.set("hlx.key", key)
        self.cfg.set("hlx.uid", int(user.get("userID", 0) or 0))
        self.cfg.set("hlx.nick", user.get("nick", "") or "")
        self.cfg.set("hlx.avatar", user.get("avatar", "") or "")
        self.cfg.set("hlx.level", int(user.get("level", 0) or 0))
        self.cfg.set("hlx.phone", account)
        self.cfg.set("hlx.password", password)
        self.cfg.save()
        return user

    def relogin(self) -> bool:
        phone = self.cfg.get("hlx.phone", "")
        pwd = self.cfg.get("hlx.password", "")
        if not phone or not pwd:
            return False
        try:
            self.login(phone, pwd)
            return True
        except Exception:
            return False

    def check_login(self) -> bool:
        try:
            return self.probe_login()
        except Exception:
            return False

    def login_state(self) -> tuple[str, str]:
        """返回 (ok|invalid|blocked|unknown, 服务端原因)；网络错误会抛异常。"""
        if not self.key:
            return "invalid", "未登录"
        obj = self._json(self._get(f"{BASE}/user/status/ANDROID/2.1?{self.auth()}"))
        st = int(obj.get("status", 0) or 0)
        msg = str(obj.get("msg") or "")
        if is_login_bad(msg):
            return "blocked", msg
        if st == 1:
            return "ok", ""
        if is_login_bad(msg):
            return "invalid", msg
        return "unknown", msg or f"status={st}"

    def probe_login(self) -> bool:
        """只判断登录态；网络错误会抛异常，避免把断网当成失效。"""
        return self.login_state()[0] == "ok"

    def logout(self) -> None:
        for k in ("key", "uid", "nick", "avatar", "level"):
            self.cfg.set(f"hlx.{k}", "" if k != "uid" and k != "level" else 0)
        self.cfg.save()

    # ---------- 用户 / 板块 ----------
    def my_info(self) -> dict:
        obj = self._json(self._get(
            f"{BASE}/user/info/ANDROID/4.1.8?{self.auth()}&user_id={self.uid}"))
        return obj.get("user") or obj

    def user_info(self, uid: int) -> dict:
        obj = self._json(self._get(
            f"{BASE}/user/info/ANDROID/4.1.8?{self.auth()}&user_id={uid}"))
        return obj.get("user") or obj

    def boards(self) -> list[tuple[int, str]]:
        obj = self._json(self._get(f"{BASE}/category/list/ANDROID/2.0"))
        out = []
        for c in obj.get("categories") or []:
            if not isinstance(c, dict):
                continue
            cid = int(c.get("categoryID", 0) or 0)
            title = c.get("title", "") or ""
            if cid > 0 and title:
                out.append((cid, title))
        return out

    # ---------- 签到 ----------
    def signin(self, cat_id: int) -> tuple[bool, str]:
        ts = int(time.time())
        sign = md5(f"cat_id{cat_id}time{ts}{SECRET}").upper()
        url = (f"{BASE}/user/signin/ANDROID/4.1.8?{self.auth()}"
               f"&cat_id={cat_id}&time={ts}")
        obj = self._json(self._post(url, f"sign={sign}"))
        ok = int(obj.get("status", 0) or 0) == 1
        return ok, (obj.get("msg") or ("" if ok else "签到失败"))

    def signin_all(self, on_progress: Optional[Callable[[int, int, str, bool, str], None]] = None,
                   skip_boards: tuple[int, ...] = (1, 4)) -> tuple[int, int, list[str]]:
        boards = [(i, n) for i, n in self.boards() if i not in skip_boards]
        ok = fail = 0
        logs: list[str] = []
        total = len(boards)
        for i, (cid, name) in enumerate(boards, 1):
            try:
                good, msg = self.signin(cid)
            except Exception as e:
                good, msg = False, str(e)
            if good:
                ok += 1
            else:
                fail += 1
            logs.append(f"{'✓' if good else '·'} {name}：{msg or '已签到'}")
            if on_progress:
                on_progress(i, total, name, good, msg)
            time.sleep(0.35)
        return ok, fail, logs

    # ---------- 帖子 / 评论 ----------
    def posts(self, cat_id: int, start: int = 0, count: int = 20) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/post/list/ANDROID/4.1.8?{self.auth()}"
            f"&cat_id={cat_id}&tag_id=0&sort_by=0&start={start}&count={count}"))
        return [p for p in (obj.get("posts") or []) if isinstance(p, dict)]

    def post_detail(self, post_id: int) -> dict:
        obj = self._json(self._get(
            f"{BASE}/post/detail/ANDROID/4.1.8?{self.auth()}"
            f"&post_id={post_id}&page=1"))
        return obj.get("post") or {}

    def comments(self, post_id: int, page: int = 1) -> list[dict]:
        """评论列表：post/detail 的顶层 comments（回复在 refComment 里）。"""
        try:
            obj = self._json(self._get(
                f"{BASE}/post/detail/ANDROID/4.1.8?{self.auth()}"
                f"&post_id={post_id}&page={page}"))
        except Exception:
            return []
        return [c for c in (obj.get("comments") or []) if isinstance(c, dict)]

    def has_my_comment(self, post_id: int, since_ms: int = 0, pages: int = 3,
                       parent_cid: int = 0, text: str = "") -> bool:
        """这个帖子下有没有我发的评论 / 我有没有回过这条评论。"""
        try:
            body = " ".join(str(text or "").split())
            for page in range(1, pages + 1):
                for c in self.comments(post_id, page):
                    u = c.get("user") or {}
                    if int((u or {}).get("userID", 0) or 0) != self.uid:
                        continue
                    if parent_cid:
                        ref = c.get("refComment") or {}
                        rid = int((ref or {}).get("commentID", 0) or 0) \
                            if isinstance(ref, dict) else 0
                        if rid != int(parent_cid):
                            continue
                        if body:
                            ct = " ".join(str(c.get("text") or "").split())
                            if ct and ct != body:
                                continue
                        return True
                    ct = int(c.get("createTime", 0) or 0)
                    if since_ms > 0 and ct and ct < since_ms:
                        continue
                    return True
        except Exception:
            pass
        return False

    def find_my_reply(self, post_id: int, parent_cid: int, text: str = "") -> bool:
        return self.has_my_comment(post_id, parent_cid=parent_cid, text=text)

    def reply_target(self, post_id: int, cid: int) -> int:
        """回复的父评论：如果目标是“回复的回复”，挂到它所属的根评论下。"""
        cid = int(cid or 0)
        if not cid:
            return 0
        try:
            for page in range(1, 4):
                for c in self.comments(post_id, page):
                    if int(c.get("commentID", 0) or 0) != cid:
                        continue
                    ref = c.get("refComment") or {}
                    rid = int((ref or {}).get("commentID", 0) or 0) \
                        if isinstance(ref, dict) else 0
                    return rid or cid
        except Exception:
            pass
        return cid

    # ---------- 互动 ----------
    def praise(self, post_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/post/praise/ANDROID/2.1?{self.auth()}&post_id={post_id}"))
        return int(obj.get("status", 0) or 0) == 1

    def is_praised(self, post_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/post/praise/check/ANDROID/2.1?{self.auth()}&post_id={post_id}"))
        return int(obj.get("isPraise", 0) or 0) == 1

    def unlike(self, post_id: int) -> bool:
        """葫芦侠的点赞接口是开关：再调一次就是取消。

        （/post/praise/cancel 系列在服务端是 404，原版注释也写了是 toggle）
        """
        obj = self._json(self._get(
            f"{BASE}/post/praise/ANDROID/2.1?{self.auth()}&post_id={post_id}"))
        if int(obj.get("praise", 0) or 0) == 2:
            return True
        return not self.is_praised(post_id)

    def favorite(self, post_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/post/favorite/create/ANDROID/4.1.8?{self.auth()}&post_id={post_id}"))
        return int(obj.get("status", 0) or 0) == 1

    def is_favorited(self, post_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/post/favorite/check/ANDROID/2.0?{self.auth()}&post_id={post_id}"))
        return int(obj.get("isFavorite", 0) or 0) == 1

    def unfavorite(self, post_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/post/favorite/destroy/ANDROID/4.1.8?{self.auth()}&post_id={post_id}"))
        return int(obj.get("status", 0) or 0) == 1

    def follow(self, user_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/friendship/follow/ANDROID/2.0?{self.auth()}&user_id={user_id}"))
        return int(obj.get("status", 0) or 0) == 1

    def following(self, count: int = 100) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/friendship/following/list/ANDROID/4.1.8?{self.auth()}"
            f"&user_id={self.uid}&start=0&count={count}"))
        return [f for f in (obj.get("friendships") or []) if isinstance(f, dict)]

    def is_following(self, user_id: int) -> bool:
        for f in self.following(100):
            u = f.get("user") or {}
            if isinstance(u, dict) and int(u.get("userID", 0) or 0) == user_id:
                return True
        return False

    def follow_safe(self, user_id: int) -> bool:
        if not user_id:
            return False
        if self.is_following(user_id):
            return True
        return self.follow(user_id)

    def follow_once(self, user_id: int) -> tuple[bool, str]:
        """已经关注过就不重复关注（避免接口把关注变成取消）。"""
        if not user_id:
            return False, "缺少 uid"
        if self.is_following(user_id):
            return False, "已经关注过了"
        return self.follow(user_id), ""

    def unfollow_once(self, user_id: int) -> tuple[bool, str]:
        """本来没关注就不要调用取消。"""
        if not user_id:
            return False, "缺少 uid"
        if not self.is_following(user_id):
            return False, "本来就没关注"
        ok = self.unfollow(user_id)
        return ok, "" if ok else "取关失败"

    def unfollow(self, user_id: int) -> bool:
        obj = self._json(self._get(
            f"{BASE}/friendship/unfollow/ANDROID/2.0?{self.auth()}&user_id={user_id}"))
        return int(obj.get("status", 0) or 0) == 1

    def mutual_friends(self, count: int = 30) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/user/friend/ANDROID/4.1.8?{self.auth()}&start=0&count={count}"))
        return [f for f in (obj.get("friendships") or []) if isinstance(f, dict)]

    def followers(self, count: int = 30) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/friendship/follower/list/ANDROID/4.1.8?{self.auth()}"
            f"&user_id={self.uid}&start=0&count={count}"))
        return [f for f in (obj.get("friendships") or []) if isinstance(f, dict)]

    def atify(self, text: str) -> tuple[str, str]:
        """把 @昵称 换成葫芦侠的提及标记，返回 (新文本, remindUsers JSON)。"""
        if not text or "@" not in text:
            return text, ""
        try:
            arr = []
            seen: set[int] = set()
            for f in self.mutual_friends(30):
                u = f.get("user") or {}
                nick = u.get("nick", "") or ""
                uid = int(u.get("userID", 0) or 0)
                if not nick or uid <= 0:
                    continue
                plain = "@" + nick
                if plain not in text:
                    continue
                if ("\u202d" + plain) not in text:
                    text = text.replace(plain, "\u202d" + plain + " \u202c")
                if uid not in seen:
                    seen.add(uid)
                    arr.append({"nick": nick, "userID": uid})
            return text, (json.dumps(arr, ensure_ascii=False) if arr else "")
        except Exception:
            return text, ""

    def comment(self, post_id: int, text: str, reply_cid: int = 0) -> tuple[bool, str]:
        text, remind = self.atify(text)
        raw = (f"_key{self.key}comment_id{reply_cid}device_code{DEV_RAW}"
               f"imagespost_id{post_id}text{text}")
        sign = md5(raw + SECRET)
        body = (f"post_id={post_id}&comment_id={reply_cid}&text={net.enc(text)}"
                f"&patcha=&images=&remindUsers={net.enc(remind)}&sign={sign}")
        obj = self._json(self._post(
            f"{BASE}/comment/create/ANDROID/4.1.8?{self.auth()}", body))
        ok = int(obj.get("status", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "评论失败")

    def comment_author(self, post_id: int, comment_id: int,
                       pages: int = 3) -> int:
        """确认评论属于谁；找不到返回 0。避免打赏到引用链里的旧评论。"""
        cid = int(comment_id or 0)
        if not cid:
            return 0
        for page in range(1, max(1, pages) + 1):
            for c in self.comments(post_id, page):
                if int(c.get("commentID", 0) or 0) == cid:
                    u = c.get("user") or {}
                    return int((u or {}).get("userID", 0) or 0)
                ref = c.get("refComment") or {}
                if isinstance(ref, dict) and int(ref.get("commentID", 0) or 0) == cid:
                    return int(ref.get("userID", 0) or 0)
        return 0

    def comment_author_by_seq(self, post_id: int, seq: int,
                              pages: int = 3) -> int:
        """按楼层号确认评论作者；葫芦侠打赏实际认 seq，不是全局 commentID。"""
        want = int(seq or 0)
        if not want:
            return 0
        for page in range(1, max(1, pages) + 1):
            for c in self.comments(post_id, page):
                if int(c.get("seq", 0) or 0) == want:
                    u = c.get("user") or {}
                    return int((u or {}).get("userID", 0) or 0)
        return 0

    def tip(self, post_id: int, score: int, text: str) -> tuple[bool, str]:
        """给帖子送葫芦。"""
        import re as _re
        score = max(1, min(5, int(score or 1)))
        text = _re.sub(r"\[[^\]]{1,10}\]", "", str(text or ""))
        text = _re.sub(r"\s+", " ", text).strip()[:10]
        if len(text) < 4:
            text = "谢谢你分享"
        raw = (f"_key{self.key}device_code{DEV_RAW}post_id{post_id}"
               f"score{score}score_txt{text}")
        sign = md5(raw + SECRET)
        body = (f"post_id={post_id}&type_id=1&isadmin=0&score={score}"
                f"&score_txt={net.enc(text)}&sign={sign}")
        obj = self._json(self._post(
            f"{BASE}/credits/transfer/ANDROID/4.1.8?{self.auth()}", body))
        ok = int(obj.get("iscredits", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "送葫芦失败")

    def tip_comment(self, post_id: int, comment_id: int, score: int,
                    text: str) -> tuple[bool, str]:
        raw = (f"_key{self.key}device_code{DEV_RAW}post_id{post_id}"
               f"score{score}score_txt{text}")
        sign = md5(raw + SECRET)
        body = (f"post_id={post_id}&comment_id={comment_id}&type_id=2&isadmin=0"
                f"&score={score}&score_txt={net.enc(text)}&sign={sign}")
        obj = self._json(self._post(
            f"{BASE}/credits/transfer/ANDROID/4.1.8?{self.auth()}", body))
        ok = int(obj.get("iscredits", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "送葫芦失败")

    def notifications(self, count: int = 20) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/message/new/list/ANDROID/4.1?{self.auth()}"
            f"&type_id=8&start=0&count={count}"))
        return [d for d in (obj.get("datas") or []) if isinstance(d, dict)]

    def review_notices(self, count: int = 10) -> list[str]:
        """type_id=1 是审核结果通知（您的评论【…】已审核通过/未通过）。"""
        obj = self._json(self._get(
            f"{BASE}/message/new/list/ANDROID/4.1?{self.auth()}"
            f"&type_id=1&start=0&count={count}"))
        out = []
        for d in (obj.get("datas") or []):
            c = d.get("content") or {}
            text = (c.get("text") or "").strip()
            if text:
                out.append(text)
        return out

    # ---------- 发帖 ----------
    def create_post(self, cat_id: int, title: str, content: str,
                    image_fids: str = "") -> tuple[bool, str]:
        """发帖。image_fids 形如 "g4/M00/xx.png,"（末尾带逗号，可多个）。"""
        detail = f"<text>{content}</text>"
        images = image_fids or ""
        raw = (f"_key{self.key}detail{detail}device_code{DEV_RAW}"
               f"images{images}title{title}voice")
        sign = md5(raw + SECRET)
        body = (f"draft_id=0&cat_id={cat_id}&tag_id=-1&type=0"
                f"&title={net.enc(title)}"
                f"&detail={net.enc(detail)}"
                f"&patcha=&voice=&lng=0.0&lat=0.0"
                f"&images={net.enc(images)}"
                f"&user_ids=&recommendTopics=&remindTopics="
                f"&sign={sign}&is_app_link=3")
        obj = self._json(self._post(
            f"{BASE}/post/create/ANDROID/4.2.2?{self.auth()}", body))
        ok = int(obj.get("status", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "发帖失败")

    # ---------- 删除 / 我的列表 ----------
    def my_posts(self, count: int = 20) -> list[dict]:
        return self.user_posts(self.uid, count)

    def user_posts(self, user_id: int, count: int = 20) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/post/create/list/ANDROID/4.1.8?{self.auth()}"
            f"&phone_brand_type=MI&start=0&count={count}&user_id={user_id}"))
        return [p for p in (obj.get("posts") or []) if isinstance(p, dict)]

    def delete_post(self, post_id: int) -> tuple[bool, str]:
        obj = self._json(self._get(
            f"{BASE}/post/destroy/ANDROID/2.0?{self.auth()}&post_id={post_id}"))
        ok = int(obj.get("status", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "删帖失败")

    def delete_comment(self, comment_id: int) -> tuple[bool, str]:
        obj = self._json(self._post(
            f"{BASE}/moderator/deleteComment/ANDROID/2.0?{self.auth()}",
            f"cid={comment_id}&reason={net.enc('删除评论')}"))
        ok = int(obj.get("status", 0) or 0) == 1
        return ok, obj.get("msg", "") or ("" if ok else "删评论失败")

    # ---------- 其它查询 ----------
    def search(self, keyword: str, count: int = 20) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/post/search/ANDROID/4.1.8?{self.auth()}"
            f"&keyword={net.enc(keyword)}&start=0&count={count}"))
        return [p for p in (obj.get("posts") or []) if isinstance(p, dict)]

    def favorites(self, user_id: int = 0, count: int = 20) -> list[dict]:
        uid = user_id or self.uid
        obj = self._json(self._get(
            f"{BASE}/post/favorite/list/ANDROID/4.1.8?{self.auth()}"
            f"&user_id={uid}&start=0&count={count}"))
        return [p for p in (obj.get("posts") or []) if isinstance(p, dict)]

    def user_comments(self, user_id: int, count: int = 20) -> list[dict]:
        obj = self._json(self._get(
            f"{BASE}/user/comment/list/ANDROID/4.1.8?{self.auth()}"
            f"&user_id={user_id}&start=0&count={count}"))
        return [c for c in (obj.get("comments") or []) if isinstance(c, dict)]

    def emoji_list(self) -> list:
        obj = self._json(self._get(f"{BASE}/emoji/list/ANDROID/2.0"))
        return obj.get("emojis") or obj.get("data") or []

    def upload_image(self, png: bytes) -> Optional[str]:
        ts = str(int(time.time() * 1000))
        nonce = f"{time.time_ns() & 0xFFFFFFFF:08x}abcdef"
        raw = (f"_key={self.key}&app_version={APP_VER}&device_code={DEV_RAW}"
               f"&gkey=000000&market_id={MARKET}&nonce_str={nonce}"
               f"&platform=2&timestamp={ts}&use_type=2&versioncode={VER_CODE}"
               f"&secret=my_sign@huluxia.com")
        sign = md5(raw).upper()
        url = (f"{UPLOAD_HOST}/upload/v3/image?_key={self.key}&app_version={APP_VER}"
               f"&device_code={DEV_ENC}&gkey=000000&market_id={MARKET}"
               f"&nonce_str={nonce}&platform=2&timestamp={ts}&use_type=2"
               f"&versioncode={VER_CODE}&sign={sign}")
        boundary = "----HlxBoundary" + ts
        body = b""
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"_key\""
                 f"\r\n\r\nkey_10\r\n").encode()
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"a.png\"\r\nContent-Type: image/png\r\n\r\n").encode()
        body += png
        body += (f"\r\n--{boundary}--\r\n").encode()
        try:
            text = net.http(url, "POST", body,
                            {"User-Agent": HLX_UA,
                             "Content-Type": f"multipart/form-data; boundary={boundary}"},
                            timeout=40)
            return self._json(text).get("fid") or None
        except Exception:
            return None
