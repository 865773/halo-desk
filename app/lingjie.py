"""灵芥空间（api.lingjie888.cn）客户端，移植自 lingjie-halo。"""
from __future__ import annotations

import base64
import json
import time
from typing import Callable, Optional

from . import net
from .authwords import is_auth_bad
from .config import CFG
from .debuglog import DBG

BASE = "http://api.lingjie888.cn/appapi"


def _log_http(method: str, path: str, t0: float, text: str) -> None:
    try:
        if not CFG.get("debug.http", True):
            return
        ms = int((time.time() - t0) * 1000)
        obj = net.json_of(text) if text else {}
        code = obj.get("code")
        msg = str(obj.get("msg") or obj.get("message") or "")[:40]
        extra = f"code={code}" + (f" msg={msg}" if msg else "")
        DBG.log("LJ", f"{method} {path} {ms}ms {extra} len={len(text or '')}")
    except Exception:
        pass


class LingjieError(Exception):
    pass


def jwt_uid(token: str) -> int:
    """从 JWT payload 里取 uid，失败返回 0。"""
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(part))
        for k in ("uid", "userId", "user_id", "sub"):
            v = payload.get(k)
            if v:
                return int(v)
    except Exception:
        pass
    return 0


class LingjieClient:
    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.auth_issue = ""

    @property
    def token(self) -> str:
        return self.cfg.get("lingjie.token", "") or ""

    @property
    def uid(self) -> int:
        return int(self.cfg.get("lingjie.uid", 0) or 0)

    @property
    def logged_in(self) -> bool:
        return bool(self.token)

    # ---------- 基础 ----------
    def _headers(self, auth: bool = True) -> dict:
        h = {"Accept": "application/json"}
        if auth and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str, params: str = "", auth: bool = True, timeout: float = 18) -> dict:
        url = BASE + path + (("?" + params) if params else "")
        t0 = time.time()
        text = net.http(url, headers=self._headers(auth), timeout=timeout)
        _log_http("GET", path, t0, text)
        obj = net.json_of(text)
        self._note_auth(obj)
        return obj

    def _post(self, path: str, fields: Optional[dict] = None, auth: bool = True,
              timeout: float = 25) -> dict:
        url = BASE + path
        t0 = time.time()
        text = net.post_form(url, fields or {}, self._headers(auth), timeout)
        _log_http("POST", path, t0, text)
        obj = net.json_of(text)
        self._note_auth(obj)
        return obj

    def _note_auth(self, obj: dict) -> None:
        msg = str(obj.get("msg") or obj.get("message") or "")
        if is_auth_bad(msg):
            self.auth_issue = msg

    @staticmethod
    def _ok(obj: dict) -> bool:
        return int(obj.get("code", 0) or 0) == 200

    # ---------- 登录 ----------
    def send_code(self, phone: str) -> tuple[bool, str]:
        obj = self._post("/sms/sendCode", {"phone": phone}, auth=False)
        return self._ok(obj), obj.get("msg") or obj.get("message") or ""

    def login_password(self, phone: str, password: str) -> dict:
        obj = self._post("/login/password", {"phone": phone, "password": password}, auth=False)
        if not self._ok(obj):
            raise LingjieError(obj.get("msg") or obj.get("message") or "登录失败")
        return self._save_login(obj, phone)

    def login_sms(self, phone: str, code: str) -> dict:
        obj = self._post("/sms/login", {"phone": phone, "code": code}, auth=False)
        if not self._ok(obj):
            raise LingjieError(obj.get("msg") or obj.get("message") or "登录失败")
        return self._save_login(obj, phone)

    def login_by_token(self, token: str) -> dict:
        token = (token or "").strip()
        if not token:
            raise LingjieError("Token 为空")
        self.cfg.set("lingjie.token", token)
        self.cfg.set("lingjie.uid", jwt_uid(token))
        info = self.me()
        self.cfg.save()
        return info

    def _save_login(self, obj: dict, phone: str) -> dict:
        data = obj.get("data") or {}
        token = ""
        for k in ("access_token", "token", "accessToken"):
            if data.get(k):
                token = data[k]
                break
        if not token:
            raise LingjieError("登录成功但没有拿到 token")
        self.cfg.set("lingjie.token", token)
        self.cfg.set("lingjie.refresh", data.get("refreshToken") or data.get("refresh_token") or "")
        self.cfg.set("lingjie.phone", phone)
        ui = data.get("userInfo") or {}
        self.cfg.set("lingjie.uid", int(ui.get("uid", 0) or jwt_uid(token)))
        self.cfg.set("lingjie.nickname", ui.get("nickname", "") or "")
        self.cfg.set("lingjie.avatar", ui.get("avatar", "") or "")
        self.cfg.save()
        return ui

    def logout(self) -> None:
        for k in ("token", "refresh", "nickname", "avatar"):
            self.cfg.set(f"lingjie.{k}", "")
        self.cfg.set("lingjie.uid", 0)
        self.cfg.save()

    def check_login(self) -> bool:
        try:
            return self.probe_login()
        except Exception:
            return False

    def login_state(self) -> tuple[str, str]:
        """返回 (ok|invalid|blocked|unknown, 服务端原因)；网络错误会抛异常。"""
        if not self.token:
            return "invalid", "未登录"
        st = self.sign_status(1)
        msg = str(st.get("msg") or st.get("message") or "")
        if is_auth_bad(msg):
            return "blocked", msg
        if self._ok(st) or bool(st.get("data")):
            return "ok", ""
        if msg:
            return "invalid", msg
        return "unknown", "登录状态无法确认"

    def probe_login(self) -> bool:
        """只判断登录态；网络错误会抛异常，避免把断网当成失效。"""
        return self.login_state()[0] == "ok"

    # ---------- 用户 ----------
    def me(self) -> dict:
        if not self.uid:
            self.cfg.set("lingjie.uid", jwt_uid(self.token))
        obj = self._get("/user/info", f"uid={self.uid}")
        data = obj.get("data") or {}
        if data:
            self.cfg.set("lingjie.nickname", data.get("nickname", "") or "")
            self.cfg.set("lingjie.avatar", data.get("avatar", "") or "")
            if data.get("uid"):
                self.cfg.set("lingjie.uid", int(data["uid"]))
            self.cfg.save()
        return data

    # ---------- 板块 / 签到 ----------
    def forums(self) -> list[tuple[int, str]]:
        obj = self._get("/forum/list")
        out = []
        for zone in obj.get("data") or []:
            for f in (zone.get("forums") or []) if isinstance(zone, dict) else []:
                try:
                    out.append((int(f.get("fid")), f.get("name", "")))
                except Exception:
                    continue
        return out

    def sign_status(self, fid: int = 1) -> dict:
        return self._get("/sign/status", f"fid={fid}")

    def sign_status_all(self) -> dict:
        st = self.sign_status(1)
        data = st.get("data") or {}
        return {
            "signed": [int(x) for x in (data.get("todaySignedFids") or [])],
            "cont_days": int(data.get("contDays", 0) or 0),
            "exp": int(data.get("exp", 0) or 0),
            "level": int(data.get("currentLv", 1) or 1),
            "next_exp": int(data.get("nextExp", 0) or 0),
        }

    def sign_in(self, fid: int) -> tuple[bool, str]:
        obj = self._post("/sign/in", {"fid": fid})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "签到失败")

    def signin_all(self, on_progress: Optional[Callable[[int, int, str, bool, str], None]] = None
                   ) -> tuple[int, int, list[str]]:
        forums = self.forums()
        if not forums:
            raise LingjieError("拿不到板块列表，登录可能已过期")
        status = self.sign_status_all()
        signed = set(status["signed"])
        ok = skip = fail = 0
        logs: list[str] = []
        total = len(forums)
        for i, (fid, name) in enumerate(forums, 1):
            if fid in signed:
                skip += 1
                logs.append(f"· {name}：今天已签到")
                if on_progress:
                    on_progress(i, total, name, True, "已签到")
                continue
            try:
                good, msg = self.sign_in(fid)
            except Exception as e:
                good, msg = False, str(e)
            if good:
                ok += 1
            else:
                fail += 1
            logs.append(f"{'✓' if good else '✗'} {name}：{msg or '签到成功'}")
            if on_progress:
                on_progress(i, total, name, good, msg)
            time.sleep(0.3)
        logs.append(f"共 {total} 个板块：新签 {ok}，已签 {skip}，失败 {fail}")
        return ok, fail, logs

    # ---------- 内容 ----------
    def themes(self, fid: int = 0, page: int = 1, size: int = 20) -> list[dict]:
        params = f"page={page}&size={size}" + (f"&fid={fid}" if fid else "")
        obj = self._get("/theme/list", params)
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)]

    def theme_detail(self, tid: int) -> dict:
        obj = self._get("/theme/detail", f"tid={tid}")
        return obj.get("data") or {}

    def comments(self, tid: int) -> list[dict]:
        obj = self._get("/theme/comment/list", f"tid={tid}")
        data = obj.get("data") or {}
        records = data.get("records") or data.get("list") or []
        return self._flatten_comments(records)

    def _flatten_comments(self, records, depth: int = 0) -> list[dict]:
        out: list[dict] = []
        for c in records or []:
            if not isinstance(c, dict):
                continue
            out.append(c)
            if depth < 3:
                for key in ("children", "replyList", "replies", "reply_list"):
                    kids = c.get(key)
                    if isinstance(kids, list):
                        out.extend(self._flatten_comments(kids, depth + 1))
        return out

    @staticmethod
    def _parent_of(c: dict) -> int:
        for k in ("parent_id", "parentId", "pid", "reply_id", "replyId"):
            try:
                v = int(c.get(k, 0) or 0)
            except Exception:
                v = 0
            if v:
                return v
        return 0

    def find_my_reply(self, tid: int, parent_cid: int, text: str = "") -> bool:
        """帖子下是否已经有我对这条评论的回复（兼容嵌套结构）。"""
        try:
            uid = int(self.uid or 0)
            body = " ".join(str(text or "").split())
            for c in self.comments(tid):
                u = c.get("user") or c.get("author") or {}
                cuid = int((u or {}).get("uid", 0) or c.get("uid", 0) or 0)
                if uid and cuid != uid:
                    continue
                if not uid and not c.get("is_mine"):
                    continue
                par = self._parent_of(c)
                content = " ".join(str(c.get("content") or c.get("commentContent") or "").split())
                same_text = bool(body and content and content == body)
                if parent_cid and par == int(parent_cid):
                    return True
                # 接口可能把回复挂成一级评论：同样内容也算已回
                if same_text and (not parent_cid or par in (0, int(parent_cid))):
                    return True
        except Exception:
            pass
        return False

    def has_my_comment(self, tid: int, parent_cid: int = 0, since_ms: int = 0) -> bool:
        """这个帖子/这条评论下有没有我的评论。"""
        try:
            uid = int(self.uid or 0)
            for c in self.comments(tid):
                u = c.get("user") or c.get("author") or {}
                cuid = int((u or {}).get("uid", 0) or c.get("uid", 0) or 0)
                if uid and cuid != uid:
                    continue
                if parent_cid and self._parent_of(c) != int(parent_cid):
                    continue
                ct = int(c.get("create_time", 0) or 0)
                if since_ms > 0 and ct and ct < since_ms:
                    continue
                return True
        except Exception:
            pass
        return False

    def publish_comment(self, tid: int, content: str, parent_id: int = 0) -> tuple[bool, str]:
        fields = {"tid": tid, "content": content, "images": "[]"}
        if parent_id:
            fields["parentId"] = parent_id
        obj = self._post("/theme/comment/publish", fields)
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "评论失败")

    # ---------- 关注 ----------
    def follow(self, uid: int) -> tuple[bool, str]:
        obj = self._post("/user/follow", {"uid": uid})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "关注失败")

    def unfollow(self, uid: int) -> tuple[bool, str]:
        obj = self._post("/user/follow/cancel", {"uid": uid})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "取关失败")

    def is_following(self, uid: int) -> bool:
        try:
            return any(int(r.get("uid", 0) or 0) == int(uid) for r in self.following_list())
        except Exception:
            return False

    def follow_once(self, uid: int) -> tuple[bool, str]:
        """已经关注过就不重复调用（接口是切换式的，重复调用会取消关注）。"""
        if self.is_following(uid):
            return False, "已经关注过了"
        ok, msg = self.follow(uid)
        return ok, msg

    def unfollow_once(self, uid: int) -> tuple[bool, str]:
        """本来没关注就不要调用，否则会变成关注。"""
        if not self.is_following(uid):
            return False, "本来就没关注"
        ok, msg = self.unfollow(uid)
        return ok, msg

    def like(self, tid: int, cancel: bool = False) -> bool:
        obj = self._post("/theme/like/cancel" if cancel else "/theme/like", {"tid": tid})
        return self._ok(obj)

    def favorite(self, tid: int, cancel: bool = False) -> bool:
        obj = self._post("/theme/favorite/cancel" if cancel else "/theme/favorite", {"tid": tid})
        return self._ok(obj)

    def notifications(self, page: int = 1) -> list[dict]:
        obj = self._get("/notification/list", f"page={page}")
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)]

    def publish_theme(self, fid: int, title: str, content: str,
                      cate_id: int = 0, images: Optional[list[str]] = None) -> tuple[bool, str]:
        fields = {
            "fid": fid,
            "cateId": cate_id,
            "title": title,
            "content": content,
            "content_mode": 0,
            "images": json.dumps(images or [], ensure_ascii=False),
        }
        obj = self._post("/theme/publish", fields)
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "发帖失败")

    # ---------- 我的帖子 / 删除 ----------
    def my_themes(self, count: int = 20) -> list[dict]:
        return self.user_themes(self.uid, count)

    def user_themes(self, uid: int, count: int = 20) -> list[dict]:
        obj = self._get("/user/themes", f"uid={uid}&type=approved&current=1")
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)][:count]

    def delete_theme(self, tid: int) -> tuple[bool, str]:
        obj = self._post("/moderator/delete",
                         {"tid": tid, "reason": "删除帖子", "recordViolation": 0})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "删帖失败")

    def delete_comment(self, cid: int) -> tuple[bool, str]:
        obj = self._post("/moderator/deleteComment",
                         {"cid": cid, "reason": "删除评论"})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "删评论失败")

    # ---------- 签到补充 ----------
    def sign_calendar(self) -> dict:
        return self._get("/sign/calendar")

    def sign_repair(self) -> tuple[bool, str]:
        obj = self._post("/sign/repair", {})
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "补签失败")

    # ---------- 打赏 ----------
    def reward_config(self) -> dict:
        obj = self._get("/reward/config")
        return obj.get("data") or {}

    def reward_publish(self, target_type: str, target_id: int, amount: int,
                       reason: str = "谢谢分享") -> tuple[bool, str]:
        obj = self._post("/reward/publish", {
            "targetType": target_type, "targetId": target_id,
            "amount": amount, "reason": reason,
        })
        ok = self._ok(obj)
        return ok, obj.get("msg") or obj.get("message") or ("" if ok else "打赏失败")

    # ---------- 用户 / 关注 ----------
    def user_comments(self, uid: int, page: int = 1) -> list[dict]:
        obj = self._get("/user/comments", f"uid={uid}&page={page}")
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)]

    def following_list(self, uid: int = 0) -> list[dict]:
        obj = self._get("/user/following", f"uid={uid or self.uid}")
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)]

    def followers_list(self, uid: int = 0) -> list[dict]:
        obj = self._get("/user/followers", f"uid={uid or self.uid}")
        data = obj.get("data") or {}
        records = data.get("records") if isinstance(data, dict) else None
        return [r for r in (records or []) if isinstance(r, dict)]

    def site_config(self) -> dict:
        obj = self._get("/site/config")
        return obj.get("data") or {}

    def theme_view(self, tid: int) -> dict:
        obj = self._get("/theme/view", f"tid={tid}")
        return obj.get("data") or {}

    def favorites(self, uid: int = 0, page: int = 1) -> list[dict]:
        """我（或某人）收藏的帖子。实测 /user/favorites?uid=&page= 可用。"""
        obj = self._get("/user/favorites", f"uid={uid or self.uid}&page={page}")
        data = obj.get("data") or {}
        return [r for r in (data.get("records") or []) if isinstance(r, dict)]

    def emoji_list(self) -> list:
        obj = self._get("/emoji/list")
        return obj.get("data") or []

    # ---------- 图片上传（七牛） ----------
    @staticmethod
    def _upload_hosts(d: dict) -> list[str]:
        """优先用接口给的 uploadHost；老代码写死 up-z2，七牛换区后要兜底。"""
        hosts = []
        h = (d.get("uploadHost") or "").strip().rstrip("/")
        if h:
            hosts.append(h)
        for fallback in ("https://up-z0.qiniup.com", "https://up-z2.qiniup.com",
                         "https://up-z1.qiniup.com"):
            if fallback not in hosts:
                hosts.append(fallback)
        return hosts

    def upload_image(self, data: bytes) -> Optional[str]:
        if not data:
            return None
        tk = self._get("/upload/token")
        if not self._ok(tk):
            return None
        d = tk.get("data") or {}
        up_token = d.get("token", "")
        if not up_token:
            return None
        domain = d.get("domain") or "http://qn.lingjie888.cn"
        prefix = d.get("keyPrefix", "") or ""
        date = time.strftime("%Y%m%d")
        is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
        ext, ctype = ("png", "image/png") if is_png else ("jpg", "image/jpeg")
        key = f"{prefix}{date}/{int(time.time() * 1000)}_{1000 + int(time.time()) % 9000}.{ext}"
        for host in self._upload_hosts(d):
            boundary = "----HaloDesk" + str(int(time.time() * 1000))
            body = b""
            for name, val in (("token", up_token), ("key", key)):
                body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
                         f"\r\n\r\n{val}\r\n").encode()
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                     f"filename=\"fish.{ext}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
            body += data
            body += f"\r\n--{boundary}--\r\n".encode()
            try:
                text = net.http(host, "POST", body,
                                {"Content-Type": f"multipart/form-data; boundary={boundary}"},
                                timeout=90, retries=0)
            except Exception as e:
                DBG.log("IMG", f"灵芥上传 {host} 异常：{e}", "WARN")
                continue
            obj = net.json_of(text)
            if obj.get("key"):
                return f"{domain.rstrip('/')}/{key}"
            DBG.log("IMG", f"灵芥上传 {host} 失败：{text[:120]}", "WARN")
        return None
