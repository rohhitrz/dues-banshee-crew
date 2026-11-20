"""Backend property tests (unittest, stdlib only, no live network calls).

Each property loops over cases drawn from `random.Random(<fixed seed>)` (at
least 100 cases), runs them through the real handler on a loopback port with
a stub upstream, and reports each case with `self.subTest`. Fixtures come from
`BackendTestCase` in test_server.py.

Property numbers match the "Correctness Properties" section of the design.
"""

import io
import json
import logging
import os
import random
import re
import socket
import string
import sys
import unittest
import urllib.error
import urllib.parse
from email.message import Message
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_server as base  # noqa: E402

BASE_URL = base.BASE_URL
UPSTREAM_LEAK = base.UPSTREAM_LEAK


def error_body_for(status):
    """Expected (HTTP status, code) for a non-success upstream status.

    Written from the design's "Summary error mapping" table, not from server.py.
    """
    return {
        401: (502, "unauthorized"),
        404: (502, "not_found"),
        503: (503, "unavailable"),
    }.get(status, (502, "upstream_error"))


# --------------------------------------------------------------------------
# Property 1: `today` is forwarded if and only if it is a Valid_Today
# --------------------------------------------------------------------------

_DIGITS = "0123456789"
_NON_ASCII_DIGITS = "\u0663\u0660\uff19\u0969\uff11\u09e6"  # Arabic-Indic, fullwidth, Devanagari, Bengali


def is_valid_today(s):
    """Independent oracle: exactly YYYY-MM-DD with ASCII digits."""
    return (
        len(s) == 10
        and s[4] == "-"
        and s[7] == "-"
        and all(c in _DIGITS for c in s[:4] + s[5:7] + s[8:])
    )


def quote_all(s):
    """Percent-encode every UTF-8 byte of `s`."""
    return "".join("%%%02X" % b for b in s.encode("utf-8"))


def gen_valid_today(rng):
    return "%04d-%02d-%02d" % (rng.randint(0, 9999), rng.randint(0, 99), rng.randint(0, 99))


def gen_invalid_today(rng):
    """A string that is guaranteed not to be a Valid_Today."""
    valid = gen_valid_today(rng)
    kind = rng.choice(
        [
            "trailing_newline",
            "leading_newline",
            "trailing_space",
            "trailing_nul",
            "unicode_digit",
            "empty",
            "drop_char",
            "extra_digit",
            "slash_separators",
            "compact",
            "short_year",
            "letters",
            "double_dash",
        ]
    )
    if kind == "trailing_newline":
        s = valid + "\n"
    elif kind == "leading_newline":
        s = "\n" + valid
    elif kind == "trailing_space":
        s = valid + " "
    elif kind == "trailing_nul":
        s = valid + "\x00"
    elif kind == "unicode_digit":
        positions = [i for i, c in enumerate(valid) if c in _DIGITS]
        i = rng.choice(positions)
        s = valid[:i] + rng.choice(_NON_ASCII_DIGITS) + valid[i + 1 :]
    elif kind == "empty":
        s = ""
    elif kind == "drop_char":
        i = rng.randrange(len(valid))
        s = valid[:i] + valid[i + 1 :]
    elif kind == "extra_digit":
        s = valid + rng.choice(_DIGITS)
    elif kind == "slash_separators":
        s = valid.replace("-", "/")
    elif kind == "compact":
        s = valid.replace("-", "")
    elif kind == "short_year":
        s = valid[2:]
    elif kind == "letters":
        i = rng.choice([0, 1, 2, 3, 5, 6, 8, 9])
        s = valid[:i] + rng.choice("abXZ") + valid[i + 1 :]
    else:
        s = valid.replace("-", "--", 1)
    assert not is_valid_today(s), (kind, s)
    return s


def gen_today_case(rng, kind):
    """Return (query_string, forwarded_value_or_None) for the given case kind."""
    if kind == "valid":
        v = gen_valid_today(rng)
        return "today=" + v, v
    if kind == "valid_fully_percent_encoded":
        v = gen_valid_today(rng)
        return "today=" + quote_all(v), v
    if kind == "valid_with_other_keys":
        v = gen_valid_today(rng)
        parts = ["a=1", "today=" + v, "b=%20x"]
        rng.shuffle(parts)
        return "&".join(parts), v
    if kind == "invalid_mutation":
        s = gen_invalid_today(rng)
        return "today=" + urllib.parse.quote(s, safe=""), None
    if kind == "invalid_bare_key":
        return "today", None
    if kind == "repeated_valid_valid":
        return "today=%s&today=%s" % (gen_valid_today(rng), gen_valid_today(rng)), None
    if kind == "repeated_valid_invalid":
        pair = [gen_valid_today(rng), urllib.parse.quote(gen_invalid_today(rng), safe="")]
        rng.shuffle(pair)
        return "today=%s&today=%s" % tuple(pair), None
    if kind == "repeated_same_valid":
        v = gen_valid_today(rng)
        return "today=%s&x=1&today=%s" % (v, v), None
    if kind == "other_keys_only":
        return "a=1&b=2", None
    if kind == "wrong_case_key":
        return "Today=" + gen_valid_today(rng), None
    if kind == "no_query":
        return "", None
    raise AssertionError(kind)


TODAY_KINDS = [
    "valid",
    "valid_fully_percent_encoded",
    "valid_with_other_keys",
    "invalid_mutation",
    "invalid_mutation",
    "invalid_mutation",
    "invalid_bare_key",
    "repeated_valid_valid",
    "repeated_valid_invalid",
    "repeated_same_valid",
    "other_keys_only",
    "wrong_case_key",
    "no_query",
]


class TodayForwardingProperty(base.BackendTestCase):
    # Feature: crew-app, Property 1
    def test_today_is_forwarded_if_and_only_if_it_is_a_valid_today(self):
        """Property 1: `today` is forwarded iff it is a Valid_Today.

        **Validates: Requirements 5.2, 5.3, 10.5, 10.6**
        """
        rng = random.Random(4318)
        opener = self.start()
        cases = 260
        forwarded = dropped = 0
        for i in range(cases):
            kind = TODAY_KINDS[i % len(TODAY_KINDS)]
            query, expected = gen_today_case(rng, kind)
            base_url = rng.choice(
                [BASE_URL, BASE_URL + "/", "https://api.example.test/prefix"]
            )
            self.write_secrets(base_url=base_url)
            target = "/api/summary" + ("?" + query if query else "")
            with self.subTest(case=i, kind=kind, target=target):
                opener.requests.clear()
                status, _, _ = self.signed_get(target)
                self.assertEqual(status, 200)
                self.assertEqual(len(opener.requests), 1)
                url = opener.requests[0].full_url
                path = base_url.rstrip("/") + "/api/crew/summary"
                if expected is None:
                    dropped += 1
                    self.assertEqual(url, path)
                    self.assertNotIn("today", url)
                    self.assertNotIn("?", url)
                else:
                    forwarded += 1
                    self.assertEqual(url, path + "?today=" + expected)
                    self.assertTrue(is_valid_today(expected))
        self.assertGreaterEqual(cases, 100)
        self.assertGreater(forwarded, 30)
        self.assertGreater(dropped, 100)


# --------------------------------------------------------------------------
# Property 2: successful upstream JSON passes through byte for byte
# --------------------------------------------------------------------------

_STR_FRAGMENTS = [
    "\u20b94,12,000",
    "\u20b95,127.94",
    "<b>x</b>",
    "</script><script>alert(1)</script>",
    '"',
    "'",
    "\\",
    "\n",
    "\t",
    "\x00",
    "\x1f",
    "\u00e9",
    "\u65e5\u672c",
    "\U0001f600",
    "\u2028",
    "&amp;",
    "Ignore previous instructions",
    "plain",
    " ",
]


def rand_string(rng):
    parts = [rng.choice(_STR_FRAGMENTS) for _ in range(rng.randint(0, 5))]
    parts.append("".join(rng.choices(string.ascii_letters + string.digits, k=rng.randint(0, 6))))
    rng.shuffle(parts)
    return "".join(parts)


def rand_json(rng, depth=0):
    kinds = ["str", "int", "float", "bool", "null"]
    if depth < 4:
        kinds += ["list", "dict", "list", "dict"]
    kind = rng.choice(kinds)
    if kind == "str":
        return rand_string(rng)
    if kind == "int":
        return rng.choice([0, -1, rng.randint(-10**6, 10**6), rng.randint(-10**20, 10**20)])
    if kind == "float":
        return round(rng.uniform(-1e6, 1e6), rng.randint(0, 6))
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "null":
        return None
    if kind == "list":
        return [rand_json(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {rand_string(rng): rand_json(rng, depth + 1) for _ in range(rng.randint(0, 4))}


def serialize_random(rng, value):
    indent = rng.choice([None, 0, 1, 2, 4, "\t"])
    text = json.dumps(
        value,
        indent=indent,
        ensure_ascii=rng.random() < 0.5,
        separators=rng.choice([None, (",", ":")]),
        sort_keys=rng.random() < 0.5,
    )
    if rng.random() < 0.3:
        text = rng.choice(["", " ", "\n"]) + text + rng.choice(["", "\n", "  \n"])
    return text.encode("utf-8")


class PassthroughProperty(base.BackendTestCase):
    # Feature: crew-app, Property 2
    def test_successful_upstream_json_passes_through_byte_for_byte(self):
        """Property 2: a 200 upstream JSON body is returned unchanged.

        **Validates: Requirements 1.1, 5.5**
        """
        rng = random.Random(2077)
        self.write_secrets()
        opener = self.start()
        cases = 200
        for i in range(cases):
            value = rand_json(rng)
            if i % 4 == 0 and not isinstance(value, dict):
                value = {"supplierName": rand_string(rng), "items": [value]}
            payload = serialize_random(rng, value)
            json.loads(payload)  # generator sanity: must be valid JSON
            with self.subTest(case=i, size=len(payload)):
                opener.outcome = (200, payload)
                status, body, response = self.signed_get("/api/summary")
                self.assertEqual(status, 200)
                self.assertEqual(body, payload)
                self.assertEqual(response.getheader("Content-Type"), "application/json")
                self.assertEqual(response.getheader("Content-Length"), str(len(payload)))
        self.assertGreaterEqual(cases, 100)


# --------------------------------------------------------------------------
# Property 3: every non-success upstream outcome maps to one error object
# --------------------------------------------------------------------------


def gen_non_json_body(rng):
    """Bytes that json.loads rejects."""
    while True:
        kind = rng.choice(
            ["random_bytes", "truncated", "html", "word", "bad_utf8", "trailing_garbage", "empty"]
        )
        if kind == "random_bytes":
            body = bytes(rng.randrange(256) for _ in range(rng.randint(1, 64)))
        elif kind == "truncated":
            full = json.dumps(
                {"supplierName": rand_string(rng), "k": [1, 2, rand_string(rng)], "z": {"a": 1}}
            ).encode("utf-8")
            body = full[: rng.randint(1, len(full) - 1)]
        elif kind == "html":
            body = ("<html><body>%s %s</body></html>" % (UPSTREAM_LEAK, rand_string(rng))).encode("utf-8")
        elif kind == "word":
            body = rng.choice([b"ok", b"Bad Gateway", b"error", b"undefined", b"{'a': 1}", b"{a:1}"])
        elif kind == "bad_utf8":
            body = b"\xff\xfe" + bytes(rng.randrange(128, 256) for _ in range(rng.randint(0, 8)))
        elif kind == "trailing_garbage":
            body = b'{"a": 1} ' + rng.choice([b"x", b"}", b"{}", b"\n,"])
        else:
            body = b""
        try:
            json.loads(body)
        except Exception:
            return body


class ErrorMappingProperty(base.BackendTestCase):
    def setUp(self):
        super().setUp()
        self.write_secrets()

    def assert_single_error(self, body, response_status, http_status, code):
        self.assertEqual(response_status, http_status)
        parsed = json.loads(body)
        self.assertEqual(parsed, {"error": code})
        self.assertEqual(list(parsed), ["error"])
        for marker in (UPSTREAM_LEAK, base.CREW_SECRET, base.LADDER_SECRET, base.PROXY_SECRET):
            self.assertNotIn(marker.encode(), body)

    # Feature: crew-app, Property 3
    def test_every_non_200_upstream_status_maps_to_exactly_one_error_object(self):
        """Property 3 (statuses): every upstream status in 100-599 except 200.

        **Validates: Requirements 5.6, 5.7, 5.8, 5.11**
        """
        statuses = [s for s in range(100, 600) if s != 200]
        self.assertGreaterEqual(len(statuses), 100)
        opener = self.start()
        for as_response in (False, True):
            # False: the real opener raises HTTPError for non-2xx.
            # True: the opener hands back a response object with that status.
            opener.return_status_as_response = as_response
            for status in statuses:
                with self.subTest(upstream=status, as_response=as_response):
                    opener.outcome = (status, UPSTREAM_LEAK.encode())
                    http_status, code = error_body_for(status)
                    got_status, body, _ = self.signed_get("/api/summary")
                    self.assert_single_error(body, got_status, http_status, code)

    # Feature: crew-app, Property 3
    def test_every_200_with_non_json_body_maps_to_upstream_error(self):
        """Property 3 (bodies): 200 with a body that is not JSON.

        **Validates: Requirements 5.6, 5.7, 5.8, 5.11**
        """
        rng = random.Random(3303)
        opener = self.start()
        cases = 200
        for i in range(cases):
            payload = gen_non_json_body(rng)
            with self.subTest(case=i, payload=payload[:40]):
                opener.outcome = (200, payload)
                status, body, _ = self.signed_get("/api/summary")
                self.assert_single_error(body, status, 502, "upstream_error")
        self.assertGreaterEqual(cases, 100)


# --------------------------------------------------------------------------
# Property 4 (Backend half): secret values never appear in responses or logs
# --------------------------------------------------------------------------


def rand_secret(rng, label):
    return "S3CR3T_%s_%s" % (label, "".join(rng.choices(string.ascii_letters + string.digits, k=rng.randint(16, 32))))


def http_error(status, secret):
    """An HTTPError whose message, headers and body all echo the secret."""
    headers = Message()
    headers["X-Echo"] = secret
    return urllib.error.HTTPError(
        BASE_URL + "/api/crew/summary?token=" + secret,
        status,
        "msg " + secret,
        headers,
        io.BytesIO(("echo " + secret).encode("utf-8")),
    )


class SecretSecrecyProperty(base.BackendTestCase):
    # Feature: crew-app, Property 4
    def test_secret_values_never_appear_in_responses_or_logs(self):
        """Property 4 (Backend half): no secret in any response body, header or log.

        **Validates: Requirements 3.4, 5.11, 10.1**
        """
        rng = random.Random(8841)
        opener = self.start()

        # Capture stdout and the logging module in addition to stderr (self.log).
        stdout = io.StringIO()
        patcher = mock.patch.object(sys, "stdout", stdout)
        patcher.start()
        self.addCleanup(patcher.stop)
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(lambda: (root.removeHandler(handler), root.setLevel(old_level)))

        def captured():
            return self.log.getvalue() + stdout.getvalue() + log_stream.getvalue()

        outcomes = [
            "ok_json",
            "ok_non_json",
            "status",
            "status_echoing_secret",
            "timeout",
            "urlerror_timeout",
            "connection_error",
            "connection_refused",
            "unexpected_exception",
            "nc_missing_file",
            "nc_bad_json",
            "nc_empty_base_url",
            "nc_http_base_url",
            "nc_empty_crew_secret",
            "unsigned_missing",
            "unsigned_wrong_secret",
            "unsigned_stale",
        ]
        cases = 255
        used = []
        for i in range(cases):
            kind = outcomes[i % len(outcomes)]
            crew = rand_secret(rng, "crew")
            ladder = rand_secret(rng, "ladder")
            proxy = rand_secret(rng, "proxy")
            secrets = [crew, ladder, proxy]
            used.extend(secrets)
            self.env["KIROCREW_PROXY_SECRET"] = proxy

            file_values = {"base_url": BASE_URL, "crew_read_secret": crew, "ladder_run_secret": ladder}
            (self.data / "ladder.json").write_text(
                json.dumps({"base_url": BASE_URL, "ladder_run_secret": ladder}), encoding="utf-8"
            )
            self.secrets_path.write_text(json.dumps(file_values), encoding="utf-8")

            sign_secret = proxy
            sign_ts = None
            send_header = True
            expected = (200, None)
            opener.return_status_as_response = False
            opener.outcome = (200, base.SUMMARY_JSON)

            if kind == "ok_json":
                pass
            elif kind == "ok_non_json":
                opener.outcome = (200, b"not json " + crew.encode())
                expected = (502, "upstream_error")
            elif kind == "status":
                status = rng.choice([s for s in range(100, 600) if s != 200])
                opener.outcome = (status, ("echo " + crew).encode())
                expected = error_body_for(status)
            elif kind == "status_echoing_secret":
                status = rng.choice([401, 404, 500, 503, 502, 418])
                opener.outcome = http_error(status, crew)
                expected = error_body_for(status)
            elif kind == "timeout":
                opener.outcome = socket.timeout("timed out " + crew)
                expected = (504, "timeout")
            elif kind == "urlerror_timeout":
                opener.outcome = urllib.error.URLError(socket.timeout("timed out " + crew))
                expected = (504, "timeout")
            elif kind == "connection_error":
                opener.outcome = urllib.error.URLError("cannot reach " + crew)
                expected = (503, "unavailable")
            elif kind == "connection_refused":
                opener.outcome = ConnectionRefusedError("refused " + crew)
                expected = (503, "unavailable")
            elif kind == "unexpected_exception":
                opener.outcome = RuntimeError("boom " + crew + " " + ladder)
                expected = (502, "upstream_error")
            elif kind == "nc_missing_file":
                self.secrets_path.unlink()
                expected = (503, "not_configured")
            elif kind == "nc_bad_json":
                text = json.dumps(file_values)
                self.secrets_path.write_text(text[: len(text) - 2], encoding="utf-8")
                expected = (503, "not_configured")
            elif kind == "nc_empty_base_url":
                file_values["base_url"] = ""
                self.secrets_path.write_text(json.dumps(file_values), encoding="utf-8")
                expected = (503, "not_configured")
            elif kind == "nc_http_base_url":
                file_values["base_url"] = "http://upstream.example.test"
                self.secrets_path.write_text(json.dumps(file_values), encoding="utf-8")
                expected = (503, "not_configured")
            elif kind == "nc_empty_crew_secret":
                file_values["crew_read_secret"] = ""
                self.secrets_path.write_text(json.dumps(file_values), encoding="utf-8")
                expected = (503, "not_configured")
            elif kind == "unsigned_missing":
                send_header = False
                expected = (401, "unsigned")
            elif kind == "unsigned_wrong_secret":
                sign_secret = rand_secret(rng, "other")
                used.append(sign_secret)
                expected = (401, "unsigned")
            else:  # unsigned_stale
                sign_ts = 1_000_000
                expected = (401, "unsigned")

            target = "/api/summary"
            headers = {}
            if send_header:
                headers["X-KiroCrew-Proxy"] = base.sign(sign_secret, "GET", target, ts=sign_ts)

            with self.subTest(case=i, kind=kind):
                opener.requests.clear()
                status, body, response = self.request("GET", target, headers=headers)
                expected_status, expected_code = expected
                self.assertEqual(status, expected_status)
                if expected_code is not None:
                    self.assertEqual(json.loads(body), {"error": expected_code})
                if expected_code in ("not_configured", "unsigned"):
                    self.assertEqual(opener.requests, [], "no upstream call expected")
                haystack_response = body + str(response.getheaders()).encode("utf-8")
                haystack_logs = captured()
                for secret in secrets + [sign_secret]:
                    self.assertNotIn(secret.encode("utf-8"), haystack_response)
                    self.assertNotIn(secret, haystack_logs)

        self.assertGreaterEqual(cases, 100)
        # Final sweep: nothing from any case leaked into anything captured.
        final = captured()
        self.assertTrue(final, "expected log lines to have been written")
        for secret in used:
            self.assertNotIn(secret, final)
        # Log lines have the METHOD PATH STATUS [code] shape only.
        line_re = re.compile(r"^[A-Z]+ \S+ \d{3}( [a-z_]+( \w+)?)?$")
        for line in self.log.getvalue().splitlines():
            self.assertRegex(line, line_re)


if __name__ == "__main__":
    unittest.main()
