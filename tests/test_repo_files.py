import fnmatch
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = REPO_ROOT / ".gitignore"
README = REPO_ROOT / "README.md"
LICENSE = REPO_ROOT / "LICENSE"

REQUIRED_IGNORES = [
    "node_modules/",
    "secrets.json",
    "data/",
    "ladder.json",
    "*.log",
    ".DS_Store",
]

# Paths that must never be ignored: directories and a file inside each.
PROTECTED_PATHS = [
    "ui/dist",
    "ui/dist/index.mjs",
    "dist",
    "dist/index.mjs",
    ".kiro",
    ".kiro/specs/crew-app/tasks.md",
    ".kiro/steering/roadmap.md",
]

SCREENSHOT = "docs/screenshots/crew-graveyard.png"
UPDATE_COMMAND = "kirocrew app update dues-banshee --source <dir>"


def ignore_lines(text):
    """Non-empty, non-comment lines of a .gitignore."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def pattern_ignores(pattern, path):
    """True if a gitignore pattern ignores `path` or any parent directory of it.

    A small model of gitignore: a leading "/" or an inner "/" anchors the
    pattern to the repo root, otherwise it matches any single path component;
    a trailing "/" restricts it to directories (every parent is a directory;
    the path itself is treated as a directory when it has no extension-like
    file part, which is true for the protected paths used here).
    """
    if pattern.startswith("!"):
        return False
    dir_only = pattern.endswith("/")
    core = pattern.strip("/")
    if not core:
        return False
    parts = path.split("/")
    for depth in range(1, len(parts) + 1):
        prefix = parts[:depth]
        is_last = depth == len(parts)
        if dir_only and is_last and "." in prefix[-1] and prefix[-1] != ".kiro":
            continue  # a file such as index.mjs is not a directory
        if "/" in pattern.rstrip("/"):
            if fnmatch.fnmatchcase("/".join(prefix), core):
                return True
        elif fnmatch.fnmatchcase(prefix[-1], core):
            return True
    return False


def json_blocks(text):
    return re.findall(r"```json\n(.*?)\n```", text, flags=re.DOTALL)


def sections(text):
    """Split markdown into chunks that each start at a heading line."""
    return re.split(r"(?m)^(?=#{1,6} )", text)


class GitignoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = ignore_lines(GITIGNORE.read_text(encoding="utf-8"))

    def test_required_entries_present(self):
        for entry in REQUIRED_IGNORES:
            with self.subTest(entry=entry):
                self.assertIn(entry, self.lines)

    def test_nothing_ignores_dist_or_kiro(self):
        for line in self.lines:
            for path in PROTECTED_PATHS:
                with self.subTest(line=line, path=path):
                    self.assertFalse(
                        pattern_ignores(line, path),
                        f".gitignore line {line!r} would ignore {path}",
                    )

    def test_matcher_detects_bad_lines(self):
        # Guards the matcher itself, so the check above cannot pass vacuously.
        for bad in ["dist", "dist/", "/dist", "ui/dist", "ui/dist/", "**/dist", "*dist*", ".kiro", ".kiro/", "/.kiro/", ".*"]:
            with self.subTest(bad=bad):
                hit = any(pattern_ignores(bad, p) for p in PROTECTED_PATHS)
                self.assertTrue(hit)


class ReadmeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        cls.blocks = [json.loads(b) for b in json_blocks(cls.text)]

    def test_install_steps_are_numbered_and_in_order(self):
        steps = re.findall(r"(?m)^(\d+)\. (.+)$", self.text)
        numbers = [int(n) for n, _ in steps[:4]]
        self.assertEqual(numbers, [1, 2, 3, 4])
        # Commands sit in indented code blocks, so read each step's full body.
        bodies = [self._step_body(n) for n in (1, 2, 3, 4)]
        self.assertIn("kirocrew app install /abs/path", bodies[0])
        for part in ("Settings", "Security", "Third-party apps"):
            self.assertIn(part, bodies[1])
        self.assertIn("kirocrew app enable dues-banshee", bodies[2])
        self.assertIn("create", bodies[3].lower())
        self.assertIn("secrets", bodies[3].lower())

    def _step_body(self, number):
        """Text of a numbered step, including its indented continuation lines."""
        match = re.search(
            rf"(?ms)^{number}\. .*?(?=^\d+\. |^#{{1,6}} )", self.text
        )
        self.assertIsNotNone(match, f"step {number} not found")
        return match.group(0)

    def test_install_commands_in_order(self):
        install = self.text.find("kirocrew app install /abs/path")
        trust = self.text.find("Third-party apps")
        enable = self.text.find("kirocrew app enable dues-banshee")
        secrets = self.text.find("Create the secrets file")
        for name, pos in [("install", install), ("trust", trust), ("enable", enable), ("secrets", secrets)]:
            with self.subTest(step=name):
                self.assertGreaterEqual(pos, 0)
        self.assertLess(install, trust)
        self.assertLess(trust, enable)
        self.assertLess(enable, secrets)

    def test_secrets_example_is_empty(self):
        matches = [b for b in self.blocks if set(b) == {"base_url", "crew_read_secret", "ladder_run_secret"}]
        self.assertEqual(len(matches), 1)
        for key, value in matches[0].items():
            with self.subTest(key=key):
                self.assertEqual(value, "")

    def test_secrets_path_documented(self):
        self.assertIn("~/.kiro/crew/apps/dues-banshee/data/secrets.json", self.text)

    def test_update_command(self):
        self.assertIn(UPDATE_COMMAND, self.text)

    def test_git_install_described_as_optional(self):
        git_sections = [s for s in sections(self.text) if re.match(r"#{1,6} .*git", s, flags=re.IGNORECASE)]
        self.assertEqual(len(git_sections), 1)
        self.assertIn("optional", git_sections[0].lower())

    def test_ladder_file_example_and_condition(self):
        matches = [b for b in self.blocks if set(b) == {"base_url", "ladder_run_secret"}]
        self.assertEqual(len(matches), 1)
        for key, value in matches[0].items():
            with self.subTest(key=key):
                self.assertEqual(value, "")
        ladder_sections = [
            s for s in sections(self.text)
            if "ladder.json" in s and '"ladder_run_secret"' in s and '"crew_read_secret"' not in s
        ]
        self.assertEqual(len(ladder_sections), 1)
        self.assertIn("failed not_configured", ladder_sections[0])
        self.assertIn("Run now", ladder_sections[0])

    def test_screenshot_path_referenced(self):
        self.assertIn(f"]({SCREENSHOT})", self.text)

    def test_screenshot_file_exists(self):
        self.assertTrue((REPO_ROOT / SCREENSHOT).is_file())


class LicenseTest(unittest.TestCase):
    def test_license_exists_and_is_mit(self):
        self.assertTrue(LICENSE.is_file())
        self.assertIn("MIT License", LICENSE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
