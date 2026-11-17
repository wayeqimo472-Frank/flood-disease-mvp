import re
from pathlib import Path
import unittest


THEME_CSS = (
    Path(__file__).resolve().parents[1] / "assets" / "app.css"
).read_text(encoding="utf-8")


class ThemeRegressionTests(unittest.TestCase):
    def test_focus_ring_never_targets_inner_baseweb_input(self) -> None:
        selectors = re.findall(
            r"(?m)^([^{}\n]*:focus-visible[^{}]*)\{",
            THEME_CSS,
        )
        self.assertTrue(selectors)
        for selector in selectors:
            cleaned = selector.strip()
            self.assertNotEqual(cleaned, ":focus-visible")
            self.assertNotIn("input", cleaned.lower())

    def test_expander_has_one_outer_border(self) -> None:
        outer_rule = re.search(
            r'\[data-testid="stExpander"\]\s*\{(.*?)\}',
            THEME_CSS,
            re.S,
        )
        self.assertIsNotNone(outer_rule)
        self.assertRegex(outer_rule.group(1), r"border:\s*0\s*;")
        self.assertRegex(
            THEME_CSS,
            r'\[data-testid="stExpander"\]\s*>\s*details\s*\{',
        )


if __name__ == "__main__":
    unittest.main()
