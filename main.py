"""大肥鱼桌面版 —— 葫芦侠三楼 + 灵芥空间合并客户端。"""
from __future__ import annotations

import os
import sys


def _prepare() -> None:
    # 高 DPI 交给 Qt6 自动处理
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Dudu.HaloDesk.1")
        except Exception:
            pass


def _cleanup_temp() -> None:
    """清掉上次异常退出留下的 _MEI 解压目录（只删 1 小时前的）。"""
    try:
        import glob
        import shutil
        import time
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.getcwd()
        now = time.time()
        for p in glob.glob(os.path.join(base, "_MEI*")):
            try:
                if os.path.isdir(p) and now - os.path.getmtime(p) > 3600:
                    shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass


def main() -> int:
    _prepare()
    _cleanup_temp()
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from app.config import CFG, data_dir
    from app.paths import icon_path
    from app.ui import theme
    from app.ui.main_window import MainWindow

    data_dir()  # 确保目录存在

    app = QApplication(sys.argv)
    app.setApplicationName("大肥鱼桌面版")
    app.setApplicationDisplayName("大肥鱼桌面版")
    app.setOrganizationName("Dudu")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    theme.apply(app)
    app.setFont(QFont("Microsoft YaHei UI", 9))

    ic = icon_path()
    if ic:
        app.setWindowIcon(QIcon(ic))

    # 单实例：避免开两个程序各回一遍消息
    server = None
    if "--selftest" not in sys.argv:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        name = "HaloDeskSingleInstance"
        probe = QLocalSocket()
        probe.connectToServer(name)
        if probe.waitForConnected(250):
            probe.write(b"show")
            probe.waitForBytesWritten(250)
            return 0
        QLocalServer.removeServer(name)
        server = QLocalServer()
        server.listen(name)

    win = MainWindow()
    splash = None
    if "--selftest" not in sys.argv:
        from app.ui.splash import Splash
        splash = Splash()
        splash.finished.connect(win.show)
        splash.finished.connect(win.raise_)
        splash.finished.connect(win.activateWindow)
        splash.start()
    else:
        win.show()
    if server is not None:
        def _another() -> None:
            while server.hasPendingConnections():
                conn = server.nextPendingConnection()
                try:
                    conn.readyRead.connect(lambda: None)
                    conn.disconnectFromServer()
                except Exception:
                    pass
            win.showNormal()
            win.raise_()
            win.activateWindow()

        server.newConnection.connect(_another)
    if CFG.get("general.first_run", True) and "--selftest" not in sys.argv:
        from PySide6.QtCore import QTimer
        from app.ui.wizard import Wizard

        def _wizard() -> None:
            if splash is not None:
                splash.finished.connect(lambda: QTimer.singleShot(
                    400, lambda: Wizard(win).exec()))
            else:
                QTimer.singleShot(600, lambda: Wizard(win).exec())

        _wizard()
    if "--selftest" in sys.argv:
        from PySide6.QtCore import QTimer

        def _selftest() -> None:
            try:
                from app.config import data_dir
                out = data_dir() / "selftest.png"
                win.grab().save(str(out))
                print("SELFTEST OK ->", out)
            except Exception as e:  # noqa: BLE001
                print("SELFTEST FAIL ->", e)
            win._quitting = True   # 跳过关闭弹窗，直接退出
            app.quit()

        QTimer.singleShot(2500, _selftest)
    rc = app.exec()
    # 关闭挂件窗口，避免进程退出时 Qt 清理卡住
    try:
        if win.pet is not None:
            win.pet.bubble.close()
            win.pet.close()
            win.pet = None
    except Exception:
        pass
    try:
        win.tray.hide()
    except Exception:
        pass
    return int(rc) if rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
