"""Backend tests (unittest, stdlib only, no live network calls).

The server runs on an ephemeral loopback port inside each test. The upstream
is a stub opener injected through make_server(); nothing leaves the process.

Layout: `BackendTestCase` holds the shared fixtures, and each group of example
tests is its own class. Property tests (task 2.4) append further classes that
reuse `BackendTestCase`.
"""

import ast
import hashlib
import hmac
import http.client
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server  # noqa: E402

SERVER_PY = Path(__file__).resolve().with_name("server.py")

BASE_URL = "https://upstream.example.test"
CREW_SECRET = "crew-secret-AAAA1111"
LADDER_SECRET = "ladder-secret-BBBB2222"
PROXY_SECRET = "proxy-secret-CCCC3333"
UPSTREAM_LEAK = "UPSTREAM-BODY-LEAK-MARKER"
SUMMARY_JSON = b'{"supplierName": "Sharma", "totals": {"outstanding": {"text": "\\u20b94,12,000"}}}'


class StubResponse:
    """Minimal context-manager response, as returned by opener.open()."""

    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class StubOpener:
    """Injected upstream. Records every request; never touches the network.

    `outcome` is one of:
      * an exception instance, raised from open();
      * (status, body): 200 returns a response, any other status raises
        urllib.error.HTTPError (as the real opener does) whose body carries
        UPSTREAM_LEAK so tests can prove it is never relayed.
    """

    def __init__(self, outcome=(200, SUMMARY_JSON), return_status_as_response=False):
        self.outcome = outcome
        self.return_status_as_response = return_status_as_response
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        outcome = self.outcome
        if isinstance(outcome, BaseException):
            raise outcome
        status, body = outcome
        if status == 200 or self.return_status_as_response:
            return StubResponse(status, body)
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "stub",
            Message(),
            io.BytesIO(UPSTREAM_LEAK.encode("utf-8")),
        )


def sign(secret, method, target, body=b"", ts=None):
    """Build an X-KiroCrew-Proxy value in the format verify_signature checks."""
    ts_str = str(int(time.time()) if ts is None else ts)
    message = "%s:%s:%s:%s" % (ts_str, method, target, hashlib.sha256(body).hexdigest())
    mac = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return "%s:%s" % (ts_str, mac)


class BackendTestCase(unittest.TestCase):
    """Shared fixtures: temp Data_Dir, stub upstream, live loopback server."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = tmp.name
        self.data = Path(self.home) / "apps" / "dues-banshee" / "data"
        self.data.mkdir(parents=True)
        self.env = {"KIROCREW_HOME": self.home, "KIROCREW_PROXY_SECRET": PROXY_SECRET}

        # The handler writes log lines to sys.stderr; capture them.
        self.log = io.StringIO()
        patcher = mock.patch.object(sys, "stderr", self.log)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._assert_no_secrets_leaked)

    def _assert_no_secrets_leaked(self):
        logged = self.log.getvalue()
        for secret in (CREW_SECRET, LADDER_SECRET, PROXY_SECRET):
            self.assertNotIn(secret, logged)
        self.assertNotIn(UPSTREAM_LEAK, logged)

    # -- fixtures --

    @property
    def secrets_path(self):
        return self.data / "secrets.json"

    def write_secrets(self, **overrides):
        content = {
            "base_url": BASE_URL,
            "crew_read_secret": CREW_SECRET,
            "ladder_run_secret": LADDER_SECRET,
        }
        content.update(overrides)
        self.secrets_path.write_text(json.dumps(content), encoding="utf-8")

    def start(self, opener=None):
        """Start the server on 127.0.0.1:<ephemeral> and return the stub opener."""
        opener = opener if opener is not None else StubOpener()
        self.opener = opener
        httpd = server.make_server("127.0.0.1", 0, opener=opener, env=self.env)
        self.port = httpd.server_address[1]
        thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()

        def stop():
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        self.addCleanup(stop)
        return opener

    # -- requests --

    def request(self, method, target, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, target, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read(), response
        finally:
            conn.close()

    def signed_get(self, target, **sign_kwargs):
        header = sign(PROXY_SECRET, "GET", target, **sign_kwargs)
        return self.request("GET", target, headers={"X-KiroCrew-Proxy": header})

    def get_summary(self, target="/api/summary"):
        """Signed GET; returns (status, parsed JSON or raw bytes)."""
        status, body, _ = self.signed_get(target)
        try:
            return status, json.loads(body)
        except ValueError:
            return status, body


class HealthTests(BackendTestCase):
    def test_health_ok_without_auth_without_secrets_file(self):
        opener = self.start()
        self.assertFalse(self.secrets_path.exists())
        status, body, response = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertEqual(response.getheader("Content-Type"), "application/json")
        self.assertEqual(opener.requests, [])

    def test_health_ok_with_secrets_file_present_and_no_upstream_call(self):
        self.write_secrets()
        opener = self.start()
        status, body, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)
        for secret in (CREW_SECRET, LADDER_SECRET, BASE_URL):
            self.assertNotIn(secret.encode(), body)
        self.assertEqual(opener.requests, [])

    def test_health_ok_with_unreadable_secrets_file(self):
        self.secrets_path.write_text("{not json", encoding="utf-8")
        self.start()
        status, _, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)


class SummaryRequestTests(BackendTestCase):
    def test_summary_request_carries_crew_bearer(self):
        self.write_secrets()
        opener = self.start()
        status, _, _ = self.signed_get("/api/summary")
        self.assertEqual(status, 200)
        self.assertEqual(len(opener.requests), 1)
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + CREW_SECRET)
        self.assertEqual(request.full_url, BASE_URL + "/api/crew/summary")

    def test_ladder_secret_is_never_sent_upstream(self):
        self.write_secrets()
        opener = self.start()
        self.signed_get("/api/summary")
        for request in opener.requests:
            for _, value in request.header_items():
                self.assertNotIn(LADDER_SECRET, value)

    def test_success_body_passes_through_unchanged(self):
        self.write_secrets()
        self.start()
        status, body, response = self.signed_get("/api/summary")
        self.assertEqual(status, 200)
        self.assertEqual(body, SUMMARY_JSON)
        self.assertEqual(response.getheader("Content-Type"), "application/json")

    def test_valid_today_forwarded_and_invalid_dropped(self):
        self.write_secrets()
        opener = self.start()
        self.signed_get("/api/summary?today=2026-11-12")
        self.signed_get("/api/summary?today=12-11-2026")
        self.signed_get("/api/summary?other=1")
        self.assertEqual(
            [r.full_url for r in opener.requests],
            [
                BASE_URL + "/api/crew/summary?today=2026-11-12",
                BASE_URL + "/api/crew/summary",
                BASE_URL + "/api/crew/summary",
            ],
        )

    def test_upstream_timeout_passed_to_opener_and_below_gateway_cap(self):
        self.write_secrets()
        opener = self.start()
        self.signed_get("/api/summary")
        self.assertEqual(opener.timeouts, [server.UPSTREAM_TIMEOUT_SECS])
        self.assertLess(server.UPSTREAM_TIMEOUT_SECS, 30)


class ErrorMappingTests(BackendTestCase):
    """Design "Summary error mapping" table: (condition) -> (HTTP status, code)."""

    def assert_error(self, outcome, http_status, code, **opener_kwargs):
        opener = self.start(StubOpener(outcome, **opener_kwargs))
        status, body, _ = self.signed_get("/api/summary")
        self.assertEqual(status, http_status)
        self.assertEqual(json.loads(body), {"error": code})
        self.assertEqual(body, json.dumps({"error": code}).encode())
        self.assertNotIn(UPSTREAM_LEAK.encode(), body)
        self.assertNotIn(CREW_SECRET.encode(), body)
        self.assertEqual(len(opener.requests), 1)

    def setUp(self):
        super().setUp()
        self.write_secrets()

    def test_upstream_status_mapping(self):
        cases = [
            (401, 502, "unauthorized"),
            (404, 502, "not_found"),
            (500, 502, "upstream_error"),
            (503, 503, "unavailable"),
            (403, 502, "upstream_error"),
            (418, 502, "upstream_error"),
            (502, 502, "upstream_error"),
        ]
        for upstream, http_status, code in cases:
            with self.subTest(upstream=upstream):
                self.assert_error((upstream, b""), http_status, code)

    def test_status_returned_as_response_object_is_mapped_too(self):
        self.assert_error((401, UPSTREAM_LEAK.encode()), 502, "unauthorized", return_status_as_response=True)

    def test_200_with_non_json_body_is_upstream_error(self):
        self.assert_error((200, b"<html>" + UPSTREAM_LEAK.encode()), 502, "upstream_error")

    def test_timeout_maps_to_504(self):
        self.assert_error(socket.timeout("timed out"), 504, "timeout")

    def test_builtin_timeout_error_maps_to_504(self):
        self.assert_error(TimeoutError("timed out"), 504, "timeout")

    def test_urlerror_wrapping_timeout_maps_to_504(self):
        self.assert_error(urllib.error.URLError(socket.timeout("timed out")), 504, "timeout")

    def test_connection_error_maps_to_unavailable(self):
        self.assert_error(urllib.error.URLError("name resolution failed"), 503, "unavailable")

    def test_os_connection_refused_maps_to_unavailable(self):
        self.assert_error(ConnectionRefusedError("refused"), 503, "unavailable")

    def test_unexpected_exception_maps_to_upstream_error_without_leaking_text(self):
        self.assert_error(RuntimeError("boom " + CREW_SECRET), 502, "upstream_error")
        self.assertIn("RuntimeError", self.log.getvalue())
        self.assertNotIn("boom", self.log.getvalue())


class NotConfiguredTests(BackendTestCase):
    def assert_not_configured(self):
        opener = self.start()
        status, body, _ = self.signed_get("/api/summary")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body), {"error": "not_configured"})
        self.assertEqual(opener.requests, [], "upstream must not be called")

    def test_missing_file(self):
        self.assertFalse(self.secrets_path.exists())
        self.assert_not_configured()

    def test_bad_json(self):
        self.secrets_path.write_text("{ nope", encoding="utf-8")
        self.assert_not_configured()

    def test_json_but_not_an_object(self):
        self.secrets_path.write_text('["https://x.test", "s"]', encoding="utf-8")
        self.assert_not_configured()

    def test_empty_base_url(self):
        self.write_secrets(base_url="")
        self.assert_not_configured()

    def test_empty_crew_read_secret(self):
        self.write_secrets(crew_read_secret="")
        self.assert_not_configured()

    def test_absent_keys(self):
        self.secrets_path.write_text("{}", encoding="utf-8")
        self.assert_not_configured()

    def test_http_base_url(self):
        self.write_secrets(base_url="http://upstream.example.test")
        self.assert_not_configured()

    def test_only_valid_ladder_json_present(self):
        (self.data / "ladder.json").write_text(
            json.dumps({"base_url": BASE_URL, "ladder_run_secret": LADDER_SECRET}),
            encoding="utf-8",
        )
        self.assertFalse(self.secrets_path.exists())
        self.assert_not_configured()

    def test_ladder_json_does_not_fill_gaps_in_secrets_file(self):
        self.write_secrets(crew_read_secret="")
        (self.data / "ladder.json").write_text(
            json.dumps({"base_url": BASE_URL, "ladder_run_secret": LADDER_SECRET}),
            encoding="utf-8",
        )
        self.assert_not_configured()


class RedirectTests(BackendTestCase):
    def test_redirect_status_maps_to_upstream_error(self):
        self.write_secrets()
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                opener = self.start(StubOpener((code, b"")))
                status, body = self.get_summary()
                self.assertEqual(status, 502)
                self.assertEqual(body, {"error": "upstream_error"})
                self.assertEqual(len(opener.requests), 1)

    def test_real_no_redirect_opener_refuses_to_follow_3xx(self):
        calls = []

        class FakeRedirectingHTTPS(urllib.request.BaseHandler):
            handler_order = 100  # runs before the real HTTPSHandler

            def https_open(self, req):
                calls.append((req.full_url, req.get_header("Authorization")))
                headers = Message()
                headers["Location"] = "https://evil.example.test/steal"
                response = urllib.response.addinfourl(
                    io.BytesIO(b""), headers, req.full_url, 302
                )
                response.msg = "Found"
                return response

        opener = server.no_redirect_opener()
        opener.add_handler(FakeRedirectingHTTPS())
        status, body = server.fetch_summary(
            BASE_URL + "/api/crew/summary", CREW_SECRET, opener
        )
        self.assertEqual((status, body), (302, b""))
        self.assertEqual(len(calls), 1, "the redirect must not be followed")
        self.assertEqual(calls[0][0], BASE_URL + "/api/crew/summary")
        self.assertEqual(server.map_upstream(status, body)[0], 502)


class SignatureTests(BackendTestCase):
    def setUp(self):
        super().setUp()
        self.write_secrets()
        self.opener = self.start()

    def assert_unsigned(self, status, body):
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body), {"error": "unsigned"})
        self.assertEqual(self.opener.requests, [], "upstream must not be called")

    def test_correctly_signed_request_is_accepted(self):
        status, _, _ = self.signed_get("/api/summary")
        self.assertEqual(status, 200)

    def test_signed_request_with_query_is_accepted(self):
        status, _, _ = self.signed_get("/api/summary?today=2026-11-12")
        self.assertEqual(status, 200)

    def test_missing_signature(self):
        status, body, _ = self.request("GET", "/api/summary")
        self.assert_unsigned(status, body)

    def test_wrong_signature(self):
        header = sign("some-other-secret", "GET", "/api/summary")
        status, body, _ = self.request("GET", "/api/summary", headers={"X-KiroCrew-Proxy": header})
        self.assert_unsigned(status, body)

    def test_malformed_signature(self):
        for value in ("garbage", ":", "abc:def", "123:", ""):
            with self.subTest(value=value):
                status, body, _ = self.request(
                    "GET", "/api/summary", headers={"X-KiroCrew-Proxy": value}
                )
                self.assert_unsigned(status, body)

    def test_stale_signature_older_than_60_seconds(self):
        status, body, _ = self.signed_get("/api/summary", ts=int(time.time()) - 61)
        self.assert_unsigned(status, body)

    def test_future_signature_more_than_60_seconds_ahead(self):
        status, body, _ = self.signed_get("/api/summary", ts=int(time.time()) + 61)
        self.assert_unsigned(status, body)

    def test_signature_for_a_different_target_is_rejected(self):
        header = sign(PROXY_SECRET, "GET", "/api/summary?today=2026-11-12")
        status, body, _ = self.request("GET", "/api/summary", headers={"X-KiroCrew-Proxy": header})
        self.assert_unsigned(status, body)

    def test_unset_proxy_secret_fails_closed(self):
        del self.env["KIROCREW_PROXY_SECRET"]
        status, body, _ = self.signed_get("/api/summary")
        self.assert_unsigned(status, body)

    def test_health_needs_no_signature(self):
        status, _, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)

    def test_unknown_signed_route_and_unsigned_unknown_route(self):
        status, body, _ = self.signed_get("/api/ladder/run")
        self.assertEqual((status, json.loads(body)), (404, {"error": "no_route"}))
        status, body, _ = self.request("GET", "/nothing")
        self.assertEqual((status, json.loads(body)), (404, {"error": "no_route"}))

    def test_non_get_is_405_and_makes_no_upstream_call(self):
        for method in ("POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                status, body, _ = self.request(method, "/api/summary")
                self.assertEqual((status, json.loads(body)), (405, {"error": "method_not_allowed"}))
        self.assertEqual(self.opener.requests, [])


class DataDirTests(unittest.TestCase):
    def test_with_kirocrew_home(self):
        env = {"KIROCREW_HOME": "/srv/crew"}
        self.assertEqual(server.data_dir(env), Path("/srv/crew/apps/dues-banshee/data"))

    def test_with_kirocrew_home_and_app_name(self):
        env = {"KIROCREW_HOME": "/srv/crew", "KIROCREW_APP_NAME": "other-name"}
        self.assertEqual(server.data_dir(env), Path("/srv/crew/apps/other-name/data"))

    def test_empty_app_name_falls_back_to_default(self):
        env = {"KIROCREW_HOME": "/srv/crew", "KIROCREW_APP_NAME": ""}
        self.assertEqual(server.data_dir(env), Path("/srv/crew/apps/dues-banshee/data"))

    def test_without_kirocrew_home_uses_default_home(self):
        with mock.patch.object(Path, "home", return_value=Path("/Users/someone")):
            expected = Path("/Users/someone/.kiro/crew/apps/dues-banshee/data")
            self.assertEqual(server.data_dir({}), expected)
            # An app name alone does not relocate the default path.
            self.assertEqual(server.data_dir({"KIROCREW_APP_NAME": "x"}), expected)

    def test_empty_kirocrew_home_uses_default_home(self):
        with mock.patch.object(Path, "home", return_value=Path("/Users/someone")):
            self.assertEqual(
                server.data_dir({"KIROCREW_HOME": ""}),
                Path("/Users/someone/.kiro/crew/apps/dues-banshee/data"),
            )


class SecretsFileSafetyTests(BackendTestCase):
    def test_secrets_file_bytes_and_mtime_unchanged_after_requests(self):
        self.write_secrets()
        old = time.time() - 86400
        os.utime(self.secrets_path, (old, old))
        before_bytes = self.secrets_path.read_bytes()
        before_stat = self.secrets_path.stat()
        self.start()
        self.request("GET", "/health")
        self.signed_get("/api/summary")
        self.signed_get("/api/summary?today=2026-11-12")
        self.request("GET", "/api/summary")  # unsigned
        after_stat = self.secrets_path.stat()
        self.assertEqual(self.secrets_path.read_bytes(), before_bytes)
        self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)
        self.assertEqual(sorted(p.name for p in self.data.iterdir()), ["secrets.json"])

    def test_missing_secrets_file_is_not_created(self):
        self.start()
        self.signed_get("/api/summary")
        self.assertFalse(self.secrets_path.exists())
        self.assertEqual(list(self.data.iterdir()), [])

    def test_secrets_and_upstream_body_absent_from_responses_and_logs(self):
        self.write_secrets()
        statuses = (200, 401, 404, 500, 503)
        for upstream in statuses:
            with self.subTest(upstream=upstream):
                self.start(StubOpener((upstream, SUMMARY_JSON)))
                _, body, response = self.signed_get("/api/summary")
                for secret in (CREW_SECRET, LADDER_SECRET, PROXY_SECRET, UPSTREAM_LEAK):
                    self.assertNotIn(secret.encode(), body)
                    self.assertNotIn(secret, str(response.getheaders()))
        # Log lines are checked against every secret in tearDown as well.
        self.assertNotIn(CREW_SECRET, self.log.getvalue())


class ModuleConstraintsTests(unittest.TestCase):
    def test_upstream_timeout_is_below_gateway_cap(self):
        self.assertLess(server.UPSTREAM_TIMEOUT_SECS, 30)

    def test_every_import_is_standard_library(self):
        tree = ast.parse(SERVER_PY.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "no relative imports")
                modules.add((node.module or "").split(".")[0])
        self.assertTrue(modules, "expected at least one import")
        for name in sorted(modules):
            with self.subTest(module=name):
                self.assertIn(name, sys.stdlib_module_names)

    def test_server_does_not_reference_ladder_file_or_ladder_endpoint(self):
        source = SERVER_PY.read_text(encoding="utf-8")
        self.assertNotIn("ladder.json", source)
        self.assertNotIn("/api/ladder", source)
        self.assertNotIn("ladder_run_secret", source)


if __name__ == "__main__":
    unittest.main()
