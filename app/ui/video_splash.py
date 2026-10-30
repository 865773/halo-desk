"""项目开场视频（dsh-video-skin 的 boot.mp4），可点击跳过。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from ..paths import resource
from . import theme


class VideoSplash(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet("background:#000;")
        self._done = False

        self.video = QVideoWidget(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.75)
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video)
        self.player.setAudioOutput(self.audio)
        self.player.setSource(QUrl.fromLocalFile(resource("assets/boot.mp4")))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.video, 1)

        self.hint = QLabel("点击画面 / 按 Esc 跳过", self)
        self.hint.setStyleSheet(
            "color:#FFFFFF;background:rgba(0,0,0,0.45);"
            "border-radius:12px;padding:6px 12px;font-size:12px;")
        self.hint.adjustSize()
        self.hint.move(20, 20)
        self.hint.raise_()

        self.bar = QProgressBar(self)
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet(
            f"QProgressBar{{background:rgba(255,255,255,0.18);border:none;}}"
            f"QProgressBar::chunk{{background:{theme.ACCENT};}}")
        self.bar.raise_()

        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(lambda *_: self._finish())
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._progress)
        self.player.durationChanged.connect(
            lambda _d: self.bar.setValue(0))

    def start(self) -> None:
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            w = int(g.width() * 0.82)
            h = int(w * 9 / 16)
            if h > int(g.height() * 0.82):
                h = int(g.height() * 0.82)
                w = int(h * 16 / 9)
            self.resize(w, h)
            self.move(g.center() - self.rect().center())
        self.show()
        self.raise_()
        self.player.play()
        self._timer.start()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self.bar.setGeometry(0, self.height() - 4, self.width(), 4)
        self.hint.adjustSize()
        self.hint.move(20, 20)

    def _progress(self) -> None:
        dur = self.player.duration() or 0
        if dur > 0:
            self.bar.setValue(int(self.player.position() * 1000 / dur))

    def _status(self, status) -> None:
        if status in (QMediaPlayer.EndOfMedia, QMediaPlayer.InvalidMedia):
            self._finish()

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        try:
            self._timer.stop()
            self.player.stop()
        except Exception:
            pass
        self.hide()
        self.finished.emit()
        self.close()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self._finish()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() in (Qt.Key_Escape, Qt.Key_Space, Qt.Key_Return):
            self._finish()
        else:
            super().keyPressEvent(e)
