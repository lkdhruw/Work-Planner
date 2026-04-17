"""Work Planner — entry point."""

import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.database import Database
from app.notifier import NotificationScheduler
from app.ui.main_window import MainWindow


def main():
    # High-DPI scaling (Qt 6 enables it by default, but be explicit)
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')

    app = QApplication(sys.argv)
    app.setApplicationName("WorkPlanner")
    app.setOrganizationName("AntiGravity")
    app.setQuitOnLastWindowClosed(True)

    # Load QSS stylesheet
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    qss_path = os.path.join(base_path, 'app', 'ui', 'styles', 'theme.qss')
    if os.path.exists(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as fh:
            app.setStyleSheet(fh.read())

    # Initialise database
    db = Database()
    db.initialize()

    # Start notification scheduler
    scheduler = NotificationScheduler(db)
    scheduler.start()

    # Show main window
    window = MainWindow(db, scheduler)
    window.show()

    result = app.exec()
    scheduler.stop()
    sys.exit(result)


if __name__ == '__main__':
    main()
