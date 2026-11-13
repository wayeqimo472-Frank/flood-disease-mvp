from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from data_integration import seed_reference_data  # noqa: E402
from storage import initialize_database, list_external_datasets  # noqa: E402


def main() -> None:
    initialize_database()
    results = seed_reference_data()
    datasets = list_external_datasets()
    total_rows = sum(int(item["row_count"]) for item in datasets)
    print(f"Imported or verified {len(results)} files.")
    print(f"Database now contains {len(datasets)} datasets and {total_rows} rows.")


if __name__ == "__main__":
    main()
