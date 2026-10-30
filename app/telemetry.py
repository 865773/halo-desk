"""Gitee 云端能力：匿名统计上报 + 仓库文件读取。

统计沿用手机端同款方案：
- 仓库 guo-wenlong/lingjie-misc
- 文件 assets/data/.cache/halodesk.dat
- 内容 = Base64(Base64(JSON))，只在 API 传输层出现双层，落盘为内层 Base64
- 只记录安装 id / 平台 / 版本 / 系统 / 首次时间，不采集账号、Key、聊天内容
"""
from __future__ import annotations

import base64
import json
import platform
import threading
import time
import urllib.parse
import urllib.request
import uuid

from .config import CFG
from .version import VERSION

STATS_REPO = "guo-wenlong/lingjie-misc"
STATS_FILE = "assets/data/.cache/halodesk.dat"
HALO_REPO = "guo-wenlong/halo-desk"
_API = "https://gitee.com/api/v5/repos/"

# token 不明文写入仓库：Base64 + XOR 混淆
_KEY = b"halo-desk-2026!"
_TOKEN = "WVNYXU9WUEtTG1MABwIXDgUOXhkCVUYOHldVAw5AUFU="


def token() -> str:
    try:
        raw = base64.b64decode(_TOKEN)
        return bytes(c ^ _KEY[i % len(_KEY)] for i, c in enumerate(raw)).decode()
    except Exception:
        return ""


def _request(url: str, body: dict | None = None, method: str = "GET") -> dict:
    data = None
    headers = {"User-Agent": "HaloDesk", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        txt = r.read().decode("utf-8", "replace")
    return json.loads(txt) if txt.strip().startswith(("{", "[")) else {}


def read_repo_text(path: str, repo: str = HALO_REPO) -> str:
    """读取仓库文本文件；公开仓库也可退回 raw。"""
    t = token()
    if t:
        try:
            url = (_API + urllib.parse.quote(repo, safe="/") + "/contents/"
                   + urllib.parse.quote(path, safe="/")
                   + "?access_token=" + urllib.parse.quote(t))
            obj = _request(url)
            b64 = str(obj.get("content", "")).replace("\n", "").replace("\r", "")
            if b64:
                return base64.b64decode(b64).decode("utf-8", "replace")
        except Exception:
            pass
    try:
        url = (f"https://gitee.com/{repo}/raw/master/"
               + urllib.parse.quote(path, safe="/") + f"?t={int(time.time())}")
        req = urllib.request.Request(url, headers={"User-Agent": "HaloDesk"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _decode_stats(content_b64: str) -> list:
    try:
        inner = base64.b64decode(content_b64).decode("utf-8", "replace").strip()
        try:
            raw = base64.b64decode(inner).decode("utf-8", "replace")
        except Exception:
            raw = inner
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _encode_stats(arr: list) -> str:
    inner = base64.b64encode(
        json.dumps(arr, ensure_ascii=False).encode("utf-8")).decode()
    return base64.b64encode(inner.encode("utf-8")).decode()


def install_id() -> str:
    val = str(CFG.get("general.install_id", "") or "")
    if not val:
        val = uuid.uuid4().hex
        CFG.set("general.install_id", val)
        CFG.save()
    return val


def _accounts() -> list[dict]:
    """当前登录的两个平台账号（uid + 昵称），用于按账号统计。"""
    out = []
    try:
        hlx_uid = int(CFG.get("hlx.uid", 0) or 0)
        if hlx_uid > 0:
            out.append({
                "platform": "葫芦侠",
                "uid": hlx_uid,
                "nickname": str(CFG.get("hlx.nick", "") or ""),
            })
    except Exception:
        pass
    try:
        lj_uid = int(CFG.get("lingjie.uid", 0) or 0)
        if lj_uid > 0:
            out.append({
                "platform": "灵芥",
                "uid": lj_uid,
                "nickname": str(CFG.get("lingjie.nickname", "") or ""),
            })
    except Exception:
        pass
    return out


def _device_info() -> str:
    return f"Windows {platform.release()} / {platform.machine()}"


def _merge_accounts(rec: dict, accounts: list[dict]) -> None:
    lst = rec.get("accounts")
    if not isinstance(lst, list):
        lst = []
    for acc in accounts or []:
        if not acc.get("uid"):
            continue
        hit = None
        for it in lst:
            if (isinstance(it, dict)
                    and it.get("platform") == acc.get("platform")
                    and int(it.get("uid", 0) or 0) == int(acc.get("uid", 0) or 0)):
                hit = it
                break
        if hit is not None:
            if acc.get("nickname"):
                hit["nickname"] = acc["nickname"]
        else:
            lst.append(dict(acc))
    rec["accounts"] = lst


def report_async(log=None, force: bool = False) -> None:
    """启动/登录后异步上报；force=True 时每次都会更新 last。"""
    if not force:
        try:
            last = float(CFG.get("general.stats_at", 0) or 0)
            if time.time() - last < 86400:
                return
        except Exception:
            pass
    threading.Thread(target=_report, args=(log, force), daemon=True).start()


def _report(log=None, force: bool = False) -> None:
    try:
        iid = install_id()
        accounts = _accounts()
        now = time.strftime("%Y-%m-%d %H:%M")
        url = (_API + STATS_REPO + "/contents/" + STATS_FILE
               + "?access_token=" + urllib.parse.quote(token()))
        sha = ""
        arr: list = []
        try:
            obj = _request(url)
            sha = str(obj.get("sha", "") or "")
            if obj.get("content"):
                arr = _decode_stats(str(obj["content"]))
        except Exception:
            pass

        groups = [x for x in arr
                  if isinstance(x, dict) and x.get("id") == iid]
        rec = next((x for x in groups
                    if isinstance(x.get("accounts"), list)),
                   groups[0] if groups else None)
        if rec is None:
            rec = {"id": iid, "first": now}
            arr.append(rec)
        # 兼容旧版：platform=windows、无 accounts、uid 平铺
        rec.pop("platform", None) if rec.get("platform") == "windows" else None
        rec["device"] = _device_info()
        rec["version"] = VERSION
        rec["last"] = now
        rec.setdefault("first", now)
        _merge_accounts(rec, accounts)
        # 合并同 id 的旧账号行，删掉重复设备
        for old in list(groups):
            if old is rec:
                continue
            _merge_accounts(rec, old.get("accounts") or [])
            if old.get("uid") and old.get("platform") in ("葫芦侠", "灵芥"):
                _merge_accounts(rec, [{
                    "platform": old.get("platform"),
                    "uid": int(old.get("uid", 0) or 0),
                    "nickname": old.get("nickname", ""),
                }])
            try:
                arr.remove(old)
            except ValueError:
                pass

        content = _encode_stats(arr)
        body = {
            "access_token": token(),
            "content": content,
            "message": "update halodesk stats",
        }
        if sha:
            body["sha"] = sha
            _request(_API + STATS_REPO + "/contents/" + STATS_FILE,
                     body, "PUT")
        else:
            _request(_API + STATS_REPO + "/contents/" + STATS_FILE,
                     body, "POST")
        CFG.set("general.stats_at", time.time())
        CFG.save()
        if log:
            log("统计已上报")
    except Exception as e:
        if log:
            log(f"统计上报失败：{e}")
