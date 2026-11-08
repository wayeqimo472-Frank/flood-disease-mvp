import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from risk_engine import FieldScenario, assess  # noqa: E402


class RiskEngineTests(unittest.TestCase):
    def _complete_scenario(self, **overrides):
        values = dict(
            crop_stage="V6",
            flood_days=5,
            waterlog_days=3,
            drainage_delay_hours=48,
            standing_water=False,
            target_disease="southern_rust",
            symptom_status="none",
            diagnosis_status="not_assessed",
            pre_flood_baseline="none",
            cultivar_name="MY73",
            disease_pressure="high",
            temperature_c=27,
            humidity_pct=95,
            wind_speed_ms=2,
        )
        values.update(overrides)
        return FieldScenario(**values)

    def test_short_flood_does_not_claim_low_risk_without_anchor(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V3",
                flood_days=1,
                waterlog_days=0,
                drainage_delay_hours=12,
                standing_water=False,
                temperature_c=20,
                humidity_pct=70,
            )
        )
        self.assertEqual(result.risk_low, "moderate")
        self.assertEqual(result.risk_high, "moderate")
        self.assertIn("减产上界<25%", result.surface_water_status)
        self.assertIn("open", result.drainage_window)
        self.assertIn("monitor", result.disease_window)

    def test_v6_long_flood_is_very_high(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=10,
                waterlog_days=0,
                drainage_delay_hours=72,
                standing_water=False,
                symptom_status="sparse",
                disease_pressure="high",
                temperature_c=27,
                humidity_pct=95,
            )
        )
        self.assertEqual(result.risk_low, "very_high")
        self.assertEqual(result.risk_high, "very_high")
        self.assertEqual(result.regional_flood_class, "not_available")
        self.assertIn("closing", result.drainage_window)
        self.assertIn("pending_diagnosis", result.disease_window)

    def test_r3_does_not_inherit_v6_mortality(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="R3",
                flood_days=10,
                waterlog_days=0,
                drainage_delay_hours=8,
                standing_water=False,
                temperature_c=20,
                humidity_pct=70,
            )
        )
        self.assertEqual(result.risk_low, "high")
        self.assertEqual(result.risk_high, "high")
        self.assertEqual(result.regional_flood_class, "not_available")
        self.assertEqual(result.disease_window_precise_days, "unknown")

    def test_short_flood_uses_e04_not_e14_as_stage_band(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=2.9,
                waterlog_days=0,
                drainage_delay_hours=8,
                standing_water=False,
                temperature_c=20,
                humidity_pct=70,
            )
        )
        self.assertEqual(result.risk_low, "moderate")
        self.assertEqual(result.regional_flood_class, "not_available")
        self.assertIn("E04", result.surface_water_status)

    def test_obvious_symptoms_without_diagnosis_require_diagnosis(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="VT",
                flood_days=6,
                waterlog_days=0,
                drainage_delay_hours=80,
                standing_water=False,
                symptom_status="obvious",
                disease_pressure="high",
            )
        )
        self.assertIn("pending_diagnosis", result.disease_window)
        self.assertIn("delayed", result.drainage_window)

    def test_confirmed_fungal_disease_opens_treatment_window(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="R3",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=36,
                standing_water=False,
                symptom_status="obvious",
                diagnosis_status="confirmed_fungal",
                temperature_c=27,
                humidity_pct=95,
                wind_speed_ms=2.0,
            )
        )
        self.assertIn("open", result.disease_window)
        self.assertEqual(result.environment_suitability, "optimal")

    def test_nonfungal_diagnosis_blocks_fungicide_window(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="R3",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=36,
                standing_water=False,
                symptom_status="obvious",
                diagnosis_status="confirmed_nonfungal",
            )
        )
        self.assertIn("no_fungicide", result.disease_window)
        self.assertEqual(result.environment_suitability, "not_applicable")
        self.assertIn(
            "不评价南方锈病环境适宜度",
            "".join(result.known_evidence),
        )
        self.assertIn("不按目标真菌病路径解释", result.stage_disease_note)

    def test_symptom_and_diagnosis_four_state_matrix(self) -> None:
        cases = [
            (
                "none_not_assessed",
                "none",
                "not_assessed",
                "尚未发现症状",
                "standby",
                "monitor",
            ),
            (
                "observed_not_diagnosed",
                "obvious",
                "not_assessed",
                "症状明显，尚未确诊",
                "required",
                "pending_diagnosis",
            ),
            (
                "observed_confirmed_fungal",
                "obvious",
                "confirmed_fungal",
                "已确认真菌性病害",
                "completed_fungal",
                "open",
            ),
            (
                "observed_confirmed_nonfungal",
                "obvious",
                "confirmed_nonfungal",
                "已排除真菌性病害",
                "completed_nonfungal",
                "no_fungicide",
            ),
        ]
        for name, symptom, diagnosis, evidence, diagnosis_status, treatment_status in cases:
            with self.subTest(name=name):
                result = assess(
                    FieldScenario(
                        crop_stage="R3",
                        flood_days=5,
                        waterlog_days=0,
                        drainage_delay_hours=36,
                        standing_water=False,
                        symptom_status=symptom,
                        diagnosis_status=diagnosis,
                        disease_pressure="low",
                        temperature_c=20,
                        humidity_pct=70,
                        wind_speed_ms=2.0,
                    )
                )
                self.assertEqual(result.field_evidence_status, evidence)
                self.assertIn(diagnosis_status, result.windows[2].status)
                self.assertIn(treatment_status, result.windows[3].status)

        no_symptom = assess(
            FieldScenario(
                crop_stage="R3",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=36,
                standing_water=False,
            )
        )
        self.assertTrue(
            any("未见症状不等于未感染" in item for item in no_symptom.unknown_evidence)
        )

    def test_nonfungal_diagnosis_does_not_raise_fungal_pressure(self) -> None:
        baseline = FieldScenario(
            crop_stage="R3",
            flood_days=5,
            waterlog_days=0,
            drainage_delay_hours=36,
            standing_water=False,
            symptom_status="none",
            diagnosis_status="confirmed_nonfungal",
        )
        symptomatic = FieldScenario(
            crop_stage="R3",
            flood_days=5,
            waterlog_days=0,
            drainage_delay_hours=36,
            standing_water=False,
            symptom_status="obvious",
            diagnosis_status="confirmed_nonfungal",
        )
        baseline_result = assess(baseline)
        symptomatic_result = assess(symptomatic)
        self.assertEqual(baseline_result.risk_label, symptomatic_result.risk_label)
        self.assertIn("真菌防治路径关闭", "".join(baseline_result.known_evidence))

    def test_leaf_spot_does_not_enter_rust_treatment_rule(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="R3",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=24,
                standing_water=False,
                target_disease="leaf_spot",
                symptom_status="obvious",
                diagnosis_status="confirmed_fungal",
            )
        )
        self.assertIn("consult_only", result.disease_window)

    def test_waterlogging_is_not_converted_to_surface_flooding(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=0,
                waterlog_days=10,
                standing_water=False,
                drainage_delay_hours=0,
            )
        )
        self.assertEqual(result.risk_low, "high")
        self.assertIn("waterlogging_management", result.drainage_window)

    def test_short_waterlogging_is_present_but_not_quantified(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=0,
                waterlog_days=3,
                standing_water=False,
                drainage_delay_hours=0,
            )
        )
        self.assertIn("存在渍水胁迫", result.waterlogging_status)
        self.assertIn("暂不分级", result.waterlogging_status)
        self.assertNotIn("渍水风险为低", result.rationale)

    def test_established_preflood_baseline_raises_interval(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V3",
                flood_days=1,
                waterlog_days=0,
                drainage_delay_hours=8,
                standing_water=False,
                pre_flood_baseline="established",
                temperature_c=20,
                humidity_pct=70,
            )
        )
        self.assertEqual(result.risk_low, "moderate")
        self.assertEqual(result.risk_high, "high")

    def test_unknown_baseline_is_shown_as_a_judgment_limit(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=48,
                standing_water=False,
                pre_flood_baseline="unknown",
                disease_pressure="high",
                temperature_c=27,
                humidity_pct=95,
            )
        )
        self.assertEqual(result.risk_high, "high")
        self.assertTrue(
            any("缺少洪涝前田块病情基线" in item for item in result.unknown_evidence)
        )
        self.assertIn("不等于田间已经发病", "".join(result.limitations))

    def test_field_evidence_keeps_symptoms_separate_from_diagnosis(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="VT",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=48,
                standing_water=False,
                symptom_status="obvious",
            )
        )
        self.assertEqual(result.field_evidence_status, "症状明显，尚未确诊")
        self.assertTrue(
            any("疑似症状尚未确诊" in item for item in result.unknown_evidence)
        )

    def test_zhengdan958_note_is_qualitative_only(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=4,
                waterlog_days=0,
                drainage_delay_hours=24,
                standing_water=False,
                cultivar_name="郑单958",
            )
        )
        self.assertIn("郑单958", result.stage_disease_note)
        self.assertIn("不据此调整病害风险", result.stage_disease_note)

    def test_cultivar_identity_has_no_unsupported_risk_bonus(self) -> None:
        common = dict(
            crop_stage="V6",
            flood_days=3,
            waterlog_days=0,
            drainage_delay_hours=24,
            standing_water=False,
            temperature_c=20,
            humidity_pct=70,
        )
        unknown = assess(FieldScenario(cultivar_name="unknown", **common))
        zhengdan = assess(FieldScenario(cultivar_name="郑单958", **common))
        self.assertEqual(unknown.risk_label, zhengdan.risk_label)
        self.assertIn("保留未知状态", unknown.stage_disease_note)
        self.assertIn("耐涝对比", zhengdan.stage_disease_note)

    def test_e14_is_not_inferred_from_field_water_days(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=5,
                waterlog_days=0,
                drainage_delay_hours=48,
                standing_water=False,
                disease_pressure="low",
                temperature_c=20,
                humidity_pct=70,
            )
        )
        self.assertEqual(result.risk_low, "moderate")
        self.assertEqual(result.regional_flood_class, "not_available")
        self.assertEqual(
            set(result.evidence_parameter_ids),
            {"P013", "P015", "P016"},
        )
        self.assertFalse({"P019", "P020", "P021"} & set(result.evidence_parameter_ids))
        self.assertFalse({"R003", "R004", "R009"} & set(result.evidence_rule_ids))

    def test_missing_environment_does_not_become_favorable(self) -> None:
        cases = [
            ("temperature_missing", None, 95),
            ("humidity_missing", 27, None),
            ("both_missing", None, None),
        ]
        for name, temperature, humidity in cases:
            with self.subTest(name=name):
                result = assess(
                    self._complete_scenario(
                        temperature_c=temperature,
                        humidity_pct=humidity,
                    )
                )
                self.assertEqual(
                    result.environment_suitability,
                    "insufficient_data",
                )
                self.assertNotEqual(result.risk_label, "数据不足")
                self.assertEqual(result.data_completeness, "partial")

    def test_missing_core_exposure_is_unknown_not_zero(self) -> None:
        result = assess(
            self._complete_scenario(
                flood_days=None,
                waterlog_days=None,
            )
        )
        self.assertEqual(result.risk_label, "数据不足")
        self.assertEqual(result.risk_low, "unknown")
        self.assertEqual(result.data_completeness, "insufficient_core")
        self.assertIn("连续田面明水天数", result.missing_inputs)
        self.assertIn("土壤饱和/渍水天数", result.missing_inputs)
        self.assertIn("未按0天处理", result.surface_water_status)
        self.assertIn("未按0天处理", result.waterlogging_status)

    def test_missing_operational_data_limits_window_only(self) -> None:
        result = assess(
            self._complete_scenario(
                drainage_delay_hours=None,
                standing_water=None,
            )
        )
        self.assertNotEqual(result.risk_label, "数据不足")
        self.assertIn("data_insufficient", result.drainage_window)
        self.assertEqual(result.windows[1].status, "condition_unknown")

    def test_e04_usage_trace_distinguishes_v6_and_r3(self) -> None:
        v6 = assess(self._complete_scenario(crop_stage="V6"))
        r3 = assess(self._complete_scenario(crop_stage="R3"))

        v6_ids = set(v6.evidence_parameter_ids)
        r3_ids = set(r3.evidence_parameter_ids)
        self.assertTrue({"P013", "P015", "P016"} <= v6_ids)
        self.assertIn("P018", r3_ids)
        self.assertNotIn("P013", r3_ids)
        self.assertFalse({"P019", "P020", "P021"} & (v6_ids | r3_ids))

        p013_uses = [
            item for item in v6.parameter_uses if item.parameter_id == "P013"
        ]
        self.assertEqual(
            {(item.role, item.field) for item in p013_uses},
            {
                ("状态判断参数", "time_value"),
                ("解释性证据", "value_high"),
            },
        )

    def test_standing_water_blocks_field_operations(self) -> None:
        result = assess(
            FieldScenario(
                crop_stage="V6",
                flood_days=4,
                waterlog_days=2,
                drainage_delay_hours=24,
                standing_water=True,
                symptom_status="sparse",
                diagnosis_status="confirmed_fungal",
            )
        )
        self.assertIn("active", result.drainage_window)
        self.assertIn("blocked_water", result.disease_window)

    def test_invalid_negative_flood_days_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FieldScenario(
                crop_stage="V6",
                flood_days=-1,
                drainage_delay_hours=0,
            )


if __name__ == "__main__":
    unittest.main()
