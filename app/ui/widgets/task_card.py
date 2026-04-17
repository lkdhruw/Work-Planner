"""Task card widget shown in the main list."""

from datetime import date

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen, QFont
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                                QPushButton, QSizePolicy, QGraphicsOpacityEffect)

from .checkbox import AnimatedCheckbox
from ...models import Task


class TaskCard(QWidget):
    """A single task entry card with animated checkbox and chevron."""

    clicked         = Signal(int)          # task id
    completion_changed = Signal(int, bool) # task id, is_completed

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui()
        self.setMinimumHeight(64)

    # ── build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Animated checkbox
        self._cb = AnimatedCheckbox(self, size=22)
        self._cb.setChecked(self.task.is_completed, animate=False)
        self._cb.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self._cb, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Text block
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)

        self._title_lbl = QLabel(self.task.title)
        self._title_lbl.setObjectName("task_card_title")
        f = self._title_lbl.font()
        f.setPointSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        self._title_lbl.setFont(f)
        self._title_lbl.setWordWrap(True)
        # Limit to 3 lines via max height (line height × 3 + small padding)
        fm = self._title_lbl.fontMetrics()
        self._title_lbl.setMaximumHeight(fm.lineSpacing() * 3 + 4)
        if self.task.is_completed:
            self._strike(True)
        text_col.addWidget(self._title_lbl)

        # Meta row (profile badge + due date)
        meta = QHBoxLayout()
        meta.setSpacing(6)
        meta.setContentsMargins(0, 0, 0, 0)

        if self.task.profile:
            badge = QLabel(f"● {self.task.profile.name}")
            badge.setObjectName("chip_profile")
            badge.setStyleSheet(
                f"background: {self._hex_alpha(self.task.profile.color, 30)};"
                f"color: {self.task.profile.color};"
                "border-radius: 8px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
            meta.addWidget(badge)

        if self.task.due_date:
            try:
                d = date.fromisoformat(self.task.due_date)
                overdue = (d < date.today()) and not self.task.is_completed
                due_lbl = QLabel(f"📅 {d.strftime('%b %d')}")
                due_lbl.setObjectName("chip_overdue" if overdue else "chip_due")
                meta.addWidget(due_lbl)
            except ValueError:
                pass

        meta.addStretch()
        text_col.addLayout(meta)
        layout.addLayout(text_col, stretch=1)

        # Chevron
        chev = QLabel("›")
        chev.setStyleSheet("color: #334155; font-size: 20px; padding-right: 2px;")
        layout.addWidget(chev, alignment=Qt.AlignmentFlag.AlignVCenter)

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _hex_alpha(hex_color: str, alpha_int: int) -> str:
        """Return rgba() string from hex color and 0-255 alpha."""
        h = hex_color.lstrip('#')
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha_int})"
        except Exception:
            return "rgba(124,58,237,30)"

    def _strike(self, on: bool):
        f = self._title_lbl.font()
        f.setStrikeOut(on)
        self._title_lbl.setFont(f)
        self._title_lbl.setStyleSheet("color: #475569;" if on else "")

    def update_task(self, task: Task):
        self.task = task
        self._title_lbl.setText(task.title)
        self._strike(task.is_completed)
        self._cb.setChecked(task.is_completed, animate=False)

    # ── signals ────────────────────────────────────────────────────────────────

    def _on_checkbox_toggled(self, checked: bool):
        self._strike(checked)
        self.task.is_completed = checked
        self.completion_changed.emit(self.task.id, checked)

    # ── mouse ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Ignore clicks on the checkbox itself (handled separately)
            child = self.childAt(event.pos())
            if child is self._cb or (child is not None and child.parent() is self._cb):
                return
            self.clicked.emit(self.task.id)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    # ── paint background ───────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        if self._hovered:
            p.fillPath(path, QBrush(QColor(255, 255, 255, 14)))
            pen = QPen(QColor(124, 58, 237, 55), 1)
        else:
            p.fillPath(path, QBrush(QColor(255, 255, 255, 7)))
            pen = QPen(QColor(255, 255, 255, 11), 1)
        p.setPen(pen)
        p.drawPath(path)
        p.end()
