"""Animated custom checkbox widget."""

from PySide6.QtCore import (Qt, QPropertyAnimation, QEasingCurve,
                             QParallelAnimationGroup, QRectF, QPointF,
                             Property, Signal, QTimer)
from PySide6.QtGui import (QPainter, QPainterPath, QPen, QBrush,
                            QLinearGradient, QColor)
from PySide6.QtWidgets import QWidget


class AnimatedCheckbox(QWidget):
    """Beautifully animated checkbox with gradient fill and stroke checkmark."""

    toggled = Signal(bool)

    # ── properties used by QPropertyAnimation ─────────────────────────────────

    def _get_fill(self): return self._fill
    def _set_fill(self, v):
        self._fill = v
        self.update()

    def _get_check(self): return self._check
    def _set_check(self, v):
        self._check = v
        self.update()

    fill_progress  = Property(float, _get_fill,  _set_fill)
    check_progress = Property(float, _get_check, _set_check)

    # ── init ──────────────────────────────────────────────────────────────────

    def __init__(self, parent=None, size: int = 22):
        super().__init__(parent)
        self._checked = False
        self._fill    = 0.0
        self._check   = 0.0

        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim_fill  = QPropertyAnimation(self, b'fill_progress')
        self._anim_fill.setDuration(180)
        self._anim_fill.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_check = QPropertyAnimation(self, b'check_progress')
        self._anim_check.setDuration(220)
        self._anim_check.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── public API ────────────────────────────────────────────────────────────

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True):
        if self._checked == checked:
            return
        self._checked = checked

        if checked:
            self._anim_check.stop()
            self._anim_fill.stop()
            self._anim_fill.setStartValue(self._fill)
            self._anim_fill.setEndValue(1.0)
            self._anim_fill.start()
            QTimer.singleShot(80, self._animate_check_in)
        else:
            self._anim_check.stop()
            self._anim_fill.stop()
            self._anim_check.setStartValue(self._check)
            self._anim_check.setEndValue(0.0)
            self._anim_check.start()
            self._anim_fill.setStartValue(self._fill)
            self._anim_fill.setEndValue(0.0)
            self._anim_fill.start()

    def _animate_check_in(self):
        self._anim_check.setStartValue(0.0)
        self._anim_check.setEndValue(1.0)
        self._anim_check.start()

    # ── events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = 5.0
        rect = QRectF(2, 2, w - 4, h - 4)

        # — background / fill ——————————————————————————————————————————————————
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)

        if self._fill > 0:
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, QColor(124, 58, 237, int(255 * self._fill)))
            grad.setColorAt(1, QColor(16, 185, 129, int(255 * self._fill)))
            p.fillPath(path, QBrush(grad))

        # — border ——————————————————————————————————————————————————————————————
        border_alpha = max(0, int(255 * (1.0 - self._fill * 0.85)))
        pen = QPen(QColor(148, 163, 184, border_alpha), 1.8)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # — checkmark —————————————————————————————————————————————————————————
        if self._check > 0:
            pen2 = QPen(QColor(255, 255, 255, min(255, int(255 * self._check * 1.5))),
                        2.2, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen2)
            p.setBrush(Qt.BrushStyle.NoBrush)

            # checkmark: start → mid → end
            s = QPointF(w * 0.22, h * 0.50)
            m = QPointF(w * 0.42, h * 0.70)
            e = QPointF(w * 0.80, h * 0.28)

            if self._check <= 0.5:
                t = self._check * 2
                cur = QPointF(s.x() + (m.x() - s.x()) * t,
                               s.y() + (m.y() - s.y()) * t)
                p.drawLine(s, cur)
            else:
                t   = (self._check - 0.5) * 2
                cur = QPointF(m.x() + (e.x() - m.x()) * t,
                               m.y() + (e.y() - m.y()) * t)
                p.drawLine(s, m)
                p.drawLine(m, cur)

        p.end()
