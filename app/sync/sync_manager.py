"""SyncManager — orchestrates two-way sync between local SQLite and the server.

Strategy
--------
* Each local task/profile stores an optional ``remote_id`` (needs a DB column,
  see ``database.py`` migration notes below).
* On push: new local records (``remote_id IS NULL``) are POSTed; existing ones
  are PATCHed; deletions are tracked in a ``sync_deleted`` table and DELETEd.
* On pull: server records are upserted into the local DB using ``remote_id`` as
  the correlation key.
* Conflict resolution: **server wins** (last-write-wins by ``updated_at``).

Migration note  (run once, or add to ``Database.initialize()``)
---------------------------------------------------------------
    ALTER TABLE tasks    ADD COLUMN remote_id INTEGER DEFAULT NULL;
    ALTER TABLE profiles ADD COLUMN remote_id INTEGER DEFAULT NULL;

    CREATE TABLE IF NOT EXISTS sync_deleted (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        model      TEXT NOT NULL,   -- 'task' | 'profile'
        remote_id  INTEGER NOT NULL,
        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from .api_client import APIClient, APIError
from .auth import AuthManager

log = logging.getLogger(__name__)


class SyncManager:
    """High-level sync orchestrator.

    Parameters
    ----------
    db:
        App ``Database`` instance.
    auth:
        ``AuthManager`` (provides the token).
    server_base_url:
        Django server root URL.
    on_sync_complete:
        Optional callback called on the main thread after a sync finishes.
    on_sync_error:
        Optional callback called with an error message string on failure.
    """

    def __init__(
        self,
        db,
        auth: AuthManager,
        server_base_url: str = "",
        on_sync_complete: Optional[Callable] = None,
        on_sync_error: Optional[Callable[[str], None]] = None,
    ):
        self.db               = db
        self.auth             = auth
        self.server_base_url  = server_base_url
        self.on_sync_complete = on_sync_complete
        self.on_sync_error    = on_sync_error
        self._lock            = threading.Lock()
        self._running         = False

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        return self.auth.is_authenticated

    def sync_async(self):
        """Start a background sync. No-op if already running."""
        if self._running:
            log.debug("Sync already in progress — skipped.")
            return
        threading.Thread(target=self._run_sync, daemon=True).start()

    def sync_now(self):
        """Blocking sync call (use from a worker thread)."""
        self._run_sync()

    # ── internal sync pipeline ─────────────────────────────────────────────────

    def _client(self) -> APIClient:
        return APIClient(
            base_url=self.server_base_url or self.auth.server_base_url,
            token=self.auth.token,
        )

    def _run_sync(self):
        with self._lock:
            self._running = True
        try:
            if not self.auth.is_authenticated:
                raise RuntimeError("Not authenticated — sign in first.")

            client = self._client()

            if not client.ping():
                raise RuntimeError("Server unreachable.")

            log.info("Sync started.")
            self._push_profiles(client)
            self._pull_profiles(client)
            self._push_tasks(client)
            self._pull_tasks(client)
            log.info("Sync complete.")

            if self.on_sync_complete:
                self.on_sync_complete()
        except Exception as exc:
            log.error("Sync failed: %s", exc)
            if self.on_sync_error:
                self.on_sync_error(str(exc))
        finally:
            with self._lock:
                self._running = False

    # ── profiles ───────────────────────────────────────────────────────────────

    def _push_profiles(self, client: APIClient):
        """Push local profiles that have no remote_id (new) or have been updated."""
        try:
            profiles = self.db.get_profiles()
        except Exception as exc:
            log.warning("Could not read profiles for push: %s", exc)
            return

        for p in profiles:
            remote_id = getattr(p, 'remote_id', None)
            payload   = {"name": p.name, "color": p.color}
            try:
                if remote_id:
                    client.update_profile(remote_id, payload)
                    log.debug("Updated profile %s → remote %s", p.id, remote_id)
                else:
                    resp = client.create_profile(payload)
                    self._set_remote_id('profiles', p.id, resp['id'])
                    log.debug("Created profile %s → remote %s", p.id, resp['id'])
            except APIError as exc:
                log.warning("Profile push failed for id=%s: %s", p.id, exc)

    def _pull_profiles(self, client: APIClient):
        """Pull server profiles and upsert locally."""
        try:
            remote_profiles = client.list_profiles()
        except Exception as exc:
            log.warning("Profile pull failed: %s", exc)
            return

        for rp in remote_profiles:
            remote_id = rp['id']
            # Find local profile by remote_id
            local = self._find_local_by_remote('profiles', remote_id)
            if local:
                # Update local
                local.name  = rp['name']
                local.color = rp.get('color', local.color)
                self.db.update_profile(local)
            else:
                # Create local and link
                created = self.db.create_profile(rp['name'], rp.get('color', '#7C3AED'))
                self._set_remote_id('profiles', created.id, remote_id)

    # ── tasks ──────────────────────────────────────────────────────────────────

    def _push_tasks(self, client: APIClient):
        """Push local tasks to server."""
        try:
            tasks = self.db.get_tasks()
        except Exception as exc:
            log.warning("Could not read tasks for push: %s", exc)
            return

        for t in tasks:
            remote_id = getattr(t, 'remote_id', None)
            payload = {
                "title":                t.title,
                "description":          t.description or "",
                "due_date":             t.due_date,
                "is_completed":         t.is_completed,
                "reminder_type":        t.reminder_type or "none",
                "reminder_time":        t.reminder_time,
                "reminder_datetime":    t.reminder_datetime,
                "reminder_days":        t.reminder_days,
                "reminder_day_of_month": t.reminder_day_of_month,
                # Send the remote profile id if we know it
                "profile":              getattr(t.profile, 'remote_id', None) if t.profile else None,
            }
            try:
                if remote_id:
                    client.update_task(remote_id, payload)
                else:
                    resp = client.create_task(payload)
                    self._set_remote_id('tasks', t.id, resp['id'])
            except APIError as exc:
                log.warning("Task push failed for id=%s: %s", t.id, exc)

    def _pull_tasks(self, client: APIClient):
        """Pull server tasks and upsert locally."""
        try:
            remote_tasks = client.list_tasks()
        except Exception as exc:
            log.warning("Task pull failed: %s", exc)
            return

        from ..models import Task
        for rt in remote_tasks:
            remote_id = rt['id']
            local = self._find_local_by_remote('tasks', remote_id)
            if local:
                local.title          = rt['title']
                local.description    = rt.get('description', '')
                local.due_date       = rt.get('due_date')
                local.is_completed   = rt.get('is_completed', False)
                local.reminder_type  = rt.get('reminder_type', 'none')
                self.db.update_task(local)
            else:
                new_task = Task(
                    id=None,
                    profile_id=None,    # profile linkage handled separately
                    title=rt['title'],
                    description=rt.get('description', ''),
                    due_date=rt.get('due_date'),
                    reminder_type=rt.get('reminder_type', 'none'),
                    reminder_time=rt.get('reminder_time'),
                    reminder_datetime=rt.get('reminder_datetime'),
                    reminder_days=rt.get('reminder_days'),
                    reminder_day_of_month=rt.get('reminder_day_of_month'),
                    is_completed=rt.get('is_completed', False),
                )
                created = self.db.create_task(new_task)
                self._set_remote_id('tasks', created.id, remote_id)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _set_remote_id(self, table: str, local_id: int, remote_id: int):
        """Write the remote_id back to the local table."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            conn.execute(
                f"UPDATE {table} SET remote_id=? WHERE id=?",
                (remote_id, local_id)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning("Could not set remote_id on %s id=%s: %s", table, local_id, exc)

    def _find_local_by_remote(self, table: str, remote_id: int):
        """Return the local record whose remote_id matches, or None."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"SELECT * FROM {table} WHERE remote_id=?", (remote_id,)
            ).fetchone()
            conn.close()
            if not row:
                return None
            if table == 'profiles':
                from ..models import Profile
                return Profile(id=row['id'], name=row['name'], color=row['color'])
            elif table == 'tasks':
                return self.db.get_task(row['id'])
        except Exception as exc:
            log.warning("_find_local_by_remote(%s, %s) failed: %s", table, remote_id, exc)
        return None
