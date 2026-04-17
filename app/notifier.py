import json
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database


class NotificationScheduler:
    """Background thread that checks reminder schedules every 60 s."""

    def __init__(self, db: 'Database'):
        self.db = db
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="ReminderScheduler")
        self._thread.start()

    def stop(self):
        self._running = False

    # ── internal ───────────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            try:
                self._check_reminders()
            except Exception as exc:
                print(f"[Notifier] error: {exc}")
            time.sleep(60)

    def _check_reminders(self):
        now = datetime.now()
        cur_time = now.strftime("%H:%M")
        cur_date = now.strftime("%Y-%m-%d")
        today_wd = now.weekday()   # 0 = Monday
        today_d  = now.day

        for task in self.db.get_tasks_with_reminders():
            rtype = task.reminder_type
            fire  = False

            if rtype == 'once':
                if task.reminder_datetime:
                    try:
                        rdt  = datetime.fromisoformat(task.reminder_datetime)
                        diff = abs((rdt - now).total_seconds())
                        fire = diff <= 60
                    except ValueError:
                        pass

            elif rtype == 'daily':
                if task.reminder_time == cur_time:
                    fire = not self.db.was_reminder_sent_today(task.id, cur_date)

            elif rtype == 'weekly':
                if task.reminder_time == cur_time:
                    try:
                        days = json.loads(task.reminder_days or '[]')
                        fire = (today_wd in days and
                                not self.db.was_reminder_sent_today(task.id, cur_date))
                    except (ValueError, TypeError):
                        pass

            elif rtype == 'monthly':
                if task.reminder_time == cur_time and task.reminder_day_of_month == today_d:
                    fire = not self.db.was_reminder_sent_today(task.id, cur_date)

            if fire:
                self._send(task)
                self.db.log_reminder_sent(task.id, cur_date)

    @staticmethod
    def _send(task):
        try:
            from plyer import notification
            body = (task.description[:120] + '…'
                    if len(task.description) > 120
                    else task.description) or 'Task reminder'
            notification.notify(
                title=f"⏰  {task.title}",
                message=body,
                app_name="Work Planner",
                timeout=10,
            )
        except Exception as exc:
            print(f"[Notifier] notify failed: {exc}")
