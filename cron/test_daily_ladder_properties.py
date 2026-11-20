"""Ladder script property tests (unittest, stdlib only, no live network calls).

Each property loops over cases from `random.Random(<fixed seed>)` and reports
through `self.subTest`. Requests go through the patched module-level
`_open(request, timeout)`; credentials live in a temp Data_Dir under a temp
KIROCREW_HOME. The shared fixtures come from `test_daily_ladder`.
"""

import io
import itertools
import json
import os
import random
import shutil
import socket
import sys
import unittest
import urllib.error
from email.message import Message

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import daily_ladder  # noqa: E402
import test_daily_ladder as base  # noqa: E402

CASES = 150
HEX = "0123456789abcdef"


def random_secret(rng, tag):
    """A distinctive secret that cannot appear in any fixed log token."""
    return "%s-%s" % (tag, "".join(rng.choice(HEX) for _ in range(rng.randint(16, 32))))


def http_error(status, body=b""):
    return urllib.error.HTTPError(
        "https://upstream.example.test/api/ladder/run",
        status,
        "msg",
        Message(),
        io.BytesIO(body),
    )


class LadderPropertyTestCase(base.LadderTestCase):
    def clear_files(self):
        for name in ("secrets.json", "ladder.json"):
            path = self.data / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()
        self.requests.clear()


class SecretsNeverLeakPropertyTests(LadderPropertyTestCase):
    # Feature: crew-app, Property 4 (Ladder half)
    def test_secret_values_never_appear_in_output_or_exceptions(self):
        rng = random.Random(4004)
        outcomes = ["status", "timeout", "connection", "not_configured"]
        for case in range(CASES):
            outcome = outcomes[case % len(outcomes)]
            secrets_bearer = random_secret(rng, "sl")
            ladder_bearer = random_secret(rng, "ll")
            crew_secret = random_secret(rng, "cr")
            all_secrets = (secrets_bearer, ladder_bearer, crew_secret)
            with self.subTest(case=case, outcome=outcome):
                self.clear_files()
                if outcome == "not_configured":
                    # Secrets are on disk but the files are unusable (http base_url).
                    self.write(
                        "secrets.json",
                        {
                            "base_url": "http://insecure.example.test",
                            "crew_read_secret": crew_secret,
                            "ladder_run_secret": secrets_bearer,
                        },
                    )
                    self.write(
                        "ladder.json",
                        {"base_url": "ftp://x.example.test", "ladder_run_secret": ladder_bearer},
                    )
                    self.outcome = base.FakeResponse(200)
                else:
                    self.write(
                        "secrets.json",
                        {
                            "base_url": base.BASE_URL,
                            "crew_read_secret": crew_secret,
                            "ladder_run_secret": secrets_bearer,
                        },
                    )
                    self.write_ladder(bearer=ladder_bearer)
                    leak = " ".join(all_secrets)
                    if outcome == "status":
                        status = rng.randint(100, 599)
                        if 200 <= status <= 299:
                            self.outcome = base.FakeResponse(status)
                        else:
                            self.outcome = http_error(status, leak.encode())
                    elif outcome == "timeout":
                        self.outcome = rng.choice(
                            [
                                socket.timeout("timed out " + leak),
                                urllib.error.URLError(socket.timeout("timed out " + leak)),
                            ]
                        )
                    else:
                        self.outcome = rng.choice(
                            [
                                urllib.error.URLError("refused Bearer " + leak),
                                ConnectionResetError("reset " + leak),
                                OSError("down " + leak),
                            ]
                        )
                output, raised = self.run_script()
                texts = [output]
                if raised is not None:
                    texts += [str(raised), repr(raised)]
                    if raised.__cause__ is not None:
                        texts += [str(raised.__cause__), repr(raised.__cause__)]
                for text in texts:
                    for secret in all_secrets:
                        self.assertNotIn(secret, text)
                if outcome == "not_configured":
                    self.assertEqual(self.requests, [])
                    self.assertIsNotNone(raised)


class StatusOutcomePropertyTests(LadderPropertyTestCase):
    # Feature: crew-app, Property 5
    def test_log_line_and_outcome_follow_the_status_code(self):
        self.write_secrets()
        for status in range(100, 600):
            with self.subTest(status=status):
                self.requests.clear()
                if 200 <= status <= 299:
                    self.outcome = base.FakeResponse(status)
                else:
                    self.outcome = http_error(status, b"BODY-MARKER")
                output, raised = self.run_script()
                self.assertEqual(
                    output.splitlines(), ["daily-ladder: status %d" % status]
                )
                self.assertEqual(len(self.requests), 1)
                if 200 <= status <= 299:
                    self.assertIsNone(raised)
                else:
                    self.assertIsInstance(raised, daily_ladder.LadderFailed)
                    self.assertEqual(str(raised), "status %d" % status)
                self.assertNotIn("BODY-MARKER", output)


# File states for Property 7. Each state maps to a list of variants; a variant
# is a callable (path, valid_content) that puts the file in that state.
def _rm(path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _missing(path, valid):
    _rm(path)


def _unreadable(path, valid):
    _rm(path)
    path.mkdir()  # a directory in place of the file cannot be opened for reading


def _not_json(path, valid):
    path.write_text("not json {", encoding="utf-8")


def _bad_base_url(variant):
    def apply(path, valid):
        content = dict(valid)
        if variant == "absent":
            del content["base_url"]
        else:
            content["base_url"] = ""
        _write_json(path, content)

    return apply


def _non_https(variant):
    def apply(path, valid):
        content = dict(valid)
        content["base_url"] = variant + "://upstream.example.test"
        _write_json(path, content)

    return apply


def _bad_secret(variant):
    def apply(path, valid):
        content = dict(valid)
        if variant == "absent":
            del content["ladder_run_secret"]
        else:
            content["ladder_run_secret"] = ""
        _write_json(path, content)

    return apply


def _valid(path, valid):
    _write_json(path, valid)


STATES = [
    ("missing", [_missing]),
    ("unreadable", [_unreadable]),
    ("not_json", [_not_json]),
    ("bad_base_url", [_bad_base_url("empty"), _bad_base_url("absent")]),
    ("non_https", [_non_https("http"), _non_https("ftp")]),
    ("bad_secret", [_bad_secret("empty"), _bad_secret("absent")]),
    ("valid", [_valid]),
]


class CredentialSourcePropertyTests(LadderPropertyTestCase):
    def check_pair(self, secrets_state, ladder_state, secrets_apply, ladder_apply, rng):
        self.clear_files()
        secrets_valid = {
            "base_url": "https://s%d.example.test" % rng.randint(0, 10**6),
            "crew_read_secret": random_secret(rng, "cr"),
            "ladder_run_secret": random_secret(rng, "sl"),
        }
        ladder_valid = {
            "base_url": "https://l%d.example.test" % rng.randint(0, 10**6),
            "ladder_run_secret": random_secret(rng, "ll"),
        }
        secrets_apply(self.data / "secrets.json", secrets_valid)
        ladder_apply(self.data / "ladder.json", ladder_valid)

        output, raised = self.run_script()
        if secrets_state == "valid":
            expected = secrets_valid
        elif ladder_state == "valid":
            expected = ladder_valid
        else:
            expected = None

        if expected is None:
            self.assertEqual(output.strip(), "daily-ladder: failed not_configured")
            self.assertIsInstance(raised, daily_ladder.LadderFailed)
            self.assertEqual(str(raised), "not_configured")
            self.assertEqual(self.requests, [])
        else:
            self.assertIsNone(raised)
            self.assertEqual(len(self.requests), 1)
            request = self.requests[0]
            self.assertEqual(
                request.full_url, expected["base_url"] + "/api/ladder/run"
            )
            self.assertEqual(
                request.get_header("Authorization"),
                "Bearer " + expected["ladder_run_secret"],
            )

    # Feature: crew-app, Property 7
    def test_all_state_pairs(self):
        rng = random.Random(9001)
        for (s_name, s_variants), (l_name, l_variants) in itertools.product(STATES, STATES):
            for s_index, s_apply in enumerate(s_variants):
                for l_index, l_apply in enumerate(l_variants):
                    with self.subTest(
                        secrets=s_name, s_variant=s_index, ladder=l_name, l_variant=l_index
                    ):
                        self.check_pair(s_name, l_name, s_apply, l_apply, rng)

    # Feature: crew-app, Property 7
    def test_random_state_pairs(self):
        rng = random.Random(9001)
        for case in range(CASES):
            s_name, s_variants = rng.choice(STATES)
            l_name, l_variants = rng.choice(STATES)
            s_apply = rng.choice(s_variants)
            l_apply = rng.choice(l_variants)
            with self.subTest(case=case, secrets=s_name, ladder=l_name):
                self.check_pair(s_name, l_name, s_apply, l_apply, rng)


if __name__ == "__main__":
    unittest.main()
