from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Profile:
    id: Optional[int]
    name: str
    color: str = '#7C3AED'
    created_at: Optional[str] = None


@dataclass
class SubTask:
    id: Optional[int]
    task_id: int
    title: str
    is_completed: bool = False
    created_at: Optional[str] = None


@dataclass
class Task:
    id: Optional[int]
    profile_id: Optional[int]
    title: str
    description: str = ''
    due_date: Optional[str] = None          # YYYY-MM-DD
    # Reminder
    reminder_type: str = 'none'             # none | once | daily | weekly | monthly
    reminder_time: Optional[str] = None     # HH:MM  (daily / weekly / monthly)
    reminder_datetime: Optional[str] = None # ISO datetime  (once)
    reminder_days: Optional[str] = None     # JSON int array e.g. "[0,3]" Mon+Thu (weekly)
    reminder_day_of_month: Optional[int] = None  # 1-31 (monthly)
    is_completed: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Populated at query time, not stored
    profile: Optional[Profile] = field(default=None, compare=False, repr=False)
    subtasks: List[SubTask] = field(default_factory=list, compare=False, repr=False)
