"""文生图：移植 hlx-halo/FishImage.java，支持 openai / dashscope / sd 三种协议。

返回的是 PNG/JPEG 字节，方便直接上传到社区。
"""
from __future__ import annotations

import base64
import json
import time
from typing import Callable, Optional

from . import net
from .config import CFG, FILES_DIR
from .debuglog import DBG

DEFAULT_OPENAI = "https://api.openai.com/v1/images/generations"
DEFAULT_DASH = ("https://dashscope.aliyuncs.com/api/v1/services/aigc/"
                "multimodal-generation/generation")


class ImageError(Exception):
    pass


def _cfg(key: str, default: str = "") -> str:
    return (CFG.get(f"fish.{key}", default) or "").strip()


def _download(url: str) -> Optional[bytes]:
    try:
        req_headers = {"User-Agent": "Mozilla/5.0"}
        import urllib.request
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as e:
        DBG.log("IMG", f"下载图片失败 {url}: {e}", "ERROR")
        return None


def generate(prompt: str, on_log: Optional[Callable[[str], None]] = None) -> Optional[bytes]:
    """生成图片，失败返回 None（原因写调试日志和 last_error）。"""
    proto = _cfg("img_proto", "openai") or "openai"
    url = _cfg("img_url")
    key = _cfg("img_key")
    model = _cfg("img_model")
    size = _cfg("img_size", "1024x1024") or "1024x1024"
    log = on_log or (lambda s: None)
    try:
        if proto == "dashscope":
            return _dashscope(url or DEFAULT_DASH, key, model, size, prompt, log)
        if proto == "sd":
            return _sd(url or "http://127.0.0.1:7860", prompt)
        return _openai_multi(url or DEFAULT_OPENAI, key, model, size, prompt, log)
    except Exception as e:
        DBG.log("IMG", f"生图异常（{proto}）：{e}", "ERROR")
        log(f"生图失败：{e}")
        return None


def _model_cands(model: str, fallback: str) -> list[str]:
    cands: list[str] = []
    if model.strip():
        cands.append(model.strip())
    for x in (fallback or "").split(","):
        x = x.strip()
        if x and x not in cands:
            cands.append(x)
    return cands


def _openai_multi(url: str, key: str, model: str, size: str, prompt: str,
                  log) -> Optional[bytes]:
    """OpenAI 协议也支持多模型轮换：余额/额度用完自动换下一个。"""
    cands = _model_cands(model, _cfg("img_models") or "gpt-image-1,dall-e-3")
    start = int(CFG.get("fish.img_model_i", 0) or 0)
    if start < 0 or start >= len(cands):
        start = 0
    last = ""
    for k in range(len(cands)):
        idx = (start + k) % len(cands)
        mdl = cands[idx]
        try:
            png = _openai(url, key, mdl, size, prompt)
            if png:
                if k:
                    DBG.log("IMG", f"换到可用模型：{mdl}")
                    log(f"换到可用模型：{mdl}")
                CFG.set("fish.img_model", mdl)
                CFG.set("fish.img_model_i", idx)
                CFG.save()
                return png
        except Exception as e:
            last = str(e)
            DBG.log("IMG", f"模型不可用 {mdl}：{last}", "WARN")
            log(f"{mdl} 不可用：{last}")
    raise ImageError(f"全部模型都不可用（{last}）")


def _openai(url: str, key: str, model: str, size: str, prompt: str) -> Optional[bytes]:
    body = {"model": model, "prompt": prompt, "n": 1, "size": size}
    r = net.post_json(url, body, {"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"}, timeout=180)
    o = net.json_of(r)
    arr = o.get("data") or []
    if not arr:
        DBG.log("IMG", f"openai 无 data：{r[:200]}", "ERROR")
        raise ImageError(_err_msg(o) or "接口没有返回图片")
    d = arr[0]
    if d.get("b64_json"):
        return base64.b64decode(d["b64_json"])
    if d.get("url"):
        png = _download(d["url"])
        if png:
            return png
    raise ImageError("返回里没有 b64_json 或 url")


def _dashscope(url: str, key: str, model: str, size: str, prompt: str,
               log) -> Optional[bytes]:
    base = url.rstrip("/")
    # 专属部署的 /api/v1 走异步任务
    if base.endswith("/api/v1"):
        return _dash_async(base, key, model, size, prompt, log)

    cands: list[str] = []
    if model:
        cands.append(model)
    preset = _cfg("img_models")
    for x in preset.split(","):
        x = x.strip()
        if x and x not in cands:
            cands.append(x)
    if not cands:
        cands = ["wan2.6-t2i"]

    start = int(CFG.get("fish.img_model_i", 0) or 0)
    if start < 0 or start >= len(cands):
        start = 0
    last = ""
    for k in range(len(cands)):
        idx = (start + k) % len(cands)
        mdl = cands[idx]
        try:
            body = {
                "model": mdl,
                "input": {"messages": [{"role": "user",
                                        "content": [{"text": prompt}]}]},
                "parameters": {"size": size.replace("x", "*"), "n": 1},
            }
            r = net.post_json(url, body, {"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"},
                              timeout=180)
            o = net.json_of(r)
            out = o.get("output") or {}
            for ch in (out.get("choices") or []):
                msg = ch.get("message") or {}
                for c in (msg.get("content") or []):
                    if c.get("image"):
                        png = _download(c["image"])
                        if png:
                            CFG.set("fish.img_model", mdl)
                            CFG.set("fish.img_model_i", idx)
                            CFG.save()
                            if k:
                                DBG.log("IMG", f"换到可用模型：{mdl}")
                            return png
            last = _err_msg(o) or str(r)[:160]
            DBG.log("IMG", f"模型不可用 {mdl}：{last}", "WARN")
        except Exception as e:
            last = str(e)
            DBG.log("IMG", f"模型 {mdl} 异常：{e}", "WARN")
    raise ImageError(f"全部模型都不可用（{last}）")


def _dash_async(base: str, key: str, model: str, size: str, prompt: str, log) -> Optional[bytes]:
    body = {"model": model or "wan2.6-t2i",
            "input": {"prompt": prompt},
            "parameters": {"size": size.replace("x", "*"), "n": 1}}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "X-DashScope-Async": "enable"}
    r = net.post_json(base + "/services/aigc/text2image/image-synthesis", body,
                      headers, timeout=60)
    DBG.log("IMG-SUBMIT", r[:300])
    o = net.json_of(r)
    out = o.get("output") or {}
    tid = out.get("task_id", "")
    if not tid:
        raise ImageError(_err_msg(o) or "没有拿到 task_id")
    for _ in range(40):
        time.sleep(3)
        rr = net.http(base + f"/tasks/{tid}", headers={"Authorization": f"Bearer {key}"},
                      timeout=30)
        oo = net.json_of(rr)
        o2 = oo.get("output") or {}
        st = o2.get("task_status", "")
        if st == "SUCCEEDED":
            res = o2.get("results") or []
            if not res or not res[0].get("url"):
                raise ImageError("结果为空")
            png = _download(res[0]["url"])
            if not png:
                raise ImageError("下载图片失败")
            return png
        if st == "FAILED":
            raise ImageError(_err_msg(oo) or "任务失败")
    raise ImageError("等待任务超时")


def _sd(url: str, prompt: str) -> Optional[bytes]:
    endpoint = url.rstrip("/")
    if not endpoint.endswith("/sdapi/v1/txt2img"):
        endpoint += "/sdapi/v1/txt2img"
    r = net.post_json(endpoint, {"prompt": prompt, "steps": 20, "width": 512,
                                 "height": 512}, {"Content-Type": "application/json"},
                      timeout=240)
    o = net.json_of(r)
    imgs = o.get("images") or []
    if not imgs:
        raise ImageError("SD 没有返回图片")
    return base64.b64decode(imgs[0].split(",")[-1])


def _err_msg(o: dict) -> str:
    if not isinstance(o, dict):
        return ""
    err = o.get("error")
    if isinstance(err, dict):
        return err.get("message", "") or json.dumps(err, ensure_ascii=False)[:120]
    if isinstance(err, str):
        return err
    return o.get("message", "") or o.get("msg", "")


def save_last(png: bytes, name: str = "last_image.png") -> str:
    p = FILES_DIR / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(png)
    except Exception:
        pass
    return str(p)


def test_generate(prompt: str) -> tuple[bool, str]:
    """给设置页用的测试：成功返回 (True, 本地路径)。"""
    png = generate(prompt)
    if not png:
        return False, "没有生成成功，看调试日志"
    path = save_last(png, "test_image.png")
    return True, path
