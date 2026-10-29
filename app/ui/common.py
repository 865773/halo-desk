"""通用控件与后台任务。"""
from __future__ import annotations

import traceback
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

from . import theme


class Card(QFrame):
    def __init__(self, parent=None, padding: int = 18, spacing: int = 10):
        super().__init__(parent)
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(padding, padding, padding, padding)
        self.box.setSpacing(spacing)


def title(text: str, sub: str = "") -> QWidget:
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    t = QLabel(text)
    t.setObjectName("pageTitle")
    lay.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("pageSub")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def card_title(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("cardTitle")
    return lb


def muted(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("muted")
    lb.setWordWrap(True)
    return lb


def hint(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("hint")
    lb.setWordWrap(True)
    return lb


def line() -> QFrame:
    f = QFrame()
    f.setObjectName("line")
    f.setFixedHeight(1)
    return f


def button(text: str, primary: bool = False, ghost: bool = False,
           on_click: Optional[Callable] = None, width: int = 0) -> QPushButton:
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    elif ghost:
        b.setObjectName("ghost")
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumHeight(34)
    if width:
        b.setFixedWidth(width)
    if on_click:
        b.clicked.connect(on_click)
    return b


def row(*widgets, spacing: int = 10, stretch_last: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for i, x in enumerate(widgets):
        if isinstance(x, int):
            lay.addStretch(x)
        else:
            lay.addWidget(x)
    return w


class Badge(QLabel):
    def __init__(self, text: str = "", kind: str = "muted", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        colors = {
            "ok": (theme.OK, "#0C2A22"),
            "warn": (theme.WARN, "#2C2411"),
            "err": (theme.ERR, "#2C1517"),
            "muted": (theme.MUTED, "#16213A"),
        }
        fg, bg = colors.get(kind, colors["muted"])
        self.setStyleSheet(
            f"color:{fg};background:{bg};border-radius:9px;padding:2px 10px;"
            f"font-size:11px;")


class Shadow(QGraphicsDropShadowEffect):
    def __init__(self, blur: int = 28, color: str = "#000000", alpha: int = 90):
        super().__init__()
        from PySide6.QtGui import QColor
        self.setBlurRadius(blur)
        self.setOffset(0, 6)
        c = QColor(color)
        c.setAlpha(alpha)
        self.setColor(c)


class Signals(QObject):
    done = Signal(object)
    fail = Signal(str)
    progress = Signal(object)


class Worker(QRunnable):
    def __init__(self, fn: Callable, signals: Signals):
        super().__init__()
        self.fn = fn
        self.signals = signals

    def run(self):
        try:
            result = self.fn(self.signals.progress.emit)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.signals.fail.emit(str(e))
            return
        self.signals.done.emit(result)


_KEEP: list[Signals] = []


def run_bg(fn: Callable, on_done: Optional[Callable] = None,
           on_fail: Optional[Callable] = None,
           on_progress: Optional[Callable] = None) -> None:
    sig = Signals()
    if on_done:
        sig.done.connect(on_done)
    if on_fail:
        sig.fail.connect(on_fail)
    if on_progress:
        sig.progress.connect(on_progress)
    _KEEP.append(sig)
    if len(_KEEP) > 200:
        del _KEEP[:100]
    QThreadPool.globalInstance().start(Worker(fn, sig))


def toast(parent: QWidget, text: str, kind: str = "info", ms: int = 2400) -> None:
    colors = {"info": theme.ACCENT, "ok": theme.OK, "err": theme.ERR,
              "warn": theme.WARN}
    lb = QLabel(text, parent)
    lb.setStyleSheet(
        f"background:{theme.CARD2};color:{colors.get(kind, theme.ACCENT)};"
        f"border:1px solid {colors.get(kind, theme.ACCENT)};border-radius:10px;"
        f"padding:8px 16px;font-weight:600;")
    lb.adjustSize()
    x = max(10, (parent.width() - lb.width()) // 2)
    y = parent.height() - lb.height() - 26
    lb.move(x, y)
    lb.show()
    lb.raise_()
    QTimer.singleShot(ms, lb.deleteLater)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def scroll_page(inner: QWidget) -> QWidget:
    from PySide6.QtWidgets import QScrollArea
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return area
