from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB_PATH = Path(
    os.environ.get("FLOOD_APP_DB_PATH", DATA_DIR / "app.db")
).resolve()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS import_batches (
            batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256 TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            imported_at TEXT NOT NULL,
            case_ids TEXT NOT NULL,
            valid_rows INTEGER NOT NULL,
            invalid_rows INTEGER NOT NULL,
            errors_json TEXT NOT NULL,
            raw_content BLOB NOT NULL
        );

        CREATE TABLE IF NOT EXISTS field_observations (
            observation_key INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES import_batches(batch_id),
            record_id TEXT,
            field_id TEXT NOT NULL,
            observation_date TEXT,
            case_id TEXT NOT NULL,
            region_code TEXT,
            crop_code TEXT,
            payload_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_observations_field_date
        ON field_observations(field_id, observation_date);

        CREATE TABLE IF NOT EXISTS assessment_runs (
            run_hash TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            case_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        );
        """
    )
    return connection


@contextmanager
def _database(db_path: Path | str | None = None):
    connection = _connect(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: Path | str | None = None) -> Path:
    path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    with _database(path):
        pass
    return path


def save_assessment_run(
    case_id: str,
    case_version: str,
    inputs: dict[str, Any],
    result: Any,
    db_path: Path | str | None = None,
) -> str:
    inputs_json = _json(inputs)
    result_json = _json(asdict(result))
    run_hash = sha256(
        _json(
            {
                "case_id": case_id,
                "case_version": case_version,
                "inputs": inputs,
                "result": asdict(result),
            }
        ).encode("utf-8")
    ).hexdigest()
    with _database(db_path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO assessment_runs
            (run_hash, case_id, case_version, created_at, inputs_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_hash,
                case_id,
                case_version,
                _now(),
                inputs_json,
                result_json,
            ),
        )
    return run_hash


def save_import_batch(
    file_name: str,
    content: bytes,
    results: pd.DataFrame,
    errors: pd.DataFrame,
    db_path: Path | str | None = None,
) -> int:
    digest = sha256(content).hexdigest()
    case_ids = sorted(
        {
            str(value)
            for value in results.get("case_id", pd.Series(dtype=str)).fillna("")
            if str(value).strip()
        }
    )
    with _database(db_path) as connection:
        existing = connection.execute(
            "SELECT batch_id FROM import_batches WHERE sha256 = ?",
            (digest,),
        ).fetchone()
        if existing:
            return int(existing["batch_id"])

        cursor = connection.execute(
            """
            INSERT INTO import_batches
            (sha256, file_name, size_bytes, imported_at, case_ids, valid_rows,
             invalid_rows, errors_json, raw_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                digest,
                file_name,
                len(content),
                _now(),
                ",".join(case_ids),
                len(results),
                len(errors),
                _json(errors.to_dict(orient="records")),
                sqlite3.Binary(content),
            ),
        )
        batch_id = int(cursor.lastrowid)
        rows = []
        for record in results.to_dict(orient="records"):
            case_id = str(record.get("case_id") or "").strip()
            if not case_id:
                raise ValueError("数据库记录缺少 case_id")
            rows.append(
                (
                    batch_id,
                    str(record.get("record_id") or "") or None,
                    str(record.get("field_id") or ""),
                    str(record.get("observation_date") or "") or None,
                    case_id,
                    str(record.get("region_code") or "") or None,
                    str(record.get("crop_code") or "") or None,
                    _json(record),
                    _json(record),
                )
            )
        connection.executemany(
            """
            INSERT INTO field_observations
            (batch_id, record_id, field_id, observation_date, case_id,
             region_code, crop_code, payload_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return batch_id


def list_import_batches(
    limit: int = 10,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    with _database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT batch_id, sha256, file_name, size_bytes, imported_at,
                   case_ids, valid_rows, invalid_rows
            FROM import_batches
            ORDER BY batch_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_batch_results(
    batch_id: int,
    db_path: Path | str | None = None,
) -> pd.DataFrame:
    with _database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT result_json
            FROM field_observations
            WHERE batch_id = ?
            ORDER BY observation_key
            """,
            (batch_id,),
        ).fetchall()
    return pd.DataFrame([json.loads(row["result_json"]) for row in rows])


def load_raw_batch(
    batch_id: int,
    db_path: Path | str | None = None,
) -> tuple[str, bytes]:
    with _database(db_path) as connection:
        row = connection.execute(
            "SELECT file_name, raw_content FROM import_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"导入批次不存在：{batch_id}")
    return str(row["file_name"]), bytes(row["raw_content"])


def list_assessment_runs(
    limit: int = 10,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    with _database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT run_hash, case_id, case_version, created_at
            FROM assessment_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_backup(
    db_path: Path | str | None = None,
    backup_dir: Path | str | None = None,
) -> Path:
    source_path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    if not source_path.is_file():
        raise ValueError(f"数据库不存在：{source_path}")
    destination_dir = (
        Path(backup_dir).resolve()
        if backup_dir
        else source_path.parent / "backups"
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (
        f"{source_path.stem}-{datetime.now().astimezone():%Y%m%d-%H%M%S}.db"
    )
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()
    return destination
