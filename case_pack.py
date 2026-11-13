from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
CASE_PACKS_DIR = PROJECT_DIR / "case_packs"
DEFAULT_CASE_ID = os.environ.get("FLOOD_APP_CASE_ID", "henan_maize_2026")


@dataclass(frozen=True)
class CasePack:
    case_id: str
    path: Path
    config: dict[str, Any]

    @property
    def name(self) -> str:
        return self.config["name"]

    @property
    def version(self) -> str:
        return self.config["version"]

    @property
    def country_code(self) -> str:
        return self.config["country_code"]

    @property
    def region_code(self) -> str:
        return self.config["region_code"]

    @property
    def crop_code(self) -> str:
        return self.config["crop_code"]

    @property
    def crop_name(self) -> str:
        return self.config["crop_name"]

    def data_file(self, key: str) -> Path:
        return self.path / self.config["parameter_files"][key]


def _read_case_config(path: Path) -> CasePack:
    config_path = path / "case.json"
    with config_path.open(encoding="utf-8") as file:
        config = json.load(file)
    required = {
        "case_id",
        "name",
        "version",
        "country_code",
        "region_code",
        "region_name",
        "crop_code",
        "crop_name",
        "stages",
        "diseases",
        "cultivars",
        "custom_scenario",
        "scenario_presets",
        "parameter_files",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"{config_path} 缺少字段：{', '.join(missing)}")
    if config["case_id"] != path.name:
        raise ValueError(f"{config_path} 的 case_id 必须与目录名一致")
    return CasePack(case_id=config["case_id"], path=path, config=config)


@lru_cache(maxsize=1)
def available_case_ids() -> tuple[str, ...]:
    if not CASE_PACKS_DIR.exists():
        return ()
    return tuple(
        sorted(
            path.name
            for path in CASE_PACKS_DIR.iterdir()
            if path.is_dir() and (path / "case.json").is_file()
        )
    )


@lru_cache(maxsize=None)
def get_case_pack(case_id: str = DEFAULT_CASE_ID) -> CasePack:
    path = CASE_PACKS_DIR / case_id
    if not (path / "case.json").is_file():
        raise ValueError(f"未知案例包：{case_id}")
    return _read_case_config(path)


def load_case_pack_from_dir(path: Path) -> CasePack:
    return _read_case_config(path.resolve())
