"""大肥鱼页：AI 配置、文生图、人设、挂件、发帖、聊天、亲密度。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QSlider, QTextBrowser,
                               QVBoxLayout)

from .. import imaging, memory, persona, publishing
from .. import brain
from ..config import CFG
from ..debuglog import DBG
from ..relations import REL, level
from . import common, theme
from .base import Page

PROTO_LABEL = {"openai": "OpenAI 兼容", "dashscope": "阿里百炼 DashScope", "sd": "SD WebUI"}
PROTO_DEFAULT_URL = {
    "openai": "https://api.openai.com/v1/images/generations",
    "dashscope": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "sd": "http://127.0.0.1:7860",
}


class FishPage(Page):
    key = "fish"

    def __init__(self, app):
        super().__init__(app, "大肥鱼",
                         "人设、记忆、生图、发帖、挂件，都在这一页。")
        self.history: list[tuple[str, str]] = []
        self._boards: list[tuple[int, str]] = []
        self._build_persona()
        self._build_publish()
        self._build_manage()
        self._build_chat()
        self.body.addStretch(1)

    # ---------- AI ----------
    def _build_ai(self) -> None:
        card = common.Card(padding=20, spacing=12)
        card.box.addWidget(common.card_title("DeepSeek 配置"))
        card.box.addWidget(common.hint(
            "只需要一个 DeepSeek API Key。模型名按官方当前可用名称填写即可。"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.api_key = QLineEdit(CFG.get("ai.key", ""))
        self.api_key.setPlaceholderText("sk-...")
        self.api_key.setEchoMode(QLineEdit.Password)
        row.addWidget(QLabel("API Key"))
        row.addWidget(self.api_key, 1)
        self.show_key = QCheckBox("显示")
        self.show_key.stateChanged.connect(
            lambda s: self.api_key.setEchoMode(QLineEdit.Normal if s else QLineEdit.Password))
        row.addWidget(self.show_key)
        card.box.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("接口地址"))
        self.base = QLineEdit(CFG.get("ai.base", "https://api.deepseek.com"))
        row2.addWidget(self.base, 2)
        row2.addWidget(QLabel("日常模型"))
        self.model_basic = QComboBox()
        self.model_basic.setEditable(True)
        self.model_basic.addItems(["deepseek-flash", "deepseek-v4-pro", "deepseek-chat"])
        self.model_basic.setCurrentText(CFG.get("ai.model_basic", "deepseek-flash"))
        row2.addWidget(self.model_basic, 1)
        row2.addWidget(QLabel("复杂模型"))
        self.model_smart = QComboBox()
        self.model_smart.setEditable(True)
        self.model_smart.addItems(["deepseek-v4-pro", "deepseek-flash", "deepseek-reasoner"])
        self.model_smart.setCurrentText(CFG.get("ai.model_smart", "deepseek-v4-pro"))
        row2.addWidget(self.model_smart, 1)
        card.box.addLayout(row2)

        row3 = QHBoxLayout()
        save = common.button("保存配置", primary=True)
        save.clicked.connect(self.save_ai)
        test = common.button("测试连接")
        test.clicked.connect(self.test_ai)
        row3.addWidget(save)
        row3.addWidget(test)
        row3.addStretch(1)
        self.ai_state = common.muted("")
        row3.addWidget(self.ai_state)
        card.box.addLayout(row3)
        self.body.addWidget(card)

    def save_ai(self) -> None:
        # AI 配置已移到「设置 → AI 配置」
        CFG.save()

    def test_ai(self) -> None:
        def work(_e):
            from .. import ai
            return ai.ask("", "只回复两个字：在的")

        def done(text):
            common.toast(self.app, f"模型回复：{text.strip()[:30]}", "ok")

        def fail(msg):
            common.toast(self.app, f"连接失败：{msg}", "err")

        common.run_bg(work, done, fail)

    # ---------- 文生图 ----------
    def _build_image(self) -> None:
        card = common.Card(padding=20, spacing=12)
        head = QHBoxLayout()
        head.addWidget(common.card_title("文生图"))
        head.addStretch(1)
        self.img_state = common.muted("")
        head.addWidget(self.img_state)
        card.box.addLayout(head)
        card.box.addWidget(common.hint(
            "支持三种协议：OpenAI 兼容 / 阿里百炼 / SD WebUI。配好之后，发帖时可以自动生成配图。"))

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("协议"))
        self.img_proto = QComboBox()
        for k, v in PROTO_LABEL.items():
            self.img_proto.addItem(v, k)
        cur = CFG.get("fish.img_proto", "openai")
        self.img_proto.setCurrentIndex(max(0, self.img_proto.findData(cur)))
        self.img_proto.currentIndexChanged.connect(self._proto_changed)
        row.addWidget(self.img_proto)
        row.addWidget(QLabel("接口地址"))
        self.img_url = QLineEdit(CFG.get("fish.img_url", ""))
        self.img_url.setPlaceholderText(PROTO_DEFAULT_URL.get(cur, ""))
        row.addWidget(self.img_url, 3)
        card.box.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("API Key"))
        self.img_key = QLineEdit(CFG.get("fish.img_key", ""))
        self.img_key.setEchoMode(QLineEdit.Password)
        self.img_key.setPlaceholderText("DashScope / OpenAI 的 Key；SD 可留空")
        row2.addWidget(self.img_key, 2)
        row2.addWidget(QLabel("模型"))
        self.img_model = QLineEdit(CFG.get("fish.img_model", "gpt-image-1"))
        row2.addWidget(self.img_model, 1)
        row2.addWidget(QLabel("尺寸"))
        self.img_size = QComboBox()
        self.img_size.setEditable(True)
        self.img_size.addItems(["1024x1024", "768x1024", "1024x768", "512x512"])
        self.img_size.setCurrentText(CFG.get("fish.img_size", "1024x1024"))
        row2.addWidget(self.img_size, 1)
        card.box.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(10)
        save = common.button("保存生图配置", primary=True)
        save.clicked.connect(self.save_image)
        test = common.button("测试生图")
        test.clicked.connect(self.test_image)
        row3.addWidget(save)
        row3.addWidget(test)
        self.img_prompt = QLineEdit()
        self.img_prompt.setPlaceholderText("测试提示词，例如：蓝白女仆装的小鲸鱼女孩，清新可爱")
        row3.addWidget(self.img_prompt, 1)
        card.box.addLayout(row3)

        self.img_preview = QLabel("还没有生成过图片")
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setFixedHeight(220)
        self.img_preview.setStyleSheet(
            f"background:{theme.BG};border:1px dashed {theme.LINE};"
            f"border-radius:10px;color:{theme.MUTED};")
        card.box.addWidget(self.img_preview)
        self.body.addWidget(card)

    def _proto_changed(self, idx: int) -> None:
        proto = self.img_proto.currentData()
        self.img_url.setPlaceholderText(PROTO_DEFAULT_URL.get(proto, ""))
        if proto == "dashscope":
            self.img_model.setText(CFG.get("fish.img_model", "wan2.6-t2i")
                                   if CFG.get("fish.img_model") else "wan2.6-t2i")

    def save_image(self) -> None:
        # 生图配置已移到「设置 → 文生图」
        CFG.save()

    def test_image(self) -> None:
        prompt = "一只蓝色的小鲸鱼女孩，清新可爱，白色背景"

        def work(_e):
            return imaging.generate(prompt)

        def done(png):
            if not png:
                common.toast(self.app, "生图失败，看「调试」页的日志", "err")
                return
            imaging.save_last(png, "test_image.png")
            common.toast(self.app, "生图成功", "ok")
            from ..activity import record
            record("genimg", f"测试生图：{prompt[:24]}")

        def fail(msg):
            common.toast(self.app, f"生图失败：{msg}", "err")

        common.run_bg(work, done, fail)

    def show_preview(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        self.img_preview.setPixmap(
            pm.scaled(self.img_preview.width() - 8, self.img_preview.height() - 8,
                      Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.img_preview.setToolTip(path)

    # ---------- 人设 ----------
    def _build_persona(self) -> None:
        card = common.Card(padding=20, spacing=12)
        card.box.addWidget(common.card_title("人设"))
        row = QHBoxLayout()
        row.addWidget(QLabel("名字"))
        self.fish_name = QLineEdit(CFG.get("fish.name", "大肥鱼"))
        self.fish_name.setFixedWidth(160)
        row.addWidget(self.fish_name)
        row.addStretch(1)
        reset = common.button("恢复默认", ghost=True)
        reset.clicked.connect(self.reset_persona)
        row.addWidget(reset)
        card.box.addLayout(row)
        self.persona_edit = QPlainTextEdit()
        self.persona_edit.setPlainText(brain.persona_template())
        self.persona_edit.setMinimumHeight(170)
        card.box.addWidget(self.persona_edit)
        card.box.addWidget(common.hint(
            "可用变量：{name} = 名字，{appearance} = 形象；保存后运行时会自动替换。"))
        save = common.button("保存人设", primary=True)
        save.clicked.connect(self.save_persona)
        row2 = QHBoxLayout()
        row2.addWidget(save)
        row2.addStretch(1)
        self.mem_label = common.muted("")
        row2.addWidget(self.mem_label)
        card.box.addLayout(row2)
        self.body.addWidget(card)

        # ---------- 形象（配图用） ----------
        appear = common.Card(padding=20, spacing=10)
        appear.box.addWidget(common.card_title("形象（生成配图用）"))
        appear.box.addWidget(common.hint(
            "写清楚发色、耳朵/尾巴、服装、配饰。配图提示词会原样带上这段，"
            "改完保存即可，下一张图生效。"))
        self.appear_edit = QPlainTextEdit()
        self.appear_edit.setPlainText(CFG.get("fish.appearance", ""))
        self.appear_edit.setMinimumHeight(110)
        appear.box.addWidget(self.appear_edit)
        arow = QHBoxLayout()
        save_a = common.button("保存形象", primary=True)
        save_a.clicked.connect(self.save_appearance)
        arow.addWidget(save_a)
        reset_a = common.button("恢复默认", ghost=True)
        reset_a.clicked.connect(self.reset_appearance)
        arow.addWidget(reset_a)
        arow.addStretch(1)
        appear.box.addLayout(arow)
        self.body.addWidget(appear)

    def save_persona(self) -> None:
        CFG.set("fish.name", self.fish_name.text().strip() or "大肥鱼")
        CFG.set("fish.persona", self.persona_edit.toPlainText().strip())
        CFG.save()
        common.toast(self.app, "人设已保存", "ok")

    def reset_persona(self) -> None:
        self.persona_edit.setPlainText(persona.DEFAULT_PERSONA)
        common.toast(self.app, "已恢复默认人设，记得点保存", "info")

    def save_appearance(self) -> None:
        CFG.set("fish.appearance", self.appear_edit.toPlainText().strip())
        CFG.save()
        common.toast(self.app, "形象已保存，下一张配图生效", "ok")

    def reset_appearance(self) -> None:
        from ..config import DEFAULTS
        self.appear_edit.setPlainText(DEFAULTS["fish"]["appearance"])
        common.toast(self.app, "已恢复默认形象，记得点保存", "info")

    # ---------- 挂件 ----------
    def _build_pet(self) -> None:
        card = common.Card(padding=20, spacing=12)
        card.box.addWidget(common.card_title("桌面挂件"))
        card.box.addWidget(common.hint(
            "置顶半透明的小鱼，可拖动。左键点一下会跟你说话，右键有菜单。"))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.pet_on = QCheckBox("显示挂件")
        self.pet_on.setChecked(bool(CFG.get("fish.enabled", False)))
        self.pet_on.stateChanged.connect(self.toggle_pet)
        row.addWidget(self.pet_on)

        row.addWidget(QLabel("大小"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(90, 260)
        self.size_slider.setValue(int(CFG.get("fish.size", 150)))
        self.size_slider.setFixedWidth(160)
        self.size_val = common.muted(str(self.size_slider.value()))
        self.size_slider.valueChanged.connect(
            lambda v: (self.size_val.setText(str(v)), self.apply_size(v)))
        row.addWidget(self.size_slider)
        row.addWidget(self.size_val)

        row.addWidget(QLabel("透明度"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(40, 100)
        self.alpha_slider.setValue(int(float(CFG.get("fish.alpha", 1.0)) * 100))
        self.alpha_slider.setFixedWidth(120)
        self.alpha_slider.valueChanged.connect(self.apply_alpha)
        row.addWidget(self.alpha_slider)
        row.addStretch(1)
        card.box.addLayout(row)

        row2 = QHBoxLayout()
        jump = common.button("把挂件叫出来", primary=True)
        jump.clicked.connect(lambda: self.app.open_pet(True))
        hide = common.button("收起挂件", ghost=True)
        hide.clicked.connect(lambda: self.app.open_pet(False))
        row2.addWidget(jump)
        row2.addWidget(hide)
        row2.addStretch(1)
        card.box.addLayout(row2)
        self.body.addWidget(card)

    def toggle_pet(self, state) -> None:
        on = bool(state)
        CFG.set("fish.enabled", on)
        CFG.save()
        self.app.open_pet(on)

    def apply_size(self, v: int) -> None:
        CFG.set("fish.size", v)
        CFG.save()
        self.app.pet_resize()

    def apply_alpha(self, v: int) -> None:
        CFG.set("fish.alpha", v / 100.0)
        CFG.save()
        self.app.pet_resize()

    # ---------- 发帖 ----------
    def _build_publish(self) -> None:
        card = common.Card(padding=20, spacing=12)
        head = QHBoxLayout()
        head.addWidget(common.card_title("发帖"))
        head.addStretch(1)
        self.post_state = common.muted("")
        head.addWidget(self.post_state)
        card.box.addLayout(head)
        card.box.addWidget(common.hint(
            "选平台和板块，写标题正文；勾选「生成配图」会先用文生图接口画一张再一起发出去。"))

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("平台"))
        self.post_platform = QComboBox()
        self.post_platform.addItem("葫芦侠三楼", "hlx")
        self.post_platform.addItem("灵芥空间", "lingjie")
        self.post_platform.currentIndexChanged.connect(self.reload_boards)
        row.addWidget(self.post_platform)
        row.addWidget(QLabel("板块"))
        self.post_board = QComboBox()
        self.post_board.setMinimumWidth(200)
        row.addWidget(self.post_board, 1)
        row.addWidget(common.button("刷新板块", ghost=True, on_click=self.reload_boards))
        card.box.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("标题"))
        self.post_title = QLineEdit()
        self.post_title.setPlaceholderText("标题")
        row2.addWidget(self.post_title, 1)
        card.box.addLayout(row2)

        self.post_content = QPlainTextEdit()
        self.post_content.setPlaceholderText("正文…")
        self.post_content.setFixedHeight(110)
        card.box.addWidget(self.post_content)

        row3 = QHBoxLayout()
        row3.setSpacing(10)
        self.post_image = QCheckBox("生成配图")
        row3.addWidget(self.post_image)
        self.post_img_prompt = QLineEdit()
        self.post_img_prompt.setPlaceholderText("配图描述（留空则按标题自动编）")
        row3.addWidget(self.post_img_prompt, 1)
        card.box.addLayout(row3)

        row4 = QHBoxLayout()
        row4.setSpacing(10)
        draft = common.button("让大肥鱼写一条", on_click=self.ai_compose)
        self.post_btn = common.button("发布", primary=True, on_click=self.do_publish)
        row4.addWidget(draft)
        row4.addWidget(self.post_btn)
        row4.addStretch(1)
        card.box.addLayout(row4)
        card.setVisible(False)   # 发帖由大肥鱼自己决策，这里不暴露手动入口
        self.body.addWidget(card)

    def reload_boards(self) -> None:
        platform = self.post_platform.currentData()
        self.post_board.clear()
        self.post_board.addItem("加载中…", 0)
        if not (self.app.cfg.get("hlx.key", "") if platform == "hlx"
                else self.app.cfg.get("lingjie.token", "")):
            self.post_board.clear()
            self.post_board.addItem("未登录", 0)
            return

        def work(_e):
            if platform == "hlx":
                return self.app.hlx.boards()
            return self.app.lj.forums()

        def done(boards):
            self._boards = boards
            self.post_board.clear()
            if not boards:
                self.post_board.addItem("没有拿到板块", 0)
                return
            for bid, name in boards:
                self.post_board.addItem(name, bid)
            DBG.log("POST", f"板块列表 {len(boards)} 个（{platform}）")

        common.run_bg(work, done, lambda e: common.toast(self.app, f"板块加载失败：{e}", "err"))

    def ai_compose(self) -> None:
        board = self.post_board.currentText() or "社区"
        hint = self.post_content.toPlainText().strip() or self.post_title.text().strip()
        self.post_state.setText("正在写…")

        def work(_e):
            return publishing.compose_post(board, hint)

        def done(res):
            title, content = res
            self.post_title.setText(title)
            self.post_content.setPlainText(content)
            self.post_state.setText("草稿已生成")

        common.run_bg(work, done,
                      lambda e: (self.post_state.setText("失败"),
                                 common.toast(self.app, f"生成失败：{e}", "err")))

    def do_publish(self) -> None:
        platform = self.post_platform.currentData()
        board_id = self.post_board.currentData() or 0
        board_name = self.post_board.currentText()
        title = self.post_title.text().strip()
        content = self.post_content.toPlainText().strip()
        if not title or not content:
            common.toast(self.app, "标题和正文都要写", "warn")
            return
        self.post_btn.setEnabled(False)
        self.post_state.setText("发布中…")

        def work(_e):
            return publishing.publish_post(
                platform, int(board_id), board_name, title, content,
                self.post_image.isChecked(), self.post_img_prompt.text().strip())

        def done(res):
            ok, msg = res
            self.post_btn.setEnabled(True)
            self.post_state.setText(msg)
            common.toast(self.app, msg, "ok" if ok else "err")
            if ok:
                self.post_title.clear()
                self.post_content.clear()
                self.app.notify_accounts()

        def fail(msg):
            self.post_btn.setEnabled(True)
            self.post_state.setText("失败")
            common.toast(self.app, f"发帖失败：{msg}", "err")

        common.run_bg(work, done, fail)

    # ---------- 管理我的帖子 ----------
    def _build_manage(self) -> None:
        card = common.Card(padding=20, spacing=10)
        card.box.addWidget(common.card_title("管理我的帖子"))
        card.box.addWidget(common.hint(
            "拉取自己最近的帖子，可以删除；也可以按评论 id 删一条评论。删了不可恢复。"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.mg_platform = QComboBox()
        self.mg_platform.addItem("葫芦侠三楼", "hlx")
        self.mg_platform.addItem("灵芥空间", "lingjie")
        self.mg_platform.currentIndexChanged.connect(self.load_my_posts)
        row.addWidget(self.mg_platform)
        self.mg_posts = QComboBox()
        self.mg_posts.setMinimumWidth(260)
        row.addWidget(self.mg_posts, 1)
        row.addWidget(common.button("刷新", ghost=True, on_click=self.load_my_posts))
        row.addWidget(common.button("删除选中帖子", on_click=self.delete_selected))
        card.box.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("评论 ID"))
        self.mg_cid = QLineEdit()
        self.mg_cid.setPlaceholderText("要删除的评论 cid")
        self.mg_cid.setFixedWidth(180)
        row2.addWidget(self.mg_cid)
        row2.addWidget(common.button("删除评论", on_click=self.delete_comment))
        row2.addStretch(1)
        self.mg_state = common.muted("")
        row2.addWidget(self.mg_state)
        card.box.addLayout(row2)
        self.body.addWidget(card)

    def load_my_posts(self) -> None:
        platform = self.mg_platform.currentData()
        self.mg_posts.clear()
        self.mg_posts.addItem("加载中…", 0)
        logged = (CFG.get("hlx.key", "") if platform == "hlx"
                  else CFG.get("lingjie.token", ""))
        if not logged:
            self.mg_posts.clear()
            self.mg_posts.addItem("未登录", 0)
            return

        def work(_e):
            return (self.app.hlx.my_posts(20) if platform == "hlx"
                    else self.app.lj.my_themes(20))

        def done(posts):
            self.mg_posts.clear()
            if not posts:
                self.mg_posts.addItem("没有拿到帖子", 0)
                return
            for p in posts:
                pid = int(p.get("postID", 0) or p.get("tid", 0) or 0)
                title = (p.get("title") or "（无标题）")[:28]
                self.mg_posts.addItem(f"{title}  #{pid}", pid)
            self.mg_state.setText(f"共 {len(posts)} 条")

        common.run_bg(work, done,
                      lambda e: common.toast(self.app, f"拉取失败：{e}", "err"))

    def delete_selected(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        pid = self.mg_posts.currentData() or 0
        if not pid:
            common.toast(self.app, "先选一条帖子", "warn")
            return
        if QMessageBox.question(self, "删帖", "确定删除这条帖子？不可恢复。") != QMessageBox.Yes:
            return
        platform = self.mg_platform.currentData()
        self.mg_state.setText("删除中…")

        def work(_e):
            return (self.app.hlx.delete_post(int(pid)) if platform == "hlx"
                    else self.app.lj.delete_theme(int(pid)))

        def done(res):
            ok, msg = res
            self.mg_state.setText("已删除" if ok else "删除失败")
            common.toast(self.app, "删除成功" if ok else f"删除失败：{msg}",
                         "ok" if ok else "err")
            if ok:
                from ..activity import record
                record("system", f"删除了帖子 #{pid}", platform)
                self.load_my_posts()

        common.run_bg(work, done, lambda e: common.toast(self.app, f"删除失败：{e}", "err"))

    def delete_comment(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        try:
            cid = int(self.mg_cid.text().strip())
        except Exception:
            common.toast(self.app, "填一个评论 id", "warn")
            return
        if QMessageBox.question(self, "删评论", "确定删除这条评论？") != QMessageBox.Yes:
            return
        platform = self.mg_platform.currentData()

        def work(_e):
            return (self.app.hlx.delete_comment(cid) if platform == "hlx"
                    else self.app.lj.delete_comment(cid))

        def done(res):
            ok, msg = res
            common.toast(self.app, "评论已删除" if ok else f"删除失败：{msg}",
                         "ok" if ok else "err")
            if ok:
                from ..activity import record
                record("system", f"删除了评论 #{cid}", platform)

        common.run_bg(work, done, lambda e: common.toast(self.app, f"删除失败：{e}", "err"))

    # ---------- 聊天 ----------
    def _build_chat(self) -> None:
        card = common.Card(padding=20, spacing=12)
        head = QHBoxLayout()
        head.addWidget(common.card_title("和大肥鱼聊天"))
        head.addSpacing(10)
        self.p_hlx = common.Badge("葫芦侠", "muted")
        self.p_lj = common.Badge("灵芥", "muted")
        head.addWidget(self.p_hlx)
        head.addWidget(self.p_lj)
        head.addStretch(1)
        self.mood_badge = common.Badge("", "muted")
        head.addWidget(self.mood_badge)
        clear = common.button("清屏", ghost=True)
        clear.clicked.connect(self.clear_chat)
        head.addWidget(clear)
        card.box.addLayout(head)
        self.chat_view = QTextBrowser()
        self.chat_view.setMinimumHeight(240)
        self.chat_view.setOpenExternalLinks(True)
        card.box.addWidget(self.chat_view)

        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("说点什么…（Enter 发送）")
        self.chat_input.returnPressed.connect(self.send_chat)
        row.addWidget(self.chat_input, 1)
        self.send_btn = common.button("发送", primary=True)
        self.send_btn.clicked.connect(self.send_chat)
        row.addWidget(self.send_btn)
        card.box.addLayout(row)
        self.body.addWidget(card)
        self._render_chat()

    def _system_prompt(self) -> str:
        persona_text = brain.persona_text()
        name = CFG.get("fish.name", "大肥鱼") or "大肥鱼"
        mood = memory.get_mood()
        platforms = []
        if CFG.get("hlx.key", ""):
            platforms.append("葫芦侠三楼")
        if CFG.get("lingjie.token", ""):
            platforms.append("灵芥空间")
        parts = [persona_text,
                 f"【你叫】{name}。别人问你叫什么，就回答「{name}」。",
                 f"【你现在的心情】{memory.mood_label(mood)}（{mood}/100）"]
        if platforms:
            parts.append("【你同时在线的社区】" + "、".join(platforms) +
                         "。主人在这两个地方都能找到你。")
        mem = memory.recent(8)
        if mem:
            parts.append("【你最近的记忆】\n" + mem)
        life = memory.recent_life(4)
        if life:
            parts.append("【你今天的生活】\n" + life)
        return brain.apply_name("\n".join(parts))

    def _render_chat(self) -> None:
        html = []
        for who, text in self.history[-60:]:
            if who == "me":
                html.append(
                    f"<div style='margin:8px 0;text-align:right'>"
                    f"<span style='background:{theme.ACCENT2};color:#04121F;"
                    f"border-radius:10px;padding:6px 10px;display:inline-block'>"
                    f"{text}</span></div>")
            else:
                html.append(
                    f"<div style='margin:8px 0'>"
                    f"<span style='background:{theme.CARD2};color:{theme.TEXT};"
                    f"border:1px solid {theme.LINE};"
                    f"border-radius:10px;padding:6px 10px;display:inline-block'>"
                    f"{text}</span></div>")
        self.chat_view.setHtml("".join(html) or
                               f"<div style='color:{theme.MUTED}'>还没聊过，说句话试试～</div>")
        self.chat_view.moveCursor(QTextCursor.End)
        self.mood_badge.setText(f"心情 {memory.mood_label()}")
        self.mood_badge.set_kind("ok" if memory.get_mood() >= 60 else "warn")

    def clear_chat(self) -> None:
        self.history.clear()
        self._render_chat()

    def send_chat(self) -> None:
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self.history.append(("me", text))
        self._render_chat()
        self.send_btn.setEnabled(False)
        system = self._system_prompt()

        def work(_e):
            from .. import ai
            return ai.ask(system, text, None)

        def done(reply):
            self.send_btn.setEnabled(True)
            self.history.append(("fish", reply.strip()))
            self._render_chat()
            memory.remember(f"和主人聊天：{text} → {reply[:60]}")
            memory.nudge_mood(1)
            self.app.cfg.set("stats.chat", int(self.app.cfg.get("stats.chat", 0)) + 1)
            self.app.cfg.save()
            from ..activity import record
            record("chat", f"主人：{text[:30]} → {reply[:40]}")

        def fail(msg):
            self.send_btn.setEnabled(True)
            self.history.append(("fish", f"（没连上模型：{msg}）"))
            self._render_chat()

        common.run_bg(work, done, fail)

    # ---------- 亲密度 ----------
    def _build_relation(self) -> None:
        card = common.Card(padding=20, spacing=12)
        head = QHBoxLayout()
        head.addWidget(common.card_title("亲密度"))
        head.addStretch(1)
        head.addWidget(common.button("刷新", ghost=True, on_click=self.render_relations))
        card.box.addLayout(head)
        card.box.addWidget(common.hint(
            "按「平台 + 用户」分别记录：回复、互动会加好感，取关/被冷落会掉。两个社区互不影响。"))
        self.rel_view = QLabel("还没有互动记录")
        self.rel_view.setWordWrap(True)
        self.rel_view.setTextFormat(Qt.RichText)
        card.box.addWidget(self.rel_view)
        self.body.addWidget(card)

    def render_relations(self) -> None:
        blocks = []
        for platform, name in (("hlx", "葫芦侠"), ("lingjie", "灵芥")):
            rows = REL.top(platform, 8)
            if not rows:
                continue
            lines = []
            for uid, nick, favor in rows:
                color = theme.OK if favor >= 70 else (theme.WARN if favor >= 40 else theme.MUTED)
                lines.append(
                    f"<span style='color:{theme.MUTED}'>{uid}</span> "
                    f"{nick or '—'} "
                    f"<span style='color:{color};font-weight:700'>{favor}</span>"
                    f" <span style='color:{theme.MUTED}'>{level(favor)}</span>")
            blocks.append(f"<div style='margin:4px 0'><b>{name}</b><br>" +
                          "<br>".join(lines) + "</div>")
        self.rel_view.setText("".join(blocks) or "还没有互动记录")

    # ---------- 刷新 ----------
    def refresh(self) -> None:
        self._render_chat()
        hlx_ok = bool(CFG.get("hlx.key", ""))
        lj_ok = bool(CFG.get("lingjie.token", ""))
        self.p_hlx.set_kind("ok" if hlx_ok else "muted")
        self.p_lj.set_kind("ok" if lj_ok else "muted")
        plat = "hlx" if hlx_ok else ("lingjie" if lj_ok else "")
        self.mem_label.setText(
            f"记忆 {len(memory.read_lines(memory.general_file(plat), 999))} 条 · "
            f"心情 {memory.get_mood(plat)}")
