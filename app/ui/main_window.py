"""Main application window — frameless, semi-transparent sidebar."""

import sys

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QPushButton, QSizePolicy, QApplication)

from .widgets.animated_stack import SlidingStack
from .task_list import TaskListView
from .task_detail import TaskDetailView
from ..database import Database
from ..notifier import NotificationScheduler


class MainWindow(QMainWindow):
    """Frameless, translucent sidebar window."""

    def __init__(self, db: Database, scheduler: NotificationScheduler):
        super().__init__()
        self.db        = db
        self.scheduler = scheduler
        self._drag_pos = QPoint()
        self._dragging = False

        self._setup_window()
        self._build_ui()
        self._load_settings()

    # ── window setup ───────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Work Planner")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        # Initial position: right edge of primary screen
        screen = QApplication.primaryScreen().availableGeometry()
        w = 340
        h = min(screen.height(), 780)
        x = screen.right() - w - 12
        y = screen.top() + (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)

    # ── build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Central transparent wrapper
        self._root = QWidget(self)
        self._root.setObjectName("main_container")
        self.setCentralWidget(self._root)

        root_lay = QVBoxLayout(self._root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Custom title bar ───────────────────────────────────────────────────
        self._title_bar = QWidget()
        self._title_bar.setObjectName("title_bar")
        self._title_bar.setFixedHeight(46)
        tb_lay = QHBoxLayout(self._title_bar)
        tb_lay.setContentsMargins(10, 0, 10, 0)
        tb_lay.setSpacing(6)

        # macOS-style dots
        self._btn_close    = QPushButton()
        self._btn_minimize = QPushButton()
        self._btn_close.setObjectName("btn_close")
        self._btn_minimize.setObjectName("btn_minimize")
        self._btn_close.setToolTip("Close")
        self._btn_minimize.setToolTip("Minimize")
        self._btn_close.clicked.connect(self.close)
        self._btn_minimize.clicked.connect(self.showMinimized)
        tb_lay.addWidget(self._btn_close)
        tb_lay.addWidget(self._btn_minimize)
        tb_lay.addSpacing(6)

        # App icon + name
        icon_lbl = QLabel("✅")
        icon_lbl.setObjectName("app_icon_label")
        tb_lay.addWidget(icon_lbl)

        title_lbl = QLabel("Work Planner")
        title_lbl.setObjectName("app_title")
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        # Settings button
        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setObjectName("btn_settings_icon")
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self._open_settings)
        tb_lay.addWidget(self._btn_settings)

        root_lay.addWidget(self._title_bar)

        # ── Sliding content area ───────────────────────────────────────────────
        self._stack = SlidingStack(self._root)
        root_lay.addWidget(self._stack, 1)

        # Page 0: Task list
        self._list_view = TaskListView(self.db, self._stack)
        self._list_view.task_clicked.connect(self._open_detail)
        self._list_view.task_completion_changed.connect(
            lambda tid, done: None          # list already updates itself
        )
        self._stack.addWidget(self._list_view)

        # Page 1: Task detail
        self._detail_view = TaskDetailView(self.db, self._stack)
        self._detail_view.back_requested.connect(self._go_back)
        self._detail_view.task_deleted.connect(self._on_task_deleted)
        self._detail_view.task_updated.connect(self._list_view.refresh)
        self._stack.addWidget(self._detail_view)

        # ── FAB (+) button ─────────────────────────────────────────────────────
        self._fab = QPushButton("+", self._root)
        self._fab.setObjectName("btn_fab")
        self._fab.setToolTip("New task")
        self._fab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fab.clicked.connect(self._open_add_task)
        self._fab.raise_()

    # ── FAB positioning ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fab = self._fab
        margin = 14
        fab.move(
            self._root.width()  - fab.width()  - margin,
            self._root.height() - fab.height() - margin,
        )

    # ── load saved settings ────────────────────────────────────────────────────

    def _load_settings(self):
        opacity = int(self.db.get_setting('opacity', '92'))
        self.setWindowOpacity(opacity / 100)

        family = self.db.get_setting('font_family', '')
        size   = int(self.db.get_setting('font_size', '13'))
        if family:
            self.apply_font(family, size)

        always_top = self.db.get_setting('always_on_top', '0') == '1'
        self.set_always_on_top(always_top)

        # Restore window position
        x = self.db.get_setting('win_x', None)
        y = self.db.get_setting('win_y', None)
        w = self.db.get_setting('win_w', None)
        h = self.db.get_setting('win_h', None)
        if all(v is not None for v in [x, y, w, h]):
            self.setGeometry(int(x), int(y), int(w), int(h))

    # ── navigation ─────────────────────────────────────────────────────────────

    def _open_detail(self, task_id: int):
        if self._stack.currentIndex() == 0 and not self._stack._animating:
            # Only load & slide when the stack is idle on the list page
            self._detail_view.load_task(task_id)
            self._stack.slideTo(1, direction='left')

    def _go_back(self):
        if self._stack.currentIndex() == 1 and not self._stack._animating:
            self._list_view.refresh()
            self._stack.slideTo(0, direction='right')

    def _on_task_deleted(self, _task_id: int):
        self._list_view.refresh()
        self._stack.slideTo(0, direction='right')



    # ── dialogs ────────────────────────────────────────────────────────────────

    def _open_add_task(self):
        from .task_form import TaskForm
        dlg = TaskForm(self.db, task=None, parent=self)
        dlg.move(self.x() + 20, self.y() + 80)
        if dlg.exec():
            self._list_view.refresh()

    def _open_settings(self):
        from .settings_window import SettingsWindow
        dlg = SettingsWindow(self.db, main_window=self, parent=self)
        dlg.adjustSize()

        screen = QApplication.primaryScreen().availableGeometry()
        dlg_w  = dlg.sizeHint().width()
        dlg_h  = dlg.sizeHint().height()

        # Try to place to the left of the main window; fall back to right side
        x = self.x() - dlg_w - 8
        if x < screen.left():
            x = self.x() + self.width() + 8   # right side
        if x + dlg_w > screen.right():
            x = screen.right() - dlg_w - 8    # clamp to screen right

        y = self.y() + 60
        if y + dlg_h > screen.bottom():
            y = screen.bottom() - dlg_h - 8

        dlg.move(x, y)
        dlg.exec()

    # ── public helpers (called by SettingsWindow) ──────────────────────────────

    def apply_font(self, family: str, size: int):
        self._list_view.set_font(family, size)

    def set_always_on_top(self, enabled: bool):
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        pos = self.pos()
        self.setWindowFlags(flags)
        self.move(pos)
        self.show()

    # ── dragging the frameless window ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only drag when pressing on title bar
            if self._title_bar.geometry().contains(event.pos()):
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._dragging = False

    # ── save position on close ─────────────────────────────────────────────────

    def closeEvent(self, event):
        g = self.geometry()
        self.db.set_setting('win_x', str(g.x()))
        self.db.set_setting('win_y', str(g.y()))
        self.db.set_setting('win_w', str(g.width()))
        self.db.set_setting('win_h', str(g.height()))
        super().closeEvent(event)
