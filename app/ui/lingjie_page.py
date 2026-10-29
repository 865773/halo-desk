"""灵芥空间页。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QLineEdit, QProgressBar, QTextBrowser, QVBoxLayout)

from . import common, theme
from .base import Page


class LingjiePage(Page):
    key = "lingjie"

    def __init__(self, app):
        super().__init__(app, "灵芥空间",
                         "支持密码登录、验证码登录，也可以直接粘贴 access token。签到覆盖全部板块。")
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
        self.auto.setChecked(bool(app.cfg.get("lingjie.auto_signin", True)))
        self.auto.stateChanged.connect(
            lambda s: (app.cfg.set("lingjie.auto_signin", bool(s)), app.cfg.save()))
        top.addWidget(self.auto)
        sign.box.addLayout(top)
        sign.box.addWidget(common.hint(
            "会自动跳过今天已签到的板块，只补签没签的。"))
        self.progress = QProgressBar()
        sign.box.addWidget(self.progress)
        self.status = common.muted("准备就绪")
        sign.box.addWidget(self.status)
        row = QHBoxLayout()
        self.btn = common.button("开始签到", primary=True)
        self.btn.clicked.connect(self.start_signin)
        row.addWidget(self.btn)
        row.addStretch(1)
        self.info_btn = common.button("查看签到状态", ghost=True)
        self.info_btn.clicked.connect(self.load_status)
        row.addWidget(self.info_btn)
        sign.box.addLayout(row)
        self.log = QTextBrowser()
        self.log.setMinimumHeight(200)
        self.log.setStyleSheet("font-size:12px;")
        sign.box.addWidget(self.log)
        self.body.addWidget(sign)
        from .memcard import UserMemoryCard
        self.user_mem = UserMemoryCard(self.app, "lingjie", "用户记忆（灵芥）")
        self.body.addWidget(self.user_mem)
        self.body.addStretch(1)

        self._countdown = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build_account()

    # ---------- 账号 ----------
    def _build_account(self) -> None:
        common.clear_layout(self.account_box)
        cfg = self.app.cfg
        if cfg.get("lingjie.token", ""):
            head = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(3)
            name = QLabel(cfg.get("lingjie.nickname", "") or "灵芥用户")
            name.setStyleSheet("font-size:17px;font-weight:700;")
            sub = QLabel(f"UID {cfg.get('lingjie.uid', 0)} · {cfg.get('lingjie.phone', '')}")
            sub.setObjectName("muted")
            col.addWidget(name)
            col.addWidget(sub)
            head.addLayout(col, 1)
            head.addWidget(common.Badge("已登录", "ok"))
            self.account_box.addLayout(head)
            self.account_box.addWidget(common.line())
            row = QHBoxLayout()
            row.addWidget(QLabel("主人 ID"))
            self.owner = QLineEdit(str(cfg.get("fish.owner_uid_lingjie", 0) or cfg.get("fish.owner_uid", 0) or 0))
            self.owner.setFixedWidth(130)
            self.owner.editingFinished.connect(self._save_owner)
            row.addWidget(self.owner)
            row.addWidget(common.hint("灵芥没有粉丝接口，手动填对方 UID"))
            row.addStretch(1)
            out = common.button("退出登录", ghost=True)
            out.clicked.connect(self.logout)
            row.addWidget(out)
            self.account_box.addLayout(row)
            return

        self.account_box.addWidget(common.hint(
            "默认走明文 HTTP 接口（api.lingjie888.cn），和手机端一致。"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.mode = QComboBox()
        self.mode.addItems(["密码登录", "验证码登录", "粘贴 Token"])
        self.mode.setFixedWidth(120)
        self.mode.currentIndexChanged.connect(self._on_mode)
        row.addWidget(self.mode)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("手机号")
        self.phone.setFixedWidth(190)
        row.addWidget(self.phone)
        self.cred = QLineEdit()
        self.cred.setPlaceholderText("密码")
        self.cred.setEchoMode(QLineEdit.Password)
        self.cred.returnPressed.connect(self.login)
        row.addWidget(self.cred, 1)
        self.code_btn = common.button("发送验证码")
        self.code_btn.clicked.connect(self.send_code)
        self.code_btn.hide()
        row.addWidget(self.code_btn)
        self.login_btn = common.button("登录", primary=True)
        self.login_btn.clicked.connect(self.login)
        row.addWidget(self.login_btn)
        row.addStretch(1)
        self.account_box.addLayout(row)

    def _on_mode(self, idx: int) -> None:
        self.code_btn.setVisible(idx == 1)
        if idx == 0:
            self.cred.setPlaceholderText("密码")
            self.cred.setEchoMode(QLineEdit.Password)
            self.phone.show()
        elif idx == 1:
            self.cred.setPlaceholderText("验证码")
            self.cred.setEchoMode(QLineEdit.Normal)
            self.phone.show()
        else:
            self.cred.setPlaceholderText("粘贴 access token")
            self.cred.setEchoMode(QLineEdit.Normal)
            self.phone.hide()
        self.cred.clear()

    def send_code(self) -> None:
        phone = self.phone.text().strip()
        if len(phone) != 11:
            common.toast(self.app, "请填写 11 位手机号", "warn")
            return
        self.code_btn.setEnabled(False)
        self._countdown = 60
        self._timer.start(1000)

        def done(res):
            ok, msg = res
            common.toast(self.app, msg or ("验证码已发送" if ok else "发送失败"),
                         "ok" if ok else "err")

        common.run_bg(lambda _e: self.app.lj.send_code(phone), done,
                      lambda e: common.toast(self.app, f"发送失败：{e}", "err"))

    def _tick(self) -> None:
        self._countdown -= 1
        if self._countdown <= 0:
            self._timer.stop()
            self.code_btn.setEnabled(True)
            self.code_btn.setText("发送验证码")
            return
        self.code_btn.setText(f"{self._countdown}s")

    def login(self) -> None:
        idx = self.mode.currentIndex()
        cred = self.cred.text()
        if not cred:
            common.toast(self.app, "请填写密码 / 验证码 / Token", "warn")
            return
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中…")

        def work(_emit):
            if idx == 0:
                return self.app.lj.login_password(self.phone.text().strip(), cred)
            if idx == 1:
                return self.app.lj.login_sms(self.phone.text().strip(), cred)
            return self.app.lj.login_by_token(cred)

        common.run_bg(work, self._on_login, self._on_login_fail)

    def _on_login(self, info) -> None:
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登录")
        nick = self.app.cfg.get("lingjie.nickname", "") or (info or {}).get("nickname", "")
        common.toast(self.app, f"登录成功，欢迎 {nick}", "ok")
        self._build_account()
        self.app.notify_accounts()
        self.load_status()

    def _on_login_fail(self, msg: str) -> None:
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登录")
        common.toast(self.app, f"登录失败：{msg}", "err")

    def logout(self) -> None:
        self.app.lj.logout()
        self._build_account()
        self.app.notify_accounts()
        common.toast(self.app, "已退出灵芥账号", "info")

    # ---------- 签到 ----------
    def load_status(self) -> None:
        if not self.app.cfg.get("lingjie.token", ""):
            return

        def work(_e):
            return self.app.lj.sign_status_all()

        def done(st):
            self.status.setText(
                f"连续签到 {st['cont_days']} 天 · 经验 {st['exp']} · Lv.{st['level']} · "
                f"今天已签 {len(st['signed'])} 个板块")
        common.run_bg(work, done, lambda e: None)

    def start_signin(self) -> None:
        if not self.app.cfg.get("lingjie.token", ""):
            common.toast(self.app, "请先登录灵芥账号", "warn")
            return
        if not self.btn.isEnabled():
            return
        self.btn.setEnabled(False)
        self.btn.setText("签到中…")
        self.progress.setValue(0)
        self.log.clear()
        self.status.setText("正在获取板块列表…")

        def work(emit):
            return self.app.lj.signin_all(
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
        self.status.setText(f"完成：新签 {ok} 个，失败 {fail} 个")
        self.log.clear()
        self.log.append("<br>".join(logs))
        self.app.cfg.set("stats.lj_signin", ok)
        self.app.cfg.save()
        if ok > 0 or fail == 0:
            from ..signin_state import mark_signed
            mark_signed("lingjie")
        self.app.notify_accounts()
        from ..activity import record
        record("signin", f"灵芥签到完成：新签 {ok} 个，失败 {fail} 个", "lingjie")
        common.toast(self.app, f"灵芥签到完成：新签 {ok} 个", "ok")
        self.load_status()

    def _fail(self, msg: str) -> None:
        self.btn.setEnabled(True)
        self.btn.setText("开始签到")
        self.status.setText("签到失败")
        common.toast(self.app, f"签到失败：{msg}", "err")

    # ---------- 记忆 / 亲密度 ----------
    def _save_owner(self) -> None:
        try:
            uid = int(self.owner.text().strip() or 0)
        except Exception:
            uid = 0
        self.app.cfg.set("fish.owner_uid_lingjie", uid)
        self.app.cfg.save()
        common.toast(self.app, f"主人 UID 已设为 {uid}" if uid else "已清空主人 UID", "ok")

    def _build_stats(self) -> None:
        card = common.Card(padding=20, spacing=10)
        head = QHBoxLayout()
        head.addWidget(common.card_title("记忆与亲密度（灵芥）"))
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
        rows = REL.top("lingjie", 6)
        lines = []
        for uid, nick, favor in rows:
            color = theme.OK if favor >= 70 else (theme.WARN if favor >= 40 else theme.MUTED)
            lines.append(f"{nick or 'uid=' + str(uid)} "
                         f"<span style='color:{color};font-weight:700'>{favor}</span> "
                         f"<span style='color:{theme.MUTED}'>{level(favor)}</span>")
        self.stats_lb.setText(
            f"用户记忆 {user_count('lingjie')} 个 · 通用记忆 "
            f"{len(read_lines(MEMORY_FILE, 999))} 条<br>"
            + ("<br>".join(lines) if lines else "还没有互动记录"))

    def refresh(self) -> None:
        self._build_account()
