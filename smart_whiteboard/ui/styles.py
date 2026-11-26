"""Visual identity of LuminaBoard: colour tokens + the global Qt style sheet."""
from __future__ import annotations

# --- palette ---------------------------------------------------------------
NAVY = "#0E1330"
NAVY_2 = "#171D47"
NAVY_3 = "#242C5E"
NAVY_LINE = "#2A3270"
ON_NAVY = "#E8ECFA"
ON_NAVY_MUTED = "#8E97C8"

BG = "#F3F1EA"          # warm neutral canvas
PANEL = "#FFFFFF"
BORDER = "#E4E1D8"
TEXT = "#1B2140"
MUTED = "#6B7194"

ACCENT = "#6C5CE7"      # violet
ACCENT_HOVER = "#7D6EF0"
ACCENT_SOFT = "#EFECFD"
TEAL = "#12B5A6"
BLUE = "#3B82F6"
ROSE = "#E11D48"
AMBER = "#F59E0B"
GREEN = "#16A34A"

STATE_COLORS = {"ok": GREEN, "warn": AMBER, "error": ROSE, "off": "#9AA0BF"}

# Pen palette (hex). First entry is the default pen colour.
INK_COLORS = ["#1F2937", "#2563EB", "#E11D48", "#16A34A", "#F59E0B", "#7C3AED", "#0D9488", "#78716C"]

FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'

APP_NAME = "LuminaBoard"
APP_TAGLINE = "Smart Interactive Whiteboard"

STYLESHEET = f"""
* {{ font-family: {FONT_FAMILY}; }}
QWidget {{ color: {TEXT}; font-size: 13px; }}
QMainWindow, QWidget#root, QWidget#page {{ background: {BG}; }}
QStackedWidget {{ background: {BG}; }}
QLabel {{ background: transparent; }}

QToolTip {{ background: {NAVY}; color: {ON_NAVY}; border: 1px solid {NAVY_LINE};
            padding: 5px 8px; border-radius: 6px; }}

/* ---- sidebar ---------------------------------------------------------- */
QFrame#sidebar {{ background: {NAVY}; }}
QLabel#brandName {{ color: white; font-size: 19px; font-weight: 800; }}
QLabel#brandTag {{ color: {ON_NAVY_MUTED}; font-size: 11px; }}
QLabel#sidebarCaption {{ color: {ON_NAVY_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QLabel#sidebarFoot {{ color: {ON_NAVY_MUTED}; font-size: 11px; }}
QPushButton#nav {{ text-align: left; padding: 11px 14px; border: none; border-radius: 12px;
                   color: {ON_NAVY_MUTED}; background: transparent; font-size: 14px; font-weight: 600; }}
QPushButton#nav:hover {{ background: {NAVY_2}; color: white; }}
QPushButton#nav:checked {{ background: {NAVY_3}; color: white; }}
QPushButton#nav[soon="true"] {{ color: #6E77AB; }}
QPushButton#nav[soon="true"]:checked, QPushButton#nav[soon="true"]:hover {{ color: white; }}

/* ---- generic panels / cards -------------------------------------------- */
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 18px; }}
QLabel#panelTitle {{ font-size: 14px; font-weight: 700; }}
QLabel#h1 {{ font-size: 30px; font-weight: 800; }}
QLabel#h2 {{ font-size: 22px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#pill {{ background: {ACCENT_SOFT}; color: {ACCENT}; border-radius: 9px; padding: 3px 10px;
               font-size: 11px; font-weight: 700; }}

QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 18px; }}
QFrame#card:hover {{ border: 1px solid {ACCENT}; background: #FCFBFF; }}
QFrame#card:focus {{ border: 2px solid {ACCENT}; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#cardText {{ color: {MUTED}; font-size: 12px; }}
QLabel#soonBadge {{ background: #F1EFE7; color: {MUTED}; border-radius: 8px; padding: 2px 8px;
                    font-size: 10px; font-weight: 700; }}

QFrame#statusPill {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px; }}

QPushButton#recent {{ text-align: left; padding: 9px 12px; border: none; border-radius: 10px;
                      background: transparent; }}
QPushButton#recent:hover {{ background: {ACCENT_SOFT}; }}

/* ---- buttons ------------------------------------------------------------ */
QPushButton {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px;
               padding: 8px 18px; font-weight: 600; }}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton:default {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QPushButton:default:hover {{ background: {ACCENT_HOVER}; color: white; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; padding: 10px 22px; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; color: white; }}

/* ---- whiteboard chrome ------------------------------------------------- */
QFrame#actionBar, QFrame#styleBar {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px; }}
QLabel#boardTitle {{ font-size: 15px; font-weight: 800; }}
QLabel#boardInfo {{ color: {MUTED}; font-size: 12px; }}
QToolButton#bar {{ border: none; border-radius: 10px; padding: 7px 11px; font-weight: 600; background: transparent; }}
QToolButton#bar:hover {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QToolButton#bar:disabled {{ color: #B7B9CC; }}
QToolButton#bar:checked {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QToolButton#bar:pressed {{ background: #E3DEFB; }}
QFrame#vsep {{ background: {BORDER}; max-width: 1px; min-width: 1px; }}

QFrame#toolRail {{ background: {NAVY}; border-radius: 18px; }}
QToolButton#tool {{ border: none; border-radius: 13px; background: transparent; }}
QToolButton#tool:hover {{ background: {NAVY_3}; }}
QToolButton#tool:checked {{ background: {ACCENT}; }}

QPushButton#swatch {{ border: 3px solid {PANEL}; border-radius: 15px; padding: 0; min-width: 24px; max-width: 24px;
                      min-height: 24px; max-height: 24px; }}
QPushButton#swatch:hover {{ border: 3px solid {ACCENT_SOFT}; }}
QPushButton#swatch:checked {{ border: 3px solid {ACCENT}; }}
QPushButton#preset {{ padding: 5px 12px; font-size: 12px; border-radius: 9px; }}
QPushButton#preset:checked {{ background: {ACCENT_SOFT}; color: {ACCENT}; border-color: {ACCENT}; }}

QSlider::groove:horizontal {{ height: 6px; background: #E6E3D9; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {ACCENT}; width: 14px; height: 14px;
                              margin: -6px 0; border-radius: 9px; }}
QSlider::handle:horizontal:hover {{ background: {ACCENT_SOFT}; }}

QComboBox {{ background: white; border: 1px solid {BORDER}; border-radius: 9px; padding: 6px 12px; min-height: 20px; }}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT};
                               selection-color: {ACCENT}; outline: none; }}
QCheckBox {{ spacing: 9px; font-weight: 600; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1.5px solid #C9C6BA; background: white; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D5D2C6; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLabel#sectionTitle {{ font-size: 11px; font-weight: 800; color: {MUTED}; letter-spacing: 1px; }}
QLabel#mono {{ font-family: Consolas, "Cascadia Mono", monospace; font-size: 12px; color: {TEXT}; }}
QLabel#stepActive {{ background: {ACCENT_SOFT}; color: {ACCENT}; border-radius: 10px; padding: 8px 12px; font-weight: 700; }}
QLabel#stepIdle {{ color: {MUTED}; padding: 8px 12px; }}
QLabel#stepDone {{ color: {GREEN}; padding: 8px 12px; font-weight: 600; }}
QFrame#note {{ background: #FFF8E6; border: 1px solid #F3DFA6; border-radius: 12px; }}
QFrame#noteError {{ background: #FDECEF; border: 1px solid #F5BFCB; border-radius: 12px; }}
QFrame#noteOk {{ background: #E8F7EE; border: 1px solid #B9E3C9; border-radius: 12px; }}

QMessageBox, QInputDialog, QDialog {{ background: {PANEL}; }}
QPlainTextEdit, QLineEdit, QTextEdit {{ background: white; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px; }}

QLabel#toast {{ background: {NAVY}; color: white; border-radius: 14px; padding: 11px 20px; font-weight: 600; }}
"""
