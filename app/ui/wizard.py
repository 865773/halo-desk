"""首次配置向导：登录两个平台、配置 DeepSeek、可选文生图。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QTabWidget, QTextBrowser, QVBoxLayout)

from ..config import CFG
from . import common, theme


def _page(html: str) -> QTextBrowser:
    tb = QTextBrowser()
    tb.setOpenExternalLinks(True)
    tb.setHtml(html)
    tb.setStyleSheet("font-size:13px;line-height:165%;")
    return tb


class Wizard(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("首次配置向导")
        self.resize(760, 620)
        lay = QVBoxLayout(self)

        title = QLabel("按顺序配好下面四项，就能启动大肥鱼")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        lay.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(_page("""
        <h3>第一步：登录葫芦侠三楼</h3>
        <ol>
          <li>切到「葫芦侠三楼」页，点「登录」；</li>
          <li>用账号密码登录（或扫码，如果页面提供）；</li>
          <li>登录成功会显示昵称、UID、等级。</li>
        </ol>
        <p>注意：葫芦侠有签到、发帖、评论等频率限制，别把间隔调太短。</p>
        """), "1 葫芦侠")
        tabs.addTab(_page("""
        <h3>第二步：登录灵芥空间</h3>
        <ol>
          <li>切到「灵芥空间」页；</li>
          <li>用账号密码或短信验证码登录；</li>
          <li>登录态是 JWT，过期后重新登录即可。</li>
        </ol>
        <p>灵芥的货币叫「芥子」，相当于葫芦侠的葫芦，程序不会乱送。</p>
        """), "2 灵芥")
        tabs.addTab(self._deepseek(), "3 DeepSeek")
        tabs.addTab(self._image(), "4 文生图")
        lay.addWidget(tabs, 1)

        hint = QLabel("配好后点「完成并启用」；也可以稍后在「总览」里手动启用。")
        hint.setObjectName("muted")
        lay.addWidget(hint)

        row = QHBoxLayout()
        row.addStretch(1)
        later = common.button("稍后再说", ghost=True, on_click=self._later)
        done = common.button("完成并启用", primary=True, on_click=self._finish)
        row.addWidget(later)
        row.addWidget(done)
        lay.addLayout(row)

    # ---------- tabs ----------
    def _deepseek(self) -> QTextBrowser:
        tb = _page("""
        <h3>第三步：配置 DeepSeek</h3>
        <ol>
          <li>打开 <a href="https://platform.deepseek.com/api_keys">platform.deepseek.com</a>
              注册并创建 API Key；</li>
          <li>把 Key 粘到下面，点保存；</li>
          <li>模型默认 deepseek-chat 即可。</li>
        </ol>
        <p>所有对话、评论、发帖、日记都走这个 Key；不填则大肥鱼不会说话。</p>
        """)
        return tb

    def _image(self) -> QTextBrowser:
        return _page("""
        <h3>第四步（可选）：文生图</h3>
        <p>不配也能用，只是发帖不带图。三种协议任选：</p>
        <ul>
          <li><b>OpenAI</b>：接口地址 + Key + 模型（如 gpt-image-1）；</li>
          <li><b>DashScope（百炼）</b>：Key + 模型（wan2.6-t2i 等），地址可留空；</li>
          <li><b>Stable Diffusion</b>：填本地地址，如 http://127.0.0.1:7860。</li>
        </ul>
        <p>配置在「大肥鱼 → 文生图」里；模型余额用完会自动换下一个。</p>
        <p>形象设定在「大肥鱼 → 形象」，会原样写进配图提示词。</p>
        """)

    # ---------- actions ----------
    def _later(self) -> None:
        CFG.set("first_run", False)
        CFG.save()
        self.accept()

    def _finish(self) -> None:
        CFG.set("first_run", False)
        CFG.save()
        home = self.app.pages.get("home")
        miss = home.missing_items() if home else []
        if miss:
            common.toast(self.app, "还差：" + "、".join(miss), "warn")
            self.accept()
            return
        CFG.set("fish.enabled", True)
        CFG.save()
        self.app.autopilot.start()
        common.toast(self.app, "配置完成，大肥鱼已启用", "ok")
        self.accept()
