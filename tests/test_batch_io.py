from io import BytesIO
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from batch_io import TEMPLATE_COLUMNS, assess_csv, result_csv, template_csv  # noqa: E402


class BatchIoTests(unittest.TestCase):
    def _csv(self, rows: list[dict[str, object]]) -> bytes:
        return pd.DataFrame(rows, columns=TEMPLATE_COLUMNS).to_csv(
            index=False
        ).encode("utf-8")

    def _row(self, **overrides: object) -> dict[str, object]:
        row = {column: "" for column in TEMPLATE_COLUMNS}
        row.update(
            {
                "record_id": "R001",
                "field_id": "F001",
                "crop_stage": "V6",
                "flood_days": "5",
                "waterlog_days": "3",
                "drainage_delay_hours": "48",
                "standing_water": "no",
                "target_disease": "southern_rust",
                "symptom_status": "none",
                "diagnosis_status": "not_assessed",
                "pre_flood_baseline": "none",
                "cultivar_name": "MY73",
                "disease_pressure": "high",
                "temperature_c": "27",
                "humidity_pct": "95",
                "wind_speed_ms": "2",
            }
        )
        row.update(overrides)
        return row

    def test_template_has_headers_without_data_rows(self) -> None:
        frame = pd.read_csv(BytesIO(template_csv()))
        self.assertEqual(list(frame.columns), TEMPLATE_COLUMNS)
        self.assertTrue(frame.empty)

    def test_saved_template_matches_generated_template(self) -> None:
        path = PROJECT_DIR / "data" / "field_observation_template_v0.6.csv"
        frame = pd.read_csv(path)
        self.assertEqual(list(frame.columns), TEMPLATE_COLUMNS)
        self.assertTrue(frame.empty)

    def test_valid_row_is_assessed_and_metadata_is_preserved(self) -> None:
        results, errors = assess_csv(
            self._csv(
                [
                    self._row(
                        observer="T01",
                        weather_source="field station",
                        notes="test record",
                    )
                ]
            )
        )
        self.assertTrue(errors.empty)
        self.assertEqual(len(results), 1)
        row = results.iloc[0]
        self.assertEqual(row["field_id"], "F001")
        self.assertEqual(row["observer"], "T01")
        self.assertEqual(row["weather_source"], "field station")
        self.assertEqual(row["environment_suitability"], "optimal")
        self.assertEqual(row["regional_flood_status"], "not_available")
        self.assertEqual(row["missing_inputs"], "")
        self.assertEqual(row["case_id"], "henan_maize_2026")
        self.assertEqual(row["region_code"], "CN-HA")
        self.assertEqual(row["country_code"], "CN")
        self.assertEqual(row["crop_code"], "maize")
        self.assertEqual(row["currency_code"], "CNY")
        self.assertTrue(result_csv(results).startswith(b"\xef\xbb\xbf"))

    def test_missing_environment_keeps_core_assessment(self) -> None:
        results, errors = assess_csv(
            self._csv(
                [
                    self._row(
                        temperature_c="",
                        humidity_pct="",
                        wind_speed_ms="",
                    )
                ]
            )
        )
        self.assertTrue(errors.empty)
        row = results.iloc[0]
        self.assertEqual(row["environment_suitability"], "insufficient_data")
        self.assertNotEqual(row["risk_label"], "数据不足")

    def test_blank_core_values_are_not_filled_with_defaults(self) -> None:
        results, errors = assess_csv(
            self._csv(
                [
                    self._row(
                        crop_stage="",
                        flood_days="",
                        waterlog_days="",
                        temperature_c="",
                        humidity_pct="",
                    )
                ]
            )
        )
        self.assertTrue(errors.empty)
        row = results.iloc[0]
        self.assertEqual(row["data_completeness"], "insufficient_core")
        self.assertEqual(row["risk_label"], "数据不足")
        self.assertIn("连续田面明水天数", row["missing_inputs"])

    def test_invalid_number_rejects_only_that_row(self) -> None:
        results, errors = assess_csv(
            self._csv(
                [
                    self._row(field_id="BAD", flood_days="five"),
                    self._row(field_id="GOOD"),
                ]
            )
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results.iloc[0]["field_id"], "GOOD")
        self.assertEqual(len(errors), 1)
        self.assertIn("不是有效数值", errors.iloc[0]["错误"])

    def test_blank_field_id_is_rejected(self) -> None:
        results, errors = assess_csv(
            self._csv([self._row(field_id="")])
        )
        self.assertTrue(results.empty)
        self.assertEqual(errors.iloc[0]["字段"], "field_id")

    def test_missing_required_column_is_reported(self) -> None:
        data = pd.DataFrame([{"field_id": "F001"}]).to_csv(index=False).encode("utf-8")
        results, errors = assess_csv(data)
        self.assertTrue(results.empty)
        self.assertTrue((errors["错误"] == "缺少必需列").all())

    def test_us_cscap_observations_are_marked_external(self) -> None:
        path = (
            PROJECT_DIR
            / "case_packs"
            / "us_corn_belt_cscap_2011_2015"
            / "processed"
            / "observations_v0.6.csv"
        )
        results, errors = assess_csv(path.read_bytes())
        self.assertTrue(errors.empty)
        self.assertEqual(len(results), 168)
        self.assertEqual(
            set(results["case_id"]),
            {"us_corn_belt_cscap_2011_2015"},
        )
        self.assertEqual(set(results["evidence_level"]), {"EXTERNAL_OBSERVED"})
        self.assertEqual(results["risk_label"].nunique(), 1)
        self.assertIn("仅监测", results.iloc[0]["risk_label"])


if __name__ == "__main__":
    unittest.main()
