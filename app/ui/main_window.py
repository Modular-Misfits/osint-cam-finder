import os
import queue

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow,
    QTabWidget, QVBoxLayout, QWidget,
)

from app.core.scanner import ScanRunner, custom_registry
from app.db.store import Store
from app.ui.custom_sources_panel import CustomSourcesPanel
from app.ui.database_panel import DatabasePanel
from app.ui.export_panel import ExportPanel
from app.ui.help_panel import HelpPanel
from app.ui.scan_panel import ScanPanel
from app.ui.settings_panel import SettingsPanel

# Obsidian Hierarchy — canonical theme tokens
C_BG      = "#111111"
C_SURFACE = "#1A1A1A"
C_OVERLAY = "#252525"
C_BORDER  = "#333333"
C_ACCENT  = "#E66B66"
C_TEXT1   = "#EDEDED"
C_TEXT2   = "#A1A1A1"
C_TEXT3   = "#8E8E8E"

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.jpg")

# Qt font-family only accepts a single name — pick the best available at runtime
def _pick_font() -> str:
    available = QFontDatabase.families()
    for candidate in ("SF Pro Display", "SF Pro Text", ".SF NS Display", "Helvetica Neue", "Helvetica", "Arial"):
        if candidate in available:
            return candidate
    return ""   # empty string = Qt picks system default, which is readable


def _make_stylesheet(font_family: str) -> str:
    font_rule = f'font-family: "{font_family}";' if font_family else ""
    return f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT1};
    {font_rule}
    font-size: 13px;
}}
QTabWidget::pane {{
    border: none;
    background-color: {C_BG};
}}
QTabBar {{
    background-color: {C_BG};
}}
QTabBar::tab {{
    background-color: {C_BG};
    color: {C_TEXT3};
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {C_TEXT1};
    border-bottom: 2px solid {C_ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {C_TEXT2};
}}
QPushButton {{
    background-color: {C_SURFACE};
    color: {C_TEXT1};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 18px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {C_OVERLAY};
    border-color: {C_TEXT3};
}}
QPushButton:disabled {{
    color: {C_TEXT3};
    border-color: {C_BORDER};
}}
QPushButton#accent {{
    background-color: {C_ACCENT};
    color: {C_TEXT1};
    border: none;
}}
QPushButton#accent:hover {{ background-color: #d45f5a; }}
QLineEdit, QComboBox {{
    background-color: {C_SURFACE};
    color: {C_TEXT1};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 13px;
    min-height: 28px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {C_TEXT3};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {C_OVERLAY};
    color: {C_TEXT1};
    border: 1px solid {C_BORDER};
    selection-background-color: {C_ACCENT};
    font-size: 13px;
    outline: none;
}}
QTextEdit, QPlainTextEdit {{
    background-color: {C_SURFACE};
    color: {C_TEXT1};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    font-family: "Courier New";
    font-size: 12px;
}}
QTableWidget {{
    background-color: {C_SURFACE};
    color: {C_TEXT1};
    border: none;
    alternate-background-color: {C_OVERLAY};
    gridline-color: {C_BORDER};
    font-size: 12px;
}}
QHeaderView::section {{
    background-color: {C_BG};
    color: {C_TEXT2};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    padding: 7px 6px;
    font-size: 12px;
    font-weight: 600;
}}
QScrollBar:vertical {{
    background-color: {C_BG};
    width: 8px;
    border: none;
}}
QScrollBar:horizontal {{
    background-color: {C_BG};
    height: 8px;
    border: none;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background-color: {C_BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:hover {{ background-color: {C_TEXT3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ background: none; border: none; }}
QProgressBar {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 3px;
    text-align: center;
    color: {C_TEXT2};
    font-size: 11px;
    min-height: 16px;
}}
QProgressBar::chunk {{
    background-color: {C_ACCENT};
    border-radius: 3px;
}}
QGroupBox {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: {C_TEXT2};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {C_TEXT2};
}}
QCheckBox {{
    color: {C_TEXT1};
    spacing: 6px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
}}
QLabel {{
    color: {C_TEXT1};
    font-size: 13px;
}}
QSplitter::handle {{ background-color: {C_BORDER}; }}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = Store()
        self.ui_queue: queue.Queue = queue.Queue()
        self.scanner = ScanRunner(self.store, self.ui_queue)

        self.setWindowTitle("OSINT Camera Finder")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._build_header(layout)
        self._build_tabs(layout)

    def _build_header(self, layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(12)

        # Logo — shown if asset exists, gracefully skipped if not yet copied
        logo_path = os.path.abspath(LOGO_PATH)
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            pix = QPixmap(logo_path)
            logo_lbl.setPixmap(
                pix.scaledToHeight(76, Qt.TransformationMode.SmoothTransformation)
            )
            logo_lbl.setFixedHeight(76)
            row.addWidget(logo_lbl)

        title = QLabel("OSINT CAMERA FINDER")
        title.setFont(QFont(_pick_font(), 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT1};")

        row.addWidget(title)
        row.addStretch()
        layout.addLayout(row)

    def _build_tabs(self, layout: QVBoxLayout):
        tabs = QTabWidget()
        self.scan_panel            = ScanPanel(self.scanner, self.ui_queue, self.store, custom_registry)
        self.db_panel              = DatabasePanel(self.store)
        self.exp_panel             = ExportPanel(self.store)
        self.custom_sources_panel  = CustomSourcesPanel(custom_registry)
        self.settings_panel        = SettingsPanel()
        self.help_panel            = HelpPanel()

        tabs.addTab(self.scan_panel,           "  Scan  ")
        tabs.addTab(self.db_panel,             "  Database  ")
        tabs.addTab(self.exp_panel,            "  Export  ")
        tabs.addTab(self.custom_sources_panel, "  Sources  ")
        tabs.addTab(self.settings_panel,       "  Settings  ")
        tabs.addTab(self.help_panel,           "  Help  ")
        tabs.currentChanged.connect(self._on_tab_change)

        layout.addWidget(tabs)

    def _on_tab_change(self, index: int):
        if index == 1:
            self.db_panel.refresh()
        elif index == 2:
            self.exp_panel.refresh_dropdowns()

    def closeEvent(self, event):
        if self.scanner.is_running():
            self.scanner.stop()
        self.store.close()
        event.accept()


def launch():
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(_make_stylesheet(_pick_font()))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
