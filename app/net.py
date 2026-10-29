"""极简 HTTP 工具：只用标准库，避免额外依赖。"""
from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class NetError(Exception):
    pass


_SSL_CTX = ssl.create_default_context()


def http(url: str, method: str = "GET", body: Optional[str] = None,
         headers: Optional[dict] = None, timeout: float = 20.0,
         retries: int = 2) -> str:
    """返回响应文本；失败抛 NetError。"""
    hd = {"User-Agent": UA}
    if headers:
        hd.update(headers)
    data = body.encode("utf-8") if isinstance(body, str) else body

    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hd, method=method)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, "replace")
        except urllib.error.HTTPError as e:
            # 有些接口把错误信息放在 body 里，仍然读出来
            try:
                raw = e.read()
                if raw:
                    return raw.decode("utf-8", "replace")
            except Exception:
                pass
            last = NetError(f"HTTP {e.code} {e.reason}")
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            last = NetError(f"网络错误：{getattr(e, 'reason', e)}")
        except Exception as e:  # pragma: no cover
            last = NetError(str(e))
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))
    raise last or NetError("请求失败")


def post_form(url: str, fields: dict, headers: Optional[dict] = None,
              timeout: float = 20.0) -> str:
    body = urllib.parse.urlencode(fields, encoding="utf-8")
    hd = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    if headers:
        hd.update(headers)
    return http(url, "POST", body, hd, timeout)


def post_json(url: str, obj: dict, headers: Optional[dict] = None,
              timeout: float = 60.0) -> str:
    body = json.dumps(obj, ensure_ascii=False)
    hd = {"Content-Type": "application/json; charset=UTF-8"}
    if headers:
        hd.update(headers)
    return http(url, "POST", body, hd, timeout)


def http_bytes(url: str, timeout: float = 30.0) -> bytes:
    """下载二进制（图片用）。"""
    hd = {"User-Agent": UA, "Accept": "image/*,*/*"}
    req = urllib.request.Request(url, headers=hd)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return resp.read()


def json_of(text: str) -> dict:
    """宽容解析：去掉前后杂字符，取第一个 { 到最后一个 }。"""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except Exception:
                return {}
    return {}


def enc(s) -> str:
    return urllib.parse.quote_plus(str(s if s is not None else ""))
