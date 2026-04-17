"""Profile creation dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QWidget, QButtonGroup,
                                QRadioButton, QSizePolicy)

from ..database import Database

COLORS = [
    ('#7C3AED', 'Indigo'),
    ('#0EA5E9', 'Sky'),
    ('#10B981', 'Emerald'),
    ('#F59E0B', 'Amber'),
    ('#EF4444', 'Red'),
    ('#EC4899', 'Pink'),
    ('#8B5CF6', 'Violet'),
    ('#06B6D4', 'Cyan'),
]


class ColorDot(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(28, 28)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply(False)

    def setActive(self, active: bool):
        self._apply(active)

    def _apply(self, active: bool):
        ring = f"border: 2px solid white;" if active else "border: 2px solid transparent;"
        self.setStyleSheet(
            f"background: {self.color}; border-radius: 14px; {ring}"
        )


class ProfileForm(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("New Profile")
        self.setModal(True)
        self.setMinimumWidth(300)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._selected_color = COLORS[0][0]
        self._color_dots: list[ColorDot] = []
        self._build()

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

        # header
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            "background: rgba(255,255,255,7);"
            "border-radius: 14px 14px 0 0;"
            "border-bottom: 1px solid rgba(255,255,255,12);"
        )
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("🗂  New Profile")
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

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(16, 16, 16, 16)
        b_lay.setSpacing(12)

        # Name
        name_lbl = QLabel("PROFILE NAME")
        name_lbl.setObjectName("label_section")
        b_lay.addWidget(name_lbl)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Work, Personal, Study…")
        b_lay.addWidget(self._name_edit)

        # Color
        color_lbl = QLabel("COLOR")
        color_lbl.setObjectName("label_section")
        b_lay.addWidget(color_lbl)
        dot_row = QHBoxLayout()
        dot_row.setSpacing(8)
        for i, (color, name) in enumerate(COLORS):
            dot = ColorDot(color)
            dot.setToolTip(name)
            dot.setActive(i == 0)
            dot.clicked.connect(lambda checked=False, c=color, d=dot: self._select_color(c, d))
            dot_row.addWidget(dot)
            self._color_dots.append(dot)
        dot_row.addStretch()
        b_lay.addLayout(dot_row)

        # Buttons
        b_lay.addStretch()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Create Profile")
        save.setObjectName("btn_primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        b_lay.addLayout(btn_row)

        c_lay.addWidget(body)

    def _select_color(self, color: str, clicked_dot: ColorDot):
        self._selected_color = color
        for dot in self._color_dots:
            dot.setActive(dot is clicked_dot)

    def _on_save(self):
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setPlaceholderText("Name is required!")
            self._name_edit.setStyleSheet("border-color: rgba(239,68,68,180);")
            return
        self.db.create_profile(name, self._selected_color)
        self.accept()
