"""Daily ladder cron script (stdlib only): POST {base_url}/api/ladder/run.

Manifest entry point: `cron/daily_ladder.py:run`. No model call, no credits.

Test seam: every HTTP request goes through the module-level function
`_open(request, timeout)`. Tests patch `cron.daily_ladder._open` (or the
module's `_open` attribute) and return an object with `getcode()` and
`close()`, or raise `urllib.error.HTTPError` / `URLError` / `socket.timeout`.

Nothing here prints or raises a secret value, a response body or a header.
Log lines are fixed tokens plus an HTTP status code. Exceptions are raised
`from None` with fixed tokens only, because the scheduler persists
`TypeName: str(e)` as the run's last error.
"""

import json
import os
import pathlib
import socket
import urllib.error
import urllib.request

APP_NAME = "dues-banshee"

# Cron `timeout` is 290 and `timeout_secs` is 300 (design D8); stay below both.
HTTP_TIMEOUT_SECS = 240


class LadderFailed(Exception):
    """Run failed. The message is always one of a fixed set of tokens."""


def data_dir(env):
    """Resolve the app Data_Dir (design D1).

    `$KIROCREW_HOME/apps/<KIROCREW_APP_NAME or dues-banshee>/data` when
    KIROCREW_HOME is set and non-empty, else `~/.kiro/crew/apps/dues-banshee/data`.
    """
    home = env.get("KIROCREW_HOME")
    if home:
        name = env.get("KIROCREW_APP_NAME") or APP_NAME
        return pathlib.Path(home) / "apps" / name / "data"
    return pathlib.Path.home() / ".kiro" / "crew" / "apps" / APP_NAME / "data"


def load_secrets(path):
    """Read `base_url` and `ladder_run_secret` from one credentials file.

    Returns {"base_url", "ladder_run_secret"} or None. Needs an https
    `base_url` and a non-empty `ladder_run_secret`. Never raises and never
    logs or echoes file content.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    base_url = data.get("base_url")
    secret = data.get("ladder_run_secret")
    if not isinstance(base_url, str) or not base_url.startswith("https://"):
        return None
    if not isinstance(secret, str) or not secret:
        return None
    return {"base_url": base_url, "ladder_run_secret": secret}


def ladder_credentials(d):
    """`secrets.json` first, then `ladder.json`, else None.

    A masked, missing, unreadable or invalid file falls through to the next.
    Which file supplied the values is not reported.
    """
    d = pathlib.Path(d)
    return load_secrets(d / "secrets.json") or load_secrets(d / "ladder.json")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so the bearer never follows a 3xx to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request, timeout):
    """Send `request` once; a refused 3xx surfaces as HTTPError. Patch in tests."""
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=timeout)


def _fail(token):
    print("daily-ladder: failed " + token)
    raise LadderFailed(token) from None


def run(ctx=None):
    """Cron entry point. `ctx` is unused."""
    creds = ladder_credentials(data_dir(os.environ))
    if creds is None:
        print("daily-ladder: failed not_configured")
        raise LadderFailed("not_configured") from None

    url = creds["base_url"].rstrip("/") + "/api/ladder/run"
    code = None
    failure = None
    try:
        request = urllib.request.Request(
            url,
            data=b"",
            method="POST",
            headers={"Authorization": "Bearer " + creds["ladder_run_secret"]},
        )
        response = _open(request, HTTP_TIMEOUT_SECS)
        try:
            code = response.getcode()
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        # An HTTP error status is still a response; the body is never read.
        code = exc.code
        try:
            exc.close()
        except Exception:
            pass
    except (socket.timeout, TimeoutError):
        failure = "timeout"
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            failure = "timeout"
        else:
            failure = "connection"
    except Exception:
        # OSError and anything else (e.g. an unusable URL): fixed token only.
        failure = "connection"

    if failure is not None:
        _fail(failure)

    print("daily-ladder: status %d" % code)
    if not 200 <= code <= 299:
        raise LadderFailed("status %d" % code) from None
