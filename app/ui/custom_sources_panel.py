import json

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.custom_sources import CustomSourceRegistry, run_custom_source
from app.core.env_loader import get_key, save_env

C_GREEN  = "#6ee7b7"
C_RED    = "#E66B66"
C_TEXT3  = "#8E8E8E"

_PAG_STYLES = ["none", "offset", "page", "cursor"]

# Fields to show in the mapping table (exclude 'source' which is always the source name)
_MAP_FIELDS = [
    "camera_id", "camera_name", "url", "camera_type", "category",
    "latitude", "longitude", "country", "country_code", "state", "city", "region",
]


class _TestWorker(QThread):
    result = pyqtSignal(str)

    def __init__(self, defn: dict):
        super().__init__()
        self._defn = defn

    def run(self):
        session = requests.Session()
        cameras = []
        logs = []
        try:
            for cam, msg in run_custom_source(self._defn, session, max_preview=10):
                logs.append(msg)
                if cam:
                    cameras.append(dict(cam))
        except Exception as e:
            logs.append(f"[!] Error: {e}")

        lines = logs + ["", f"--- {len(cameras)} cameras ---", ""]
        if cameras:
            lines.append(json.dumps(cameras, indent=2))
        self.result.emit("\n".join(lines))


class CustomSourcesPanel(QWidget):
    def __init__(self, registry: CustomSourceRegistry):
        super().__init__()
        self._registry  = registry
        self._editing   = ""   # name of source currently loaded in form, "" = new
        self._worker: _TestWorker | None = None
        self._build()
        self._refresh_list()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        # Left pane
        left = QWidget()
        left.setFixedWidth(220)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(10, 10, 6, 10)

        lbl = QLabel("Custom Sources")
        lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
        left_lay.addWidget(lbl)

        self._list = QListWidget()
        self._list.currentTextChanged.connect(self._on_list_select)
        left_lay.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self._new_source)
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._delete_source)
        self._del_btn.setEnabled(False)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(self._del_btn)
        left_lay.addLayout(btn_row)

        splitter.addWidget(left)

        # Right pane (scrollable)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(right_scroll.Shape.NoFrame)
        right_inner = QWidget()
        right_lay   = QVBoxLayout(right_inner)
        right_lay.setContentsMargins(10, 10, 16, 10)
        right_lay.setSpacing(10)

        right_lay.addWidget(self._build_endpoint_box())
        right_lay.addWidget(self._build_auth_box())
        right_lay.addWidget(self._build_pagination_box())
        right_lay.addWidget(self._build_mapping_box())
        right_lay.addLayout(self._build_action_row())
        right_lay.addWidget(self._build_preview_box())
        right_lay.addStretch()

        right_scroll.setWidget(right_inner)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _build_endpoint_box(self) -> QGroupBox:
        box  = QGroupBox("Endpoint")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self._name_edit    = QLineEdit()
        self._name_edit.setPlaceholderText("Unique display name")
        self._enabled_chk  = QCheckBox("Enabled")
        self._enabled_chk.setChecked(True)
        self._url_edit     = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.example.com/cameras")
        self._method_combo = QComboBox()
        self._method_combo.addItems(["GET", "POST"])

        form.addRow("Name:", self._name_edit)
        form.addRow("", self._enabled_chk)
        form.addRow("Endpoint URL:", self._url_edit)
        form.addRow("Method:", self._method_combo)
        return box

    def _build_auth_box(self) -> QGroupBox:
        box  = QGroupBox("Authentication & Request")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self._headers_edit = QPlainTextEdit()
        self._headers_edit.setPlaceholderText("Authorization: Bearer {MY_KEY}\nAccept: application/json")
        self._headers_edit.setFixedHeight(72)

        self._params_edit  = QPlainTextEdit()
        self._params_edit.setPlaceholderText("limit=100\nformat=json")
        self._params_edit.setFixedHeight(56)

        self._apikey_var   = QLineEdit()
        self._apikey_var.setPlaceholderText("MY_SOURCE_API_KEY")
        self._apikey_val   = QLineEdit()
        self._apikey_val.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_var.textChanged.connect(self._on_apikey_var_change)

        apikey_row = QHBoxLayout()
        apikey_row.addWidget(self._apikey_val)
        save_key_btn = QPushButton("Save Key")
        save_key_btn.setFixedWidth(80)
        save_key_btn.clicked.connect(self._save_api_key)
        apikey_row.addWidget(save_key_btn)

        form.addRow("Headers:", self._headers_edit)
        form.addRow("Params:", self._params_edit)
        form.addRow("API key env var:", self._apikey_var)
        form.addRow("API key value:", apikey_row)

        hint = QLabel("Use {ENV_VAR} in URL/headers/params to inject key values at scan time.")
        hint.setStyleSheet(f"color: {C_TEXT3}; font-size: 11px;")
        hint.setWordWrap(True)
        box.layout().addRow("", hint)  # type: ignore[union-attr]
        return box

    def _build_pagination_box(self) -> QGroupBox:
        box  = QGroupBox("Pagination")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self._pag_style    = QComboBox()
        self._pag_style.addItems(_PAG_STYLES)
        self._pag_style.currentTextChanged.connect(self._on_pag_style_change)

        self._pag_param    = QLineEdit()
        self._pag_param.setPlaceholderText("offset")
        self._pag_size     = QSpinBox()
        self._pag_size.setRange(1, 10000)
        self._pag_size.setValue(100)
        self._pag_max      = QSpinBox()
        self._pag_max.setRange(1, 10000)
        self._pag_max.setValue(200)
        self._cursor_path  = QLineEdit()
        self._cursor_path.setPlaceholderText("next_cursor")
        self._cursor_param = QLineEdit()
        self._cursor_param.setPlaceholderText("cursor")

        self._pag_param_row    = (QLabel("Param name:"),    self._pag_param)
        self._pag_size_row     = (QLabel("Page size:"),     self._pag_size)
        self._cursor_path_row  = (QLabel("Cursor path:"),   self._cursor_path)
        self._cursor_param_row = (QLabel("Cursor param:"),  self._cursor_param)

        form.addRow("Style:", self._pag_style)
        form.addRow(*self._pag_param_row)
        form.addRow(*self._pag_size_row)
        form.addRow(QLabel("Max pages:"), self._pag_max)
        form.addRow(*self._cursor_path_row)
        form.addRow(*self._cursor_param_row)

        self._on_pag_style_change("none")
        return box

    def _build_mapping_box(self) -> QGroupBox:
        box = QGroupBox("Response Mapping")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 12, 12, 12)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Cameras path:"))
        self._cam_path = QLineEdit()
        self._cam_path.setPlaceholderText("data.cameras  (leave empty if response IS the list)")
        cam_row.addWidget(self._cam_path)
        lay.addLayout(cam_row)

        self._map_table = QTableWidget(len(_MAP_FIELDS), 3)
        self._map_table.setHorizontalHeaderLabels(["Camera Field", "JSON Path (jmespath)", "Default Value"])
        self._map_table.verticalHeader().setVisible(False)
        self._map_table.horizontalHeader().setStretchLastSection(True)
        self._map_table.setColumnWidth(0, 120)
        self._map_table.setColumnWidth(1, 220)
        self._map_table.setColumnWidth(2, 140)
        self._map_table.setFixedHeight(min(len(_MAP_FIELDS) * 28 + 30, 380))

        for i, field in enumerate(_MAP_FIELDS):
            label_item = QTableWidgetItem(field)
            label_item.setFlags(label_item.flags() & ~label_item.flags().ItemIsEditable)  # type: ignore[attr-defined]
            self._map_table.setItem(i, 0, label_item)
            self._map_table.setItem(i, 1, QTableWidgetItem(""))
            self._map_table.setItem(i, 2, QTableWidgetItem(""))

        lay.addWidget(self._map_table)
        return box

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._test_btn = QPushButton("Test")
        self._test_btn.clicked.connect(self._test_source)
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("accent")
        self._save_btn.clicked.connect(self._save_source)
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)

        row.addWidget(self._test_btn)
        row.addWidget(self._save_btn)
        row.addWidget(self._status_lbl, stretch=1)
        return row

    def _build_preview_box(self) -> QGroupBox:
        box = QGroupBox("Test Preview")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 8, 12, 12)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(200)
        self._preview.setPlaceholderText("Click 'Test' to preview the first 10 cameras from this source.")
        lay.addWidget(self._preview)
        return box

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_pag_style_change(self, style: str):
        show_param   = style in ("offset", "page")
        show_size    = style == "offset"
        show_cursor  = style == "cursor"

        for lbl, widget in (self._pag_param_row, self._pag_size_row):
            lbl.setVisible(show_param)
            widget.setVisible(show_param)
        self._pag_size.setVisible(show_size)
        for lbl, widget in (self._cursor_path_row, self._cursor_param_row):
            lbl.setVisible(show_cursor)
            widget.setVisible(show_cursor)

    def _on_apikey_var_change(self, text: str):
        var = text.strip()
        if var:
            self._apikey_val.setText(get_key(var))

    def _on_list_select(self, name: str):
        if not name:
            return
        defn = self._registry.get(name)
        if defn:
            self._load_form(defn)
            self._editing = name
            self._del_btn.setEnabled(True)

    # ── List management ───────────────────────────────────────────────────────

    def _refresh_list(self):
        current = self._list.currentItem()
        cur_name = current.text() if current else ""
        self._list.blockSignals(True)
        self._list.clear()
        for s in self._registry.all():
            self._list.addItem(s["name"])
        self._list.blockSignals(False)
        # Restore selection
        for i in range(self._list.count()):
            if self._list.item(i).text() == cur_name:
                self._list.setCurrentRow(i)
                break

    def _new_source(self):
        self._editing = ""
        self._del_btn.setEnabled(False)
        self._clear_form()
        self._list.clearSelection()

    def _delete_source(self):
        name = self._editing
        if not name:
            return
        reply = QMessageBox.question(
            self, "Delete Source",
            f"Delete custom source '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._registry.delete(name)
            self._editing = ""
            self._del_btn.setEnabled(False)
            self._clear_form()
            self._refresh_list()
            self._set_status("Deleted.", C_TEXT3)

    # ── Form helpers ──────────────────────────────────────────────────────────

    def _clear_form(self):
        self._name_edit.clear()
        self._enabled_chk.setChecked(True)
        self._url_edit.clear()
        self._method_combo.setCurrentIndex(0)
        self._headers_edit.clear()
        self._params_edit.clear()
        self._pag_style.setCurrentIndex(0)
        self._pag_param.clear()
        self._pag_size.setValue(100)
        self._pag_max.setValue(200)
        self._cursor_path.clear()
        self._cursor_param.clear()
        self._cam_path.clear()
        self._apikey_var.clear()
        self._apikey_val.clear()
        for i in range(len(_MAP_FIELDS)):
            self._map_table.setItem(i, 1, QTableWidgetItem(""))
            self._map_table.setItem(i, 2, QTableWidgetItem(""))
        self._status_lbl.clear()
        self._preview.clear()

    def _load_form(self, defn: dict):
        self._name_edit.setText(defn.get("name", ""))
        self._enabled_chk.setChecked(defn.get("enabled", True))
        self._url_edit.setText(defn.get("endpoint", ""))
        method = defn.get("method", "GET")
        idx = self._method_combo.findText(method)
        self._method_combo.setCurrentIndex(idx if idx >= 0 else 0)

        # Headers & params
        headers = defn.get("headers", {})
        self._headers_edit.setPlainText("\n".join(f"{k}: {v}" for k, v in headers.items()))
        params = defn.get("params", {})
        self._params_edit.setPlainText("\n".join(f"{k}={v}" for k, v in params.items()))

        # Pagination
        pag = defn.get("pagination", {})
        style = pag.get("style", "none")
        si = self._pag_style.findText(style)
        self._pag_style.setCurrentIndex(si if si >= 0 else 0)
        self._pag_param.setText(pag.get("param_name", ""))
        self._pag_size.setValue(int(pag.get("page_size", 100)))
        self._pag_max.setValue(int(pag.get("max_pages", 200)))
        self._cursor_path.setText(pag.get("cursor_path", ""))
        self._cursor_param.setText(pag.get("cursor_param", ""))

        # Mapping
        self._cam_path.setText(defn.get("cameras_path", ""))
        field_map = defn.get("field_map", {})
        defaults  = defn.get("defaults", {})
        for i, field in enumerate(_MAP_FIELDS):
            self._map_table.setItem(i, 1, QTableWidgetItem(field_map.get(field, "")))
            self._map_table.setItem(i, 2, QTableWidgetItem(str(defaults.get(field, ""))))

        # API key
        env_var = defn.get("api_key_env_var", "")
        self._apikey_var.setText(env_var)

        self._status_lbl.clear()

    def _form_to_defn(self) -> dict:
        # Parse headers
        headers: dict[str, str] = {}
        for line in self._headers_edit.toPlainText().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()

        # Parse params
        params: dict[str, str] = {}
        for line in self._params_edit.toPlainText().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                params[k.strip()] = v.strip()

        # Pagination
        style = self._pag_style.currentText()
        pag: dict = {"style": style, "max_pages": self._pag_max.value()}
        if style in ("offset", "page"):
            pag["param_name"] = self._pag_param.text().strip()
        if style == "offset":
            pag["page_size"] = self._pag_size.value()
        if style == "cursor":
            pag["cursor_path"]  = self._cursor_path.text().strip()
            pag["cursor_param"] = self._cursor_param.text().strip()

        # Field map & defaults
        field_map: dict[str, str] = {}
        defaults:  dict[str, str] = {}
        for i, field in enumerate(_MAP_FIELDS):
            path    = (self._map_table.item(i, 1) or QTableWidgetItem()).text().strip()
            default = (self._map_table.item(i, 2) or QTableWidgetItem()).text().strip()
            if path:
                field_map[field] = path
            if default:
                defaults[field] = default

        return {
            "name":            self._name_edit.text().strip(),
            "enabled":         self._enabled_chk.isChecked(),
            "endpoint":        self._url_edit.text().strip(),
            "method":          self._method_combo.currentText(),
            "headers":         headers,
            "params":          params,
            "pagination":      pag,
            "cameras_path":    self._cam_path.text().strip(),
            "field_map":       field_map,
            "defaults":        defaults,
            "api_key_env_var": self._apikey_var.text().strip(),
        }

    # ── Actions ───────────────────────────────────────────────────────────────

    def _save_api_key(self):
        var = self._apikey_var.text().strip()
        val = self._apikey_val.text().strip()
        if not var:
            self._set_status("Enter env var name first.", C_RED)
            return
        save_env({var: val})
        self._set_status(f"Key saved to .env as {var}.", C_GREEN)

    def _test_source(self):
        defn   = self._form_to_defn()
        errors = self._registry.validate(defn, original_name=self._editing)
        if errors:
            self._set_status("\n".join(errors), C_RED)
            return

        self._preview.setPlainText("Running test fetch...")
        self._test_btn.setEnabled(False)
        self._worker = _TestWorker(defn)
        self._worker.result.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, text: str):
        self._preview.setPlainText(text)
        self._test_btn.setEnabled(True)
        self._worker = None

    def _save_source(self):
        defn   = self._form_to_defn()
        errors = self._registry.validate(defn, original_name=self._editing)
        if errors:
            self._set_status("\n".join(errors), C_RED)
            return
        try:
            if self._editing:
                self._registry.update(self._editing, defn)
            else:
                self._registry.add(defn)
            self._editing = defn["name"]
            self._del_btn.setEnabled(True)
            self._refresh_list()
            self._set_status("Saved.", C_GREEN)
        except ValueError as e:
            self._set_status(str(e), C_RED)

    def _set_status(self, msg: str, color: str = C_TEXT3):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
