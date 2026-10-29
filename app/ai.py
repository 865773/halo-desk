"""DeepSeek / OpenAI 兼容接口 + 生图（三种协议）。"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from . import net
from .config import CFG


class AIError(Exception):
    pass


def _headers() -> dict:
    key = CFG.get("ai.key", "")
    if not key:
        raise AIError("还没有填写 DeepSeek API Key")
    return {"Authorization": f"Bearer {key}",
            "Content-Type": "application/json"}


def _url(path: str) -> str:
    base = (CFG.get("ai.base", "https://api.deepseek.com") or "").rstrip("/")
    return base + path


def chat(messages: list[dict], model: Optional[str] = None,
         temperature: float = 1.0, stream: bool = False,
         on_delta: Optional[Callable[[str], None]] = None,
         timeout: float = 90) -> str:
    """普通或流式对话，返回完整文本。"""
    model = model or CFG.get("ai.model_basic", "deepseek-flash")
    body = {"model": model, "messages": messages,
            "temperature": temperature, "stream": bool(stream)}
    url = _url("/chat/completions")
    if not stream:
        text = net.post_json(url, body, _headers(), timeout=timeout)
        obj = net.json_of(text)
        try:
            return obj["choices"][0]["message"]["content"] or ""
        except Exception:
            raise AIError(obj.get("error", {}).get("message") or "模型没有返回内容")

    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=_headers(), method="POST")
    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"]
                except Exception:
                    continue
                piece = delta.get("content") or ""
                if piece:
                    parts.append(piece)
                    if on_delta:
                        on_delta(piece)
    except Exception as e:
        raise AIError(f"流式请求失败：{e}")
    return "".join(parts)


def ask(system: str, user: str, model: Optional[str] = None,
        stream: bool = False, on_delta: Optional[Callable[[str], None]] = None) -> str:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return chat(msgs, model, stream=stream, on_delta=on_delta)


def ask_json(system: str, user: str, model: Optional[str] = None) -> dict:
    text = ask(system, user, model)
    return net.json_of(text)


def chat_with_images(system: str, user: str, image_urls: list[str],
                     model: Optional[str] = None) -> str:
    content: list[dict] = [{"type": "text", "text": user}]
    for u in image_urls[:3]:
        content.append({"type": "image_url",
                        "image_url": {"url": u, "detail": "low"}})
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": content})
    return chat(msgs, model)


# ---------------- 生图 ----------------

def gen_image(prompt: str) -> str:
    """返回图片 URL 或本地文件路径（SD 返回 base64 时写文件）。"""
    proto = CFG.get("fish.img_proto", "openai")
    model = CFG.get("fish.img_model", "gpt-image-1")
    size = CFG.get("fish.img_size", "1024x1024")
    key = CFG.get("fish.img_key", "")
    url = CFG.get("fish.img_url", "") or ""

    if proto == "openai":
        endpoint = url or "https://api.openai.com/v1/images/generations"
        obj = net.json_of(net.post_json(
            endpoint, {"model": model, "prompt": prompt, "n": 1, "size": size},
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=180))
        data = (obj.get("data") or [{}])[0]
        return data.get("url") or data.get("b64_json") or ""
    if proto == "dashscope":
        endpoint = url or ("https://dashscope.aliyuncs.com/api/v1/services/aigc/"
                           "multimodal-generation/generation")
        obj = net.json_of(net.post_json(
            endpoint,
            {"model": model, "input": {"messages": [{"role": "user",
                                                     "content": [{"text": prompt}]}]},
             "parameters": {"size": size.replace("x", "*"), "n": 1}},
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=180))
        try:
            out = obj["output"]["choices"][0]["message"]["content"]
            for item in out:
                if item.get("image"):
                    return item["image"]
        except Exception:
            pass
        return ""
    if proto == "sd":
        endpoint = (url or "http://127.0.0.1:7860") + "/sdapi/v1/txt2img"
        obj = net.json_of(net.post_json(
            endpoint, {"prompt": prompt, "steps": 20, "width": 512, "height": 512},
            {"Content-Type": "application/json"}, timeout=240))
        imgs = obj.get("images") or []
        if imgs:
            import base64, time as _t
            from .config import FILES_DIR
            p = FILES_DIR / f"img_{int(_t.time())}.png"
            p.write_bytes(base64.b64decode(imgs[0].split(",")[-1]))
            return str(p)
    return ""
