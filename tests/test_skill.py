import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "tax-bomb" / "SKILL.md"
DISCLAIMER = "Reminders a supplier sends to its own buyers. Not legal advice."

REQUIRED_TERMS = [
    "43B(h)",
    "37(2)(g)",
    "s.15",
    "31 March",
    "daysLeft",
    "deductionAtRiskText",
    "unavailable",
    "supplierName",
    "buyerName",
    "invoiceNumber",
]


def split_skill(text):
    """Return (frontmatter, body) or raise AssertionError if frontmatter is malformed."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise AssertionError("SKILL.md must start with '---'")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise AssertionError("SKILL.md frontmatter has no closing '---'")


class SkillWordingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.frontmatter, cls.body = split_skill(cls.text)

    def test_frontmatter_names_the_skill(self):
        self.assertTrue(self.text.startswith("---"))
        names = [
            line.split(":", 1)[1].strip()
            for line in self.frontmatter.splitlines()
            if line.startswith("name:")
        ]
        self.assertEqual(names, ["tax-bomb"])

    def test_required_terms_present(self):
        for term in REQUIRED_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_prefilled_message_named_before_pasted_text(self):
        prefilled = self.body.find('prefilled "Ask the banshee" message')
        pasted = self.body.find("text the user pastes")
        self.assertGreaterEqual(prefilled, 0)
        self.assertGreaterEqual(pasted, 0)
        self.assertLess(prefilled, pasted)

    def test_figures_taken_only_from_final_labels(self):
        sentence = (
            "Take the two figures only from the final `Days to 31 March:` and "
            "`Deduction at risk:` in the message, after the `buyer (data): \"…\".` field. "
            "If either label appears more than once, say the figures are unavailable "
            "and ask the user to check the page."
        )
        self.assertIn(sentence, self.text)

    def test_last_non_empty_line_is_disclaimer(self):
        non_empty = [line for line in self.text.splitlines() if line.strip()]
        self.assertEqual(non_empty[-1], DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
