import ast
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "app.json"

ALLOWED_TOP_LEVEL_KEYS = {
    "name",
    "version",
    "displayName",
    "description",
    "author",
    "license",
    "minKiroCrewVersion",
    "iconPath",
    "skills",
    "crons",
    "ui",
    "backend",
    "credentialMasks",
    "permissions",
}


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_no_extra_top_level_keys(self):
        self.assertEqual(set(self.manifest), ALLOWED_TOP_LEVEL_KEYS)

    def test_identity_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], "dues-banshee")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["displayName"], "Dues Banshee")
        self.assertIsInstance(m["description"], str)
        self.assertTrue(m["description"].strip())
        self.assertEqual(m["author"], "rohhitrz")
        self.assertEqual(m["license"], "MIT")
        self.assertEqual(m["minKiroCrewVersion"], "0.13.0")
        self.assertEqual(m["iconPath"], "assets/icon.png")

    def test_skills(self):
        self.assertEqual(self.manifest["skills"], ["skills/tax-bomb"])

    def test_ui(self):
        ui = self.manifest["ui"]
        self.assertEqual(ui["entry"], "dist/index.mjs")
        self.assertEqual(len(ui["pages"]), 1)
        self.assertEqual(ui["pages"][0]["label"], "Graveyard of Dues")

    def test_backend(self):
        self.assertEqual(
            self.manifest["backend"],
            {
                "entryPoint": "backend/server.py",
                "type": "python",
                "port": "auto",
                "healthCheck": "/health",
            },
        )

    def test_credential_masks(self):
        masks = self.manifest["credentialMasks"]
        self.assertEqual(masks, ["secrets.json"])
        self.assertNotIn("ladder.json", masks)

    def test_permissions(self):
        self.assertEqual(
            self.manifest["permissions"],
            {"api": ["/apps/dues-banshee/api"], "cron": True, "network": True},
        )
        self.assertNotIn("chatLaunch", self.manifest["permissions"])

    def test_no_chat_launch_anywhere(self):
        self.assertNotIn("chatLaunch", json.dumps(self.manifest))

    def test_single_daily_ladder_cron(self):
        crons = self.manifest["crons"]
        self.assertEqual(len(crons), 1)
        cron = crons[0]
        self.assertEqual(cron["name"], "daily-ladder")
        self.assertEqual(cron["cron_expr"], "0 9 * * *")
        self.assertEqual(cron["timezone"], "Asia/Kolkata")
        self.assertIs(cron["strict_schedule"], True)
        self.assertEqual(cron["script"], "cron/daily_ladder.py:run")
        self.assertEqual(cron["timeout_secs"], 300)
        self.assertLess(cron["timeout"], cron["timeout_secs"] - 5)


class ManifestPathsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_skill_files_exist(self):
        for skill in self.manifest["skills"]:
            skill_dir = REPO_ROOT / skill
            self.assertTrue(skill_dir.is_dir(), skill)
            self.assertTrue((skill_dir / "SKILL.md").is_file(), skill)

    def test_ui_entry_exists(self):
        self.assertTrue((REPO_ROOT / "ui").is_dir())
        entry = REPO_ROOT / "ui" / self.manifest["ui"]["entry"]
        self.assertTrue(entry.is_file(), str(entry))

    def test_backend_entry_point_exists(self):
        entry = REPO_ROOT / self.manifest["backend"]["entryPoint"]
        self.assertTrue(entry.is_file(), str(entry))

    def test_icon_exists(self):
        self.assertTrue((REPO_ROOT / self.manifest["iconPath"]).is_file())

    def test_cron_script_defines_function(self):
        script = self.manifest["crons"][0]["script"]
        file_part, _, func_name = script.partition(":")
        self.assertTrue(file_part)
        self.assertTrue(func_name)
        path = REPO_ROOT / file_part
        self.assertTrue(path.is_file(), str(path))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn(func_name, defined)


if __name__ == "__main__":
    unittest.main()
