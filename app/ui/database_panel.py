from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.core.schema import CATEGORIES
from app.db.store import Store

PAGE_SIZE = 200

COLUMNS = [
    ("source",      "Source",     90),
    ("category",    "Category",   80),
    ("camera_name", "Name",      160),
    ("url",         "URL",       220),
    ("country_code","CC",         40),
    ("state",       "State",      70),
    ("city",        "City",       90),
    ("latitude",    "Lat",        70),
    ("longitude",   "Lon",        70),
    ("status",      "Status",     60),
    ("last_seen",   "Last Seen", 130),
]

# Obsidian Hierarchy tokens (local copies — avoids importing main_window)
_C_BG      = "#111111"
_C_SURFACE = "#1A1A1A"
_C_BORDER  = "#333333"
_C_ACCENT  = "#E66B66"
_C_TEXT1   = "#EDEDED"
_C_TEXT2   = "#A1A1A1"
_C_TEXT3   = "#8E8E8E"

COLOR_OFFLINE = _C_TEXT3
COLOR_ACTIVE  = _C_TEXT1

# Accent button style — identical to "Start Scan" button in scan_panel
_ACCENT_BTN = f"""
    QPushButton {{
        background-color: {_C_ACCENT};
        color: {_C_TEXT1};
        border: none;
        border-radius: 6px;
        padding: 6px 18px;
        font-size: 13px;
    }}
    QPushButton:hover {{ background-color: #d45f5a; }}
    QPushButton:disabled {{ background-color: #7a3a37; color: {_C_TEXT3}; }}
"""

# Flat filter panel — no raised background, blends into page
_FILTER_PANEL = f"""
    QWidget#filter_panel {{
        background-color: {_C_SURFACE};
        border: 1px solid {_C_BORDER};
        border-radius: 6px;
    }}
    QWidget#filter_panel QLabel {{
        background-color: transparent;
        color: {_C_TEXT2};
        font-size: 13px;
    }}
    QWidget#filter_panel QComboBox {{
        background-color: {_C_BG};
        color: {_C_TEXT1};
        border: 1px solid {_C_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        min-height: 26px;
    }}
    QWidget#filter_panel QComboBox::drop-down {{ border: none; width: 18px; }}
    QWidget#filter_panel QComboBox QAbstractItemView {{
        background-color: {_C_SURFACE};
        color: {_C_TEXT1};
        border: 1px solid {_C_BORDER};
        selection-background-color: {_C_ACCENT};
    }}
    QWidget#filter_panel QLineEdit {{
        background-color: {_C_BG};
        color: {_C_TEXT1};
        border: 1px solid {_C_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        min-height: 26px;
    }}
    QWidget#filter_panel QCheckBox {{
        background-color: transparent;
        color: {_C_TEXT1};
        font-size: 13px;
        spacing: 5px;
    }}
    QWidget#filter_panel QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        background-color: {_C_BG};
        border: 1px solid {_C_BORDER};
        border-radius: 3px;
    }}
    QWidget#filter_panel QCheckBox::indicator:checked {{
        background-color: {_C_ACCENT};
        border-color: {_C_ACCENT};
    }}
"""


class DatabasePanel(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store  = store
        self.offset = 0
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(6)

        # ── Filters ───────────────────────────────────────────────────────────
        # Use a plain QWidget with objectName so the flat stylesheet applies
        # cleanly without the QGroupBox title bar creating a second visual layer.
        filt_panel = QWidget()
        filt_panel.setObjectName("filter_panel")
        filt_panel.setStyleSheet(_FILTER_PANEL)
        filt_lay = QVBoxLayout(filt_panel)
        filt_lay.setSpacing(8)
        filt_lay.setContentsMargins(12, 10, 12, 10)

        # Section label — replaces QGroupBox title
        section_lbl = QLabel("Filters")
        section_lbl.setStyleSheet(f"color: {_C_TEXT3}; font-size: 11px; font-weight: 600;")
        filt_lay.addWidget(section_lbl)

        # Row 1 — dropdowns + search + action buttons
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        row1.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(130)
        row1.addWidget(self.source_combo)

        row1.addSpacing(4)
        row1.addWidget(QLabel("Country:"))
        self.country_combo = QComboBox()
        self.country_combo.setMinimumWidth(70)
        row1.addWidget(self.country_combo)

        row1.addSpacing(4)
        row1.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["", "active", "offline", "unknown"])
        self.status_combo.setMinimumWidth(90)
        row1.addWidget(self.status_combo)

        row1.addSpacing(4)
        row1.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("name / city / url...")
        self.search_edit.setMaximumWidth(340)
        row1.addWidget(self.search_edit, stretch=1)

        row1.addSpacing(8)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("accent")
        apply_btn.setMinimumWidth(80)
        apply_btn.setStyleSheet(_ACCENT_BTN)
        apply_btn.clicked.connect(self._apply_filters)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("accent")
        clear_btn.setMinimumWidth(75)
        clear_btn.setStyleSheet(_ACCENT_BTN)
        clear_btn.clicked.connect(self._clear_filters)

        row1.addWidget(apply_btn)
        row1.addWidget(clear_btn)
        filt_lay.addLayout(row1)

        # Row 2 — category label + checkboxes on same row
        cat_row = QHBoxLayout()
        cat_row.setSpacing(0)

        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet(f"color: {_C_TEXT3}; font-size: 11px;")
        cat_row.addWidget(cat_lbl)
        cat_row.addSpacing(12)

        self.cat_checks: dict[str, QCheckBox] = {}
        for cat in CATEGORIES:
            cb = QCheckBox(cat)
            self.cat_checks[cat] = cb
            cat_row.addWidget(cb)
            cat_row.addSpacing(28)

        cat_row.addStretch()
        filt_lay.addLayout(cat_row)

        root.addWidget(filt_panel)

        # ── Row count ─────────────────────────────────────────────────────────
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color: {_C_TEXT3}; font-size: 9pt;")
        root.addWidget(self.count_lbl)

        # ── Table ─────────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        hdr = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # URL column stretches

        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.table, stretch=1)

        # ── Pagination ────────────────────────────────────────────────────────
        pag_row = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_page)
        self.page_lbl = QLabel("")
        self.page_lbl.setStyleSheet(f"color: {_C_TEXT3}; font-size: 9pt;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)

        pag_row.addWidget(self.prev_btn)
        pag_row.addWidget(self.next_btn)
        pag_row.addWidget(self.page_lbl)
        pag_row.addStretch()
        pag_row.addWidget(refresh_btn)
        root.addLayout(pag_row)

    def _query_kwargs(self) -> dict:
        cats = [cat for cat, cb in self.cat_checks.items() if cb.isChecked()]
        return {
            "source":       self.source_combo.currentText(),
            "categories":   cats or None,
            "country_code": self.country_combo.currentText(),
            "status":       self.status_combo.currentText(),
            "search":       self.search_edit.text().strip(),
        }

    def refresh(self):
        sources   = [""] + self.store.sources()
        countries = [""] + self.store.country_codes()

        self.source_combo.blockSignals(True)
        self.country_combo.blockSignals(True)
        cur_src = self.source_combo.currentText()
        cur_cc  = self.country_combo.currentText()
        self.source_combo.clear()
        self.source_combo.addItems(sources)
        self.country_combo.clear()
        self.country_combo.addItems(countries)
        if cur_src in sources:
            self.source_combo.setCurrentText(cur_src)
        if cur_cc in countries:
            self.country_combo.setCurrentText(cur_cc)
        self.source_combo.blockSignals(False)
        self.country_combo.blockSignals(False)

        self._load_page()

    def _apply_filters(self):
        self.offset = 0
        self._load_page()

    def _clear_filters(self):
        self.source_combo.setCurrentIndex(0)
        self.country_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.search_edit.clear()
        for cb in self.cat_checks.values():
            cb.setChecked(False)
        self.offset = 0
        self._load_page()

    def _load_page(self):
        kwargs = self._query_kwargs()
        total  = self.store.count(**kwargs)
        rows   = self.store.query(**kwargs, limit=PAGE_SIZE, offset=self.offset)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            is_offline = row.get("status") == "offline"
            for c, (key, _, _) in enumerate(COLUMNS):
                val = row.get(key) or ""
                if key in ("latitude", "longitude") and val:
                    try:
                        val = f"{float(val):.4f}"
                    except (ValueError, TypeError):
                        pass
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if is_offline:
                    item.setForeground(QColor(COLOR_OFFLINE))
                self.table.setItem(r, c, item)

        self.table.setSortingEnabled(True)

        page_num   = self.offset // PAGE_SIZE + 1
        page_total = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.count_lbl.setText(f"{total:,} cameras")
        self.page_lbl.setText(f"Page {page_num} of {page_total}")
        self.prev_btn.setEnabled(self.offset > 0)
        self.next_btn.setEnabled(self.offset + PAGE_SIZE < total)

    def _prev_page(self):
        self.offset = max(0, self.offset - PAGE_SIZE)
        self._load_page()

    def _next_page(self):
        self.offset += PAGE_SIZE
        self._load_page()
