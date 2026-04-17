"""Add / Edit task form dialog with full reminder scheduling."""

import json

from PySide6.QtCore import Qt, QDate, QTime, QDateTime
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QLineEdit, QTextEdit, QPushButton, QComboBox,
                                QDateEdit, QTimeEdit, QDateTimeEdit,
                                QCheckBox, QSpinBox, QFrame, QWidget,
                                QScrollArea, QSizePolicy)

from ..database import Database
from ..models import Task

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
PROFILE_COLORS = [
    '#7C3AED', '#0EA5E9', '#10B981', '#F59E0B',
    '#EF4444', '#EC4899', '#8B5CF6', '#06B6D4',
]


class TaskForm(QDialog):
    """Modal dialog to create or edit a task with reminder scheduling."""

    def __init__(self, db: Database, task: Task | None = None, parent=None):
        super().__init__(parent)
        self.db   = db
        self.task = task
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setMinimumHeight(600)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._day_checks: list[QCheckBox] = []
        self._build_ui()
        if task:
            self._populate(task)

    # ── build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
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
        c_lay.setSpacing(0)
        outer.addWidget(container)

        # ── title bar ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(
            "background: rgba(255,255,255,7);"
            "border-radius: 14px 14px 0 0;"
            "border-bottom: 1px solid rgba(255,255,255,12);"
        )
        header.setFixedHeight(48)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel("✏  Edit Task" if self.task else "＋  New Task")
        f = title_lbl.font()
        f.setPointSize(14)
        f.setWeight(QFont.Weight.Bold)
        title_lbl.setFont(f)
        h_lay.addWidget(title_lbl, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "background: rgba(239,68,68,150); border: none; border-radius: 6px;"
            "color: white; font-size: 12px;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        h_lay.addWidget(close_btn)

        c_lay.addWidget(header)

        # ── body (scrollable) ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Title
        lay.addWidget(self._section("TITLE"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Task title *")
        lay.addWidget(self._title_edit)

        # Profile
        lay.addWidget(self._section("PROFILE"))
        self._profile_combo = QComboBox()
        self._profile_combo.addItem("None", None)
        for p in self.db.get_profiles():
            self._profile_combo.addItem(p.name, p.id)
        lay.addWidget(self._profile_combo)

        # Description
        lay.addWidget(self._section("DESCRIPTION  (optional)"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Add details…")
        self._desc_edit.setFixedHeight(72)
        lay.addWidget(self._desc_edit)

        # Due date
        lay.addWidget(self._section("DUE DATE  (optional)"))
        due_row = QHBoxLayout()
        self._due_check = QCheckBox("Set due date")
        due_row.addWidget(self._due_check)
        due_row.addStretch()
        lay.addLayout(due_row)
        self._due_edit = QDateEdit()
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setDate(QDate.currentDate())
        self._due_edit.hide()
        lay.addWidget(self._due_edit)
        self._due_check.toggled.connect(self._due_edit.setVisible)

        # ── Reminder ───────────────────────────────────────────────────────────
        lay.addWidget(self._divider())
        lay.addWidget(self._section("REMINDER  (optional)"))

        self._reminder_type = QComboBox()
        self._reminder_type.addItems(["None", "Once", "Daily", "Weekly", "Monthly"])
        self._reminder_type.currentIndexChanged.connect(self._on_reminder_type_changed)
        lay.addWidget(self._reminder_type)

        # Once: datetime picker
        self._once_widget = QWidget()
        once_lay = QVBoxLayout(self._once_widget)
        once_lay.setContentsMargins(0, 0, 0, 0)
        once_lay.setSpacing(6)
        once_lay.addWidget(QLabel("Remind at:"))
        self._once_dt = QDateTimeEdit()
        self._once_dt.setCalendarPopup(True)
        self._once_dt.setDateTime(QDateTime.currentDateTime())
        self._once_dt.setDisplayFormat("dd MMM yyyy  HH:mm")
        once_lay.addWidget(self._once_dt)
        self._once_widget.hide()
        lay.addWidget(self._once_widget)

        # Daily / Weekly / Monthly share a time picker
        self._time_widget = QWidget()
        t_lay = QVBoxLayout(self._time_widget)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(6)
        t_lay.addWidget(QLabel("At time:"))
        self._time_edit = QTimeEdit()
        self._time_edit.setTime(QTime(9, 0))
        self._time_edit.setDisplayFormat("HH:mm")
        t_lay.addWidget(self._time_edit)
        self._time_widget.hide()
        lay.addWidget(self._time_widget)

        # Weekly: day checkboxes
        self._weekly_widget = QWidget()
        w_lay = QVBoxLayout(self._weekly_widget)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(4)
        w_lay.addWidget(QLabel("On days:"))
        days_grid = QHBoxLayout()
        days_grid.setSpacing(4)
        for i, day in enumerate(WEEKDAYS):
            cb = QCheckBox(day[:3])
            cb.setStyleSheet("font-size: 11px;")
            days_grid.addWidget(cb)
            self._day_checks.append(cb)
        w_lay.addLayout(days_grid)
        self._weekly_widget.hide()
        lay.addWidget(self._weekly_widget)

        # Monthly: day spinner
        self._monthly_widget = QWidget()
        m_lay = QHBoxLayout(self._monthly_widget)
        m_lay.setContentsMargins(0, 0, 0, 0)
        m_lay.setSpacing(8)
        m_lay.addWidget(QLabel("On day:"))
        self._month_day_spin = QSpinBox()
        self._month_day_spin.setRange(1, 31)
        self._month_day_spin.setValue(1)
        m_lay.addWidget(self._month_day_spin)
        m_lay.addWidget(QLabel("of each month"))
        m_lay.addStretch()
        self._monthly_widget.hide()
        lay.addWidget(self._monthly_widget)

        # ── buttons ────────────────────────────────────────────────────────────
        lay.addStretch()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._save_btn = QPushButton("Save Task")
        self._save_btn.setObjectName("btn_primary")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        lay.addLayout(btn_row)

        scroll.setWidget(body)
        c_lay.addWidget(scroll)

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("label_section")
        return lbl

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background: rgba(255,255,255,10); max-height:1px; margin: 4px 0;")
        return f

    # ── populate existing task ─────────────────────────────────────────────────

    def _populate(self, task: Task):
        self._title_edit.setText(task.title)
        self._desc_edit.setPlainText(task.description or '')

        # Profile
        idx = self._profile_combo.findData(task.profile_id)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)

        # Due date
        if task.due_date:
            try:
                d = QDate.fromString(task.due_date, "yyyy-MM-dd")
                self._due_check.setChecked(True)
                self._due_edit.setDate(d)
            except Exception:
                pass

        # Reminder
        rt_map = {'once': 1, 'daily': 2, 'weekly': 3, 'monthly': 4}
        rt_idx = rt_map.get(task.reminder_type, 0)
        self._reminder_type.setCurrentIndex(rt_idx)

        if task.reminder_datetime:
            try:
                dt = QDateTime.fromString(task.reminder_datetime, Qt.DateFormat.ISODate)
                self._once_dt.setDateTime(dt)
            except Exception:
                pass

        if task.reminder_time:
            try:
                t = QTime.fromString(task.reminder_time, "HH:mm")
                self._time_edit.setTime(t)
            except Exception:
                pass

        if task.reminder_days:
            try:
                days = json.loads(task.reminder_days)
                for i, cb in enumerate(self._day_checks):
                    cb.setChecked(i in days)
            except Exception:
                pass

        if task.reminder_day_of_month:
            self._month_day_spin.setValue(task.reminder_day_of_month)

    # ── reminder type visibility ───────────────────────────────────────────────

    def _on_reminder_type_changed(self, index: int):
        label = self._reminder_type.currentText().lower()
        self._once_widget.setVisible(label == 'once')
        self._time_widget.setVisible(label in ('daily', 'weekly', 'monthly'))
        self._weekly_widget.setVisible(label == 'weekly')
        self._monthly_widget.setVisible(label == 'monthly')

    # ── save ───────────────────────────────────────────────────────────────────

    def _on_save(self):
        title = self._title_edit.text().strip()
        if not title:
            self._title_edit.setPlaceholderText("Title is required!")
            self._title_edit.setStyleSheet(
                "border-color: rgba(239,68,68,180); background: rgba(239,68,68,15);"
            )
            return

        profile_id = self._profile_combo.currentData()
        description = self._desc_edit.toPlainText().strip()

        due_date = None
        if self._due_check.isChecked():
            due_date = self._due_edit.date().toString("yyyy-MM-dd")

        rtype = self._reminder_type.currentText().lower()
        if rtype == 'none':
            rtype = 'none'
        r_time = None
        r_dt   = None
        r_days = None
        r_dom  = None

        if rtype == 'once':
            r_dt = self._once_dt.dateTime().toString(Qt.DateFormat.ISODate)
        elif rtype == 'daily':
            r_time = self._time_edit.time().toString("HH:mm")
        elif rtype == 'weekly':
            selected = [i for i, cb in enumerate(self._day_checks) if cb.isChecked()]
            if not selected:
                selected = [0]   # default Monday
            r_days = json.dumps(selected)
            r_time = self._time_edit.time().toString("HH:mm")
        elif rtype == 'monthly':
            r_dom  = self._month_day_spin.value()
            r_time = self._time_edit.time().toString("HH:mm")

        if self.task:
            self.task.title       = title
            self.task.profile_id  = profile_id
            self.task.description = description
            self.task.due_date    = due_date
            self.task.reminder_type         = rtype
            self.task.reminder_time         = r_time
            self.task.reminder_datetime     = r_dt
            self.task.reminder_days         = r_days
            self.task.reminder_day_of_month = r_dom
            self.db.update_task(self.task)
        else:
            new_task = Task(
                id=None,
                profile_id=profile_id,
                title=title,
                description=description,
                due_date=due_date,
                reminder_type=rtype,
                reminder_time=r_time,
                reminder_datetime=r_dt,
                reminder_days=r_days,
                reminder_day_of_month=r_dom,
            )
            self.db.create_task(new_task)

        self.accept()
