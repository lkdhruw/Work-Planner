"""Task detail view with subtasks, slide-in from list."""

import json
from datetime import date

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QScrollArea, QFrame,
                                QLineEdit, QMessageBox, QSizePolicy)

from .widgets.checkbox import AnimatedCheckbox
from ..models import Task, SubTask
from ..database import Database


class SubtaskRow(QWidget):
    """A single subtask row with animated checkbox and delete."""

    delete_requested = Signal(int)   # subtask id
    completion_changed = Signal(int, bool)

    def __init__(self, subtask: SubTask, parent=None):
        super().__init__(parent)
        self.subtask = subtask
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)

        self._cb = AnimatedCheckbox(self, size=18)
        self._cb.setChecked(self.subtask.is_completed, animate=False)
        self._cb.toggled.connect(
            lambda v: self.completion_changed.emit(self.subtask.id, v)
        )
        lay.addWidget(self._cb, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._lbl = QLabel(self.subtask.title)
        f = self._lbl.font()
        f.setPointSize(12)
        self._lbl.setFont(f)
        if self.subtask.is_completed:
            self._apply_strike(True)
        lay.addWidget(self._lbl, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(
            "background: transparent; border: none; color: #334155; font-size: 12px;"
        )
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.subtask.id))
        lay.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._cb.toggled.connect(self._apply_strike)

    def _apply_strike(self, on: bool):
        f = self._lbl.font()
        f.setStrikeOut(on)
        self._lbl.setFont(f)
        self._lbl.setStyleSheet("color: #475569;" if on else "")


class TaskDetailView(QWidget):
    """Detailed task view with subtasks, info chips, edit/delete."""

    back_requested  = Signal()
    task_deleted    = Signal(int)
    task_updated    = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._task: Task | None = None
        self._subtask_rows: list[SubtaskRow] = []
        self._build_ui()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ─────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("detail_header")
        header.setFixedHeight(52)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 10, 0)
        h_lay.setSpacing(8)

        self._btn_back = QPushButton("← Back")
        self._btn_back.setObjectName("btn_back")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self.back_requested)
        h_lay.addWidget(self._btn_back)
        h_lay.addStretch()

        self._btn_edit = QPushButton("✏ Edit")
        self._btn_edit.setObjectName("btn_ghost")
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.clicked.connect(self._on_edit)
        h_lay.addWidget(self._btn_edit)

        self._btn_delete = QPushButton("🗑 Delete")
        self._btn_delete.setObjectName("btn_danger")
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.clicked.connect(self._on_delete)
        h_lay.addWidget(self._btn_delete)

        root.addWidget(header)

        # ── scrollable body ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("detail_scroll_content")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(14, 14, 14, 20)
        self._body_layout.setSpacing(12)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ── public API ─────────────────────────────────────────────────────────────

    def load_task(self, task_id: int):
        self._task = self.db.get_task(task_id)
        if not self._task:
            return
        self._task.subtasks = self.db.get_subtasks(task_id)
        self._render()

    # ── rendering ──────────────────────────────────────────────────────────────

    def _render(self):
        # Clear body — setParent(None) immediately removes from layout so the
        # old content is invisible before the new one is painted (avoids overlap)
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)   # detach immediately
                w.deleteLater()     # free memory on next event loop tick
            # also clean up layout items (nested layouts, spacers)
            elif item.layout():
                self._clear_layout(item.layout())
        self._subtask_rows.clear()

        task = self._task

        # ── title row with checkbox ────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        self._main_cb = AnimatedCheckbox(self, size=26)
        self._main_cb.setChecked(task.is_completed, animate=False)
        self._main_cb.toggled.connect(self._on_main_toggle)
        title_row.addWidget(self._main_cb, alignment=Qt.AlignmentFlag.AlignTop)

        self._title_lbl = QLabel(task.title)
        self._title_lbl.setObjectName("label_detail_title")
        self._title_lbl.setWordWrap(True)
        f = self._title_lbl.font()
        f.setPointSize(17)
        f.setWeight(QFont.Weight.Bold)
        self._title_lbl.setFont(f)
        title_row.addWidget(self._title_lbl, 1)

        self._body_layout.addLayout(title_row)

        # ── info chips ─────────────────────────────────────────────────────────
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        chips_row.setContentsMargins(36, 0, 0, 0)

        if task.profile:
            c = task.profile.color
            chip = QLabel(f"● {task.profile.name}")
            chip.setObjectName("chip_profile")
            chip.setStyleSheet(
                f"background: {self._hex_a(c, 30)}; color: {c};"
                "border-radius: 10px; padding: 3px 10px;"
                "font-size: 11px; font-weight: 600;"
            )
            chips_row.addWidget(chip)

        if task.due_date:
            try:
                d = date.fromisoformat(task.due_date)
                overdue = d < date.today() and not task.is_completed
                lbl = QLabel(f"📅  {d.strftime('%b %d, %Y')}")
                lbl.setObjectName("chip_overdue" if overdue else "chip_due")
                chips_row.addWidget(lbl)
            except ValueError:
                pass

        if task.reminder_type and task.reminder_type != 'none':
            rl = QLabel(f"🔔  {self._reminder_text(task)}")
            rl.setObjectName("chip_reminder")
            rl.setWordWrap(True)
            chips_row.addWidget(rl)

        chips_row.addStretch()
        self._body_layout.addLayout(chips_row)

        # ── description ────────────────────────────────────────────────────────
        if task.description:
            self._body_layout.addWidget(self._divider())
            desc_hdr = QLabel("DESCRIPTION")
            desc_hdr.setObjectName("label_section")
            self._body_layout.addWidget(desc_hdr)
            desc_lbl = QLabel(task.description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; line-height: 1.5;")
            self._body_layout.addWidget(desc_lbl)

        # ── subtasks ───────────────────────────────────────────────────────────
        self._body_layout.addWidget(self._divider())
        st_header_row = QHBoxLayout()
        st_hdr = QLabel("SUBTASKS")
        st_hdr.setObjectName("label_section")
        st_header_row.addWidget(st_hdr)
        st_header_row.addStretch()
        count_lbl = QLabel(
            f"{sum(1 for st in task.subtasks if st.is_completed)}/{len(task.subtasks)}"
        )
        count_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        st_header_row.addWidget(count_lbl)
        self._body_layout.addLayout(st_header_row)

        # Subtask container
        self._subtasks_container = QWidget()
        sc_lay = QVBoxLayout(self._subtasks_container)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.setSpacing(2)
        for st in task.subtasks:
            row = SubtaskRow(st, self)
            row.delete_requested.connect(self._on_delete_subtask)
            row.completion_changed.connect(self._on_subtask_toggle)
            sc_lay.addWidget(row)
            self._subtask_rows.append(row)
        self._body_layout.addWidget(self._subtasks_container)

        # Add subtask input
        self._add_st_input = QLineEdit()
        self._add_st_input.setObjectName("subtask_add_line")
        self._add_st_input.setPlaceholderText("+ Add subtask…")
        self._add_st_input.returnPressed.connect(self._on_add_subtask)
        self._body_layout.addWidget(self._add_st_input)

        self._body_layout.addStretch()

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout):
        """Recursively remove all items from a layout without a parent widget."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                TaskDetailView._clear_layout(item.layout())

    @staticmethod
    def _hex_a(hex_color: str, a: int) -> str:
        h = hex_color.lstrip('#')
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{a})"
        except Exception:
            return f"rgba(124,58,237,{a})"

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: rgba(255,255,255,10); max-height:1px;")
        return line

    @staticmethod
    def _reminder_text(task) -> str:
        rt = task.reminder_type
        if rt == 'once':
            return f"Once at {task.reminder_datetime or ''}"
        if rt == 'daily':
            return f"Daily at {task.reminder_time or ''}"
        if rt == 'weekly':
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            try:
                days = [day_names[d] for d in json.loads(task.reminder_days or '[]')]
                return f"Every {', '.join(days)} at {task.reminder_time or ''}"
            except Exception:
                return f"Weekly at {task.reminder_time or ''}"
        if rt == 'monthly':
            return f"Monthly on day {task.reminder_day_of_month} at {task.reminder_time or ''}"
        return ''

    # ── actions ────────────────────────────────────────────────────────────────

    def _on_main_toggle(self, checked: bool):
        if self._task:
            self._task.is_completed = checked
            self.db.toggle_task(self._task.id, checked)
            self.task_updated.emit()

    def _on_subtask_toggle(self, subtask_id: int, is_completed: bool):
        self.db.toggle_subtask(subtask_id, is_completed)

    def _on_add_subtask(self):
        title = self._add_st_input.text().strip()
        if not title or not self._task:
            return
        st = SubTask(id=None, task_id=self._task.id, title=title)
        st = self.db.create_subtask(st)
        self._task.subtasks.append(st)
        self._add_st_input.clear()

        # Add row to container
        row = SubtaskRow(st, self)
        row.delete_requested.connect(self._on_delete_subtask)
        row.completion_changed.connect(self._on_subtask_toggle)
        cont_lay = self._subtasks_container.layout()
        cont_lay.addWidget(row)
        self._subtask_rows.append(row)

    def _on_delete_subtask(self, subtask_id: int):
        self.db.delete_subtask(subtask_id)
        if self._task:
            self._task.subtasks = [st for st in self._task.subtasks
                                   if st.id != subtask_id]
        for row in self._subtask_rows:
            if row.subtask.id == subtask_id:
                self._subtask_rows.remove(row)
                row.deleteLater()
                break

    def _on_edit(self):
        if not self._task:
            return
        from .task_form import TaskForm
        dlg = TaskForm(self.db, task=self._task, parent=self.window())
        if dlg.exec():
            self.load_task(self._task.id)
            self.task_updated.emit()

    def _on_delete(self):
        if not self._task:
            return
        msg = QMessageBox(self.window())
        msg.setWindowTitle("Delete Task")
        msg.setText(f'Delete "{self._task.title}"?\nThis will also remove all subtasks.')
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msg.setStyleSheet("QMessageBox { background: rgb(13,17,38); color: #F1F5F9; }")
        if msg.exec() == QMessageBox.StandardButton.Yes:
            task_id = self._task.id
            self.db.delete_task(task_id)
            self._task = None
            self.task_deleted.emit(task_id)
