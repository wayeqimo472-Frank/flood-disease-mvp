import json
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from data_integration import (  # noqa: E402
    load_icasa_mapping,
    parse_geojson_geometries,
    parse_sar_metrics_csv,
)
from storage import (  # noqa: E402
    initialize_database,
    list_external_datasets,
    list_plot_flood_metrics,
    list_plot_geometries,
    load_external_records,
    save_external_dataset,
    save_plot_flood_metrics,
    save_plot_geometries,
)


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = PROJECT_DIR / "tmp" / f"integration-{self._testMethodName}.db"
        self.db_path.parent.mkdir(exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)
        initialize_database(self.db_path)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)

    def test_icasa_mapping_contains_exact_and_unsupported_fields(self) -> None:
        mapping = load_icasa_mapping()
        self.assertGreaterEqual(len(mapping), 20)
        self.assertIn("exact", set(mapping["mapping_strength"]))
        self.assertIn("no_standard", set(mapping["mapping_strength"]))
        yield_row = mapping.loc[mapping["local_field"] == "yield_kg_ha"].iloc[0]
        self.assertEqual(yield_row["icasa_code_display"], "HWAM")
        self.assertEqual(yield_row["icasa_unit"], "kg/ha")

    def test_geojson_parser_preserves_evidence_boundary(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"field_id": "F001"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [113.0, 34.0],
                                [113.1, 34.0],
                                [113.1, 34.1],
                                [113.0, 34.0],
                            ]
                        ],
                    },
                }
            ],
        }
        geometries = parse_geojson_geometries(
            json.dumps(payload).encode("utf-8"),
            case_id="henan_maize_2026",
            source="ftw_prediction",
        )
        self.assertEqual(geometries[0]["field_id"], "F001")
        self.assertEqual(geometries[0]["evidence_level"], "remote_sensed")
        self.assertEqual(geometries[0]["quality"], "model_prediction")

        payload["features"][0]["properties"] = {}
        with self.assertRaises(ValueError):
            parse_geojson_geometries(
                json.dumps(payload).encode("utf-8"),
                case_id="henan_maize_2026",
                source="ftw_prediction",
            )

    def test_sar_parser_rejects_out_of_range_coverage(self) -> None:
        valid = (
            "field_id,event_id,event_date,flooded_area_pct,max_water_depth_m\n"
            "F001,E2026,2026-07-20,65,0.4\n"
        ).encode("utf-8")
        records = parse_sar_metrics_csv(
            valid,
            case_id="henan_maize_2026",
        )
        self.assertEqual(records[0]["evidence_level"], "remote_sensed")
        self.assertEqual(records[0]["flooded_area_pct"], 65.0)

        invalid = valid.replace(b",65,", b",165,")
        with self.assertRaises(ValueError):
            parse_sar_metrics_csv(
                invalid,
                case_id="henan_maize_2026",
            )

    def test_external_records_are_deduplicated_and_queryable(self) -> None:
        records = [{"field_id": "F001", "yield_kg_ha": 10000}]
        arguments = dict(
            dataset_id="test_dataset",
            title="测试数据",
            category="测试",
            source_path="tmp/test.csv",
            source_sha256="abc123",
            records=records,
            evidence_level="observed",
            columns=["field_id", "yield_kg_ha"],
            db_path=self.db_path,
        )
        changed, rows = save_external_dataset(**arguments)
        second_changed, second_rows = save_external_dataset(**arguments)
        self.assertTrue(changed)
        self.assertFalse(second_changed)
        self.assertEqual(rows, second_rows)
        self.assertEqual(len(list_external_datasets(self.db_path)), 1)
        loaded = load_external_records("test_dataset", db_path=self.db_path)
        self.assertEqual(loaded.iloc[0]["field_id"], "F001")

    def test_geometry_and_flood_metric_round_trip(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [113.0, 34.0],
                    [113.1, 34.0],
                    [113.1, 34.1],
                    [113.0, 34.0],
                ]
            ],
        }
        inserted = save_plot_geometries(
            [
                {
                    "field_id": "F001",
                    "case_id": "henan_maize_2026",
                    "source": "ftw_prediction",
                    "evidence_level": "remote_sensed",
                    "quality": "model_prediction",
                    "geometry": geometry,
                }
            ],
            db_path=self.db_path,
        )
        repeated = save_plot_geometries(
            [
                {
                    "field_id": "F001",
                    "case_id": "henan_maize_2026",
                    "source": "ftw_prediction",
                    "evidence_level": "remote_sensed",
                    "quality": "model_prediction",
                    "geometry": geometry,
                }
            ],
            db_path=self.db_path,
        )
        self.assertEqual(inserted, 1)
        self.assertEqual(repeated, 0)
        self.assertEqual(len(list_plot_geometries(db_path=self.db_path)), 1)

        metric = {
            "field_id": "F001",
            "case_id": "henan_maize_2026",
            "event_id": "E2026",
            "event_date": "2026-07-20",
            "flooded_area_pct": 65.0,
            "max_water_depth_m": 0.4,
            "source": "sentinel1_sar_worker",
            "evidence_level": "remote_sensed",
        }
        self.assertEqual(
            save_plot_flood_metrics([metric], db_path=self.db_path),
            1,
        )
        self.assertEqual(
            save_plot_flood_metrics([metric], db_path=self.db_path),
            0,
        )
        self.assertEqual(len(list_plot_flood_metrics(db_path=self.db_path)), 1)


if __name__ == "__main__":
    unittest.main()
