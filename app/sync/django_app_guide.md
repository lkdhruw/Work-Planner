# Django App Integration Guide — Work Planner Sync

This document explains how to create a **Django app** (not a new project) inside
your existing Django project to expose a DRF API that the Work Planner desktop
client can sync with.

---

## 1. Prerequisites

Your existing Django project should already have:

```
your_project/
    manage.py
    your_project/
        settings.py
        urls.py
        wsgi.py
```

Install required packages if not already present:

```bash
pip install djangorestframework
```

Add to `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework.authtoken',   # Token authentication
    'workplanner',                # the new app (created below)
]
```

Also add DRF default authentication settings:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # for browser login
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

---

## 2. Create the Django App

```bash
python manage.py startapp workplanner
```

Directory structure after creation:

```
workplanner/
    __init__.py
    admin.py
    apps.py
    migrations/
        __init__.py
    models.py
    serializers.py      -- create this
    views.py
    urls.py             -- create this
    tests.py
```

---

## 3. Models (`workplanner/models.py`)

```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Profile(models.Model):
    """Task profile / category, per user."""
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profiles')
    name       = models.CharField(max_length=120)
    color      = models.CharField(max_length=20, default='#7C3AED')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [('user', 'name')]

    def __str__(self):
        return f"{self.user.username} / {self.name}"


class Task(models.Model):
    """A single task item, owned by a user and optionally assigned a profile."""

    REMINDER_CHOICES = [
        ('none',    'None'),
        ('once',    'Once'),
        ('daily',   'Daily'),
        ('weekly',  'Weekly'),
        ('monthly', 'Monthly'),
    ]

    user                 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    profile              = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks'
    )
    title                = models.CharField(max_length=500)
    description          = models.TextField(blank=True, default='')
    due_date             = models.DateField(null=True, blank=True)
    is_completed         = models.BooleanField(default=False)
    reminder_type        = models.CharField(max_length=10, choices=REMINDER_CHOICES, default='none')
    reminder_time        = models.TimeField(null=True, blank=True)
    reminder_datetime    = models.DateTimeField(null=True, blank=True)
    reminder_days        = models.JSONField(null=True, blank=True)
    reminder_day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_completed', 'due_date', '-created_at']

    def __str__(self):
        return self.title


class SubTask(models.Model):
    """A checklist item belonging to a Task."""
    task         = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title        = models.CharField(max_length=500)
    is_completed = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.title
```

Run migrations:

```bash
python manage.py makemigrations workplanner
python manage.py migrate
```

---

## 4. Serializers (`workplanner/serializers.py`)

```python
from rest_framework import serializers
from .models import Profile, Task, SubTask


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Profile
        fields = ['id', 'name', 'color', 'created_at']
        read_only_fields = ['id', 'created_at']


class SubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SubTask
        fields = ['id', 'task', 'title', 'is_completed', 'created_at']
        read_only_fields = ['id', 'task', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubTaskSerializer(many=True, read_only=True)
    profile  = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model  = Task
        fields = [
            'id', 'profile', 'title', 'description', 'due_date',
            'is_completed', 'reminder_type', 'reminder_time',
            'reminder_datetime', 'reminder_days', 'reminder_day_of_month',
            'subtasks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'subtasks', 'created_at', 'updated_at']
```

---

## 5. ViewSets (`workplanner/views.py`)

```python
from django.http import JsonResponse
from django.shortcuts import redirect

from rest_framework import viewsets, permissions
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Profile, Task, SubTask
from .serializers import ProfileSerializer, TaskSerializer, SubTaskSerializer


class IsOwner(permissions.BasePermission):
    """Object-level permission: only the owner can access."""
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class   = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class   = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = Task.objects.filter(user=self.request.user).select_related('profile')
        profile_id = self.request.query_params.get('profile')
        if profile_id:
            qs = qs.filter(profile_id=profile_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubTaskViewSet(viewsets.ModelViewSet):
    serializer_class   = SubTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SubTask.objects.filter(
            task_id=self.kwargs['task_pk'],
            task__user=self.request.user,
        )

    def perform_create(self, serializer):
        task = Task.objects.get(pk=self.kwargs['task_pk'], user=self.request.user)
        serializer.save(task=task)


def desktop_auth_view(request):
    """
    Desktop sign-in flow:

    1. Desktop app opens browser -> GET /api/desktop-auth/?next=<callback_url>
    2. If not logged in, Django redirects to the login page.
    3. After successful login the user is redirected back here.
    4. This view creates/fetches the DRF token and appends it to the callback
       URL, then redirects the browser to localhost so the desktop HTTP
       listener can capture it.

    Example callback: http://localhost:9731/auth/callback?token=<TOKEN>
    """
    next_url = request.GET.get('next', '')
    if not request.user.is_authenticated:
        from django.conf import settings as s
        return redirect(f"{s.LOGIN_URL}?next={request.path}?next={next_url}")

    token, _ = Token.objects.get_or_create(user=request.user)
    if next_url:
        separator = '&' if '?' in next_url else '?'
        return redirect(f"{next_url}{separator}token={token.key}")
    return JsonResponse({'token': token.key})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ping(request):
    """Health-check -- returns 200 if token is valid."""
    return Response({'status': 'ok', 'user': request.user.username})
```

---

## 6. URL Configuration

### `workplanner/urls.py` (new file)

```python
from django.urls import path, include
from rest_framework_nested import routers      # pip install drf-nested-routers

from . import views

router = routers.DefaultRouter()
router.register(r'profiles', views.ProfileViewSet, basename='profile')
router.register(r'tasks',    views.TaskViewSet,    basename='task')

tasks_router = routers.NestedDefaultRouter(router, r'tasks', lookup='task')
tasks_router.register(r'subtasks', views.SubTaskViewSet, basename='task-subtasks')

urlpatterns = [
    path('',              include(router.urls)),
    path('',              include(tasks_router.urls)),
    path('ping/',         views.ping,               name='wp-ping'),
    path('desktop-auth/', views.desktop_auth_view,  name='desktop-auth'),
]
```

Install nested router package:

```bash
pip install drf-nested-routers
```

### Include in project `urls.py`

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout
    path('api/',      include('workplanner.urls')),
]
```

---

## 7. Admin Registration (`workplanner/admin.py`)

```python
from django.contrib import admin
from .models import Profile, Task, SubTask

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ['name', 'user', 'color', 'created_at']
    list_filter   = ['user']

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display  = ['title', 'user', 'profile', 'is_completed', 'due_date']
    list_filter   = ['user', 'is_completed', 'reminder_type']
    search_fields = ['title', 'description']

@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display  = ['title', 'task', 'is_completed']
```

---

## 8. Auto-create Token for New Users (`workplanner/signals.py`)

```python
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

@receiver(post_save, sender=get_user_model())
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
```

Wire it up in `workplanner/apps.py`:

```python
from django.apps import AppConfig

class WorkplannerConfig(AppConfig):
    name = 'workplanner'

    def ready(self):
        import workplanner.signals  # noqa: F401
```

Create tokens for existing users:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
for u in get_user_model().objects.all():
    Token.objects.get_or_create(user=u)
print('Done.')
"
```

---

## 9. Desktop Auth Flow Diagram

```
Desktop App                  Browser               Django Server
    |                           |                        |
    |-- opens browser URL ----->|                        |
    |   /api/desktop-auth/      |-- GET desktop-auth/ -->|
    |   ?next=localhost:9731    |<-- redirect /login/ ---|
    |                           |-- POST credentials --->|
    |                           |<-- redirect back ------|
    |                           |-- GET desktop-auth/ -->|
    |                           |<-- redirect to --------|
    |                           |  localhost:9731/auth/callback?token=XXX
    |<-- local server captures token -------------------|
    |   stores in settings DB   |                        |
    |                           |                        |
    |-- API calls with ----------------------------------------->|
    |   Authorization: Token XXX                                  |
```

---

## 10. API Endpoint Reference

| Method   | URL                                      | Description                         |
|----------|------------------------------------------|-------------------------------------|
| GET      | /api/ping/                               | Health check (requires token)       |
| GET      | /api/desktop-auth/                       | Browser-based sign-in trigger       |
| GET      | /api/profiles/                           | List user's profiles                |
| POST     | /api/profiles/                           | Create profile                      |
| PATCH    | /api/profiles/id/                        | Update profile                      |
| DELETE   | /api/profiles/id/                        | Delete profile                      |
| GET      | /api/tasks/                              | List tasks (filter: ?profile=id)    |
| POST     | /api/tasks/                              | Create task                         |
| PATCH    | /api/tasks/id/                           | Update task                         |
| DELETE   | /api/tasks/id/                           | Delete task                         |
| GET      | /api/tasks/id/subtasks/                  | List subtasks for a task            |
| POST     | /api/tasks/id/subtasks/                  | Add subtask                         |
| PATCH    | /api/tasks/id/subtasks/sub_id/           | Update subtask                      |
| DELETE   | /api/tasks/id/subtasks/sub_id/           | Delete subtask                      |

---

## 11. Desktop SQLite Migration

Run once against the local `workplanner.db` before activating sync:

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

---

## 12. Quick-Start Checklist

- [ ] `pip install djangorestframework drf-nested-routers`
- [ ] Add apps + REST_FRAMEWORK config to `settings.py`
- [ ] `python manage.py startapp workplanner`
- [ ] Copy models, serializers, views, urls, admin, signals code above
- [ ] Include workplanner.urls at /api/ in project urls.py
- [ ] `python manage.py makemigrations workplanner && python manage.py migrate`
- [ ] Create auth tokens for existing users
- [ ] Verify `/api/ping/` returns 200 with a valid token
- [ ] Add `remote_id` columns to desktop `workplanner.db`
- [ ] Set `sync_server_url` in desktop app settings
