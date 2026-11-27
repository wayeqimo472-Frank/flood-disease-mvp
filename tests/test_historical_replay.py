import json
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from batch_io import TEMPLATE_COLUMNS  # noqa: E402
from data_integration import parse_geojson_geometries, parse_sar_metrics_csv  # noqa: E402


REPLAY_DIR = PROJECT_DIR / "data" / "historical_replay"


class HistoricalReplayAndTrialTests(unittest.TestCase):
    def test_sheqi_geojson_and_sar_csv_pass_validators(self) -> None:
        geo_bytes = (REPLAY_DIR / "sheqi_2024_sample_plots.geojson").read_bytes()
        geometries = parse_geojson_geometries(
            geo_bytes,
            case_id="henan_maize_2026",
            source="ftw_prediction",
        )
        self.assertEqual(len(geometries), 4)

        sar_bytes = (REPLAY_DIR / "sheqi_2024_sar_flood_metrics.csv").read_bytes()
        records = parse_sar_metrics_csv(
            sar_bytes,
            case_id="henan_maize_2026",
            source="sentinel1_rtc_planetary_computer",
        )
        self.assertEqual(len(records), 20)

        sar_df = pd.read_csv(REPLAY_DIR / "sheqi_2024_sar_flood_metrics.csv")
        plain_01 = sar_df[sar_df["field_id"] == "SHEQI_PLAIN_01"].set_index("event_date")
        ctrl_01 = sar_df[sar_df["field_id"] == "SHEQI_CTRL_01"].set_index("event_date")
        self.assertGreater(float(plain_01.loc["2024-07-16", "flooded_area_pct"]), 30.0)
        self.assertLess(float(plain_01.loc["2024-07-28", "flooded_area_pct"]), 2.0)
        self.assertLess(float(ctrl_01.loc["2024-07-16", "flooded_area_pct"]), 2.0)

    def test_sheqi_weather_and_replay_timeline_align(self) -> None:
        weather = pd.read_csv(REPLAY_DIR / "sheqi_2024_weather_daily.csv").set_index("date")
        timeline = pd.read_csv(REPLAY_DIR / "sheqi_2024_replay_timeline.csv")
        summary = json.loads((REPLAY_DIR / "sheqi_2024_replay_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["s1_scenes_count"], 5)
        self.assertEqual(len(timeline), 54)
        self.assertGreater(float(weather.loc["2024-07-16", "precip_open_meteo_mm"]), 40.0)
        self.assertEqual(int(weather.loc["2024-07-22", "rh90_wet_hours"]), 0)
        self.assertLess(
            int(weather.loc["2024-07-22", "dpd_physical_wet_hours"]),
            int(weather.loc["2024-07-15", "dpd_physical_wet_hours"]),
        )
        milestones = timeline[timeline["official_milestone"].fillna("") != ""]
        self.assertGreaterEqual(len(milestones), 6)

    def test_local_trial_template_contains_batch_columns(self) -> None:
        template_path = PROJECT_DIR / "data" / "local_trial_observation_template_v0.1.csv"
        frame = pd.read_csv(template_path)
        self.assertEqual(len(frame), 0)
        self.assertTrue(set(TEMPLATE_COLUMNS).issubset(set(frame.columns)))


if __name__ == "__main__":
    unittest.main()
