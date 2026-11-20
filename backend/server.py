"""Dues Banshee backend: pure helpers (Python standard library only).

The HTTP server and routes are added in a later task. Nothing in this module
logs, prints or formats a secret value into an exception message.
"""

import hashlib
import hmac
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_NAME = "dues-banshee"

# Gateway proxy cap is 30 s (design D4); keep 10 s of margin.
UPSTREAM_TIMEOUT_SECS = 20

_MAX_SKEW_SECONDS = 60
_MAX_TS_DIGITS = 12
_TODAY_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def data_dir(env):
    """Resolve the app Data_Dir (design D1).

    `$KIROCREW_HOME/apps/<KIROCREW_APP_NAME or dues-banshee>/data` when
    KIROCREW_HOME is set and non-empty, else `~/.kiro/crew/apps/dues-banshee/data`.
    """
    home = env.get("KIROCREW_HOME")
    if home:
        name = env.get("KIROCREW_APP_NAME") or APP_NAME
        return Path(home) / "apps" / name / "data"
    return Path.home() / ".kiro" / "crew" / "apps" / APP_NAME / "data"


def load_secrets(path):
    """Read `base_url` and `crew_read_secret` from the Secrets_File.

    Returns {"base_url", "crew_read_secret"} or None. Read-only; never raises
    and never logs or echoes file content.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    base_url = data.get("base_url")
    secret = data.get("crew_read_secret")
    if not isinstance(base_url, str) or not base_url.startswith("https://"):
        return None
    if not isinstance(secret, str) or not secret:
        return None
    return {"base_url": base_url, "crew_read_secret": secret}


def valid_today(value):
    """Format check only: four digits, dash, two digits, dash, two digits."""
    return isinstance(value, str) and _TODAY_RE.fullmatch(value) is not None


def summary_url(base_url, query):
    """Build the Summary_Endpoint URL.

    `query` is a mapping of key -> list of values (as `urllib.parse.parse_qs`
    returns) or a raw query string. `today` is forwarded only when there is
    exactly one value and it is a Valid_Today; every other key is dropped.
    """
    url = base_url.rstrip("/") + "/api/crew/summary"
    if isinstance(query, str):
        query = urllib.parse.parse_qs(query, keep_blank_values=True)
    values = (query or {}).get("today")
    if isinstance(values, str):
        values = [values]
    if values is not None and len(values) == 1 and valid_today(values[0]):
        url += "?today=" + values[0]
    return url


def _error(status, code):
    return status, json.dumps({"error": code}).encode("utf-8")


def map_upstream(status, body):
    """Map an upstream summary response to (http_status, response_bytes).

    200 with valid JSON returns the upstream bytes unchanged. Every other
    outcome returns exactly {"error": "<code>"}; the upstream body is dropped.
    """
    if status == 200:
        try:
            json.loads(body)
        except Exception:
            return _error(502, "upstream_error")
        return 200, body
    if status == 401:
        return _error(502, "unauthorized")
    if status == 404:
        return _error(502, "not_found")
    if status == 503:
        return _error(503, "unavailable")
    return _error(502, "upstream_error")


def verify_signature(header, method, target, body, secret, now):
    """Verify the gateway's `X-KiroCrew-Proxy: <ts>:<hmac>` header (design D9).

    HMAC-SHA256(secret, "<ts>:<method>:<target>:<sha256hex(body)>"), +/-60 s,
    constant-time compare. Fails closed on a missing secret or header.
    """
    if not secret or not header or not isinstance(header, str) or ":" not in header:
        return False
    ts_str, _, signature = header.partition(":")
    if not (ts_str.isascii() and ts_str.isdigit()) or len(ts_str) > _MAX_TS_DIGITS:
        return False
    if not signature:
        return False
    if abs(now - int(ts_str)) > _MAX_SKEW_SECONDS:
        return False
    body_hash = hashlib.sha256(body or b"").hexdigest()
    message = "%s:%s:%s:%s" % (ts_str, method, target, body_hash)
    expected = hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(
        expected.encode("utf-8", "surrogatepass"),
        signature.encode("utf-8", "surrogatepass"),
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so the bearer never follows a 3xx to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def no_redirect_opener():
    """An opener that raises HTTPError on any 3xx instead of following it."""
    return urllib.request.build_opener(_NoRedirect)


def fetch_summary(url, bearer, opener):
    """One GET with the Crew bearer. Returns (status, body).

    The body is read only on 200; any other HTTP status returns b"". Timeouts
    and connection errors propagate to the caller. No retry.
    """
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": "Bearer " + bearer, "Accept": "application/json"},
    )
    try:
        with opener.open(request, timeout=UPSTREAM_TIMEOUT_SECS) as response:
            status = response.status
            body = response.read() if status == 200 else b""
            return status, body
    except urllib.error.HTTPError as err:
        code = err.code
        err.close()
        return code, b""
