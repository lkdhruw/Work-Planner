import sys
import shutil
import sqlite3
import os
from typing import List, Optional

from .models import Profile, Task, SubTask


def _get_user_data_dir() -> str:
    """Return a persistent, OS-appropriate directory for app data.

    Windows : %APPDATA%\\WorkPlanner
    macOS   : ~/Library/Application Support/WorkPlanner
    Linux   : ~/.local/share/WorkPlanner
    """
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))
    data_dir = os.path.join(base, 'WorkPlanner')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = _get_user_data_dir()
            db_path  = os.path.join(data_dir, 'workplanner.db')

            # ── One-time migration: move legacy db from the exe/script folder ──
            legacy_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'workplanner.db'
            )
            if not os.path.exists(db_path) and os.path.exists(legacy_path):
                shutil.move(legacy_path, db_path)

        self.db_path = db_path


    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL UNIQUE,
                    color      TEXT DEFAULT '#7C3AED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id            INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
                    title                 TEXT NOT NULL,
                    description           TEXT DEFAULT '',
                    due_date              TEXT DEFAULT NULL,
                    reminder_type         TEXT DEFAULT 'none',
                    reminder_time         TEXT DEFAULT NULL,
                    reminder_datetime     TEXT DEFAULT NULL,
                    reminder_days         TEXT DEFAULT NULL,
                    reminder_day_of_month INTEGER DEFAULT NULL,
                    is_completed          BOOLEAN DEFAULT 0,
                    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS subtasks (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    title        TEXT NOT NULL,
                    is_completed BOOLEAN DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS reminder_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id   INTEGER NOT NULL,
                    sent_date TEXT NOT NULL,
                    UNIQUE(task_id, sent_date)
                );
            """)

    # ── Settings ──────────────────────────────────────────────────────────────

    def get_setting(self, key: str, default=None):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                (key, value)
            )

    # ── Profiles ───────────────────────────────────────────────────────────────

    def get_profiles(self) -> List[Profile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles ORDER BY name"
            ).fetchall()
            return [
                Profile(id=r['id'], name=r['name'], color=r['color'],
                        created_at=r['created_at'])
                for r in rows
            ]

    def create_profile(self, name: str, color: str) -> Profile:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO profiles (name, color) VALUES (?,?)", (name, color)
            )
            return Profile(id=cur.lastrowid, name=name, color=color)

    def update_profile(self, profile: Profile):
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET name=?, color=? WHERE id=?",
                (profile.name, profile.color, profile.id)
            )

    def delete_profile(self, profile_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))

    # ── Tasks ──────────────────────────────────────────────────────────────────

    def _row_to_task(self, r) -> Task:
        profile = None
        if r['profile_id']:
            profile = Profile(
                id=r['profile_id'],
                name=r['profile_name'],
                color=r['profile_color']
            )
        return Task(
            id=r['id'],
            profile_id=r['profile_id'],
            title=r['title'],
            description=r['description'] or '',
            due_date=r['due_date'],
            reminder_type=r['reminder_type'] or 'none',
            reminder_time=r['reminder_time'],
            reminder_datetime=r['reminder_datetime'],
            reminder_days=r['reminder_days'],
            reminder_day_of_month=r['reminder_day_of_month'],
            is_completed=bool(r['is_completed']),
            created_at=r['created_at'],
            updated_at=r['updated_at'],
            profile=profile,
        )

    def get_tasks(self, profile_id: Optional[int] = None,
                  include_completed: bool = True) -> List[Task]:
        with self._connect() as conn:
            base = """
                SELECT t.*,
                       p.name  AS profile_name,
                       p.color AS profile_color
                FROM   tasks t
                       LEFT JOIN profiles p ON t.profile_id = p.id
            """
            conditions, params = [], []
            if profile_id is not None:
                conditions.append("t.profile_id = ?")
                params.append(profile_id)
            if not include_completed:
                conditions.append("t.is_completed = 0")
            if conditions:
                base += " WHERE " + " AND ".join(conditions)
            base += (
                " ORDER BY t.is_completed ASC,"
                " CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,"
                " t.due_date ASC,"
                " t.created_at DESC"
            )
            rows = conn.execute(base, params).fetchall()
            return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT t.*,
                       p.name  AS profile_name,
                       p.color AS profile_color
                FROM   tasks t
                       LEFT JOIN profiles p ON t.profile_id = p.id
                WHERE  t.id = ?
                """,
                (task_id,)
            ).fetchone()
            return self._row_to_task(row) if row else None

    def create_task(self, task: Task) -> Task:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (profile_id, title, description, due_date,
                     reminder_type, reminder_time, reminder_datetime,
                     reminder_days, reminder_day_of_month)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (task.profile_id, task.title, task.description, task.due_date,
                 task.reminder_type, task.reminder_time, task.reminder_datetime,
                 task.reminder_days, task.reminder_day_of_month)
            )
            task.id = cur.lastrowid
            return task

    def update_task(self, task: Task):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    profile_id=?, title=?, description=?, due_date=?,
                    reminder_type=?, reminder_time=?, reminder_datetime=?,
                    reminder_days=?, reminder_day_of_month=?,
                    is_completed=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (task.profile_id, task.title, task.description, task.due_date,
                 task.reminder_type, task.reminder_time, task.reminder_datetime,
                 task.reminder_days, task.reminder_day_of_month,
                 task.is_completed, task.id)
            )

    def delete_task(self, task_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def toggle_task(self, task_id: int, is_completed: bool):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET is_completed=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (is_completed, task_id)
            )

    # ── Subtasks ───────────────────────────────────────────────────────────────

    def get_subtasks(self, task_id: int) -> List[SubTask]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM subtasks WHERE task_id=? ORDER BY created_at",
                (task_id,)
            ).fetchall()
            return [
                SubTask(id=r['id'], task_id=r['task_id'], title=r['title'],
                        is_completed=bool(r['is_completed']),
                        created_at=r['created_at'])
                for r in rows
            ]

    def create_subtask(self, subtask: SubTask) -> SubTask:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO subtasks (task_id, title) VALUES (?,?)",
                (subtask.task_id, subtask.title)
            )
            subtask.id = cur.lastrowid
            return subtask

    def update_subtask(self, subtask: SubTask):
        with self._connect() as conn:
            conn.execute(
                "UPDATE subtasks SET title=?, is_completed=? WHERE id=?",
                (subtask.title, subtask.is_completed, subtask.id)
            )

    def delete_subtask(self, subtask_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))

    def toggle_subtask(self, subtask_id: int, is_completed: bool):
        with self._connect() as conn:
            conn.execute(
                "UPDATE subtasks SET is_completed=? WHERE id=?",
                (is_completed, subtask_id)
            )

    # ── Reminder support ───────────────────────────────────────────────────────

    def get_tasks_with_reminders(self) -> List[Task]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.*,
                       p.name  AS profile_name,
                       p.color AS profile_color
                FROM   tasks t
                       LEFT JOIN profiles p ON t.profile_id = p.id
                WHERE  t.reminder_type != 'none'
                  AND  t.is_completed = 0
                """
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def log_reminder_sent(self, task_id: int, sent_date: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO reminder_log (task_id, sent_date) VALUES (?,?)",
                (task_id, sent_date)
            )

    def was_reminder_sent_today(self, task_id: int, date_str: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reminder_log WHERE task_id=? AND sent_date=?",
                (task_id, date_str)
            ).fetchone()
            return row is not None
