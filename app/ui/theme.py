"""统一外观：深蓝配色 + 卡片式界面。"""

BG = "#0B1220"
BG2 = "#0F172A"
CARD = "#141F35"
CARD2 = "#1B2942"
LINE = "#243553"
TEXT = "#E6EDF7"
MUTED = "#8FA3BF"
ACCENT = "#38BDF8"
ACCENT2 = "#0EA5E9"
OK = "#34D399"
WARN = "#FBBF24"
ERR = "#F87171"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
    color: {TEXT};
}}
QWidget#root {{ background: {BG2}; }}
QWidget#sidebar {{ background: {BG}; border-right: 1px solid {LINE}; }}

QLabel#logo {{ font-size: 20px; font-weight: 800; color: #FFFFFF; }}
QLabel#logoSub {{ color: {MUTED}; font-size: 11px; letter-spacing: 1px; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 800; }}
QLabel#pageSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#big {{ font-size: 26px; font-weight: 800; }}
QLabel#ok {{ color: {OK}; }}
QLabel#warn {{ color: {WARN}; }}
QLabel#err {{ color: {ERR}; }}

QFrame#card {{
    background: {CARD};
    border: 1px solid {LINE};
    border-radius: 14px;
}}
QFrame#line {{ background: {LINE}; max-height: 1px; min-height: 1px; border: none; }}

QPushButton {{
    background: {CARD2};
    border: 1px solid {LINE};
    border-radius: 9px;
    padding: 4px 16px;
    min-height: 22px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #223354; border-color: #35507A; }}
QPushButton:pressed {{ background: #1A2943; }}
QPushButton:disabled {{ color: #5B6E8C; background: #131E33; }}

QPushButton#primary {{
    background: {ACCENT2};
    border: 1px solid {ACCENT};
    color: #04121F;
    font-weight: 700;
}}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QPushButton#ghost {{ background: transparent; }}
QPushButton#ghost:hover {{ background: #1B2942; }}

QPushButton#nav {{
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: {MUTED};
    font-size: 14px;
}}
QPushButton#nav:hover {{ background: #14203A; color: {TEXT}; }}
QPushButton#nav:checked {{
    background: #14263F;
    color: {ACCENT};
    font-weight: 700;
    padding-left: 14px;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QTimeEdit, QDateEdit, QDateTimeEdit {{
    background: #0E1729;
    border: 1px solid {LINE};
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: {ACCENT2};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QSpinBox::up-button, QSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; height: 0px; border: none; }}
QComboBox QAbstractItemView {{
    background: {CARD2}; border: 1px solid {LINE};
    selection-background-color: {ACCENT2}; outline: none;
}}

QProgressBar {{
    background: #0E1729; border: none; border-radius: 6px;
    height: 10px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}

QScrollArea, QStackedWidget {{ background: transparent; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #26395B; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #34507A; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTextBrowser {{ background: #0E1729; border: 1px solid {LINE}; border-radius: 12px; padding: 8px; }}

QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {LINE}; background: #0E1729;
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QToolTip {{
    background: {CARD2}; color: {TEXT}; border: 1px solid {LINE};
    border-radius: 6px; padding: 5px 8px;
}}

QMenu {{
    background: {CARD2}; border: 1px solid {LINE};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 7px; }}
QMenu::item:selected {{ background: #22375A; }}
"""


def card_style(radius: int = 14) -> str:
    return (f"QFrame{{background:{CARD};border:1px solid {LINE};"
            f"border-radius:{radius}px;}}")
