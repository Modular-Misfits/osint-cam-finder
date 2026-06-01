import queue

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.custom_sources import CustomSourceRegistry
from app.core.enricher import EnrichRunner
from app.core.scanner import ScanRunner
from app.db.store import Store

COUNTRY_MAP = {
    "United States":  "US",
    "Canada":         "CA",
    "Mexico":         "MX",
    "Brazil":         "BR",
    "Romania":        "RO",
    "Nigeria":        "NG",
    "South Africa":   "ZA",
    "France":         "FR",
    "Madagascar":     "MG",
    "Russia":         "RU",
    "Germany":        "DE",
    "Finland":        "FI",
    "China":          "CN",
    "Japan":          "JP",
    "North Korea":    "NK",
    "Taiwan":         "TW",
    "American Samoa": "AS",
    "Netherlands":    "NL",
    "India":          "IN",
    "Switzerland":    "CH",
    "Tanzania":       "TZ",
    "Belarus":        "BY",
    "Estonia":        "EE",
    "Slovenia":       "SI",
}

SOURCES = ["Insecam", "FAA WeatherCams", "OpenStreetMap", "Windy Webcams", "US DOT Traffic"]

DOT_STATES = {
    "All States": "",
    "New York":   "NY",
}

# Sources that take no filter option
_NO_OPTION_SOURCES = {"FAA WeatherCams"}

COLOR_NEW     = "#6ee7b7"
COLOR_UPDATED = "#93c5fd"
COLOR_ERROR   = "#E66B66"
COLOR_DIM     = "#8E8E8E"
COLOR_FG      = "#EDEDED"

_C_BG      = "#111111"
_C_SURFACE = "#1A1A1A"
_C_BORDER  = "#333333"
_C_ACCENT  = "#E66B66"
_C_TEXT1   = "#EDEDED"
_C_TEXT2   = "#A1A1A1"
_C_TEXT3   = "#8E8E8E"

_FLAT_PANEL = f"""
    QWidget#scan_ctrl_panel {{
        background-color: {_C_SURFACE};
        border: 1px solid {_C_BORDER};
        border-radius: 6px;
    }}
    QWidget#scan_ctrl_panel QLabel {{
        background-color: transparent;
        color: {_C_TEXT2};
        font-size: 13px;
    }}
    QWidget#scan_ctrl_panel QComboBox {{
        background-color: {_C_BG};
        color: {_C_TEXT1};
        border: 1px solid {_C_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        min-height: 26px;
    }}
    QWidget#scan_ctrl_panel QComboBox::drop-down {{ border: none; width: 18px; }}
    QWidget#scan_ctrl_panel QComboBox QAbstractItemView {{
        background-color: {_C_SURFACE};
        color: {_C_TEXT1};
        border: 1px solid {_C_BORDER};
        selection-background-color: {_C_ACCENT};
    }}
"""

_LOG_PANEL = f"""
    QWidget#log_panel {{
        background-color: {_C_SURFACE};
        border: 1px solid {_C_BORDER};
        border-radius: 6px;
    }}
    QWidget#log_panel QLabel {{
        background-color: transparent;
        color: {_C_TEXT3};
        font-size: 11px;
        font-weight: 600;
    }}
    QWidget#log_panel QTextEdit {{
        background-color: {_C_BG};
        border: none;
        border-radius: 0px;
    }}
"""

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


class ScanPanel(QWidget):
    def __init__(self, scanner: ScanRunner, ui_queue: queue.Queue, store: Store,
                 custom_registry: CustomSourceRegistry):
        super().__init__()
        self.scanner          = scanner
        self.ui_queue         = ui_queue
        self.store            = store
        self._custom_registry = custom_registry
        self._enricher        = EnrichRunner(store, ui_queue)
        self._build()
        self._sync_sources()
        custom_registry.register_change_callback(self._sync_sources)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(100)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # ── Source controls ───────────────────────────────────────────────────
        ctrl_panel = QWidget()
        ctrl_panel.setObjectName("scan_ctrl_panel")
        ctrl_panel.setStyleSheet(_FLAT_PANEL)
        ctrl_lay = QHBoxLayout(ctrl_panel)
        ctrl_lay.setContentsMargins(12, 10, 12, 10)
        ctrl_lay.setSpacing(10)

        ctrl_lay.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(SOURCES)
        self.source_combo.currentTextChanged.connect(self._on_source_change)
        ctrl_lay.addWidget(self.source_combo)

        ctrl_lay.addSpacing(8)
        self.option_label = QLabel("Country:")
        ctrl_lay.addWidget(self.option_label)
        self.option_combo = QComboBox()
        self.option_combo.addItems(list(COUNTRY_MAP.keys()))
        ctrl_lay.addWidget(self.option_combo)

        ctrl_lay.addStretch()

        self.start_btn = QPushButton("Start Scan")
        self.start_btn.setMinimumWidth(100)
        self.start_btn.setStyleSheet(_ACCENT_BTN)
        self.start_btn.clicked.connect(self._start)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumWidth(70)
        self.stop_btn.setStyleSheet(_ACCENT_BTN)
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)

        ctrl_lay.addSpacing(16)

        self.enrich_btn = QPushButton("Enrich Insecam")
        self.enrich_btn.setMinimumWidth(130)
        self.enrich_btn.setStyleSheet(_ACCENT_BTN)
        self.enrich_btn.setToolTip(
            "Fetch detail pages for all Insecam cameras missing lat/lon.\n"
            "Runs with rate limiting (0.5s between requests)."
        )
        self.enrich_btn.clicked.connect(self._start_enrich)

        self.enrich_stop_btn = QPushButton("Stop Enrich")
        self.enrich_stop_btn.setMinimumWidth(100)
        self.enrich_stop_btn.setStyleSheet(_ACCENT_BTN)
        self.enrich_stop_btn.clicked.connect(self._stop_enrich)
        self.enrich_stop_btn.setEnabled(False)

        self.recat_btn = QPushButton("Re-categorize DB")
        self.recat_btn.setMinimumWidth(140)
        self.recat_btn.setStyleSheet(_ACCENT_BTN)
        self.recat_btn.setToolTip("Re-run category inference on every camera in the DB using updated keywords.")
        self.recat_btn.clicked.connect(self._recategorize)

        ctrl_lay.addWidget(self.start_btn)
        ctrl_lay.addWidget(self.stop_btn)
        ctrl_lay.addWidget(self.enrich_btn)
        ctrl_lay.addWidget(self.enrich_stop_btn)
        ctrl_lay.addWidget(self.recat_btn)

        root.addWidget(ctrl_panel)

        # ── Progress ──────────────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Ready")
        self.progress.setFixedHeight(18)
        root.addWidget(self.progress)

        # ── Stats row ─────────────────────────────────────────────────────────
        stats_lay = QHBoxLayout()
        stats_lay.setSpacing(20)
        self.lbl_new       = QLabel("New: 0")
        self.lbl_updated   = QLabel("Updated: 0")
        self.lbl_unchanged = QLabel("Unchanged: 0")
        self.lbl_total     = QLabel("Total: 0")
        self.lbl_new.setStyleSheet(f"color: {COLOR_NEW}; font-weight: 600;")
        self.lbl_updated.setStyleSheet(f"color: {COLOR_UPDATED}; font-weight: 600;")
        self.lbl_unchanged.setStyleSheet(f"color: {COLOR_DIM};")
        self.lbl_total.setStyleSheet(f"color: {COLOR_FG}; font-weight: 600;")
        for lbl in (self.lbl_new, self.lbl_updated, self.lbl_unchanged, self.lbl_total):
            stats_lay.addWidget(lbl)
        stats_lay.addStretch()
        root.addLayout(stats_lay)

        # ── Live log ──────────────────────────────────────────────────────────
        log_panel = QWidget()
        log_panel.setObjectName("log_panel")
        log_panel.setStyleSheet(_LOG_PANEL)
        log_lay = QVBoxLayout(log_panel)
        log_lay.setContentsMargins(10, 8, 10, 10)
        log_lay.setSpacing(6)

        log_title = QLabel("Live Log")
        log_lay.addWidget(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        log_lay.addWidget(self.log)

        root.addWidget(log_panel, stretch=1)

    def _sync_sources(self):
        current = self.source_combo.currentText()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        all_sources = SOURCES + [s["name"] for s in self._custom_registry.enabled()]
        self.source_combo.addItems(all_sources)
        idx = self.source_combo.findText(current)
        self.source_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.source_combo.blockSignals(False)
        self._on_source_change(self.source_combo.currentText())

    def _on_source_change(self, source: str):
        self.option_combo.clear()
        if source in _NO_OPTION_SOURCES:
            self.option_label.setText("(global)")
            self.option_combo.setEnabled(False)
        elif source == "US DOT Traffic":
            self.option_label.setText("State:")
            self.option_combo.addItems(list(DOT_STATES.keys()))
            self.option_combo.setEnabled(True)
        elif source in ("Windy Webcams", "OpenStreetMap"):
            self.option_label.setText("Country (opt):")
            self.option_combo.addItems(["All"] + list(COUNTRY_MAP.keys()))
            self.option_combo.setEnabled(True)
        elif self._custom_registry.get(source) is not None:
            self.option_label.setText("(no filter)")
            self.option_combo.setEnabled(False)
        else:
            self.option_label.setText("Country:")
            self.option_combo.addItems(list(COUNTRY_MAP.keys()))
            self.option_combo.setEnabled(True)

    def _start(self):
        source = self.source_combo.currentText()
        opt    = self.option_combo.currentText()

        kwargs: dict = {}
        if source == "Insecam":
            kwargs = {"country_code": COUNTRY_MAP.get(opt, "US"), "country_name": opt}
        elif source == "Windy Webcams":
            kwargs = {"country_code": COUNTRY_MAP.get(opt, "") if opt != "All" else ""}
        elif source == "OpenStreetMap":
            cc = COUNTRY_MAP.get(opt, "")
            kwargs = {"countries": [cc] if cc else None}
        elif source == "US DOT Traffic":
            kwargs = {"state_code": DOT_STATES.get(opt, "")}
        elif self._custom_registry.get(source) is not None:
            kwargs = {}

        self._log(f"[*] Starting {source} scan...", COLOR_DIM)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setFormat("Scanning...")
        self.scanner.start(source, **kwargs)

    def _stop(self):
        self.scanner.stop()
        self._log("[!] Stop requested — finishing current camera...", COLOR_ERROR)

    def _start_enrich(self):
        if self._enricher.is_running() or self.scanner.is_running():
            return
        # Use the currently-selected country filter if source is Insecam, else enrich all
        source = self.source_combo.currentText()
        opt    = self.option_combo.currentText()
        cc     = COUNTRY_MAP.get(opt, "") if source == "Insecam" and opt not in ("", "All") else ""
        count  = len(self.store.insecam_unenriched_ids(cc))
        if count == 0:
            self._log("[*] No unenriched Insecam cameras found — nothing to do.", COLOR_DIM)
            return
        self._log(f"[*] Starting Insecam enrichment — {count} cameras to enrich...", COLOR_DIM)
        self.start_btn.setEnabled(False)
        self.enrich_btn.setEnabled(False)
        self.enrich_stop_btn.setEnabled(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Enriching...")
        self._enricher.start(cc)

    def _stop_enrich(self):
        self._enricher.stop()
        self._log("[!] Enrich stop requested...", COLOR_ERROR)

    def _recategorize(self):
        if self.scanner.is_running() or self._enricher.is_running():
            return
        updated = self.store.recategorize_all()
        self._log(f"[+] Re-categorized {updated} cameras.", COLOR_NEW if updated else COLOR_DIM)

    def _log(self, text: str, color: str = COLOR_FG):
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.setTextColor(QColor(color))
        self.log.insertPlainText(text + "\n")
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _poll(self):
        try:
            while True:
                event = self.ui_queue.get_nowait()
                etype = event["type"]
                data  = event["data"]

                if etype == "log":
                    color = COLOR_ERROR if "[!]" in data else COLOR_NEW if "[+]" in data else COLOR_DIM
                    self._log(data, color)

                elif etype == "camera_found":
                    delta = data.get("_delta", "")
                    color = COLOR_NEW if delta == "new" else COLOR_DIM
                    self._log(
                        f"  [{delta.upper():9}] {data.get('url') or data.get('camera_name', '')}"
                        f"  | {data.get('category', '')} | {data.get('city', '')}",
                        color,
                    )

                elif etype == "progress":
                    done  = data["done"]
                    total = data["total"]
                    if total:
                        self.progress.setRange(0, total)
                        self.progress.setValue(done)
                        self.progress.setFormat(f"{done} / {total}")

                elif etype == "scan_complete":
                    self._on_complete(data)

                elif etype == "scan_error":
                    self._log(f"[!] Error: {data}", COLOR_ERROR)
                    self._reset_controls()

        except queue.Empty:
            pass

    def _on_complete(self, counts: dict):
        self.lbl_new.setText(f"New: {counts.get('new', 0)}")
        self.lbl_updated.setText(f"Updated: {counts.get('updated', 0)}")
        self.lbl_unchanged.setText(f"Unchanged: {counts.get('unchanged', 0)}")
        self.lbl_total.setText(f"Total: {counts.get('total', 0)}")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat(f"Complete — {counts.get('total', 0)} cameras")
        self._reset_controls()
        self._log("[+] Scan complete.", COLOR_NEW)

    def _reset_controls(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.enrich_btn.setEnabled(True)
        self.enrich_stop_btn.setEnabled(False)
        self.recat_btn.setEnabled(True)
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setFormat("Ready")
