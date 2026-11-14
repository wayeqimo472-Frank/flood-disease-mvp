import atexit
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

TEST_TMP = PROJECT_DIR / "tmp"
TEST_TMP.mkdir(exist_ok=True)
APP_TEST_DIR = Path(tempfile.mkdtemp(prefix="app-test-db-", dir=TEST_TMP))
os.environ["FLOOD_APP_DB_PATH"] = str(APP_TEST_DIR / "app.db")
atexit.register(shutil.rmtree, APP_TEST_DIR, ignore_errors=True)

from batch_io import TEMPLATE_COLUMNS  # noqa: E402


class AppSmokeTests(unittest.TestCase):
    def _app(self) -> AppTest:
        return AppTest.from_file(str(PROJECT_DIR / "app.py")).run(timeout=20)

    def _risk_app(self) -> AppTest:
        app = self._app()
        app.switch_page(str(PROJECT_DIR / "pages" / "2_risk.py")).run(timeout=20)
        return app

    def _field_data_app(self) -> AppTest:
        app = self._app()
        app.switch_page(str(PROJECT_DIR / "pages" / "4_field_data.py")).run(timeout=20)
        return app

    def _evidence_app(self) -> AppTest:
        app = self._app()
        app.switch_page(str(PROJECT_DIR / "pages" / "5_evidence.py")).run(timeout=20)
        return app

    def _integration_app(self) -> AppTest:
        app = self._app()
        app.switch_page(
            str(PROJECT_DIR / "pages" / "6_integration.py")
        ).run(timeout=20)
        return app

    def _simulation_app(self) -> AppTest:
        app = self._app()
        app.switch_page(
            str(PROJECT_DIR / "pages" / "7_simulation.py")
        ).run(timeout=20)
        return app

    def _cards(self, app: AppTest) -> list[str]:
        markup = next(
            item.value for item in app.markdown if "result-metrics" in item.value
        )
        return re.findall(r'result-metric-value">(.*?)</div>', markup)

    def _submitted_inputs(self, app: AppTest):
        frame = next(
            item.value
            for item in app.dataframe
            if "已提交值" in item.value.columns
        )
        return frame.set_index("字段")["已提交值"]

    def _parameter_table(self, app: AppTest):
        return next(
            item.value
            for item in app.dataframe
            if "实际使用字段" in item.value.columns
        )

    def _selectbox(self, app: AppTest, label: str):
        return next(item for item in app.selectbox if item.label == label)

    def test_overview_renders_without_exception(self) -> None:
        app = self._app()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "项目总览")
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(
            any("最近一次计算摘要" in item.value for item in app.subheader)
        )
        self.assertTrue(any("暂无记录" in item.value for item in app.markdown))

    def test_integration_page_renders_without_exception(self) -> None:
        app = self._integration_app()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "数据拼接与公开案例")
        self.assertTrue(
            any("当前数据库还没有导入公开数据索引" in item.value for item in app.warning)
        )
        self.assertTrue(
            any("ICASA 标准字段映射" in item.value for item in app.subheader)
        )
        self.assertTrue(
            any("FTW 代码许可为 MIT" in item.value for item in app.caption)
        )

    def test_apsim_page_labels_simulated_output(self) -> None:
        app = self._simulation_app()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "APSIM 虚拟实验")
        self.assertTrue(
            any("不是田间实测" in item.value for item in app.warning)
        )
        self.assertEqual(app.metric[0].value, "模型仿真")
        self.assertEqual(app.metric[1].value, "5 个")

    def test_risk_page_renders_without_exception(self) -> None:
        app = self._risk_app()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "风险情景筛查")
        self.assertTrue(
            any('class="result-metrics"' in item.value for item in app.markdown)
        )
        self.assertTrue(
            any("涝渍暴露" in item.value for item in app.markdown)
        )
        self.assertTrue(any("决策摘要" in item.value for item in app.subheader))
        self.assertGreaterEqual(len(app.dataframe), 1)
        self.assertTrue(
            any("情景假设值，非田间实测" in item.value for item in app.info)
        )
        self.assertTrue(
            any("才会应用" in item.value for item in app.caption)
        )
        submitted = self._submitted_inputs(app)
        self.assertEqual(submitted["日平均温度"], "27℃")
        self.assertEqual(submitted["平均相对湿度"], "95%")
        self.assertEqual(submitted["预计作业风速"], "2m/s")

    def test_preset_changes_numeric_inputs(self) -> None:
        app = self._risk_app()
        self._selectbox(app, "快速情景").set_value(
            "短时淹水 / 及时排水"
        ).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input[0].value, 2.0)
        self.assertEqual(app.number_input[1].value, 0.0)
        self.assertEqual(app.number_input[2].value, 12.0)

    def test_custom_scenario_has_no_v6_fallback(self) -> None:
        app = self._risk_app()
        self._selectbox(app, "快速情景").set_value("自定义").run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.number_input], [None] * 6)
        self.assertIsNone(self._selectbox(app, "玉米生育期").value)
        self.assertIsNone(self._selectbox(app, "目标病害").value)
        self.assertIsNone(self._selectbox(app, "当前症状").value)
        self.assertEqual(self._cards(app)[1], "数据不足")
        self.assertEqual(
            self._submitted_inputs(app)["情景来源"],
            "自定义情景",
        )

    def test_modifying_preset_marks_parameters_as_modified(self) -> None:
        app = self._risk_app()
        app.number_input[0].set_value(7.0).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(
            any("参数已修改" in item.value for item in app.warning)
        )
        self.assertEqual(
            self._submitted_inputs(app)["连续田面明水天数"],
            "7天",
        )
        self.assertIn("（参数已修改）", self._submitted_inputs(app)["情景来源"])

    def test_missing_environment_states(self) -> None:
        cases = [
            ("temperature_present_humidity_missing", 20.0, None, 2.0),
            ("temperature_missing_humidity_present", None, 70.0, 2.0),
            ("all_environment_missing", None, None, None),
        ]
        for name, temperature, humidity, wind in cases:
            with self.subTest(name=name):
                app = self._risk_app()
                app.number_input[3].set_value(temperature)
                app.number_input[4].set_value(humidity)
                app.number_input[5].set_value(wind)
                app.run(timeout=20)
                self.assertFalse(app.exception)
                self.assertEqual(self._cards(app)[4], "数据不足")
                self.assertNotEqual(self._cards(app)[1], "数据不足")

    def test_custom_values_differ_from_preset_and_are_used(self) -> None:
        app = self._risk_app()
        self._selectbox(app, "快速情景").set_value("自定义").run(timeout=20)
        app.number_input[0].set_value(7.0)
        app.number_input[1].set_value(3.0)
        app.number_input[2].set_value(48.0)
        app.number_input[3].set_value(27.0)
        app.number_input[4].set_value(95.0)
        app.number_input[5].set_value(2.0)
        self._selectbox(app, "玉米生育期").set_value("V6")
        self._selectbox(app, "当前田面明水状态").set_value("no")
        self._selectbox(app, "目标病害").set_value("southern_rust")
        self._selectbox(app, "当前症状").set_value("none")
        self._selectbox(app, "周边病害压力或外部菌源").set_value("high")
        app.run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual(self._cards(app)[2], "明水7天 / 渍水3天")
        self.assertEqual(
            self._submitted_inputs(app)["情景来源"],
            "自定义情景",
        )

    def test_parameter_table_tracks_v6_and_r3_paths(self) -> None:
        app = self._risk_app()
        app.switch_page(str(PROJECT_DIR / "pages" / "5_evidence.py")).run(timeout=20)
        v6 = self._parameter_table(app)
        self.assertIn("P015", set(v6["parameter_id"]))
        self.assertFalse({"P019", "P020", "P021"} & set(v6["parameter_id"]))
        p013_roles = set(v6.loc[v6["parameter_id"] == "P013", "用途类别"])
        self.assertEqual(
            p013_roles,
            {"状态判断参数", "解释性证据"},
        )

        app.switch_page(str(PROJECT_DIR / "pages" / "2_risk.py")).run(timeout=20)
        self._selectbox(app, "玉米生育期").set_value("R3").run(timeout=20)
        app.switch_page(str(PROJECT_DIR / "pages" / "5_evidence.py")).run(timeout=20)
        r3 = self._parameter_table(app)
        self.assertIn("P018", set(r3["parameter_id"]))
        self.assertNotIn("P013", set(r3["parameter_id"]))

    def test_csv_upload_returns_batch_results(self) -> None:
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
                "temperature_c": "27",
                "humidity_pct": "95",
                "wind_speed_ms": "2",
            }
        )
        data = pd.DataFrame([row], columns=TEMPLATE_COLUMNS).to_csv(
            index=False
        ).encode("utf-8")
        app = self._field_data_app()
        app.file_uploader[0].upload("field.csv", data, "text/csv").run(timeout=20)
        self.assertFalse(app.exception)
        results = next(
            item.value
            for item in app.dataframe
            if "risk_label" in item.value.columns
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results.iloc[0]["field_id"], "F001")
        self.assertEqual(results.iloc[0]["regional_flood_status"], "not_available")

    def test_intervention_page_reuses_applied_risk_scenario(self) -> None:
        app = self._risk_app()
        app.number_input[0].set_value(7.0).run(timeout=20)
        app.switch_page(
            str(PROJECT_DIR / "pages" / "3_intervention.py")
        ).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(any("明水7天" in item.value for item in app.caption))
        self.assertTrue(
            any("APSIM 排水时限参考" in item.label for item in app.expander)
        )

        app.switch_page(str(PROJECT_DIR / "pages" / "2_risk.py")).run(timeout=20)
        self.assertEqual(app.number_input[0].value, 7.0)

    def test_csv_upload_persists_across_page_switch(self) -> None:
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
            }
        )
        data = pd.DataFrame([row], columns=TEMPLATE_COLUMNS).to_csv(
            index=False
        ).encode("utf-8")
        app = self._field_data_app()
        app.file_uploader[0].upload("field.csv", data, "text/csv").run(timeout=20)
        app.switch_page(str(PROJECT_DIR / "pages" / "2_risk.py")).run(timeout=20)
        app.switch_page(str(PROJECT_DIR / "pages" / "4_field_data.py")).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(any("当前会话上传" in item.value for item in app.subheader))
        self.assertTrue(any("field.csv" in item.value for item in app.markdown))
        self.assertTrue(any("v1" in item.value for item in app.markdown))

if __name__ == "__main__":
    unittest.main()
