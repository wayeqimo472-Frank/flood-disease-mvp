import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from batch_io import assess_csv  # noqa: E402


class DemoScenarioTests(unittest.TestCase):
    def test_demo_csv_runs_without_errors_and_is_marked_test_only(self) -> None:
        path = PROJECT_DIR / "data" / "demo_scenarios_v0.4.csv"
        results, errors = assess_csv(path.read_bytes())

        self.assertTrue(errors.empty)
        self.assertEqual(len(results), 8)
        self.assertEqual(set(results["evidence_level"]), {"TEST_ONLY"})
        self.assertTrue(results["notes"].str.contains("不是田间观测").all())
        self.assertEqual(
            results.set_index("record_id").loc["TEST-007", "risk_label"],
            "数据不足",
        )
        self.assertEqual(
            results.set_index("record_id").loc["TEST-005", "treatment_status"],
            "no_fungicide",
        )


if __name__ == "__main__":
    unittest.main()
