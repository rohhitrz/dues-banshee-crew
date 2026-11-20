"""Ladder script example tests (unittest, stdlib only, no live network calls).

Every HTTP request in `daily_ladder` goes through the module-level
`_open(request, timeout)`, which these tests patch. A temp Data_Dir is created
under a temp KIROCREW_HOME, so nothing outside the temp directory is read.
"""

import ast
import contextlib
import io
import json
import os
import pathlib
import socket
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import daily_ladder  # noqa: E402

LADDER_PY = pathlib.Path(__file__).resolve().with_name("daily_ladder.py")

BASE_URL = "https://upstream.example.test"
OTHER_BASE_URL = "https://other.example.test"
SECRETS_BEARER = "secrets-ladder-AAAA1111"
LADDER_BEARER = "ladder-file-BBBB2222"
CREW_SECRET = "crew-read-CCCC3333"


class FakeResponse:
    """Response with only `getcode()` and `close()`, as the script uses."""

    def __init__(self, status):
        self._status = status
        self.closed = False

    def getcode(self):
        return self._status

    def close(self):
        self.closed = True


class LadderTestCase(unittest.TestCase):
    """Shared fixtures: temp KIROCREW_HOME, Data_Dir, patched `_open`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = pathlib.Path(tmp.name)
        self.data = self.home / "apps" / "dues-banshee" / "data"
        self.data.mkdir(parents=True)

        env = mock.patch.dict(
            os.environ, {"KIROCREW_HOME": str(self.home)}, clear=False
        )
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("KIROCREW_APP_NAME", None)

        self.requests = []
        self.timeouts = []
        self.outcome = FakeResponse(200)
        patcher = mock.patch.object(daily_ladder, "_open", side_effect=self._fake_open)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_open(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def write(self, name, content):
        (self.data / name).write_text(
            content if isinstance(content, str) else json.dumps(content),
            encoding="utf-8",
        )

    def write_secrets(self, bearer=SECRETS_BEARER, base_url=BASE_URL):
        self.write(
            "secrets.json",
            {
                "base_url": base_url,
                "crew_read_secret": CREW_SECRET,
                "ladder_run_secret": bearer,
            },
        )

    def write_ladder(self, bearer=LADDER_BEARER, base_url=OTHER_BASE_URL):
        self.write("ladder.json", {"base_url": base_url, "ladder_run_secret": bearer})

    def run_script(self):
        """Run the script. Returns (captured output, raised exception or None)."""
        out, err = io.StringIO(), io.StringIO()
        raised = None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                daily_ladder.run()
            except daily_ladder.LadderFailed as exc:
                raised = exc
        return out.getvalue() + err.getvalue(), raised


class DataDirTests(unittest.TestCase):
    def test_uses_kirocrew_home_when_set(self):
        d = daily_ladder.data_dir({"KIROCREW_HOME": "/tmp/kc"})
        self.assertEqual(d, pathlib.Path("/tmp/kc/apps/dues-banshee/data"))

    def test_uses_app_name_override_under_kirocrew_home(self):
        d = daily_ladder.data_dir(
            {"KIROCREW_HOME": "/tmp/kc", "KIROCREW_APP_NAME": "other-name"}
        )
        self.assertEqual(d, pathlib.Path("/tmp/kc/apps/other-name/data"))

    def test_defaults_to_home_directory_without_kirocrew_home(self):
        expected = pathlib.Path.home() / ".kiro" / "crew" / "apps" / "dues-banshee" / "data"
        self.assertEqual(daily_ladder.data_dir({}), expected)

    def test_empty_kirocrew_home_counts_as_unset(self):
        expected = pathlib.Path.home() / ".kiro" / "crew" / "apps" / "dues-banshee" / "data"
        self.assertEqual(daily_ladder.data_dir({"KIROCREW_HOME": ""}), expected)


class RequestShapeTests(LadderTestCase):
    def test_sends_exactly_one_post_with_bearer_and_empty_body(self):
        self.write_secrets()
        output, raised = self.run_script()
        self.assertIsNone(raised)
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, BASE_URL + "/api/ladder/run")
        self.assertNotIn("?", request.full_url)
        self.assertEqual(
            request.get_header("Authorization"), "Bearer " + SECRETS_BEARER
        )
        self.assertEqual(request.data, b"")

    def test_trailing_slash_on_base_url_does_not_double_up(self):
        self.write_secrets(base_url=BASE_URL + "/")
        self.run_script()
        self.assertEqual(self.requests[0].full_url, BASE_URL + "/api/ladder/run")

    def test_crew_read_secret_is_never_sent(self):
        self.write_secrets()
        self.run_script()
        request = self.requests[0]
        for value in list(request.headers.values()) + list(request.unredirected_hdrs.values()):
            self.assertNotIn(CREW_SECRET, value)

    def test_http_timeout_is_below_cron_limits(self):
        self.assertLess(daily_ladder.HTTP_TIMEOUT_SECS, 290)
        self.assertLess(daily_ladder.HTTP_TIMEOUT_SECS, 300)
        self.write_secrets()
        self.run_script()
        self.assertEqual(self.timeouts, [daily_ladder.HTTP_TIMEOUT_SECS])


class CredentialSourceTests(LadderTestCase):
    def test_secrets_json_wins_over_a_different_valid_ladder_json(self):
        self.write_secrets()
        self.write_ladder()
        self.run_script()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(
            self.requests[0].get_header("Authorization"), "Bearer " + SECRETS_BEARER
        )
        self.assertEqual(self.requests[0].full_url, BASE_URL + "/api/ladder/run")

    def test_ladder_json_used_when_secrets_json_is_missing(self):
        self.write_ladder()
        output, raised = self.run_script()
        self.assertIsNone(raised)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(
            self.requests[0].get_header("Authorization"), "Bearer " + LADDER_BEARER
        )
        self.assertEqual(self.requests[0].full_url, OTHER_BASE_URL + "/api/ladder/run")

    def test_ladder_json_used_when_secrets_json_is_unreadable(self):
        self.write("secrets.json", "not json {")
        self.write_ladder()
        self.run_script()
        self.assertEqual(
            self.requests[0].get_header("Authorization"), "Bearer " + LADDER_BEARER
        )

    def test_no_files_logs_not_configured_and_sends_nothing(self):
        output, raised = self.run_script()
        self.assertEqual(output.strip(), "daily-ladder: failed not_configured")
        self.assertIsInstance(raised, daily_ladder.LadderFailed)
        self.assertEqual(str(raised), "not_configured")
        self.assertEqual(self.requests, [])

    def test_http_base_url_is_not_configured(self):
        self.write_secrets(base_url="http://upstream.example.test")
        output, raised = self.run_script()
        self.assertIsNotNone(raised)
        self.assertEqual(self.requests, [])

    def test_empty_ladder_secret_is_not_configured(self):
        self.write_secrets(bearer="")
        output, raised = self.run_script()
        self.assertIsNotNone(raised)
        self.assertEqual(output.strip(), "daily-ladder: failed not_configured")
        self.assertEqual(self.requests, [])

    def test_no_secret_in_output_or_exception_text(self):
        scenarios = []
        for label, setup, outcome in [
            ("ok", lambda: (self.write_secrets(), self.write_ladder()), FakeResponse(200)),
            ("ladder-only", lambda: self.write_ladder(), FakeResponse(200)),
            ("status", lambda: self.write_secrets(), FakeResponse(503)),
            ("timeout", lambda: self.write_secrets(), socket.timeout("timed out")),
            ("connection", lambda: self.write_secrets(), urllib.error.URLError("boom")),
            ("not_configured", lambda: None, FakeResponse(200)),
        ]:
            scenarios.append((label, setup, outcome))
        for label, setup, outcome in scenarios:
            with self.subTest(label):
                for name in ("secrets.json", "ladder.json"):
                    path = self.data / name
                    if path.exists():
                        path.unlink()
                self.requests.clear()
                setup()
                self.outcome = outcome
                output, raised = self.run_script()
                texts = [output]
                if raised is not None:
                    texts += [str(raised), repr(raised)]
                for text in texts:
                    for secret in (SECRETS_BEARER, LADDER_BEARER, CREW_SECRET):
                        self.assertNotIn(secret, text)


class OutcomeTests(LadderTestCase):
    def setUp(self):
        super().setUp()
        self.write_secrets()

    def test_2xx_logs_status_and_returns_normally(self):
        for status in (200, 201, 202, 204, 299):
            with self.subTest(status=status):
                self.requests.clear()
                self.outcome = FakeResponse(status)
                output, raised = self.run_script()
                self.assertIsNone(raised)
                self.assertEqual(output.strip(), "daily-ladder: status %d" % status)
                self.assertEqual(len(self.requests), 1)
                self.assertTrue(self.outcome.closed)

    def test_non_2xx_response_logs_status_and_raises(self):
        for status in (301, 400, 401, 404, 500, 503):
            with self.subTest(status=status):
                self.requests.clear()
                self.outcome = FakeResponse(status)
                output, raised = self.run_script()
                self.assertEqual(output.strip(), "daily-ladder: status %d" % status)
                self.assertIsInstance(raised, daily_ladder.LadderFailed)
                self.assertEqual(str(raised), "status %d" % status)
                self.assertEqual(len(self.requests), 1)

    def test_http_error_is_a_status_and_body_is_not_logged(self):
        body = io.BytesIO(b"UPSTREAM-BODY-LEAK-MARKER")
        self.outcome = urllib.error.HTTPError(
            BASE_URL + "/api/ladder/run", 401, "Unauthorized", Message(), body
        )
        output, raised = self.run_script()
        self.assertEqual(output.strip(), "daily-ladder: status 401")
        self.assertEqual(str(raised), "status 401")
        self.assertNotIn("UPSTREAM-BODY-LEAK-MARKER", output + str(raised))
        self.assertEqual(len(self.requests), 1)

    def test_timeout_logs_one_failure_line_and_does_not_retry(self):
        self.outcome = socket.timeout("timed out")
        output, raised = self.run_script()
        self.assertEqual(output.strip().splitlines(), ["daily-ladder: failed timeout"])
        self.assertIsInstance(raised, daily_ladder.LadderFailed)
        self.assertEqual(str(raised), "timeout")
        self.assertEqual(len(self.requests), 1)

    def test_urlerror_wrapping_a_timeout_is_a_timeout(self):
        self.outcome = urllib.error.URLError(socket.timeout("timed out"))
        output, raised = self.run_script()
        self.assertEqual(output.strip().splitlines(), ["daily-ladder: failed timeout"])
        self.assertEqual(str(raised), "timeout")
        self.assertEqual(len(self.requests), 1)

    def test_connection_error_logs_one_failure_line_and_does_not_retry(self):
        for exc in (
            urllib.error.URLError(ConnectionRefusedError("refused")),
            ConnectionResetError("reset"),
            OSError("network down"),
        ):
            with self.subTest(exc=type(exc).__name__):
                self.requests.clear()
                self.outcome = exc
                output, raised = self.run_script()
                self.assertEqual(
                    output.strip().splitlines(), ["daily-ladder: failed connection"]
                )
                self.assertIsInstance(raised, daily_ladder.LadderFailed)
                self.assertEqual(str(raised), "connection")
                self.assertEqual(len(self.requests), 1)


class StdlibOnlyTests(unittest.TestCase):
    def test_every_import_is_standard_library(self):
        tree = ast.parse(LADDER_PY.read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import in daily_ladder.py")
                modules.append(node.module)
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module):
                self.assertIn(module.split(".")[0], sys.stdlib_module_names)


if __name__ == "__main__":
    unittest.main()
