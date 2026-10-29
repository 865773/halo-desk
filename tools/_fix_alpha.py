import os
import sys

import numpy as np
from PySide6.QtGui import QImage

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
DIR = os.path.join(ROOT, "assets", "pet", "shenshen")


def process(path):
    img = QImage(path)
    if img.isNull():
        return
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    ptr = img.bits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    near_black = (rgb.max(axis=2) < 32)
    # flood fill from borders over near-black background
    visited = np.zeros((h, w), dtype=bool)
    stack = []
    for x in range(w):
        stack.append((0, x)); stack.append((h - 1, x))
    for y in range(h):
        stack.append((y, 0)); stack.append((y, w - 1))
    while stack:
        y, x = stack.pop()
        if y < 0 or x < 0 or y >= h or x >= w:
            continue
        if visited[y, x] or not near_black[y, x]:
            continue
        visited[y, x] = True
        stack.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    arr[visited, 3] = 0
    # soften edge: alpha for near-black pixels adjacent to transparent
    # crop to content
    ys, xs = np.where(arr[:, :, 3] > 8)
    if len(xs) == 0:
        return
    x0, x1 = max(0, xs.min() - 2), min(w, xs.max() + 3)
    y0, y1 = max(0, ys.min() - 2), min(h, ys.max() + 3)
    arr = arr[y0:y1, x0:x1].copy()
    hh, ww = arr.shape[0], arr.shape[1]
    out = QImage(arr.data, ww, hh, 4 * ww, QImage.Format_RGBA8888).copy()
    out = out.scaled(300, 300, mode=1) if False else out.scaled(
        300, 300)
    out.save(path)
    print(os.path.basename(path), "->", ww, hh)


if __name__ == "__main__":
    for f in sorted(os.listdir(DIR)):
        if f.endswith(".png"):
            process(os.path.join(DIR, f))
