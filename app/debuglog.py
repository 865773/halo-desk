"""调试日志：所有网络/AI/自动化动作都记一份，方便排查。"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from .config import LOGS_DIR


class DebugLog(QObject):
    line = Signal(str)

    def __init__(self, path=None, max_lines: int = 3000):
        super().__init__()
        self.path = path or (LOGS_DIR / "debug.log")
        self._buf: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                for ln in self.path.read_text("utf-8", "replace").splitlines()[-500:]:
                    self._buf.append(ln)
        except Exception:
            pass

    def log(self, tag: str, msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%m-%d %H:%M:%S")
        line = f"[{ts}] [{level:<5}] [{tag}] {msg}"
        with self._lock:
            self._buf.append(line)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
        self.line.emit(line)

    def tail(self, n: int = 300) -> list[str]:
        with self._lock:
            return list(self._buf)[-n:]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
            try:
                self.path.write_text("", "utf-8")
            except Exception:
                pass


DBG = DebugLog()
