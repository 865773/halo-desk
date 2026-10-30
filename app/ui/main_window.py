"""主窗口：侧边导航 + 页面栈 + 托盘 + 挂件管理。"""
from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QPushButton, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from ..automation import AutoPilot
from .. import memory
from ..config import CFG
from ..hlx import HlxClient
from ..lingjie import LingjieClient
from ..paths import icon_path
from . import common, theme
from .activity_page import ActivityPage
from .auto_page import AutoPage
from .debug_page import DebugPage
from .fish_page import FishPage
from .hlx_page import HlxPage
from .home import HomePage
from .lingjie_page import LingjiePage
from .pet import PetWindow
from .settings_page import SettingsPage
from .memory_page import MemoryPage

NAVS = [
    ("home", "⌂  总览"),
    ("hlx", "▣  葫芦侠三楼"),
    ("lingjie", "◈  灵芥空间"),
    ("fish", "✿  大肥鱼"),
    ("memory", "❏  记忆"),
    ("activity", "≡  动态"),
    ("auto", "⚙  自动任务"),
    ("debug", "⌘  调试"),
    ("settings", "☰  设置"),
]


class MainWindow(QMainWindow):
    accounts_changed = Signal()

    def _migrate_owner(self) -> None:
        """旧版只有一个 owner_uid，这里复制到两个平台各自的主人（只补空的）。"""
        legacy = int(CFG.get("fish.owner_uid", 0) or 0)
        if legacy <= 0:
            return
        for key in ("fish.owner_uid_hlx", "fish.owner_uid_lingjie"):
            if not int(CFG.get(key, 0) or 0):
                CFG.set(key, legacy)
        CFG.save()

    def _warm_names(self) -> None:
        """后台把用户记忆里只有 uid 的补上昵称。"""

        def work(_emit):
            from .. import names
            return names.backfill("hlx", self.hlx) + names.backfill("lingjie", self.lj)

        def done(n):
            if n:
                from ..debuglog import DBG
                DBG.log("NAME", f"补了 {n} 个昵称")
                try:
                    self.pages["hlx"].user_mem.reload()
                    self.pages["lingjie"].user_mem.reload()
                except Exception:
                    pass

        from .common import run_bg
        run_bg(work, done, lambda e: None)

    def _warm_emoji(self) -> None:
        """后台拉一次灵芥表情表（7 天缓存），失败就用内置兜底。"""
        if not CFG.get("lingjie.token", ""):
            return

        def work(_emit):
            from ..emoji import refresh_lingjie
            return refresh_lingjie(self.lj)

        def done(n):
            if n:
                from ..debuglog import DBG
                DBG.log("EMOJI", f"灵芥表情表已更新：{n} 个")

        from .common import run_bg
        run_bg(work, done, lambda e: None)

    def __init__(self):
        super().__init__()
        self.cfg = CFG
        self._migrate_owner()
        self.hlx = HlxClient(CFG)
        self.lj = LingjieClient(CFG)
        self.autopilot = AutoPilot(self)
        self.pet: PetWindow | None = None
        self._quitting = False
        QTimer.singleShot(4000, self._warm_emoji)
        QTimer.singleShot(6000, self._warm_names)

        self.setWindowTitle("大肥鱼桌面版 · 葫芦侠 + 灵芥")
        self.resize(1120, 760)
        self.setMinimumSize(940, 640)
        ic = icon_path()
        if ic:
            self.setWindowIcon(QIcon(ic))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)

        self.pages = {
            "home": HomePage(self),
            "hlx": HlxPage(self),
            "lingjie": LingjiePage(self),
            "fish": FishPage(self),
            "memory": MemoryPage(self),
            "activity": ActivityPage(self),
            "auto": AutoPage(self),
            "debug": DebugPage(self),
            "settings": SettingsPage(self),
        }
        for key, _ in NAVS:
            self.stack.addWidget(self.pages[key])
        self.stack.currentChanged.connect(self._on_page_changed)

        self._build_tray()
        self.autopilot.replied.connect(self._on_pet_reply)
        self.autopilot.incoming.connect(self._on_pet_incoming)
        self.autopilot.auth_failed.connect(self._on_auth_failed)
        self.show_page(CFG.get("general.page", "home") or "home")
        self._refresh_sidebar_status()
        QTimer.singleShot(1200, self._auto_signin)
        QTimer.singleShot(1800, self._refresh_profiles)
        QTimer.singleShot(2600, self._validate_logins)
        # 每次打开更新一次生活记忆；之后由自动任务慢循环每小时检查
        QTimer.singleShot(9000, lambda: self.autopilot._life_tick(force=True))
        self._login_timer = QTimer(self)
        self._login_timer.setInterval(30000)
        self._login_timer.timeout.connect(lambda: self._check_logins(quiet=True))
        self._login_timer.start()
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(20000)
        self._ui_timer.timeout.connect(self._light_refresh)
        self._ui_timer.start()

    def _light_refresh(self) -> None:
        """轻量刷新当前页（只读本地数据，不请求网络）。"""
        cur = self.stack.currentWidget()
        if cur is self.pages.get("home"):
            cur.refresh()

    def _on_pet_incoming(self, platform: str, nick: str, text: str) -> None:
        if self.pet is None or not self.pet.isVisible():
            return
        if not CFG.get("auto.pet_notify", True):
            return
        where = "葫芦侠" if platform == "hlx" else "灵芥"
        face = "happy"
        low = ("凶", "骂", "讨厌", "滚", "烦")
        praise = ("可爱", "喜欢", "夸", "棒", "好看")
        if any(k in text for k in low):
            face = "angry"
        elif any(k in text for k in praise):
            face = "shy"
        elif memory.get_mood(platform) <= 35:
            face = "angry"
        self.pet.set_face(face, 5000)
        self.pet.say(f"{where}·{nick}：{text}", 8000)

    def _on_auth_failed(self, platform: str) -> None:
        """监听/回复时接口返回未登录：立刻清掉该平台并刷新界面。"""
        if platform == "hlx":
            if not CFG.get("hlx.key", ""):
                return
            for k in ("hlx.key", "hlx.uid", "hlx.nick", "hlx.level"):
                CFG.set(k, "" if k.endswith("key") or k.endswith("nick") else 0)
            name = "葫芦侠"
        else:
            if not CFG.get("lingjie.token", ""):
                return
            for k in ("lingjie.token", "lingjie.uid", "lingjie.nickname",
                      "lingjie.level", "lingjie.exp", "lingjie.next_exp"):
                CFG.set(k, "" if k in ("lingjie.token", "lingjie.nickname") else 0)
            name = "灵芥"
        if not (CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
            CFG.set("fish.enabled", False)
            CFG.set("auto.enabled", False)
            try:
                self.autopilot.stop()
            except Exception:
                pass
        CFG.save()
        self.notify_accounts()
        try:
            self.tray.showMessage("登录已失效",
                                  f"{name} 登录已失效，请重新登录（记忆会保留）。",
                                  QSystemTrayIcon.Warning, 5000)
        except Exception:
            pass
        DBG.log("LOGIN", f"{name} 登录失效，已自动退出", "WARN")

    def _on_pet_reply(self, platform: str, nick: str, text: str) -> None:
        if self.pet is None or not self.pet.isVisible():
            return
        if not CFG.get("auto.pet_notify", True):
            return
        where = "葫芦侠" if platform == "hlx" else "灵芥"
        self.pet.set_face("happy", 5000)
        self.pet.say(f"我回了 {nick}：{text}", 6000)

    # ---------- UI ----------
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(212)
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 22, 16, 16)
        v.setSpacing(6)

        logo = QLabel("🐟 大肥鱼")
        logo.setObjectName("logo")
        sub = QLabel("HALO DESKTOP")
        sub.setObjectName("logoSub")
        v.addWidget(logo)
        v.addWidget(sub)
        v.addSpacing(18)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, label in NAVS:
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.group.addButton(b)
            v.addWidget(b)
            setattr(self, f"nav_{key}", b)
        v.addStretch(1)

        self.side_status = QLabel("未登录")
        self.side_status.setObjectName("hint")
        self.side_status.setWordWrap(True)
        v.addWidget(self.side_status)
        ver = QLabel("v8.5 · 桌面合并版")
        ver.setObjectName("hint")
        v.addWidget(ver)
        return side

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(icon_path()), self)
        self.tray.setToolTip("大肥鱼桌面版")
        menu = QMenu()
        a_show = QAction("显示主界面", menu)
        a_show.triggered.connect(self.show_main)
        a_pet = QAction("打开大肥鱼挂件", menu)
        a_pet.triggered.connect(lambda: self.open_pet(True))
        a_sign = QAction("两个平台签到", menu)
        a_sign.triggered.connect(self.signin_all)
        a_quit = QAction("退出", menu)
        a_quit.triggered.connect(self.quit)
        menu.addAction(a_show)
        menu.addAction(a_pet)
        menu.addSeparator()
        menu.addAction(a_sign)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()

    # ---------- 页面 ----------
    def page(self, key: str):
        return self.pages.get(key)

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            key = "home"
        self.stack.setCurrentWidget(self.pages[key])
        btn = getattr(self, f"nav_{key}", None)
        if btn:
            btn.setChecked(True)
        CFG.set("general.page", key)
        CFG.save()
        self.pages[key].refresh()

    def _on_page_changed(self, _idx: int) -> None:
        w = self.stack.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()

    def notify_accounts(self) -> None:
        self.accounts_changed.emit()
        try:
            from .. import memory
            memory.ensure_account("hlx")
            memory.ensure_account("lingjie")
            from ..relations import REL
            REL.rekey("hlx")
            REL.rekey("lingjie")
            from .. import names
            names.ensure("hlx")
            names.ensure("lingjie")
        except Exception:
            pass
        self._refresh_sidebar_status()
        self.pages["home"].refresh()
        try:
            from ..activity import ACT
            ACT.reload()
        except Exception:
            pass
        for key in ("hlx", "lingjie"):
            pg = self.pages.get(key)
            if pg is not None and getattr(pg, "user_mem", None) is not None:
                pg.user_mem.reload()
        cur = self.stack.currentWidget()
        if hasattr(cur, "refresh") and cur is not self.pages["home"]:
            cur.refresh()

    def _refresh_sidebar_status(self) -> None:
        hlx = "葫芦侠 已登录" if CFG.get("hlx.key", "") else "葫芦侠 未登录"
        lj = "灵芥 已登录" if CFG.get("lingjie.token", "") else "灵芥 未登录"
        self.side_status.setText(f"{hlx}\n{lj}")

    # ---------- 挂件 ----------
    def open_pet(self, on: bool | None = None) -> None:
        if on is None:
            on = not (self.pet is not None and self.pet.isVisible())
        CFG.set("fish.pet_on", bool(on))
        CFG.save()
        fp = self.pages.get("fish")
        if fp is not None and hasattr(fp, "pet_on"):
            fp.pet_on.blockSignals(True)
            fp.pet_on.setChecked(bool(on))
            fp.pet_on.blockSignals(False)

        if on:
            if self.pet is None:
                self.pet = PetWindow(self)
                self.pet.open_main.connect(self.show_main)
            self.pet.apply_settings()
            self.pet.show_near_default()
        elif self.pet is not None:
            self.pet.hide()

    def close_pet(self) -> None:
        try:
            if self.pet is not None:
                self.pet.bubble.close()
                self.pet.close()
                self.pet = None
        except Exception:
            self.pet = None
        CFG.set("fish.pet_on", False)
        CFG.save()
        fp = self.pages.get("fish")
        if fp is not None and hasattr(fp, "pet_on"):
            fp.pet_on.blockSignals(True)
            fp.pet_on.setChecked(False)
            fp.pet_on.blockSignals(False)

    def pet_resize(self) -> None:
        if self.pet is not None:
            self.pet.apply_settings()
            self.pet.show()

    # ---------- 动作 ----------
    def signin_all(self) -> None:
        did = False
        if CFG.get("hlx.key", ""):
            self.show_page("hlx")
            self.pages["hlx"].start_signin()
            did = True
        if CFG.get("lingjie.token", ""):
            self.pages["lingjie"].start_signin()
            did = True
        if not did:
            common.toast(self, "两个平台都还没登录", "warn")

    def _auto_signin(self) -> None:
        from ..signin_state import signed_today
        self._refresh_sidebar_status()
        enabled = self.cfg.get("fish.enabled", False)
        if self.cfg.get("fish.pet_on", True):
            self.open_pet(True)
        # 每次打开自动检测：今天没签到就补签
        if enabled and self.cfg.get("hlx.key", "") and self.cfg.get("hlx.auto_signin", True):
            if signed_today("hlx"):
                self.pages["hlx"].status.setText("今天已经签到过了，跳过")
            else:
                self.pages["hlx"].start_signin()
        if enabled and self.cfg.get("lingjie.token", "") \
                and self.cfg.get("lingjie.auto_signin", True):
            if signed_today("lingjie"):
                self.pages["lingjie"].status.setText("今天已经签到过了，跳过")
            else:
                self.pages["lingjie"].start_signin()
        if enabled:
            self.autopilot.start()

    def _refresh_profiles(self) -> None:
        """后台刷新昵称/头像/等级，供总览显示。"""
        if not (CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
            return

        def work(_e):
            out = {}
            try:
                if CFG.get("hlx.key", ""):
                    out["hlx"] = self.hlx.my_info()
            except Exception:
                pass
            try:
                if CFG.get("lingjie.token", ""):
                    out["lj"] = self.lj.me()
            except Exception:
                pass
            return out

        def done(data):
            from .. import net
            from .home import _avatar_file
            h = data.get("hlx") or {}
            if h:
                CFG.set("hlx.nick", h.get("nick", ""))
                CFG.set("hlx.uid", int(h.get("userID", 0) or CFG.get("hlx.uid", 0)))
                CFG.set("hlx.level", int(h.get("level", 0) or 0))
                u = h.get("avatar") or ""
                if u:
                    try:
                        _avatar_file("hlx").write_bytes(net.http_bytes(u, 20))
                    except Exception:
                        pass
            l = data.get("lj") or {}
            if l:
                CFG.set("lingjie.nickname", l.get("nickname", ""))
                CFG.set("lingjie.uid", int(l.get("uid", 0) or CFG.get("lingjie.uid", 0)))
                CFG.set("lingjie.level", int(l.get("currentLv", 0) or 0))
                CFG.set("lingjie.exp", int(l.get("exp", 0) or 0))
                CFG.set("lingjie.next_exp", int(l.get("nextExp", 0) or 0))
                u = l.get("avatar") or ""
                if u:
                    try:
                        _avatar_file("lingjie").write_bytes(net.http_bytes(u, 20))
                    except Exception:
                        pass
            CFG.save()
            self.pages["home"].refresh()

        from .common import run_bg
        run_bg(work, done, lambda _e: None)

    def _validate_logins(self) -> None:
        """检测登录态：失效就清掉该平台登录并提示重新登录。"""
        self._check_logins(quiet=False)

    def _check_logins(self, quiet: bool = True) -> None:
        if getattr(self, "_login_checking", False):
            return
        if not (CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
            return
        self._login_checking = True

        def work(_e):
            out = {}
            try:
                if CFG.get("hlx.key", ""):
                    out["hlx"] = bool(self.hlx.probe_login())
            except Exception:
                out["hlx"] = True
            try:
                if CFG.get("lingjie.token", ""):
                    out["lj"] = bool(self.lj.probe_login())
            except Exception:
                out["lj"] = True
            return out

        def done(res):
            self._login_checking = False
            bad = []
            if res.get("hlx") is False:
                for k in ("hlx.key", "hlx.uid", "hlx.nick", "hlx.level"):
                    CFG.set(k, "" if k.endswith("key") or k.endswith("nick") else 0)
                bad.append("葫芦侠")
            if res.get("lj") is False:
                for k in ("lingjie.token", "lingjie.uid", "lingjie.nickname",
                          "lingjie.level", "lingjie.exp", "lingjie.next_exp"):
                    CFG.set(k, "" if k in ("lingjie.token", "lingjie.nickname") else 0)
                bad.append("灵芥")
            if bad:
                if not (CFG.get("hlx.key", "") or CFG.get("lingjie.token", "")):
                    CFG.set("fish.enabled", False)
                    CFG.set("auto.enabled", False)
                    try:
                        self.autopilot.stop()
                    except Exception:
                        pass
                CFG.save()
                self.notify_accounts()
                msg = ("、".join(bad) + " 的登录已失效，请重新登录。\n"
                       "该账号的记忆仍然保留，登录后会恢复。")
                DBG.log("LOGIN", "登录失效：" + "、".join(bad), "WARN")
                if quiet:
                    try:
                        self.tray.showMessage("登录已失效", msg,
                                              QSystemTrayIcon.Warning, 5000)
                    except Exception:
                        pass
                else:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "登录已失效", msg)

        def fail(_e):
            self._login_checking = False

        from .common import run_bg
        run_bg(work, done, fail)

    def show_wizard(self) -> None:
        from .wizard import Wizard
        Wizard(self).exec()

    def _tray_clicked(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.show_main()

    def show_main(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self) -> None:
        self._quitting = True
        try:
            self.autopilot.stop()
        except Exception:
            pass
        try:
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().clear()
        except Exception:
            pass
        if self.pet is not None:
            self.pet.bubble.close()
            self.pet.close()
            self.pet = None
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e) -> None:  # noqa: N802
        if self._quitting:
            e.accept()
            return
        e.ignore()
        saved = (CFG.get("general.close_action", "") or "").strip()
        if saved == "minimize":
            self.hide()
            return
        if saved == "quit":
            self.quit()
            return
        from PySide6.QtWidgets import QCheckBox, QMessageBox
        box = QMessageBox(self)
        box.setWindowTitle("关闭大肥鱼")
        box.setText("要最小化到托盘继续后台运行，还是直接退出？")
        remember = QCheckBox("记住我的选择")
        box.setCheckBox(remember)
        b_min = box.addButton("最小化到托盘", QMessageBox.AcceptRole)
        b_quit = box.addButton("退出程序", QMessageBox.DestructiveRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.exec()
        action = ""
        if box.clickedButton() is b_min:
            action = "minimize"
        elif box.clickedButton() is b_quit:
            action = "quit"
        if remember.isChecked() and action:
            CFG.set("general.close_action", action)
            CFG.save()
        if action == "minimize":
            self.hide()
            self.tray.showMessage("大肥鱼还在后台运行",
                                  "点托盘图标可以再打开，右键菜单可以退出。",
                                  QSystemTrayIcon.Information, 2000)
        elif action == "quit":
            self.quit()

    def changeEvent(self, e) -> None:  # noqa: N802
        # 最小化时收进托盘，继续后台运行
        if e.type() == e.Type.WindowStateChange and self.isMinimized():
            e.ignore()
            self.hide()
            try:
                self.tray.showMessage("大肥鱼在后台运行", "点托盘图标恢复窗口。",
                                      QSystemTrayIcon.Information, 1500)
            except Exception:
                pass
        super().changeEvent(e)
