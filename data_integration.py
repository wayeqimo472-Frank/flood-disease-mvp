from __future__ import annotations

import io
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from storage import save_external_dataset


PROJECT_DIR = Path(__file__).resolve().parent
US_CSCAP_DIR = (
    PROJECT_DIR
    / "case_packs"
    / "us_corn_belt_cscap_2011_2015"
)
PUBLIC_EVIDENCE_V02_DIR = PROJECT_DIR / "data" / "public_evidence_v0.2"
ICASA_MAPPING_PATH = PROJECT_DIR / "data" / "icasa_field_mapping_v0.1.csv"
ICASA_SOURCE_URL = "https://github.com/DSSAT/ICASA-Dictionary"
ICASA_SOURCE_COMMIT = "2168f366b7c35ce6997c8fb0055dc259e9341ad3"
SAR_REQUIRED_COLUMNS = {
    "field_id",
    "event_id",
    "event_date",
    "flooded_area_pct",
}


@dataclass(frozen=True)
class ReferenceSource:
    dataset_id: str
    title: str
    path: Path
    category: str
    evidence_level: str
    license: str
    source_url: str
    description: str


US_FILES = {
    "site_metadata.csv": ("美国 CSCAP 站点元数据", "observed"),
    "corn_yield.csv": ("美国 CSCAP 玉米产量", "observed"),
    "disease_ratings.csv": ("美国 CSCAP 病害评级", "observed"),
    "disease_yield_matched.csv": ("美国 CSCAP 病害产量匹配", "observed"),
    "field_operations.csv": ("美国 CSCAP 田间作业", "observed"),
    "pesticides.csv": ("美国 CSCAP 农药记录", "observed"),
    "water_table_daily.csv": ("美国 CSCAP 逐日地下水位", "observed"),
    "tile_flow_daily.csv": ("美国 CSCAP 逐日排水流量", "observed"),
    "observations_v0.6.csv": ("美国 CSCAP 暴雨病害规范化观测", "observed"),
}

PUBLIC_V02_FILES = {
    "one_acre_overall_exposure_summary.csv": (
        "One Acre Fund 水分与病害暴露汇总",
        "CC BY 4.0",
        "derived",
    ),
    "one_acre_exposure_disease_summary.csv": (
        "One Acre Fund 暴露与病害交叉汇总",
        "CC BY 4.0",
        "derived",
    ),
    "one_acre_water_and_disease_fields.csv": (
        "One Acre Fund 水分与病害同报田块",
        "CC BY 4.0",
        "observed",
    ),
    "flood_tolerant_maize_2020_plots.csv": (
        "耐涝玉米洪水前后田块观测",
        "CC0",
        "remote_sensed",
    ),
    "divine_leaf_wetness_hourly.csv": (
        "DIVINE 逐小时叶面湿润",
        "CC BY 4.0",
        "observed",
    ),
    "divine_leaf_wetness_daily.csv": (
        "DIVINE 逐日叶面湿润",
        "CC BY 4.0",
        "derived",
    ),
    "italy_leaf_wetness_site_summary.csv": (
        "意大利叶面湿润站点汇总",
        "CC BY-NC 4.0",
        "derived",
    ),
    "lwd_rh90_proxy_validation.csv": (
        "RH90 代理叶面湿润验证",
        "CC BY-NC 4.0",
        "derived",
    ),
    "lwd_rh90_proxy_summary.csv": (
        "RH90 代理叶面湿润汇总",
        "CC BY-NC 4.0",
        "derived",
    ),
}

REMOTE_PUBLIC_FILES = {
    "public_evidence_catalog_v0.1.csv": (
        "公开案例目录",
        "mixed-open",
        "metadata",
    ),
    "public_flood_case_maize_v0.1.csv": (
        "真实淹水田与未淹对照 NDVI 时序",
        "CC0",
        "remote_sensed",
    ),
    "public_case_metrics_v0.1.csv": (
        "真实淹水案例关键指标",
        "CC0",
        "derived",
    ),
    "public_waterlogging_survival_maize_v0.1.csv": (
        "80 个玉米基因型 9 天涝渍存活试验",
        "CC BY 4.0",
        "observed",
    ),
    "public_disease_progress_maize_v0.1.csv": (
        "巴西玉米病害时间进展拟合参数",
        "CC BY 4.0",
        "derived",
    ),
}

PROJECT_REGISTERS = {
    "public_dataset_register_v0.2.csv": (
        "项目公开数据登记",
        "metadata",
    ),
    "public_data_gap_matrix_v0.2.csv": (
        "项目公开数据缺口矩阵",
        "metadata",
    ),
    "all_missing_data_v0.3.csv": (
        "项目逐字段缺失数据总表",
        "metadata",
    ),
}


def reference_sources() -> list[ReferenceSource]:
    sources: list[ReferenceSource] = []
    for filename, (title, evidence_level) in US_FILES.items():
        sources.append(
            ReferenceSource(
                dataset_id=f"us_cscap_{Path(filename).stem}",
                title=title,
                path=US_CSCAP_DIR / "processed" / filename,
                category="US CSCAP",
                evidence_level=evidence_level,
                license="CC0",
                source_url="https://doi.org/10.15482/USDA.ADC/1411953",
                description=(
                    "美国玉米带 Sustainable Corn CAP 2011-2015 "
                    "外部观测数据。"
                ),
            )
        )
    for filename, (title, license_name, evidence_level) in PUBLIC_V02_FILES.items():
        sources.append(
            ReferenceSource(
                dataset_id=f"public_evidence_v02_{Path(filename).stem}",
                title=title,
                path=PUBLIC_EVIDENCE_V02_DIR / filename,
                category="公开证据 v0.2",
                evidence_level=evidence_level,
                license=license_name,
                source_url=str(PROJECT_DIR / "data" / "public_dataset_register_v0.2.csv"),
                description="项目 v0.2 公开数据整理结果。",
            )
        )
    for filename, (title, license_name, evidence_level) in REMOTE_PUBLIC_FILES.items():
        sources.append(
            ReferenceSource(
                dataset_id=f"public_evidence_v01_{Path(filename).stem}",
                title=title,
                path=PROJECT_DIR / "data" / filename,
                category="公开证据 v0.1",
                evidence_level=evidence_level,
                license=license_name,
                source_url="https://github.com/wayeqimo472-Frank/flood-disease-mvp",
                description="分支调研加入的公开案例数据。",
            )
        )
    for filename, (title, evidence_level) in PROJECT_REGISTERS.items():
        sources.append(
            ReferenceSource(
                dataset_id=f"project_{Path(filename).stem}",
                title=title,
                path=PROJECT_DIR / "data" / filename,
                category="项目索引",
                evidence_level=evidence_level,
                license="project metadata",
                source_url="",
                description="项目自身的公开数据登记或缺口整理。",
            )
        )
    return sources


def discover_reference_sources() -> list[ReferenceSource]:
    return [
        source
        for source in reference_sources()
        if source.path.is_file()
    ]


def seed_reference_data(
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for source in discover_reference_sources():
        content = source.path.read_bytes()
        frame = pd.read_csv(source.path)
        records = json.loads(
            frame.to_json(orient="records", force_ascii=False, date_format="iso")
        )
        changed, row_count = save_external_dataset(
            dataset_id=source.dataset_id,
            title=source.title,
            category=source.category,
            source_path=str(source.path.relative_to(PROJECT_DIR)),
            source_sha256=sha256(content).hexdigest(),
            records=records,
            evidence_level=source.evidence_level,
            columns=[str(column) for column in frame.columns],
            source_url=source.source_url or None,
            license_name=source.license,
            metadata={
                "description": source.description,
                "case_id": (
                    "us_corn_belt_cscap_2011_2015"
                    if source.category == "US CSCAP"
                    else None
                ),
            },
            db_path=db_path,
        )
        results.append(
            {
                "dataset_id": source.dataset_id,
                "title": source.title,
                "rows": row_count,
                "changed": changed,
            }
        )
    return results


def load_icasa_mapping() -> pd.DataFrame:
    return pd.read_csv(ICASA_MAPPING_PATH)


def _validate_position(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError(f"{label} 坐标格式无效")
    longitude, latitude = value[0], value[1]
    if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
        raise ValueError(f"{label} 经纬度必须是数字")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError(f"{label} 经纬度超出范围")


def parse_geojson_geometries(
    content: bytes,
    *,
    case_id: str,
    source: str,
) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"GeoJSON 无法读取：{error}") from error
    if payload.get("type") != "FeatureCollection":
        raise ValueError("仅支持 GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("GeoJSON 没有可用要素")

    evidence_level = "observed" if source == "field_survey" else "remote_sensed"
    quality = "field_survey" if source == "field_survey" else "model_prediction"
    geometries: list[dict[str, Any]] = []
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise ValueError(f"要素 {index} 不是对象")
        geometry = feature.get("geometry")
        properties = feature.get("properties") or {}
        if not isinstance(geometry, dict):
            raise ValueError(f"要素 {index} 缺少 geometry")
        geometry_type = geometry.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"要素 {index} 仅支持 Polygon 或 MultiPolygon")
        field_id = str(
            properties.get("field_id")
            or properties.get("plot_id")
            or ""
        ).strip()
        if not field_id:
            raise ValueError(f"要素 {index} 缺少 properties.field_id 或 plot_id")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError(f"要素 {index} 缺少 coordinates")
        polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError(f"要素 {index} 多边形为空")
            outer_ring = polygon[0]
            if not isinstance(outer_ring, list) or len(outer_ring) < 3:
                raise ValueError(f"要素 {index} 外环至少需要 3 个坐标点")
            for position_index, position in enumerate(outer_ring, start=1):
                _validate_position(
                    position,
                    f"要素 {index} 外环第 {position_index} 点",
                )
        geometries.append(
            {
                "field_id": field_id,
                "case_id": case_id,
                "source": source,
                "evidence_level": evidence_level,
                "quality": quality,
                "geometry": geometry,
            }
        )
    return geometries


def parse_sar_metrics_csv(
    content: bytes,
    *,
    case_id: str,
    source: str = "sentinel1_sar_worker",
) -> list[dict[str, Any]]:
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype=str).fillna("")
    except (pd.errors.ParserError, UnicodeDecodeError) as error:
        raise ValueError(f"SAR 指标 CSV 无法读取：{error}") from error
    missing = sorted(SAR_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"SAR 指标 CSV 缺少字段：{', '.join(missing)}")
    if frame.empty:
        raise ValueError("SAR 指标 CSV 没有数据行")

    records: list[dict[str, Any]] = []
    for row_number, row in frame.iterrows():
        row_id = row_number + 2
        field_id = str(row["field_id"]).strip()
        event_id = str(row["event_id"]).strip()
        if not field_id or not event_id:
            raise ValueError(f"第 {row_id} 行 field_id 或 event_id 为空")
        try:
            flooded_area_pct = float(row["flooded_area_pct"])
        except ValueError as error:
            raise ValueError(f"第 {row_id} 行 flooded_area_pct 不是数字") from error
        if not 0 <= flooded_area_pct <= 100:
            raise ValueError(f"第 {row_id} 行 flooded_area_pct 必须在 0–100")
        max_depth = str(row.get("max_water_depth_m", "")).strip()
        try:
            max_depth_value = float(max_depth) if max_depth else None
        except ValueError as error:
            raise ValueError(f"第 {row_id} 行 max_water_depth_m 不是数字") from error
        if max_depth_value is not None and max_depth_value < 0:
            raise ValueError(f"第 {row_id} 行 max_water_depth_m 不能为负")
        record = {
            key: str(value).strip() or None
            for key, value in row.to_dict().items()
        }
        record.update(
            {
                "field_id": field_id,
                "case_id": case_id,
                "event_id": event_id,
                "event_date": record.get("event_date"),
                "flooded_area_pct": flooded_area_pct,
                "max_water_depth_m": max_depth_value,
                "source": source,
                "evidence_level": "remote_sensed",
            }
        )
        records.append(record)
    return records


def sar_metrics_template() -> bytes:
    frame = pd.DataFrame(
        columns=[
            "field_id",
            "event_id",
            "event_date",
            "flood_start_date",
            "flood_end_date",
            "recession_date",
            "flooded_area_pct",
            "max_water_depth_m",
            "source_scene_ids",
            "method_version",
        ]
    )
    return frame.to_csv(index=False).encode("utf-8")


def geometry_template() -> bytes:
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "field_id_source": "properties.field_id",
            "accepted_geometry_types": ["Polygon", "MultiPolygon"],
        },
        "features": [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
