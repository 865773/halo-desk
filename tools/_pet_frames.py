"""克隆 dsh-pet，抽取 shenshen 动画帧，去黑底、裁剪、等比缩放。"""
import os
import shutil

import av
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from dulwich import porcelain

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
REPO = os.path.join(ROOT, ".petrepo2")
OUT = os.path.join(ROOT, "assets", "pet", "shenshen")
URL = "https://gitcode.com/gh_mirrors/ds/dsh-pet-indesktop.git"

JOBS = {
    "idle": ("待机呼吸休闲.webm", 10),
    "happy": ("点击回应-开心跃动.webm", 6),
    "shy": ("点击回应-害羞惊讶.webm", 4),
    "angry": ("点击回应-傲娇生气.webm", 4),
    "drag": ("被鼠标拖拽悬空反馈.webm", 2),
    "eat": ("偷吃零食被抓住.webm", 4),
}


def key_and_crop(img: QImage) -> QImage:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.bits(), dtype=np.uint8).reshape(h, w, 4).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    near_black = rgb.max(axis=2) < 32
    visited = np.zeros((h, w), dtype=bool)
    stack = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)]
    stack += [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
    while stack:
        y, x = stack.pop()
        if y < 0 or x < 0 or y >= h or x >= w or visited[y, x] or not near_black[y, x]:
            continue
        visited[y, x] = True
        stack.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    arr[visited, 3] = 0
    ys, xs = np.where(arr[:, :, 3] > 8)
    if len(xs) == 0:
        return img
    x0, x1 = max(0, xs.min() - 2), min(w, xs.max() + 3)
    y0, y1 = max(0, ys.min() - 2), min(h, ys.max() + 3)
    arr = arr[y0:y1, x0:x1].copy()
    hh, ww = arr.shape[0], arr.shape[1]
    out = QImage(arr.data, ww, hh, 4 * ww, QImage.Format_RGBA8888).copy()
    return out.scaled(4000, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def main():
    shutil.rmtree(REPO, ignore_errors=True)
    porcelain.clone(URL, REPO, depth=1)
    src = os.path.join(REPO, "assets", "characters", "shenshen", "videos")
    index = {}
    for base, _d, files in os.walk(src):
        for f in files:
            if f.endswith(".webm"):
                index[f] = os.path.join(base, f)
    os.makedirs(OUT, exist_ok=True)
    for key, (fname, n) in JOBS.items():
        path = index.get(fname)
        if not path:
            print("missing", key)
            continue
        c = av.open(path)
        st = c.streams.video[0]
        frames = []
        for fr in c.decode(st):
            frames.append(fr)
            if len(frames) >= 600:
                break
        c.close()
        step = max(1, len(frames) // n)
        cnt = 0
        for i in range(0, len(frames), step):
            if cnt >= n:
                break
            a = frames[i].to_ndarray(format="rgba")
            h, w = a.shape[0], a.shape[1]
            qi = QImage(a.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            qi = key_and_crop(qi)
            qi.save(os.path.join(OUT, f"{key}_{cnt}.png"))
            cnt += 1
        print(key, cnt)
    shutil.rmtree(REPO, ignore_errors=True)


if __name__ == "__main__":
    main()
