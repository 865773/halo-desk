import math
import os
import struct
import wave

import av

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
ASSETS = os.path.join(ROOT, "assets")
SRC = os.path.join(os.path.expanduser("~"), "Desktop", "叮咚.mp3")


def mp3_to_wav(src, dst):
    if not os.path.exists(src):
        print("no mp3")
        return
    c = av.open(src)
    st = c.streams.audio[0]
    frames = []
    sr = 44100
    ch = 2
    for fr in c.decode(st):
        sr = fr.sample_rate
        ch = len(fr.layout.channels)
        frames.append(fr.to_ndarray())
    c.close()
    import numpy as np
    data = np.concatenate(frames, axis=1) if frames else None
    if data is None:
        return
    with wave.open(dst, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    print("wav", dst)


def make_startup(dst):
    sr = 44100
    dur = 1.1
    n = int(sr * dur)
    frames = bytearray()
    # 柔和的上行三音 chime
    notes = [(523.25, 0.0), (659.25, 0.12), (783.99, 0.24)]
    for i in range(n):
        t = i / sr
        v = 0.0
        for f, start in notes:
            if t < start:
                continue
            tt = t - start
            env = math.exp(-tt * 3.2) * min(1.0, tt * 40)
            v += 0.28 * env * math.sin(2 * math.pi * f * tt)
            v += 0.08 * env * math.sin(2 * math.pi * f * 2 * tt)
        s = max(-1.0, min(1.0, v))
        frames += struct.pack("<h", int(s * 32767))
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    print("startup", dst)


mp3_to_wav(SRC, os.path.join(ASSETS, "dingdong.wav"))
make_startup(os.path.join(ASSETS, "startup.wav"))
