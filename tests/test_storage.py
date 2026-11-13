import sys
import shutil
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from risk_engine import FieldScenario, assess  # noqa: E402
from storage import (  # noqa: E402
    create_backup,
    initialize_database,
    list_assessment_runs,
    list_import_batches,
    load_batch_results,
    load_raw_batch,
    save_assessment_run,
    save_import_batch,
)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = PROJECT_DIR / "tmp" / f"storage-test-{self._testMethodName}.db"
        self.backup_dir = (
            PROJECT_DIR / "tmp" / f"storage-test-backups-{self._testMethodName}"
        )
        self.db_path.parent.mkdir(exist_ok=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)
        initialize_database(self.db_path)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def test_import_batch_round_trip_and_deduplication(self) -> None:
        content = b"field_id,value\nF001,5\n"
        results = pd.DataFrame(
            [
                {
                    "record_id": "R001",
                    "field_id": "F001",
                    "observation_date": "2026-08-20",
                    "case_id": "henan_maize_2026",
                    "region_code": "CN-HA",
                    "crop_code": "maize",
                    "risk_label": "中",
                }
            ]
        )
        errors = pd.DataFrame(columns=["行号", "字段", "错误"])

        first = save_import_batch(
            "field.csv",
            content,
            results,
            errors,
            db_path=self.db_path,
        )
        second = save_import_batch(
            "field.csv",
            content,
            results,
            errors,
            db_path=self.db_path,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(list_import_batches(db_path=self.db_path)), 1)
        persisted = load_batch_results(first, db_path=self.db_path)
        self.assertEqual(persisted.iloc[0]["field_id"], "F001")
        name, raw = load_raw_batch(first, db_path=self.db_path)
        self.assertEqual(name, "field.csv")
        self.assertEqual(raw, content)

    def test_assessment_runs_are_deduplicated(self) -> None:
        scenario = FieldScenario(
            crop_stage="V6",
            flood_days=5,
            waterlog_days=3,
            drainage_delay_hours=48,
            standing_water=False,
            temperature_c=27,
            humidity_pct=95,
            wind_speed_ms=2,
        )
        result = assess(scenario)
        inputs = scenario.__dict__

        first = save_assessment_run(
            result.case_id,
            result.case_version,
            inputs,
            result,
            db_path=self.db_path,
        )
        second = save_assessment_run(
            result.case_id,
            result.case_version,
            inputs,
            result,
            db_path=self.db_path,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(list_assessment_runs(db_path=self.db_path)), 1)

    def test_database_backup_is_a_readable_copy(self) -> None:
        content = b"field_id\nF001\n"
        results = pd.DataFrame(
            [
                {
                    "record_id": "R001",
                    "field_id": "F001",
                    "case_id": "henan_maize_2026",
                    "region_code": "CN-HA",
                    "crop_code": "maize",
                    "risk_label": "中",
                }
            ]
        )
        save_import_batch(
            "field.csv",
            content,
            results,
            pd.DataFrame(columns=["行号", "字段", "错误"]),
            db_path=self.db_path,
        )
        backup = create_backup(
            self.db_path,
            backup_dir=self.backup_dir,
        )
        self.assertTrue(backup.is_file())
        self.assertEqual(len(list_import_batches(db_path=backup)), 1)


if __name__ == "__main__":
    unittest.main()
