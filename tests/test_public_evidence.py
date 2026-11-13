import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"


class PublicEvidenceDataTests(unittest.TestCase):
    def test_catalog_tracks_imported_and_candidate_sources(self) -> None:
        catalog = pd.read_csv(DATA_DIR / "public_evidence_catalog_v0.1.csv")
        self.assertEqual(len(catalog), 6)
        self.assertEqual(
            catalog["integration_status"].str.startswith("已导入").sum(),
            3,
        )
        self.assertTrue(catalog["doi"].str.startswith("10.").all())

    def test_flood_case_contains_control_and_flooded_trajectories(self) -> None:
        flood = pd.read_csv(DATA_DIR / "public_flood_case_maize_v0.1.csv")
        self.assertEqual(len(flood), 6)
        self.assertEqual(flood["condition"].nunique(), 2)
        self.assertTrue(flood["mean_ndvi"].between(0, 1).all())
        self.assertEqual(
            set(flood["source_id"]),
            {"10.5281/zenodo.14261169"},
        )

    def test_maize_waterlogging_survival_records_are_bounded(self) -> None:
        survival = pd.read_csv(
            DATA_DIR / "public_waterlogging_survival_maize_v0.1.csv"
        )
        self.assertEqual(len(survival), 80)
        self.assertTrue(survival["survival_pct"].between(0, 100).all())
        self.assertTrue(survival["genotype"].is_unique)

    def test_disease_progress_has_source_scope_and_fit_quality(self) -> None:
        progress = pd.read_csv(
            DATA_DIR / "public_disease_progress_maize_v0.1.csv"
        )
        self.assertEqual(len(progress), 13)
        self.assertTrue(progress["r_squared"].between(0, 1).all())
        self.assertTrue(
            progress["evidence_scope"].str.contains("巴西").all()
        )


if __name__ == "__main__":
    unittest.main()
