"""启动页：入场动画 + 启动音。"""
from __future__ import annotations

import os

from PySide6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation,
                            QRectF, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from ..config import CFG
from ..paths import resource
from . import theme


class Splash(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(560, 340)
        self._frames = []
        for i in range(16):
            pm = QPixmap(resource(f"assets/pet/shenshen/idle_{i}.png"))
            if pm.isNull():
                break
            self._frames.append(pm)
        self._fi = 0
        self._tick = 0
        self._total = 46          # 46 * 45ms ≈ 2.1s
        self._name = CFG.get("fish.name", "大肥鱼") or "大肥鱼"
        self._close_timer = QTimer(self)
        self._close_timer.setInterval(45)
        self._close_timer.timeout.connect(self._step)
        self._sound = None
        self._play_sound()

    def _play_sound(self) -> None:
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            self._sound = QSoundEffect(self)
            self._sound.setSource(QUrl.fromLocalFile(resource("assets/startup.wav")))
            self._sound.setVolume(0.6)
            self._sound.play()
        except Exception:
            self._sound = None

    def start(self) -> None:
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center() - self.rect().center())
        self.setWindowOpacity(0.0)
        self.show()
        self._close_timer.start()

    def _step(self) -> None:
        self._tick += 1
        self._fi = (self._tick // 2) % max(1, len(self._frames))
        op = min(1.0, self._tick / 8.0)
        self.setWindowOpacity(op)
        self.update()
        if self._tick >= self._total:
            self._close_timer.stop()
            self._done()

    def _done(self) -> None:
        if getattr(self, "_finished", False):
            return
        self._finished = True
        self.finished.emit()
        # 主界面会用开场视频交叉淡入；这里保底清理
        QTimer.singleShot(700, self._cleanup)

    def fade_out(self, ms: int = 260) -> None:
        """和开场视频交叉淡出，不再做几何放大。"""
        try:
            self._fade = QPropertyAnimation(self, b"windowOpacity", self)
            self._fade.setDuration(ms)
            self._fade.setStartValue(self.windowOpacity())
            self._fade.setEndValue(0.0)
            self._fade.setEasingCurve(QEasingCurve.InOutQuad)
            self._fade.finished.connect(self._cleanup)
            self._fade.start()
        except Exception:
            self._cleanup()

    def _cleanup(self) -> None:
        try:
            self.hide()
            self.deleteLater()
        except Exception:
            pass

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        base_w, base_h = 560.0, 340.0
        s = min(self.width() / base_w, self.height() / base_h)
        p.translate((self.width() - base_w * s) / 2,
                    (self.height() - base_h * s) / 2)
        p.scale(s, s)
        rect = QRectF(0, 0, base_w, base_h).adjusted(1, 1, -1, -1)
        g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if theme.is_dark():
            g.setColorAt(0, QColor("#0B1220"))
            g.setColorAt(1, QColor("#14263F"))
            text = "#E6EDF7"
            sub = "#8FA3BF"
        else:
            g.setColorAt(0, QColor("#FFFFFF"))
            g.setColorAt(1, QColor("#EAF1FF"))
            text = "#1F2937"
            sub = "#6B7280"
        p.setBrush(g)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 22, 22)

        # 角色帧
        if self._frames:
            pm = self._frames[self._fi]
            side = 190
            pm = pm.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (base_w - pm.width()) / 2
            p.drawPixmap(QPointF(x, 26), pm)

        # 名字
        f = QFont("Microsoft YaHei UI", 22, QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(text))
        p.drawText(QRectF(0, 210, base_w, 36), Qt.AlignCenter, self._name)

        # 副标题
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.setPen(QColor(sub))
        p.drawText(QRectF(0, 246, base_w, 22), Qt.AlignCenter,
                   "HALO DESK · 葫芦侠三楼 × 灵芥空间")

        # 进度条
        ratio = min(1.0, self._tick / float(self._total))
        bar_w = 240
        bx = (base_w - bar_w) / 2
        by = 288
        p.setBrush(QColor(theme.LINE))
        p.drawRoundedRect(QRectF(bx, by, bar_w, 4), 2, 2)
        p.setBrush(QColor(theme.ACCENT))
        p.drawRoundedRect(QRectF(bx, by, bar_w * ratio, 4), 2, 2)
