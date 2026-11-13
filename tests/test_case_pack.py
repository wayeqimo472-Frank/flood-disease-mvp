import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from case_pack import DEFAULT_CASE_ID, available_case_ids, get_case_pack  # noqa: E402
from risk_engine import FieldScenario, assess  # noqa: E402


class CasePackTests(unittest.TestCase):
    def test_default_case_pack_is_discoverable(self) -> None:
        case_ids = available_case_ids()
        self.assertIn(DEFAULT_CASE_ID, case_ids)
        self.assertIn("us_corn_belt_cscap_2011_2015", case_ids)

    def test_case_metadata_and_files_are_separate_from_engine(self) -> None:
        pack = get_case_pack(DEFAULT_CASE_ID)
        self.assertEqual(pack.region_code, "CN-HA")
        self.assertEqual(pack.crop_code, "maize")
        self.assertIn("southern_rust", pack.config["diseases"])
        self.assertIn("郑单958", pack.config["cultivars"])
        self.assertTrue(pack.data_file("priors").is_file())
        self.assertTrue(pack.data_file("rules").is_file())
        self.assertTrue(pack.data_file("gaps").is_file())

    def test_assessment_carries_case_scope(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=5,
                waterlog_days=3,
                drainage_delay_hours=48,
                standing_water=False,
                temperature_c=27,
                humidity_pct=95,
                wind_speed_ms=2,
            )
        )
        self.assertEqual(result.case_id, "henan_maize_2026")
        self.assertEqual(result.region_code, "CN-HA")
        self.assertEqual(result.crop_code, "maize")
        self.assertEqual(result.case_version, "0.6.0")
        self.assertEqual(result.risk_model, "quantitative_stage_rules")

    def test_unknown_case_pack_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FieldScenario(
                crop_stage="V6",
                flood_days=5,
                drainage_delay_hours=48,
                case_id="missing_case",
            )

    def test_monitoring_only_case_does_not_invent_quantitative_risk(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=0,
                waterlog_days=4,
                drainage_delay_hours=48,
                standing_water=False,
                target_disease="ear_rot",
                symptom_status="obvious",
                diagnosis_status="confirmed_fungal",
                temperature_c=24,
                humidity_pct=85,
                wind_speed_ms=2,
                case_id="us_corn_belt_cscap_2011_2015",
            )
        )
        self.assertEqual(result.risk_model, "monitoring_only")
        self.assertEqual(result.risk_label, "仅监测（无本地定量校准）")
        self.assertEqual(result.risk_low, "not_modeled")
        self.assertEqual(result.environment_suitability, "not_modeled")
        self.assertTrue(
            all(
                "未作本地校准" in item.evidence
                for item in result.windows
            )
        )


if __name__ == "__main__":
    unittest.main()
