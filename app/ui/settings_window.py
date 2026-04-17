"""Settings window: transparency slider, font picker, always-on-top toggle."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSlider, QFontComboBox, QSpinBox,
                                QCheckBox, QWidget, QFrame, QSizePolicy)

from ..database import Database


class SettingsWindow(QDialog):
    """Settings window for transparency, font, and window behaviour."""

    def __init__(self, db: Database, main_window, parent=None):
        super().__init__(parent)
        self.db   = db
        self._mw  = main_window     # reference to MainWindow
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(320)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._build()
        self._load()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setStyleSheet(
            "background: rgb(13,17,38);"
            "border: 1px solid rgba(255,255,255,18);"
            "border-radius: 14px;"
        )
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        # ── title bar ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            "background: rgba(255,255,255,7);"
            "border-radius: 14px 14px 0 0;"
            "border-bottom: 1px solid rgba(255,255,255,12);"
        )
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("⚙  Settings")
        f = title.font(); f.setPointSize(14); f.setWeight(QFont.Weight.Bold)
        title.setFont(f)
        h_lay.addWidget(title, 1)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(28, 28)
        x_btn.setStyleSheet(
            "background: rgba(239,68,68,150); border: none; border-radius: 6px;"
            "color: white; font-size: 12px;"
        )
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.reject)
        h_lay.addWidget(x_btn)
        c_lay.addWidget(hdr)

        # ── body ───────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(16, 16, 16, 16)
        b_lay.setSpacing(16)

        # Transparency group
        b_lay.addWidget(self._group_label("TRANSPARENCY"))
        tr_row = QHBoxLayout()
        tr_row.setSpacing(12)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(40, 100)
        self._opacity_slider.setValue(92)
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        tr_row.addWidget(self._opacity_slider, 1)
        self._opacity_lbl = QLabel("92%")
        self._opacity_lbl.setFixedWidth(38)
        self._opacity_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._opacity_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        tr_row.addWidget(self._opacity_lbl)
        b_lay.addLayout(tr_row)

        # Font family group
        b_lay.addWidget(self._divider())
        b_lay.addWidget(self._group_label("TASK LIST FONT"))
        self._font_combo = QFontComboBox()
        self._font_combo.setEditable(False)
        self._font_combo.currentFontChanged.connect(self._on_font_changed)
        b_lay.addWidget(self._font_combo)

        # Font size
        fs_row = QHBoxLayout()
        fs_row.setSpacing(10)
        fs_row.addWidget(QLabel("Size:"))
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 24)
        self._font_size_spin.setValue(13)
        self._font_size_spin.setSuffix(" pt")
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        fs_row.addWidget(self._font_size_spin)
        fs_row.addStretch()
        b_lay.addLayout(fs_row)

        # Preview label
        self._preview_lbl = QLabel("The quick brown fox jumps over the lazy dog")
        self._preview_lbl.setWordWrap(True)
        self._preview_lbl.setStyleSheet(
            "color: #94A3B8; background: rgba(255,255,255,5);"
            "border-radius: 8px; padding: 8px 10px;"
        )
        b_lay.addWidget(self._preview_lbl)

        # Window behaviour group
        b_lay.addWidget(self._divider())
        b_lay.addWidget(self._group_label("WINDOW BEHAVIOUR"))
        self._always_top_cb = QCheckBox("Always on top of other windows")
        self._always_top_cb.toggled.connect(self._on_always_top)
        b_lay.addWidget(self._always_top_cb)

        # ── Server Sync ────────────────────────────────────────────────────────
        b_lay.addWidget(self._divider())
        b_lay.addWidget(self._group_label("SERVER SYNC"))
        sync_row = QHBoxLayout()
        sync_row.setSpacing(10)

        self._sync_status_lbl = QLabel("Not signed in")
        self._sync_status_lbl.setStyleSheet(
            "color: #64748B; font-size: 12px;"
        )
        sync_row.addWidget(self._sync_status_lbl, 1)

        self._signin_btn = QPushButton("Sign In")
        self._signin_btn.setObjectName("btn_primary")
        self._signin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._signin_btn.setFixedHeight(32)
        # Placeholder — actual auth will be wired in a future update
        self._signin_btn.clicked.connect(self._on_signin_clicked)
        sync_row.addWidget(self._signin_btn)
        b_lay.addLayout(sync_row)

        # Buttons
        b_lay.addStretch()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        b_lay.addLayout(btn_row)

        c_lay.addWidget(body)

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _group_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("label_section")
        return lbl

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background: rgba(255,255,255,10); max-height:1px; margin: 2px 0;")
        return f

    # ── load / save ────────────────────────────────────────────────────────────

    def _load(self):
        opacity = int(self.db.get_setting('opacity', '92'))
        self._opacity_slider.setValue(opacity)

        font_family = self.db.get_setting('font_family', '')
        if font_family:
            self._font_combo.setCurrentFont(QFont(font_family))

        font_size = int(self.db.get_setting('font_size', '13'))
        self._font_size_spin.setValue(font_size)
        self._update_preview()

        always_top = self.db.get_setting('always_on_top', '0') == '1'
        self._always_top_cb.setChecked(always_top)

    # ── callbacks ──────────────────────────────────────────────────────────────

    def _on_opacity_changed(self, value: int):
        self._opacity_lbl.setText(f"{value}%")
        self._mw.setWindowOpacity(value / 100)
        self.db.set_setting('opacity', str(value))

    def _on_font_changed(self, font: QFont):
        self.db.set_setting('font_family', font.family())
        self._update_preview()
        self._apply_font_to_list()

    def _on_font_size_changed(self, size: int):
        self.db.set_setting('font_size', str(size))
        self._update_preview()
        self._apply_font_to_list()

    def _on_always_top(self, checked: bool):
        self.db.set_setting('always_on_top', '1' if checked else '0')
        if hasattr(self._mw, 'set_always_on_top'):
            self._mw.set_always_on_top(checked)

    def _update_preview(self):
        font = self._font_combo.currentFont()
        font.setPointSize(self._font_size_spin.value())
        self._preview_lbl.setFont(font)

    def _apply_font_to_list(self):
        if hasattr(self._mw, 'apply_font'):
            self._mw.apply_font(
                self._font_combo.currentFont().family(),
                self._font_size_spin.value()
            )

    def _on_signin_clicked(self):
        """Placeholder — browser-based sign-in flow to be implemented."""
        # Future: open browser for DRF token auth, store token in settings
        pass
