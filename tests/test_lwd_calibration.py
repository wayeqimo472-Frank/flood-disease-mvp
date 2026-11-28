import json
import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from lwd_calibration import (  # noqa: E402
    DEFAULT_LWD_CV_PATH,
    DEFAULT_LWD_MODEL_PATH,
    DEFAULT_LWD_RELIABILITY_PATH,
    DEFAULT_LWD_SUMMARY_PATH,
    build_lwd_features,
    compute_dew_point_depression,
    compute_reliability_bins,
    estimate_lwd_hour_probability,
    predict_gleason_physical,
    predict_rh_hysteresis_physical,
)


class LwdCalibrationTests(unittest.TestCase):
    def test_frozen_model_has_valid_physical_signs(self) -> None:
        model = json.loads(DEFAULT_LWD_MODEL_PATH.read_text(encoding="utf-8"))
        self.assertEqual(model["model_version"], "lwd_proxy_calib_v0.1")
        self.assertLess(model["weights"]["dew_point_depression_c"], 0.0)
        self.assertGreater(model["weights"]["is_raining"], 0.0)
        self.assertGreater(model["dpd_threshold_c"], 0.0)

    def test_calibration_summary_and_reliability_bins_are_valid(self) -> None:
        summary = pd.read_csv(DEFAULT_LWD_SUMMARY_PATH)
        cv = pd.read_csv(DEFAULT_LWD_CV_PATH)
        reliability = pd.read_csv(DEFAULT_LWD_RELIABILITY_PATH)
        self.assertEqual(len(summary), 14)
        self.assertEqual(len(cv), 112)
        self.assertEqual(len(reliability), 40)

        for dataset_name in ("Italy 7-site", "DIVINE Spain"):
            sub = summary[summary["dataset"] == dataset_name].set_index("model_name")
            base = sub.loc["rh90_baseline"]
            dpd = sub.loc["dpd_physical_threshold"]
            gleason = sub.loc["gleason_cart_physical"]
            hyst = sub.loc["rh_hysteresis_physical"]
            log_m = sub.loc["multifeature_logistic"]
            t_log = sub.loc["multifeature_temporal_logistic"]
            self.assertGreater(dpd["mean_sensitivity"], base["mean_sensitivity"] + 0.30)
            self.assertGreater(log_m["mean_sensitivity"], base["mean_sensitivity"] + 0.30)
            self.assertGreater(t_log["mean_sensitivity"], base["mean_sensitivity"] + 0.30)
            self.assertGreater(
                dpd["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.10
            )
            self.assertGreater(
                log_m["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.10
            )
            self.assertGreater(
                hyst["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.04
            )
            self.assertGreater(
                gleason["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.03
            )

        for _, row in reliability.groupby(["dataset", "model_name"]):
            self.assertGreaterEqual(float(row["ece"].iloc[0]), 0.0)
            self.assertLessEqual(float(row["ece"].iloc[0]), 1.0)
            self.assertGreater(int(row["sample_count"].sum()), 5000)

    def test_zero_param_physical_baselines_and_reliability_helper(self) -> None:
        raw = pd.DataFrame(
            {
                "timestamp": [
                    "2024-07-16T02:00:00",
                    "2024-07-16T03:00:00",
                    "2024-07-16T14:00:00",
                ],
                "temperature_c": [22.0, 22.0, 30.0],
                "rh_pct": [95.0, 78.0, 50.0],
                "rain_mm": [2.0, 0.0, 0.0],
                "wind_speed_ms": [1.5, 1.5, 3.0],
            }
        )
        feats = build_lwd_features(raw)
        gleason = predict_gleason_physical(feats)
        self.assertEqual(gleason.tolist(), [True, False, False])

        # Hour 2 retains post-rain drying lag (prev_hour_rain_mm > 0 and rh >= 75)
        hyst = predict_rh_hysteresis_physical(feats)
        self.assertEqual(hyst.tolist(), [True, True, False])

        bins_df, ece = compute_reliability_bins([1, 0, 1, 0], [0.9, 0.1, 0.85, 0.15], n_bins=5)
        self.assertEqual(len(bins_df), 5)
        self.assertLess(ece, 0.2)

    def test_missing_core_inputs_return_none_and_high_humidity_exceeds_dry(self) -> None:
        missing = estimate_lwd_hour_probability(None, 90.0)
        self.assertIsNone(missing.wet_probability)
        self.assertIsNone(missing.is_wet)
        self.assertEqual(missing.evidence_level, "proxy_model_estimate")

        wet = estimate_lwd_hour_probability(24.0, 96.0, rain_mm=2.0, is_night=1.0)
        dry = estimate_lwd_hour_probability(33.0, 45.0, rain_mm=0.0, is_night=0.0)
        self.assertIsNotNone(wet.wet_probability)
        self.assertIsNotNone(dry.wet_probability)
        self.assertGreater(wet.wet_probability, dry.wet_probability)
        self.assertLess(compute_dew_point_depression(24.0, 96.0), 1.0)


if __name__ == "__main__":
    unittest.main()
