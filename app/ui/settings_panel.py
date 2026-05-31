from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.env_loader import get_key, save_env

C_TEXT2 = "#A1A1A1"
C_TEXT3 = "#8E8E8E"
C_GREEN = "#6ee7b7"
C_ACCENT = "#E66B66"

# Registry of all API keys the app uses.
# Each entry: (env_var_name, display_label, hint_text, is_secret)
API_KEYS = [
    ("WINDY_API_KEY",  "Windy Webcams API Key",  "Get free key at windy.com/api/webcams", True),
]


class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._fields: dict[str, QLineEdit] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(20)

        # ── API Keys ──────────────────────────────────────────────────────────
        keys_box = QGroupBox("API Keys")
        form = QFormLayout(keys_box)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        for env_var, label, hint, is_secret in API_KEYS:
            field = QLineEdit()
            field.setText(get_key(env_var))
            if is_secret:
                field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(hint)
            field.setMinimumWidth(360)

            row = QHBoxLayout()
            row.addWidget(field)

            if is_secret:
                toggle = QPushButton("Show")
                toggle.setFixedWidth(54)
                toggle.setCheckable(True)
                toggle.toggled.connect(
                    lambda checked, f=field, b=toggle: (
                        f.setEchoMode(
                            QLineEdit.EchoMode.Normal if checked
                            else QLineEdit.EchoMode.Password
                        ),
                        b.setText("Hide" if checked else "Show"),
                    )
                )
                row.addWidget(toggle)

            hint_lbl = QLabel(hint)
            hint_lbl.setStyleSheet(f"color: {C_TEXT3}; font-size: 11px;")

            cell = QWidget()
            cell_lay = QVBoxLayout(cell)
            cell_lay.setContentsMargins(0, 0, 0, 0)
            cell_lay.setSpacing(2)
            cell_lay.addLayout(row)
            cell_lay.addWidget(hint_lbl)

            form.addRow(label + ":", cell)
            self._fields[env_var] = field

        root.addWidget(keys_box)

        # ── Save button ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("accent")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._save)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {C_GREEN}; font-size: 12px;")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._status_lbl)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Note ─────────────────────────────────────────────────────────────
        note = QLabel(
            "Keys are saved to a local .env file in the project directory and never uploaded."
        )
        note.setStyleSheet(f"color: {C_TEXT3}; font-size: 11px;")
        note.setWordWrap(True)
        root.addWidget(note)

        root.addStretch()

    def _save(self):
        keys = {env_var: self._fields[env_var].text().strip() for env_var in self._fields}
        save_env(keys)
        self._status_lbl.setText("Saved.")
        # Clear status after 3 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))
