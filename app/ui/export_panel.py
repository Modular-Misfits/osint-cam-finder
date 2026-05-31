from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from app.core.schema import CATEGORIES
from app.db.store import Store


class ExportPanel(QWidget):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 30)

        box = QGroupBox("Export Cameras to JSON")
        lay = QVBoxLayout(box)
        lay.setSpacing(10)

        # Source
        r = QHBoxLayout()
        r.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(160)
        r.addWidget(self.source_combo)
        r.addStretch()
        lay.addLayout(r)

        # Categories
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Categories:"))
        self.cat_checks: dict[str, QCheckBox] = {}
        for cat in CATEGORIES:
            cb = QCheckBox(cat)
            self.cat_checks[cat] = cb
            r2.addWidget(cb)
        r2.addStretch()
        lay.addLayout(r2)

        # Country + Status
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Country:"))
        self.country_combo = QComboBox()
        self.country_combo.setMinimumWidth(70)
        r3.addWidget(self.country_combo)
        r3.addSpacing(16)
        r3.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["", "active", "offline", "unknown"])
        self.status_combo.setCurrentText("active")
        r3.addWidget(self.status_combo)
        r3.addStretch()
        lay.addLayout(r3)

        # Preview count
        r4 = QHBoxLayout()
        preview_btn = QPushButton("Preview Count")
        preview_btn.clicked.connect(self._preview_count)
        self.preview_lbl = QLabel("")
        self.preview_lbl.setStyleSheet("color: #8E8E8E; font-size: 9pt;")
        r4.addWidget(preview_btn)
        r4.addWidget(self.preview_lbl)
        r4.addStretch()
        lay.addLayout(r4)

        # Output path
        r5 = QHBoxLayout()
        r5.addWidget(QLabel("Output file:"))
        self.path_edit = QLineEdit("cameras_export.json")
        r5.addWidget(self.path_edit, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        r5.addWidget(browse_btn)
        lay.addLayout(r5)

        # Export button + result
        r6 = QHBoxLayout()
        export_btn = QPushButton("Export JSON")
        export_btn.clicked.connect(self._export)
        self.result_lbl = QLabel("")
        self.result_lbl.setStyleSheet("color: #6ee7b7; font-weight: 600; font-size: 9pt;")
        r6.addWidget(export_btn)
        r6.addWidget(self.result_lbl)
        r6.addStretch()
        lay.addLayout(r6)

        outer.addWidget(box)
        outer.addStretch()

        self.refresh_dropdowns()

    def refresh_dropdowns(self):
        sources   = [""] + self.store.sources()
        countries = [""] + self.store.country_codes()

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

    def _query_kwargs(self) -> dict:
        cats = [cat for cat, cb in self.cat_checks.items() if cb.isChecked()]
        return {
            "source":       self.source_combo.currentText(),
            "categories":   cats or None,
            "country_code": self.country_combo.currentText(),
            "status":       self.status_combo.currentText(),
        }

    def _preview_count(self):
        self.refresh_dropdowns()
        n = self.store.count(**self._query_kwargs())
        self.preview_lbl.setText(f"{n:,} cameras match current filters")

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", self.path_edit.text(),
            "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self.path_edit.setText(path)

    def _export(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Export", "Please specify an output file path.")
            return
        self.result_lbl.setText("Exporting...")
        try:
            n = self.store.export_json(path, **self._query_kwargs())
            self.result_lbl.setText(f"Exported {n:,} cameras → {path}")
        except Exception as e:
            self.result_lbl.setText("")
            QMessageBox.critical(self, "Export Failed", str(e))
