# FastAPI Integration Guide — Work Planner Sync

This document explains how to create a **FastAPI backend** to expose a REST API that the Work Planner desktop client can sync with. 

---

## 1. Prerequisites

Install the required packages:

```bash
pip install fastapi "uvicorn[standard]" sqlalchemy databases asyncpg pydantic
```

*(Note: We will use SQLAlchemy with an SQLite backend in these examples, but you can use PostgreSQL/MySQL).*

---

## 2. Models (SQLAlchemy)

Create your SQLAlchemy models to represent `User`, `Profile`, `Task`, and `SubTask`.

```python
# models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date, Time, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    token = Column(String, unique=True, index=True)
    
class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    color = Column(String, default="#7C3AED")
    
    owner = relationship("User")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    title = Column(String, index=True)
    description = Column(String, default="")
    due_date = Column(Date, nullable=True)
    is_completed = Column(Boolean, default=False)
    
    reminder_type = Column(String, default="none")
    reminder_time = Column(Time, nullable=True)
    reminder_datetime = Column(DateTime, nullable=True)
    reminder_days = Column(JSON, nullable=True)
    reminder_day_of_month = Column(Integer, nullable=True)
    
    owner = relationship("User")
    profile = relationship("Profile")
    subtasks = relationship("SubTask", back_populates="task", cascade="all, delete-orphan")

class SubTask(Base):
    __tablename__ = "subtasks"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    title = Column(String, index=True)
    is_completed = Column(Boolean, default=False)
    
    task = relationship("Task", back_populates="subtasks")
```

---

## 3. Pydantic Schemas (DTOs)

```python
# schemas.py
from datetime import date, time, datetime
from typing import List, Optional
from pydantic import BaseModel

class SubTaskBase(BaseModel):
    title: str
    is_completed: bool = False

class SubTaskResponse(SubTaskBase):
    id: int
    task_id: int
    class Config:
        orm_mode = True

class ProfileBase(BaseModel):
    name: str
    color: str = "#7C3AED"

class ProfileResponse(ProfileBase):
    id: int
    class Config:
        orm_mode = True

class TaskBase(BaseModel):
    title: str
    profile: Optional[int] = None
    description: str = ""
    due_date: Optional[date] = None
    is_completed: bool = False
    reminder_type: str = "none"
    reminder_time: Optional[time] = None
    reminder_datetime: Optional[datetime] = None
    reminder_days: Optional[List[int]] = None
    reminder_day_of_month: Optional[int] = None

class TaskResponse(TaskBase):
    id: int
    subtasks: List[SubTaskResponse] = []
    class Config:
        orm_mode = True
```

---

## 4. Authentication Dependency

In FastAPI, we can create a dependency to extract the `Authorization: Token <token>` header sent by the desktop client.

```python
# auth.py
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import models

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Token "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    user = db.query(models.User).filter(models.User.token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

---

## 5. API Endpoints

Create the main router matching the endpoints expected by the desktop application.

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
import models, schemas, auth
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# -- Ping --
@app.get("/api/ping/")
def ping(user: models.User = Depends(auth.get_current_user)):
    return {"status": "ok", "user": user.username}

# -- Desktop Auth --
@app.get("/api/desktop-auth/")
def desktop_auth_view(next: str = ""):
    """
    Mock endpoint for desktop auth. Usually you'd have an HTML login form here.
    Once authenticated, you generate a token and redirect back to the client.
    """
    # Assuming user is authenticated and token is 'mock_token_123'
    token = "mock_token_123" 
    if next:
        separator = '&' if '?' in next else '?'
        return RedirectResponse(f"{next}{separator}token={token}")
    return {"token": token}

# -- Profiles --
@app.get("/api/profiles/", response_model=List[schemas.ProfileResponse])
def get_profiles(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Profile).filter(models.Profile.user_id == user.id).all()

@app.post("/api/profiles/", response_model=schemas.ProfileResponse)
def create_profile(profile: schemas.ProfileBase, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_obj = models.Profile(**profile.dict(), user_id=user.id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

# -- Tasks --
@app.get("/api/tasks/", response_model=List[schemas.TaskResponse])
def get_tasks(profile: int = None, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    query = db.query(models.Task).filter(models.Task.user_id == user.id)
    if profile:
        query = query.filter(models.Task.profile_id == profile)
    return query.all()

@app.post("/api/tasks/", response_model=schemas.TaskResponse)
def create_task(task: schemas.TaskBase, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    task_data = task.dict()
    profile_id = task_data.pop("profile")
    db_obj = models.Task(**task_data, profile_id=profile_id, user_id=user.id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

# ... Add remaining PATCH / DELETE endopints for Tasks and Subtasks following the same pattern ...
```

---

## 6. Desktop Auth Flow Summary

```
Desktop App                         Browser                      FastAPI Server
    |                                  |                              |
    |── opens login URL ──────────────>|                              |
    |   /api/desktop-auth/?next=...    |── GET /api/desktop-auth/ ──>|
    |                                  |<── HTML Login Form ─────────|
    |                                  |── POST credentials ─────────>|
    |                                  |── Server generates token     |
    |                                  |<── redirect to localhost ───|
    |                                  |   http://localhost:9731/auth/callback?token=XXX
    |<── local server captures token ──|                              |
    |   stores token in settings DB    |                              |
    |── subsequent API calls with ────────────────────────────────────>|
    |   Authorization: Token XXX                                      |
```

---

## 7. API Endpoint Reference

| Method   | URL                                      | Description                         |
|----------|------------------------------------------|-------------------------------------|
| GET      | /api/ping/                               | Health check (requires token)       |
| GET      | /api/desktop-auth/                       | Browser-based sign-in trigger       |
| GET      | /api/profiles/                           | List user's profiles                |
| POST     | /api/profiles/                           | Create profile                      |
| PATCH    | /api/profiles/{id}/                      | Update profile                      |
| DELETE   | /api/profiles/{id}/                      | Delete profile                      |
| GET      | /api/tasks/                              | List tasks (filter: ?profile=id)    |
| POST     | /api/tasks/                              | Create task                         |
| PATCH    | /api/tasks/{id}/                         | Update task                         |
| DELETE   | /api/tasks/{id}/                         | Delete task                         |
| GET      | /api/tasks/{task_id}/subtasks/           | List subtasks for a task            |
| POST     | /api/tasks/{task_id}/subtasks/           | Add subtask                         |
| PATCH    | /api/tasks/{task_id}/subtasks/{sub_id}/  | Update subtask                      |
| DELETE   | /api/tasks/{task_id}/subtasks/{sub_id}/  | Delete subtask                      |

---

## 8. Database Column Migration (Desktop Side)

Ensure these are applied (or are auto-managed by your SQLite init sequence in the Work Planner desktop app):

```sql
ALTER TABLE tasks    ADD COLUMN remote_id INTEGER DEFAULT NULL;
ALTER TABLE profiles ADD COLUMN remote_id INTEGER DEFAULT NULL;

CREATE TABLE IF NOT EXISTS sync_deleted (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    model      TEXT NOT NULL,
    remote_id  INTEGER NOT NULL,
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
