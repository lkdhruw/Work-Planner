"""Main task-list view with profile filter tabs."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QScrollArea, QSizePolicy,
                                QFrame, QSpacerItem)

from .widgets.task_card import TaskCard
from ..models import Task, Profile
from ..database import Database


class ProfileTabButton(QPushButton):
    def __init__(self, text: str, profile_id=None, color: str = '#7C3AED',
                 parent=None):
        super().__init__(text, parent)
        self.profile_id = profile_id
        self._color = color
        self._active = False
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def setActive(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                f"background: {self._hex_a(self._color, 35)};"
                f"color: {self._color};"
                f"border: 1px solid {self._hex_a(self._color, 60)};"
                "border-radius: 8px; padding: 5px 14px;"
                "font-size: 12px; font-weight: 600;"
            )
        else:
            self.setStyleSheet(
                "background: transparent; color: #64748B; border: none;"
                "border-radius: 8px; padding: 5px 14px; font-size: 12px;"
            )

    @staticmethod
    def _hex_a(hex_color: str, a: int) -> str:
        h = hex_color.lstrip('#')
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{a})"
        except Exception:
            return f"rgba(124,58,237,{a})"


class TaskListView(QWidget):
    """Main list view: profile tabs + scrollable task cards."""

    task_clicked    = Signal(int)           # task id
    add_task_clicked = Signal()
    task_completion_changed = Signal(int, bool)

    PROFILE_COLORS = [
        '#7C3AED', '#0EA5E9', '#10B981', '#F59E0B',
        '#EF4444', '#EC4899', '#8B5CF6', '#06B6D4',
    ]

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._active_profile_id: int | None = None
        self._tab_buttons: list[ProfileTabButton] = []
        self._cards: list[TaskCard] = []
        self._build_ui()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── profile tab bar ────────────────────────────────────────────────────
        bar_container = QWidget()
        bar_container.setObjectName("profile_bar")
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(8, 0, 8, 0)
        bar_layout.setSpacing(4)

        # Scroll area to hold tabs (many profiles)
        self._tab_scroll = QScrollArea()
        self._tab_scroll.setWidgetResizable(True)
        self._tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tab_scroll.setFixedHeight(44)
        self._tab_scroll.setStyleSheet("background: transparent; border: none;")

        self._tab_inner = QWidget()
        self._tab_inner.setStyleSheet("background: transparent;")
        self._tab_inner_layout = QHBoxLayout(self._tab_inner)
        self._tab_inner_layout.setContentsMargins(0, 4, 0, 4)
        self._tab_inner_layout.setSpacing(4)
        self._tab_inner_layout.addStretch()

        self._tab_scroll.setWidget(self._tab_inner)
        bar_layout.addWidget(self._tab_scroll, 1)

        # Add profile button
        self._btn_add_profile = QPushButton("+")
        self._btn_add_profile.setObjectName("btn_add_profile")
        self._btn_add_profile.setFixedSize(32, 32)
        self._btn_add_profile.setToolTip("New profile")
        self._btn_add_profile.clicked.connect(self._on_add_profile)
        bar_layout.addWidget(self._btn_add_profile,
                             alignment=Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(bar_container)

        # ── task scroll area ───────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 80)   # bottom gap for FAB
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll, 1)

        # ── empty state ────────────────────────────────────────────────────────
        self._empty_lbl = QLabel("No tasks yet.\nTap + to add one ✨")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            "color: #334155; font-size: 14px; line-height: 1.6;")
        self._empty_lbl.hide()
        root.addWidget(self._empty_lbl)

        self.refresh()

    # ── public API ─────────────────────────────────────────────────────────────

    def refresh(self):
        self._rebuild_tabs()
        self._rebuild_cards()

    # ── tabs ───────────────────────────────────────────────────────────────────

    def _rebuild_tabs(self):
        # Clear existing
        for btn in self._tab_buttons:
            btn.deleteLater()
        self._tab_buttons.clear()

        lay = self._tab_inner_layout
        # Remove all except stretch
        while lay.count() > 1:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profiles = self.db.get_profiles()

        # "All" tab
        all_btn = ProfileTabButton("All", profile_id=None, color='#7C3AED')
        all_btn.setActive(self._active_profile_id is None)
        all_btn.clicked.connect(lambda: self._select_profile(None))
        lay.insertWidget(lay.count() - 1, all_btn)
        self._tab_buttons.append(all_btn)

        for i, prof in enumerate(profiles):
            color = prof.color or self.PROFILE_COLORS[i % len(self.PROFILE_COLORS)]
            btn = ProfileTabButton(prof.name, profile_id=prof.id, color=color)
            btn.setActive(self._active_profile_id == prof.id)
            btn.clicked.connect(
                lambda checked=False, pid=prof.id: self._select_profile(pid)
            )
            lay.insertWidget(lay.count() - 1, btn)
            self._tab_buttons.append(btn)

    def _select_profile(self, profile_id):
        self._active_profile_id = profile_id
        for btn in self._tab_buttons:
            btn.setActive(btn.profile_id == profile_id)
        self._rebuild_cards()

    # ── cards ──────────────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        # Remove existing cards
        for card in self._cards:
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        tasks = self.db.get_tasks(profile_id=self._active_profile_id)

        if not tasks:
            self._empty_lbl.show()
            self._scroll.hide()
        else:
            self._empty_lbl.hide()
            self._scroll.show()
            for task in tasks:
                subtasks = self.db.get_subtasks(task.id)
                task.subtasks = subtasks
                card = TaskCard(task, self)
                card.clicked.connect(self.task_clicked)
                card.completion_changed.connect(self._on_completion_changed)
                # Insert before the final stretch
                idx = self._list_layout.count() - 1
                self._list_layout.insertWidget(idx, card)
                self._cards.append(card)

    def _on_completion_changed(self, task_id: int, is_completed: bool):
        self.db.toggle_task(task_id, is_completed)
        self.task_completion_changed.emit(task_id, is_completed)

    # ── profile dialog ──────────────────────────────────────────────────────────

    def _on_add_profile(self):
        from .profile_form import ProfileForm
        dlg = ProfileForm(self.db, self.window())
        if dlg.exec():
            self.refresh()

    def set_font(self, family: str, size: int):
        """Apply dynamic font to all task title labels."""
        for card in self._cards:
            f = card._title_lbl.font()
            f.setFamily(family)
            f.setPointSize(size)
            card._title_lbl.setFont(f)
