import re
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEME_CSS = (PROJECT_ROOT / "assets" / "app.css").read_text(encoding="utf-8")
UI_COMPONENTS = (PROJECT_ROOT / "ui_components.py").read_text(encoding="utf-8")


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

    def test_interface_images_are_local_and_present(self) -> None:
        image_dir = PROJECT_ROOT / "static" / "images"
        for name in ("corn-field.jpg", "field-aerial.jpg", "farmland.jpg"):
            image = image_dir / name
            self.assertTrue(image.is_file(), name)
            self.assertGreater(image.stat().st_size, 10_000)
            self.assertIn(f"app/static/images/{name}", UI_COMPONENTS)


if __name__ == "__main__":
    unittest.main()
