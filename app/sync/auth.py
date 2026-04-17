"""Authentication manager — browser-based DRF Token auth flow.

Flow:
  1. Open the Django login page in the system browser.
  2. The Django view redirects to a local callback URL after successful login,
     carrying the DRF token as a query-param (or the desktop app can poll a
     dedicated endpoint using a one-time code).
  3. AuthManager stores the token in the app settings DB.

Token is then sent as  ``Authorization: Token <token>``  on every API request.
"""

from __future__ import annotations

import threading
import webbrowser
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ── defaults (overridden by settings) ─────────────────────────────────────────
DEFAULT_CALLBACK_PORT = 9731
CALLBACK_PATH = "/auth/callback"


class _CallbackHandler(BaseHTTPRequestHandler):
    """Tiny one-shot HTTP handler that captures the token from the redirect."""

    token: Optional[str] = None
    on_token: Optional[Callable[[str], None]] = None

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == CALLBACK_PATH:
            qs = parse_qs(parsed.query)
            token = qs.get("token", [None])[0]
            if token:
                _CallbackHandler.token = token
                if _CallbackHandler.on_token:
                    _CallbackHandler.on_token(token)
                self._respond(200, "Sign-in successful! You may close this tab.")
            else:
                self._respond(400, "Token missing from callback URL.")
        else:
            self._respond(404, "Not found.")

    def _respond(self, code: int, body: str):
        encoded = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):  # silence default access log
        pass


class AuthManager:
    """Manages DRF token authentication for the Work Planner desktop app.

    Parameters
    ----------
    db:
        The ``Database`` instance used to persist the auth token.
    server_base_url:
        Root URL of the Django server, e.g. ``https://example.com``.
    login_path:
        Django URL path that initiates the browser sign-in flow.
        The path should accept ``?next=<callback_url>`` so Django can redirect
        back after a successful login.  Defaults to ``/api/desktop-auth/``.
    callback_port:
        Local port the tiny callback server listens on.
    """

    SETTINGS_KEY_TOKEN   = "sync_token"
    SETTINGS_KEY_BASEURL = "sync_server_url"

    def __init__(
        self,
        db,
        server_base_url: str = "",
        login_path: str = "/api/desktop-auth/",
        callback_port: int = DEFAULT_CALLBACK_PORT,
    ):
        self.db               = db
        self.server_base_url  = server_base_url or db.get_setting(self.SETTINGS_KEY_BASEURL, "")
        self.login_path       = login_path
        self.callback_port    = callback_port
        self._httpd: Optional[HTTPServer] = None

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def token(self) -> Optional[str]:
        """Return the stored DRF token, or ``None`` if not authenticated."""
        return self.db.get_setting(self.SETTINGS_KEY_TOKEN)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def start_login(self, on_success: Callable[[str], None], on_error: Callable[[str], None]):
        """Open the browser for sign-in and start the local callback listener.

        Parameters
        ----------
        on_success:
            Called (from a background thread) with the token string once the
            user authenticates successfully.
        on_error:
            Called with an error message string if something goes wrong.
        """
        if not self.server_base_url:
            on_error("Server URL is not configured.")
            return

        callback_url = f"http://localhost:{self.callback_port}{CALLBACK_PATH}"
        login_url = (
            f"{self.server_base_url.rstrip('/')}{self.login_path}"
            f"?next={callback_url}"
        )

        def _store_and_notify(token: str):
            self.db.set_setting(self.SETTINGS_KEY_TOKEN, token)
            log.info("DRF token received and stored.")
            self._stop_callback_server()
            on_success(token)

        _CallbackHandler.token = None
        _CallbackHandler.on_token = _store_and_notify

        threading.Thread(target=self._run_callback_server, args=(on_error,), daemon=True).start()
        log.info("Opening browser: %s", login_url)
        webbrowser.open(login_url)

    def logout(self):
        """Remove the stored token."""
        self.db.set_setting(self.SETTINGS_KEY_TOKEN, "")
        log.info("Logged out — token cleared.")

    def set_server_url(self, url: str):
        """Persist the server base URL."""
        self.server_base_url = url.rstrip("/")
        self.db.set_setting(self.SETTINGS_KEY_BASEURL, self.server_base_url)

    # ── internal ───────────────────────────────────────────────────────────────

    def _run_callback_server(self, on_error: Callable[[str], None]):
        try:
            self._httpd = HTTPServer(("localhost", self.callback_port), _CallbackHandler)
            self._httpd.timeout = 300  # wait up to 5 min for user to log in
            self._httpd.handle_request()
        except OSError as exc:
            log.error("Callback server error: %s", exc)
            on_error(str(exc))
        finally:
            self._httpd = None

    def _stop_callback_server(self):
        if self._httpd:
            try:
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
