"""葫芦侠三楼页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QTextBrowser, QVBoxLayout, QWidget)

from . import common, theme
from .base import Page


class HlxPage(Page):
    key = "hlx"

    def __init__(self, app):
        super().__init__(app, "葫芦侠三楼",
                         "官方接口登录，一键签到全部板块。签到结果会写进下方日志。")
        self.account_card = common.Card(padding=20, spacing=12)
        self.body.addWidget(self.account_card)
        self.account_card.box.addWidget(common.card_title("账号"))
        self.account_card.box.addWidget(common.line())
        self.account_box = QVBoxLayout()
        self.account_card.box.addLayout(self.account_box)

        sign = common.Card(padding=20, spacing=12)
        top = QHBoxLayout()
        top.addWidget(common.card_title("一键签到"))
        top.addStretch(1)
        self.auto = QCheckBox("启动时自动签到")
        self.auto.setChecked(bool(app.cfg.get("hlx.auto_signin", True)))
        self.auto.stateChanged.connect(
            lambda s: (app.cfg.set("hlx.auto_signin", bool(s)), app.cfg.save()))
        top.addWidget(self.auto)
        sign.box.addLayout(top)
        sign.box.addWidget(common.hint(
            "按板块列表逐个签到，已签过的会返回提示，不影响结果。间隔 0.35 秒，避免触发风控。"))
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        sign.box.addWidget(self.progress)
        self.status = common.muted("准备就绪")
        sign.box.addWidget(self.status)
        row = QHBoxLayout()
        self.btn = common.button("开始签到", primary=True)
        self.btn.clicked.connect(self.start_signin)
        row.addWidget(self.btn)
        row.addStretch(1)
        self.refresh_btn = common.button("刷新账号信息", ghost=True)
        self.refresh_btn.clicked.connect(self.refresh_info)
        row.addWidget(self.refresh_btn)
        sign.box.addLayout(row)
        self.log = QTextBrowser()
        self.log.setMinimumHeight(200)
        self.log.setStyleSheet("font-size:12px;")
        sign.box.addWidget(self.log)
        self.body.addWidget(sign)
        from .memcard import UserMemoryCard
        self.user_mem = UserMemoryCard(self.app, "hlx", "用户记忆（葫芦侠）")
        self.body.addWidget(self.user_mem)
        self.body.addStretch(1)

        self._build_account()

    # ---------- 账号卡片 ----------
    def _build_account(self) -> None:
        common.clear_layout(self.account_box)
        cfg = self.app.cfg
        logged = bool(cfg.get("hlx.key", ""))
        if logged:
            head = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(3)
            name = QLabel(cfg.get("hlx.nick", "") or "葫芦侠用户")
            name.setStyleSheet("font-size:17px;font-weight:700;")
            sub = QLabel(f"UID {cfg.get('hlx.uid', 0)} · Lv.{cfg.get('hlx.level', 0)} · "
                         f"{cfg.get('hlx.phone', '')}")
            sub.setObjectName("muted")
            col.addWidget(name)
            col.addWidget(sub)
            head.addLayout(col, 1)
            badge = common.Badge("已登录", "ok")
            head.addWidget(badge)
            self.account_box.addLayout(head)
            self.account_box.addWidget(common.line())
            row = QHBoxLayout()
            row.addWidget(QLabel("主人 ID"))
            self.owner = QLineEdit(str(cfg.get("fish.owner_uid_hlx", 0) or cfg.get("fish.owner_uid", 0) or 0))
            self.owner.setFixedWidth(130)
            self.owner.editingFinished.connect(self._save_owner)
            row.addWidget(self.owner)
            auto = common.button("从粉丝自动获取", ghost=True)
            auto.clicked.connect(self._auto_owner)
            row.addWidget(auto)
            row.addStretch(1)
            out = common.button("退出登录", ghost=True)
            out.clicked.connect(self.logout)
            row.addWidget(out)
            self.account_box.addLayout(row)
            return

        self.account_box.addWidget(common.hint(
            "使用葫芦侠账号登录（手机号 + 密码）。密码只保存在本机配置文件里。"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("手机号")
        self.phone.setFixedWidth(200)
        self.pwd = QLineEdit()
        self.pwd.setPlaceholderText("密码")
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.returnPressed.connect(self.login)
        row.addWidget(self.phone)
        row.addWidget(self.pwd)
        self.login_btn = common.button("登录", primary=True)
        self.login_btn.clicked.connect(self.login)
        row.addWidget(self.login_btn)
        row.addStretch(1)
        self.account_box.addLayout(row)

    def _save_owner(self) -> None:
        try:
            uid = int(self.owner.text().strip() or 0)
        except Exception:
            uid = 0
        self.app.cfg.set("fish.owner_uid_hlx", uid)
        self.app.cfg.save()
        common.toast(self.app, f"主人 UID 已设为 {uid}" if uid else "已清空主人 UID", "ok")

    def _auto_owner(self) -> None:
        """从关注我的粉丝里挑一个设为主人（手机版就是这么认的）。"""

        def work(_e):
            return self.app.hlx.followers(30)

        def done(fans):
            if not fans:
                common.toast(self.app, "没有取到粉丝列表", "warn")
                return
            names = []
            ids = []
            for f in fans[:20]:
                u = f.get("user") or {}
                uid = int(u.get("userID", 0) or 0)
                if not uid:
                    continue
                ids.append(uid)
                names.append(f"{u.get('nick') or '无名'} (uid={uid})")
            if not ids:
                common.toast(self.app, "粉丝列表里没有可用账号", "warn")
                return
            from PySide6.QtWidgets import QInputDialog
            pick, ok = QInputDialog.getItem(self, "选择主人", "关注你的粉丝：", names, 0, False)
            if not ok:
                return
            idx = names.index(pick)
            self.app.cfg.set("fish.owner_uid_hlx", ids[idx])
            self.app.cfg.save()
            self._build_account()
            common.toast(self.app, f"主人已设为 {pick}", "ok")

        common.run_bg(work, done, lambda e: common.toast(self.app, f"获取失败：{e}", "err"))

    def login(self) -> None:
        phone = self.phone.text().strip()
        pwd = self.pwd.text()
        if not phone or not pwd:
            common.toast(self.app, "请填写手机号和密码", "warn")
            return
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中…")

        def work(_emit):
            return self.app.hlx.login(phone, pwd)

        common.run_bg(work, self._on_login, self._on_login_fail)

    def _on_login(self, user) -> None:
        common.toast(self.app, f"登录成功，欢迎 {user.get('nick', '')}", "ok")
        self._build_account()
        self.app.notify_accounts()

    def _on_login_fail(self, msg: str) -> None:
        self._build_account()
        common.toast(self.app, f"登录失败：{msg}", "err")

    def logout(self) -> None:
        self.app.hlx.logout()
        self._build_account()
        self.app.notify_accounts()
        common.toast(self.app, "已退出葫芦侠账号", "info")

    def refresh_info(self) -> None:
        if not self.app.cfg.get("hlx.key", ""):
            common.toast(self.app, "请先登录", "warn")
            return

        def work(_emit):
            return self.app.hlx.my_info()

        def done(info):
            if info.get("nick"):
                self.app.cfg.set("hlx.nick", info.get("nick"))
                self.app.cfg.set("hlx.level", int(info.get("level", 0) or 0))
                self.app.cfg.set("hlx.uid", int(info.get("userID", 0) or self.app.cfg.get("hlx.uid", 0)))
                self.app.cfg.save()
                self._build_account()
                common.toast(self.app, "账号信息已刷新", "ok")
            else:
                common.toast(self.app, "没有取到账号信息，可能登录已失效", "warn")

        common.run_bg(work, done, lambda e: common.toast(self.app, f"刷新失败：{e}", "err"))

    # ---------- 签到 ----------
    def start_signin(self) -> None:
        if not self.app.cfg.get("hlx.key", ""):
            common.toast(self.app, "请先登录葫芦侠账号", "warn")
            return
        if self.btn.isEnabled() is False:
            return
        self.btn.setEnabled(False)
        self.btn.setText("签到中…")
        self.progress.setValue(0)
        self.log.clear()
        self.status.setText("正在获取板块列表…")

        def work(emit):
            return self.app.hlx.signin_all(
                lambda i, t, name, ok, msg: emit((i, t, name, ok, msg)))

        common.run_bg(work, self._done, self._fail, self._progress)

    def _progress(self, payload) -> None:
        i, t, name, ok, msg = payload
        self.progress.setValue(int(i * 100 / max(1, t)))
        self.status.setText(f"正在签到 {i}/{t}：「{name}」")
        self.log.append(
            f"<span style='color:{theme.OK if ok else theme.MUTED}'>"
            f"{'✓' if ok else '·'}</span> {name}　{msg or '已签到'}")

    def _done(self, result) -> None:
        ok, fail, logs = result
        self.btn.setEnabled(True)
        self.btn.setText("再签到一次")
        self.progress.setValue(100)
        self.status.setText(f"完成：成功 {ok} 个，失败 {fail} 个")
        self.log.clear()
        self.log.append("<br>".join(logs))
        stats = self.app.cfg
        stats.set("stats.hlx_signin", ok)
        stats.save()
        if ok > 0 or fail == 0:
            from ..signin_state import mark_signed
            mark_signed("hlx")
        self.app.notify_accounts()
        from ..activity import record
        record("signin", f"葫芦侠签到完成：成功 {ok} 个，失败 {fail} 个", "hlx")
        common.toast(self.app, f"葫芦侠签到完成：成功 {ok} 个", "ok")

    def _fail(self, msg: str) -> None:
        self.btn.setEnabled(True)
        self.btn.setText("开始签到")
        self.status.setText("签到失败")
        common.toast(self.app, f"签到失败：{msg}", "err")

    # ---------- 记忆 / 亲密度 ----------
    def _build_stats(self) -> None:
        card = common.Card(padding=20, spacing=10)
        head = QHBoxLayout()
        head.addWidget(common.card_title("记忆与亲密度（葫芦侠）"))
        head.addStretch(1)
        head.addWidget(common.button("刷新", ghost=True, on_click=self.render_stats))
        card.box.addLayout(head)
        self.stats_lb = QLabel("—")
        self.stats_lb.setWordWrap(True)
        self.stats_lb.setTextFormat(Qt.RichText)
        card.box.addWidget(self.stats_lb)
        self.body.addWidget(card)

    def render_stats(self) -> None:
        from ..memory import MEMORY_FILE, read_lines, user_count
        from ..relations import REL, level
        rows = REL.top("hlx", 6)
        lines = []
        for uid, nick, favor in rows:
            color = theme.OK if favor >= 70 else (theme.WARN if favor >= 40 else theme.MUTED)
            lines.append(f"{nick or 'uid=' + str(uid)} "
                         f"<span style='color:{color};font-weight:700'>{favor}</span> "
                         f"<span style='color:{theme.MUTED}'>{level(favor)}</span>")
        self.stats_lb.setText(
            f"用户记忆 {user_count('hlx')} 个 · 通用记忆 "
            f"{len(read_lines(MEMORY_FILE, 999))} 条<br>"
            + ("<br>".join(lines) if lines else "还没有互动记录"))

    def refresh(self) -> None:
        self._build_account()
