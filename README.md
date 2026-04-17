# Work Planner

A modern, semi-transparent Python desktop sidebar widget for task and project management.

## Features

- 🪟 **Frameless transparent sidebar** — sits on your desktop without a native title bar
- 🎨 **Dark glassmorphism UI** — professional dark theme with purple/cyan gradient accents
- 📋 **Profiles** — group tasks into colored profiles (Work, Personal, Study, etc.)
- ✅ **Tasks & Subtasks** — create tasks with animated checkboxes, add inline subtasks
- 📅 **Due dates** with overdue detection (highlighted in amber/red)
- 🔔 **Flexible reminders**:
  - One-time (specific date & time)
  - Daily at HH:MM
  - Weekly on selected weekdays at HH:MM
  - Monthly on a specific day at HH:MM
- ➡️ **Slide animations** — task detail slides in from the right
- ⚙️ **Settings**: transparency slider (40–100%), font family & size picker, always-on-top toggle
- 💾 **Persistent** — window position, settings, and all data saved to SQLite

## Requirements

- Python 3.10+
- Windows 11 (x86-64) or macOS (Apple Silicon M3 supported natively)

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Project Structure

```
Work Planner/
├── main.py                        # Entry point
├── requirements.txt
├── workplanner.db                 # Auto-created SQLite database
└── app/
    ├── database.py                # SQLite data layer
    ├── models.py                  # Profile, Task, SubTask dataclasses
    ├── notifier.py                # Background reminder scheduler (plyer)
    └── ui/
        ├── main_window.py         # Frameless, translucent sidebar window
        ├── task_list.py           # Main list view + profile tabs
        ├── task_detail.py         # Task detail + subtask management
        ├── task_form.py           # Add/Edit task dialog
        ├── profile_form.py        # Create profile dialog
        ├── settings_window.py     # Settings: opacity, font, always-on-top
        ├── styles/theme.qss       # Full dark glassmorphism stylesheet
        └── widgets/
            ├── animated_stack.py  # Sliding page transition widget
            ├── checkbox.py        # Animated gradient checkbox
            └── task_card.py       # Individual task card
```

## Reminder Schedule Types

| Type | Description | Example |
|------|-------------|---------|
| Once | Fire at an exact date+time | Apr 25, 2026 at 09:00 |
| Daily | Every day at a time | Every day at 08:30 |
| Weekly | Specific weekdays at a time | Every Mon & Thu at 09:00 |
| Monthly | On a day number every month | Every month on the 5th at 10:00 |

## Database Location

The SQLite database is stored in a permanent OS-specific user data folder so that rebuilding the app or moving the executable does not erase your tasks:

- **Windows**: `%APPDATA%\WorkPlanner\workplanner.db`
- **macOS**: `~/Library/Application Support/WorkPlanner/workplanner.db`
- **Linux**: `~/.local/share/WorkPlanner/workplanner.db`

## Packaging

Use the included build script to generate standalone executables (e.g. `.exe` on Windows or `.app` on macOS):
```bash
python build_app.py
```
This handles temporary paths and resolves the QSS stylesheet natively for your operating system.
