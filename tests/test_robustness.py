import atexit
import os
import sys
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

TEST_TMP = PROJECT_DIR / "tmp"
TEST_TMP.mkdir(exist_ok=True)
ROBUST_TEST_DIR = Path(tempfile.mkdtemp(prefix="robust-test-db-", dir=TEST_TMP))
os.environ.setdefault("FLOOD_APP_DB_PATH", str(ROBUST_TEST_DIR / "app.db"))
atexit.register(lambda: os.path.exists(ROBUST_TEST_DIR) and __import__("shutil").rmtree(ROBUST_TEST_DIR, ignore_errors=True))

from risk_engine import FieldScenario  # noqa: E402
from robustness import UncertaintyBounds, analyze_robustness  # noqa: E402


class RobustnessAndNewPagesTests(unittest.TestCase):
    def test_diagnosis_gate_stays_invariant_under_large_bounds(self) -> None:
        base = FieldScenario(
            crop_stage="R3",
            flood_days=4.0,
            waterlog_days=3.0,
            drainage_delay_hours=48.0,
            standing_water=False,
            target_disease="southern_rust",
            symptom_status="obvious",
            diagnosis_status="not_assessed",
            pre_flood_baseline="unknown",
            cultivar_name="unknown",
            disease_pressure="high",
            temperature_c=27.0,
            humidity_pct=92.0,
            wind_speed_ms=2.0,
            case_id="henan_maize_2026",
        )
        bounds = UncertaintyBounds(
            flood_days_delta=2.0,
            waterlog_days_delta=2.0,
            drainage_delay_delta_hours=24.0,
            temperature_delta_c=2.0,
            humidity_delta_pct=8.0,
            wind_delta_ms=1.0,
        )
        report = analyze_robustness(base, bounds)
        self.assertGreater(report.total_scenarios, 100)
        by_win = {w.window: w for w in report.window_results}
        self.assertEqual(by_win["诊断窗口"].stability_tier, "稳健不变")
        self.assertEqual(by_win["诊断窗口"].base_agreement_pct, 100.0)
        self.assertEqual(by_win["病害防治窗口"].stability_tier, "稳健不变")
        self.assertEqual(by_win["病害防治窗口"].base_status, "pending_diagnosis")

    def test_wind_and_temp_thresholds_identify_exact_sensitive_drivers(self) -> None:
        base = FieldScenario(
            crop_stage="VT",
            flood_days=3.0,
            waterlog_days=2.0,
            drainage_delay_hours=24.0,
            standing_water=False,
            target_disease="southern_rust",
            symptom_status="obvious",
            diagnosis_status="confirmed_fungal",
            pre_flood_baseline="sporadic",
            cultivar_name="unknown",
            disease_pressure="high",
            temperature_c=29.0,
            humidity_pct=92.0,
            wind_speed_ms=2.8,
            case_id="henan_maize_2026",
        )
        bounds = UncertaintyBounds(
            temperature_delta_c=2.0,  # 29+2 = 31 >= 30 threshold
            wind_delta_ms=1.0,        # 2.8+1.0 = 3.8 >= 3.3 threshold
        )
        report = analyze_robustness(base, bounds)
        by_win = {w.window: w for w in report.window_results}
        ctrl = by_win["病害防治窗口"]
        self.assertEqual(ctrl.stability_tier, "对误差敏感")
        self.assertIn("预计作业风速", ctrl.sensitive_drivers)
        self.assertGreater(len(report.priority_verifications), 0)

    def test_missing_core_inputs_produce_single_safe_scenario(self) -> None:
        base = FieldScenario(
            crop_stage="V6",
            flood_days=None,
            waterlog_days=None,
            drainage_delay_hours=None,
            standing_water=None,
            target_disease="southern_rust",
            symptom_status="none",
            diagnosis_status="not_assessed",
            pre_flood_baseline="unknown",
            cultivar_name="unknown",
            disease_pressure="unknown",
            temperature_c=None,
            humidity_pct=None,
            wind_speed_ms=None,
            case_id="henan_maize_2026",
        )
        bounds = UncertaintyBounds(
            flood_days_delta=2.0,
            temperature_delta_c=2.0,
            humidity_delta_pct=10.0,
            wind_delta_ms=1.0,
        )
        report = analyze_robustness(base, bounds)
        self.assertEqual(report.total_scenarios, 1)
        self.assertEqual(report.risk_agreement_pct, 100.0)

    def test_new_streamlit_sections_render_without_exception(self) -> None:
        # 1. Decision robustness section on 3_intervention.py
        app = AppTest.from_file(str(PROJECT_DIR / "app.py")).run(timeout=20)
        app.switch_page(str(PROJECT_DIR / "pages" / "2_risk.py")).run(timeout=20)
        app.switch_page(str(PROJECT_DIR / "pages" / "3_intervention.py")).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(
            any("不确定性区间与决策稳健性分析" in item.value for item in app.subheader)
        )
        self.assertTrue(
            any(
                {"窗口", "基准状态", "区间一致率", "稳健等级", "敏感驱动因子"} <= set(df.value.columns)
                for df in app.dataframe
            )
        )

        # 2. LWD Reliability & ECE calibration section on 5_evidence.py
        app.switch_page(str(PROJECT_DIR / "pages" / "5_evidence.py")).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(
            any("概率校准曲线（Reliability Diagram）" in item.value for item in app.markdown)
        )

        # 3. Three-event replay comparison & selector on 6_integration.py
        app.switch_page(str(PROJECT_DIR / "pages" / "6_integration.py")).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(
            any("三案例历史洪涝 SAR 与气象窗口回放" in item.value for item in app.subheader)
        )
        replay_selector = next(s for s in app.selectbox if s.label == "选择回放案例")
        replay_selector.set_value("浚县 2021（蓄滞洪区长历时）").run(timeout=20)
        self.assertFalse(app.exception)
        replay_selector = next(s for s in app.selectbox if s.label == "选择回放案例")
        replay_selector.set_value("涿州 2023（蓄滞洪区＋超标准行洪）").run(timeout=20)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
