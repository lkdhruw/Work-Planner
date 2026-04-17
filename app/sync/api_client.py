"""DRF API Client — wraps all HTTP calls to the Django backend.

Every request adds the ``Authorization: Token <token>`` header
once a token is available.  Requests are made synchronously (blocking);
callers are responsible for running them in a background thread/worker.

Endpoints mirror the Django app described in ``django_app_guide.md``.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when the server returns a non-2xx response."""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body   = body
        super().__init__(f"HTTP {status}: {body}")


class APIClient:
    """Thin HTTP client for the Work Planner DRF backend.

    Parameters
    ----------
    base_url:
        Server root, e.g. ``https://example.com``.
    token:
        DRF auth token (may be ``None`` before sign-in).
    timeout:
        Request timeout in seconds.
    """

    def __init__(self, base_url: str, token: Optional[str] = None, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.token    = token
        self.timeout  = timeout

    # ── internal ───────────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Token {self.token}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
    ) -> Any:
        url     = self._url(path)
        body    = json.dumps(data).encode() if data is not None else None
        req     = urllib.request.Request(
            url, data=body, headers=self._headers(), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            log.error("API %s %s → %s: %s", method, url, exc.code, body)
            raise APIError(exc.code, body) from exc
        except urllib.error.URLError as exc:
            log.error("API %s %s → network error: %s", method, url, exc.reason)
            raise

    # ── convenience wrappers ───────────────────────────────────────────────────

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, data: Dict) -> Any:
        return self._request("POST", path, data)

    def patch(self, path: str, data: Dict) -> Any:
        return self._request("PATCH", path, data)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ── Task endpoints ─────────────────────────────────────────────────────────

    def list_tasks(self) -> List[Dict]:
        """GET /api/tasks/ — return list of task dicts."""
        return self.get("/api/tasks/")

    def create_task(self, payload: Dict) -> Dict:
        """POST /api/tasks/"""
        return self.post("/api/tasks/", payload)

    def update_task(self, remote_id: int, payload: Dict) -> Dict:
        """PATCH /api/tasks/<id>/"""
        return self.patch(f"/api/tasks/{remote_id}/", payload)

    def delete_task(self, remote_id: int):
        """DELETE /api/tasks/<id>/"""
        return self.delete(f"/api/tasks/{remote_id}/")

    # ── Profile endpoints ──────────────────────────────────────────────────────

    def list_profiles(self) -> List[Dict]:
        return self.get("/api/profiles/")

    def create_profile(self, payload: Dict) -> Dict:
        return self.post("/api/profiles/", payload)

    def update_profile(self, remote_id: int, payload: Dict) -> Dict:
        return self.patch(f"/api/profiles/{remote_id}/", payload)

    def delete_profile(self, remote_id: int):
        return self.delete(f"/api/profiles/{remote_id}/")

    # ── Subtask endpoints ──────────────────────────────────────────────────────

    def list_subtasks(self, task_id: int) -> List[Dict]:
        return self.get(f"/api/tasks/{task_id}/subtasks/")

    def create_subtask(self, task_id: int, payload: Dict) -> Dict:
        return self.post(f"/api/tasks/{task_id}/subtasks/", payload)

    def update_subtask(self, task_id: int, subtask_id: int, payload: Dict) -> Dict:
        return self.patch(f"/api/tasks/{task_id}/subtasks/{subtask_id}/", payload)

    def delete_subtask(self, task_id: int, subtask_id: int):
        return self.delete(f"/api/tasks/{task_id}/subtasks/{subtask_id}/")

    # ── Health check ──────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the server is reachable and token is valid."""
        try:
            self.get("/api/ping/")
            return True
        except Exception:
            return False
