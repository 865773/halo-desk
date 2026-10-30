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


def report_async(log=None) -> None:
    """启动后异步上报一次；24 小时内不重复。"""
    try:
        last = float(CFG.get("general.stats_at", 0) or 0)
        if time.time() - last < 86400:
            return
    except Exception:
        pass
    threading.Thread(target=_report, args=(log,), daemon=True).start()


def _report(log=None) -> None:
    try:
        iid = install_id()
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
        if any(isinstance(x, dict) and x.get("id") == iid for x in arr):
            CFG.set("general.stats_at", time.time())
            CFG.save()
            return
        arr.append({
            "id": iid,
            "platform": "windows",
            "version": VERSION,
            "device": f"Windows {platform.release()} / {platform.machine()}",
            "first": time.strftime("%Y-%m-%d %H:%M"),
        })
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
