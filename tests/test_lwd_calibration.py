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
    DEFAULT_LWD_SUMMARY_PATH,
    compute_dew_point_depression,
    estimate_lwd_hour_probability,
)


class LwdCalibrationTests(unittest.TestCase):
    def test_frozen_model_has_valid_physical_signs(self) -> None:
        model = json.loads(DEFAULT_LWD_MODEL_PATH.read_text(encoding="utf-8"))
        self.assertEqual(model["model_version"], "lwd_proxy_calib_v0.1")
        self.assertLess(model["weights"]["dew_point_depression_c"], 0.0)
        self.assertGreater(model["weights"]["is_raining"], 0.0)
        self.assertGreater(model["dpd_threshold_c"], 0.0)

    def test_calibration_summary_improves_sensitivity_and_balanced_accuracy(self) -> None:
        summary = pd.read_csv(DEFAULT_LWD_SUMMARY_PATH)
        cv = pd.read_csv(DEFAULT_LWD_CV_PATH)
        self.assertEqual(len(summary), 8)
        self.assertEqual(len(cv), 64)

        for dataset_name in ("Italy 7-site", "DIVINE Spain"):
            sub = summary[summary["dataset"] == dataset_name].set_index("model_name")
            base = sub.loc["rh90_baseline"]
            dpd = sub.loc["dpd_physical_threshold"]
            log_m = sub.loc["multifeature_logistic"]
            self.assertGreater(dpd["mean_sensitivity"], base["mean_sensitivity"] + 0.30)
            self.assertGreater(log_m["mean_sensitivity"], base["mean_sensitivity"] + 0.30)
            self.assertGreater(
                dpd["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.10
            )
            self.assertGreater(
                log_m["mean_balanced_accuracy"], base["mean_balanced_accuracy"] + 0.10
            )

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
