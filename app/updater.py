"""检查更新 / 公告：版本信息由 Gitee 上的 version.txt 控制。"""
from __future__ import annotations

import hashlib
import re
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QVBoxLayout

from .ui import theme
from .telemetry import HALO_REPO, read_repo_text
from .version import VERSION, is_newer

_busy = False
_bridge = None


class _Bridge(QObject):
    done = Signal(dict, bool)
    failed = Signal(str, bool)


def _parse(text: str) -> dict:
    data = {"version": "", "update_force": "0", "announcement": "",
            "announcement_force": "0", "download_url": "", "notes": ""}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def check(parent, manual: bool = False) -> None:
    global _busy, _bridge
    if _busy:
        return
    _busy = True
    _bridge = _Bridge(parent)
    _bridge.done.connect(lambda data, m: _on_done(parent, data, m))
    _bridge.failed.connect(lambda msg, m: _on_failed(parent, msg, m))

    def _work() -> None:
        try:
            text = read_repo_text("version.txt", HALO_REPO)
            if not text.strip():
                _bridge.failed.emit("检查更新失败", manual)
            else:
                _bridge.done.emit(_parse(text), manual)
        except Exception as e:
            _bridge.failed.emit(str(e), manual)

    threading.Thread(target=_work, daemon=True).start()


def _reset() -> None:
    global _busy
    _busy = False


def _on_failed(parent, msg: str, manual: bool) -> None:
    _reset()
    if manual and parent is not None:
        try:
            from .ui import common
            common.toast(parent, f"检查更新失败：{msg}", "warn")
        except Exception:
            pass


def _on_done(parent, data: dict, manual: bool) -> None:
    _reset()
    if parent is None:
        return
    remote = str(data.get("version", "") or "").strip()
    ann = str(data.get("announcement", "") or "").strip()
    if ann in ("0", "none", "无"):
        ann = ""
    if remote and is_newer(remote):
        _show_update(parent, remote, data)
        return
    if ann:
        h = hashlib.sha1(ann.encode("utf-8")).hexdigest()
        if h != str(CFG_get("general.seen_announcement", "")):
            _show_announcement(parent, ann, _truthy(data.get("announcement_force")))
            _set_seen(h)
            return
    if manual:
        try:
            from .ui import common
            common.toast(parent, f"已是最新版本 v{VERSION}", "ok")
        except Exception:
            pass


def CFG_get(key: str, default=None):
    from .config import CFG
    return CFG.get(key, default)


def _set_seen(h: str) -> None:
    from .config import CFG
    CFG.set("general.seen_announcement", h)
    CFG.save()


def _dialog_style(dlg: QDialog) -> None:
    bg = "#0F1A2E" if theme.WALL else theme.BG2
    fg = theme.TEXT
    dlg.setStyleSheet(
        f"QDialog{{background:{bg};}} QLabel{{color:{fg};}}"
        f"QCheckBox{{color:{fg};}}")


def _show_update(parent, remote: str, data: dict) -> None:
    from .ui import common
    url = str(data.get("download_url", "") or "").strip() \
        or "https://gitee.com/guo-wenlong/halo-desk"
    force = _truthy(data.get("update_force"))
    notes = str(data.get("notes", "") or "").strip()
    dlg = QDialog(parent)
    dlg.setWindowTitle("发现新版本")
    dlg.setMinimumWidth(460)
    _dialog_style(dlg)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 22, 24, 18)
    lay.setSpacing(12)
    title = QLabel(f"发现新版本 v{remote}")
    title.setStyleSheet(f"font-size:18px;font-weight:700;color:{theme.TEXT};")
    lay.addWidget(title)
    body = QLabel(f"当前版本 v{VERSION}\n\n" +
                  (notes or "有新的功能和修复，建议更新到最新版。"))
    body.setWordWrap(True)
    lay.addWidget(body)
    if force:
        tip = QLabel("这是强制更新，更新完成前无法继续使用。")
        tip.setStyleSheet(f"color:{theme.WARN};")
        lay.addWidget(tip)
    row = QHBoxLayout()
    row.addStretch(1)

    def _go() -> None:
        QDesktopServices.openUrl(QUrl(url))
        dlg.accept()
        if force:
            QApplication.quit()

        row.addWidget(common.button("去下载", primary=True, on_click=_go))
    if force:
        row.addWidget(common.button("退出程序", ghost=True,
                                    on_click=lambda: QApplication.quit()))
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowCloseButtonHint)
    else:
        row.addWidget(common.button("以后再说", ghost=True,
                                    on_click=dlg.accept))
    lay.addLayout(row)
    if force:
        dlg.closeEvent = lambda e: e.ignore()
        dlg.reject = lambda: None
    dlg.exec()


def _show_announcement(parent, text: str, force: bool) -> None:
    from .ui import common
    dlg = QDialog(parent)
    dlg.setWindowTitle("公告")
    dlg.setMinimumWidth(440)
    _dialog_style(dlg)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 22, 24, 18)
    lay.setSpacing(12)
    title = QLabel("公告")
    title.setStyleSheet(f"font-size:17px;font-weight:700;color:{theme.TEXT};")
    lay.addWidget(title)
    body = QLabel(text)
    body.setWordWrap(True)
    lay.addWidget(body)
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(common.button("知道了", primary=True, on_click=dlg.accept))
    lay.addLayout(row)
    if force:
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowCloseButtonHint)
        dlg.closeEvent = lambda e: e.ignore()
        dlg.reject = lambda: None
    dlg.exec()
