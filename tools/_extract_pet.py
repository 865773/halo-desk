import os

import av
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
SRC = os.path.join(ROOT, ".petrepo", "assets", "characters", "shenshen", "videos")
OUT = os.path.join(ROOT, "assets", "pet", "shenshen")
os.makedirs(OUT, exist_ok=True)

index = {}
for base, _dirs, files in os.walk(SRC):
    for f in files:
        if f.endswith(".webm"):
            index[f] = os.path.join(base, f)

JOBS = {
    "idle": ("待机呼吸休闲.webm", 10),
    "happy": ("点击回应-开心跃动.webm", 6),
    "shy": ("点击回应-害羞惊讶.webm", 4),
    "angry": ("点击回应-傲娇生气.webm", 4),
    "drag": ("被鼠标拖拽悬空反馈.webm", 2),
    "eat": ("偷吃零食被抓住.webm", 4),
}


def extract(key, fname, n):
    path = index.get(fname)
    if not path:
        print("missing", key, repr(fname))
        return
    container = av.open(path)
    stream = container.streams.video[0]
    frames = []
    for frame in container.decode(stream):
        frames.append(frame)
        if len(frames) >= 600:
            break
    container.close()
    if not frames:
        print("no frames", key)
        return
    step = max(1, len(frames) // n)
    count = 0
    for i in range(0, len(frames), step):
        if count >= n:
            break
        img = frames[i].to_ndarray(format="rgba")
        h, w = img.shape[0], img.shape[1]
        qi = QImage(img.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
        qi = qi.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        qi.save(os.path.join(OUT, f"{key}_{count}.png"))
        count += 1
    print(key, "frames", len(frames), "saved", count)


if __name__ == "__main__":
    print("index", len(index))
    for key, (fname, n) in JOBS.items():
        extract(key, fname, n)
