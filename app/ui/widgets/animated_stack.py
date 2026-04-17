"""Sliding stacked widget with left/right page transitions."""

from PySide6.QtCore import (QPropertyAnimation, QParallelAnimationGroup,
                             QEasingCurve, QRect, Signal)
from PySide6.QtWidgets import QWidget, QStackedWidget


class SlidingStack(QWidget):
    """Two-page container that slides pages in/out horizontally."""

    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._current = 0
        self._animating = False
        self._anim_group: QParallelAnimationGroup | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def addWidget(self, widget: QWidget) -> int:
        idx = len(self._pages)
        widget.setParent(self)
        if idx == 0:
            widget.setGeometry(0, 0, self.width(), self.height())
            widget.show()
        else:
            widget.setGeometry(self.width(), 0, self.width(), self.height())
            widget.hide()
        self._pages.append(widget)
        return idx

    def currentIndex(self) -> int:
        return self._current

    def currentWidget(self) -> QWidget | None:
        return self._pages[self._current] if self._pages else None

    def widget(self, index: int) -> QWidget | None:
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return None

    def slideTo(self, index: int, direction: str = 'left'):
        """Animate to page *index*.  direction='left'  means new page enters from right."""
        if index == self._current or self._animating or not self._pages:
            return
        if not (0 <= index < len(self._pages)):
            return

        self._animating = True
        old_w = self._pages[self._current]
        new_w = self._pages[index]
        w = self.width()
        h = self.height()

        # Position incoming page off-screen
        if direction == 'left':
            new_w.setGeometry(w, 0, w, h)
            old_exit = QRect(-w, 0, w, h)
            new_enter = QRect(0, 0, w, h)
        else:
            new_w.setGeometry(-w, 0, w, h)
            old_exit  = QRect(w, 0, w, h)
            new_enter = QRect(0, 0, w, h)

        new_w.show()
        new_w.raise_()

        a_old = QPropertyAnimation(old_w, b'geometry')
        a_old.setDuration(320)
        a_old.setStartValue(old_w.geometry())
        a_old.setEndValue(old_exit)
        a_old.setEasingCurve(QEasingCurve.Type.InOutCubic)

        a_new = QPropertyAnimation(new_w, b'geometry')
        a_new.setDuration(320)
        a_new.setStartValue(new_w.geometry())
        a_new.setEndValue(new_enter)
        a_new.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(a_old)
        self._anim_group.addAnimation(a_new)
        self._anim_group.finished.connect(
            lambda: self._on_done(old_w, index)
        )
        self._anim_group.start()

    def _on_done(self, old_w: QWidget, new_index: int):
        old_w.hide()
        old_w.setGeometry(self.width(), 0, self.width(), self.height())
        self._current = new_index
        self._animating = False
        self._anim_group = None
        self.page_changed.emit(new_index)

    # ── resize ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        for i, page in enumerate(self._pages):
            if i == self._current:
                page.setGeometry(0, 0, w, h)
            else:
                page.setGeometry(w, 0, w, h)
                page.hide()
