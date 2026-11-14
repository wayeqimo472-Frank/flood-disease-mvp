import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))


class PublicEvidenceTests(unittest.TestCase):
    def test_one_acre_summary_is_present(self) -> None:
        relative_source = (
            Path("raw_data")
            / "one_acre_fund_maize_survey_2016_2022"
            / "One_Acre_Fund_MEL_maize_survey_data_2016-2022.csv"
        )
        source = next(
            (
                candidate / relative_source
                for candidate in (
                    PROJECT_DIR.parent / "additional data",
                    PROJECT_DIR.parent.parent
                    / "360MoveData"
                    / "Users"
                    / "Lenovo"
                    / "Desktop"
                    / "大创项目"
                    / "additional data",
                )
                if (candidate / relative_source).is_file()
            ),
            None,
        )
        if source is None:
            self.skipTest("本地 One Acre Fund 原始CSV未随仓库提供")
        frame = pd.read_csv(source)
        self.assertEqual(len(frame), 14773)
        self.assertEqual(int((frame["water_excess"] & frame["disease"]).sum()), 43)
        self.assertTrue(frame["yield_kg_ha"].notna().all())

    def test_derived_public_evidence_files(self) -> None:
        evidence_dir = PROJECT_DIR / "data" / "public_evidence_v0.2"
        self.assertEqual(
            len(pd.read_csv(evidence_dir / "divine_leaf_wetness_hourly.csv")),
            8784,
        )
        self.assertEqual(
            len(pd.read_csv(evidence_dir / "flood_tolerant_maize_2020_plots.csv")),
            1594,
        )
        self.assertEqual(
            len(pd.read_csv(evidence_dir / "italy_leaf_wetness_site_summary.csv")),
            7,
        )
        lwd_summary = pd.read_csv(evidence_dir / "lwd_rh90_proxy_summary.csv")
        self.assertEqual(len(lwd_summary), 2)
        self.assertLess(lwd_summary["mean_sensitivity"].max(), 0.5)

    def test_public_register_and_gap_matrix(self) -> None:
        register = pd.read_csv(
            PROJECT_DIR / "data" / "public_dataset_register_v0.2.csv"
        )
        gaps = pd.read_csv(
            PROJECT_DIR / "data" / "public_data_gap_matrix_v0.2.csv"
        )
        self.assertGreaterEqual(len(register), 10)
        self.assertGreaterEqual(len(gaps), 14)
        self.assertEqual(set(gaps["priority"]), {"P0", "P1", "P2"})
        self.assertTrue(
            {
                "ONEACRE-MAIZE",
                "FLOOD-MAIZE-UAV",
                "DIVINE-LWD",
                "ITALY-LWD",
            }.issubset(set(register["dataset_id"]))
        )

    def test_complete_missing_data_register(self) -> None:
        missing = pd.read_csv(
            PROJECT_DIR / "data" / "all_missing_data_v0.3.csv"
        )
        self.assertEqual(len(missing), 50)
        self.assertEqual(
            missing["priority"].value_counts().to_dict(),
            {"P1": 24, "P0": 20, "P2": 6},
        )
        self.assertEqual(missing["data_id"].nunique(), len(missing))


if __name__ == "__main__":
    unittest.main()
