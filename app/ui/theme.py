"""统一外观：默认浅色，可切换深色（黑夜模式）。"""
from __future__ import annotations

from ..config import CFG

LIGHT = {
    "BG": "#F6F8FB", "BG2": "#FFFFFF", "CARD": "#FFFFFF", "CARD2": "#F2F5FA",
    "LINE": "#E5EAF2", "TEXT": "#1F2937", "MUTED": "#6B7280",
    "ACCENT": "#2F6BFF", "ACCENT2": "#4F86FF", "OK": "#059669",
    "WARN": "#D97706", "ERR": "#DC2626",
    "FIELD": "#F8FAFC", "HOVER": "#EFF3F9", "NAV_HOVER": "#F1F5F9",
    "NAV_ACTIVE": "#E8F0FE", "SEL": "#DBEAFE", "SCROLL": "#CBD5E1",
    "SCROLL_HOVER": "#94A3B8", "BTN_PRESS": "#E2E8F0", "DISABLED": "#9CA3AF",
}

DARK = {
    "BG": "#0B1220", "BG2": "#0F172A", "CARD": "#141F35", "CARD2": "#1B2942",
    "LINE": "#243553", "TEXT": "#E6EDF7", "MUTED": "#8FA3BF",
    "ACCENT": "#38BDF8", "ACCENT2": "#0EA5E9", "OK": "#34D399",
    "WARN": "#FBBF24", "ERR": "#F87171",
    "FIELD": "#0E1729", "HOVER": "#223354", "NAV_HOVER": "#14203A",
    "NAV_ACTIVE": "#14263F", "SEL": "#1B2942", "SCROLL": "#26395B",
    "SCROLL_HOVER": "#34507A", "BTN_PRESS": "#1A2943", "DISABLED": "#5B6E8C",
}

P = dict(LIGHT)
WALL = False
BG = P["BG"]; BG2 = P["BG2"]; CARD = P["CARD"]; CARD2 = P["CARD2"]
LINE = P["LINE"]; TEXT = P["TEXT"]; MUTED = P["MUTED"]
ACCENT = P["ACCENT"]; ACCENT2 = P["ACCENT2"]; OK = P["OK"]
WARN = P["WARN"]; ERR = P["ERR"]
QSS = ""


def _template(p: dict) -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
    color: {p['TEXT']};
}}
QWidget#root {{ background: {p['BG2']}; }}
QWidget#sidebar {{ background: {p['BG']}; border-right: 1px solid {p['LINE']}; }}

QLabel#logo {{ font-size: 20px; font-weight: 800; color: {p['TEXT']}; }}
QLabel#logoSub {{ color: {p['MUTED']}; font-size: 11px; letter-spacing: 1px; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 800; color: {p['TEXT']}; }}
QLabel#pageSub {{ color: {p['MUTED']}; font-size: 12px; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 700; color: {p['TEXT']}; }}
QLabel#muted {{ color: {p['MUTED']}; }}
QLabel#hint {{ color: {p['MUTED']}; font-size: 12px; }}
QLabel#big {{ font-size: 26px; font-weight: 800; color: {p['TEXT']}; }}
QLabel#ok {{ color: {p['OK']}; }}
QLabel#warn {{ color: {p['WARN']}; }}
QLabel#err {{ color: {p['ERR']}; }}

QFrame#card {{
    background: {p['CARD']};
    border: 1px solid {p['LINE']};
    border-radius: 14px;
}}
QFrame#line {{ background: {p['LINE']}; max-height: 1px; min-height: 1px; border: none; }}

QPushButton {{
    background: {p['CARD2']};
    border: 1px solid {p['LINE']};
    border-radius: 9px;
    padding: 4px 16px;
    min-height: 22px;
    color: {p['TEXT']};
}}
QPushButton:hover {{ background: {p['HOVER']}; border-color: {p['ACCENT']}; }}
QPushButton:pressed {{ background: {p['BTN_PRESS']}; }}
QPushButton:disabled {{ color: {p['DISABLED']}; background: {p['CARD2']}; }}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['ACCENT']}, stop:1 {p['ACCENT2']});
    border: 1px solid {p['ACCENT']};
    color: #FFFFFF;
    font-weight: 700;
}}
QPushButton#primary:hover {{ background: {p['ACCENT2']}; }}
QPushButton#ghost {{ background: transparent; }}
QPushButton#ghost:hover {{ background: {p['NAV_HOVER']}; }}

QPushButton#nav {{
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: {p['MUTED']};
    font-size: 14px;
}}
QPushButton#nav:hover {{ background: {p['NAV_HOVER']}; color: {p['TEXT']}; }}
QPushButton#nav:checked {{
    background: {p['NAV_ACTIVE']};
    color: {p['ACCENT']};
    font-weight: 700;
    padding-left: 14px;
    border-left: 3px solid {p['ACCENT']};
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QTimeEdit, QDateEdit, QDateTimeEdit {{
    background: {p['FIELD']};
    border: 1px solid {p['LINE']};
    border-radius: 9px;
    padding: 7px 10px;
    color: {p['TEXT']};
    selection-background-color: {p['SEL']};
    selection-color: {p['TEXT']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {p['ACCENT']};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QSpinBox::up-button, QSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; height: 0px; border: none; }}
QComboBox QAbstractItemView {{
    background: {p['CARD']}; border: 1px solid {p['LINE']};
    selection-background-color: {p['SEL']}; color: {p['TEXT']}; outline: none;
}}

QProgressBar {{
    background: {p['CARD2']}; border: none; border-radius: 6px;
    height: 10px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p['ACCENT']}; border-radius: 6px; }}

QScrollArea, QStackedWidget {{ background: transparent; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['SCROLL']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['SCROLL_HOVER']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTextBrowser {{
    background: {p['FIELD']}; color: {p['TEXT']};
    border: 1px solid {p['LINE']}; border-radius: 12px; padding: 8px;
}}
QListWidget, QListView {{
    background: {p['FIELD']};
    color: {p['TEXT']};
    border: 1px solid {p['LINE']};
    border-radius: 10px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; color: {p['TEXT']}; }}
QListWidget::item:selected {{ background: {p['SEL']}; color: {p['TEXT']}; }}
QListWidget::item:hover {{ background: {p['NAV_HOVER']}; }}

QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {p['LINE']}; background: {p['FIELD']};
}}
QCheckBox::indicator:checked {{ background: {p['ACCENT']}; border-color: {p['ACCENT']}; }}
QCheckBox#switch::indicator {{
    width: 46px; height: 24px; border-radius: 12px;
    background: {p['SCROLL']}; border: 1px solid {p['LINE']};
}}
QCheckBox#switch::indicator:checked {{
    background: {p['ACCENT']}; border-color: {p['ACCENT']};
}}

QToolTip {{
    background: {p['CARD']}; color: {p['TEXT']}; border: 1px solid {p['LINE']};
    border-radius: 6px; padding: 5px 8px;
}}
QMenu {{
    background: {p['CARD']}; border: 1px solid {p['LINE']};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 7px; color: {p['TEXT']}; }}
QMenu::item:selected {{ background: {p['SEL']}; }}
QTabWidget::pane {{ border: 1px solid {p['LINE']}; border-radius: 10px; }}
QTabBar::tab {{
    background: {p['CARD2']}; border: 1px solid {p['LINE']};
    padding: 6px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{ background: {p['CARD']}; color: {p['ACCENT']}; }}
"""


def _set_globals(p: dict) -> None:
    global BG, BG2, CARD, CARD2, LINE, TEXT, MUTED, ACCENT, ACCENT2
    global OK, WARN, ERR, FIELD, SEL, P, QSS
    P = dict(p)
    BG = p["BG"]; BG2 = p["BG2"]; CARD = p["CARD"]; CARD2 = p["CARD2"]
    LINE = p["LINE"]; TEXT = p["TEXT"]; MUTED = p["MUTED"]
    ACCENT = p["ACCENT"]; ACCENT2 = p["ACCENT2"]; OK = p["OK"]
    WARN = p["WARN"]; ERR = p["ERR"]
    FIELD = p["FIELD"]; SEL = p["SEL"]
    QSS = _template(p)


def is_dark() -> bool:
    mode = CFG.get("general.ui_mode", "")
    if mode:
        return mode == "dark"
    return bool(CFG.get("general.dark_mode", False))


def apply(app, mode: str | None = None, dark: bool | None = None) -> None:
    global WALL
    if mode is None:
        mode = "dark" if (dark if dark is not None else is_dark()) else "light"
    if mode == "wallpaper":
        _set_globals(LIGHT)
        WALL = True
    elif mode == "dark":
        _set_globals(DARK)
        WALL = False
    else:
        _set_globals(LIGHT)
        WALL = False
    if app is not None:
        qss = QSS
        if WALL:
            try:
                from pathlib import Path
                img = Path(__file__).resolve().parents[2] / "assets" / "wallpaper.jpg"
                url = str(img).replace("\\", "/")
                qss += (
                    f'QWidget#root {{ border-image: url("{url}") 0 0 0 0 '
                    f'stretch stretch; background: transparent; }}'
                    f'QWidget#sidebar {{ background: rgba(255,255,255,0.80); '
                    f'border-right: 1px solid {LINE}; }}'
                    f'QWidget#pageBody, QWidget#pageBody > QWidget {{ '
                    f'background: transparent; }}'
                    f'QScrollArea > QWidget#qt_scrollarea_viewport {{ '
                    f'background: transparent; }}'
                    f'QFrame#card {{ background: rgba(255,255,255,0.90); }}'
                )
            except Exception:
                pass
        app.setStyleSheet(qss)


def card_style(radius: int = 14) -> str:
    return (f"QFrame{{background:{CARD};border:1px solid {LINE};"
            f"border-radius:{radius}px;}}")


_set_globals(LIGHT)
