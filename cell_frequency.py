from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

from load_data import CSV_PATH, DB_PATH, initialize_database, load_data


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_COLUMNS = ("sample", "total_count", "population", "count", "percentage")


FREQUENCY_QUERY = """
WITH sample_totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample_id
)
SELECT
    samples.sample_code AS sample,
    sample_totals.total_count,
    cell_types.name AS population,
    cell_counts.count,
    ROUND(cell_counts.count * 100.0 / sample_totals.total_count, 2) AS percentage
FROM cell_counts
JOIN sample_totals
    ON sample_totals.sample_id = cell_counts.sample_id
JOIN samples
    ON samples.id = cell_counts.sample_id
JOIN cell_types
    ON cell_types.id = cell_counts.cell_type_id
ORDER BY samples.sample_code, cell_types.id;
"""


def ensure_database_exists() -> None:
    if not DB_PATH.exists():
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"Missing source CSV: {CSV_PATH}")

        with sqlite3.connect(DB_PATH) as connection:
            initialize_database(connection)
            load_data(connection)


def write_frequency_table(connection: sqlite3.Connection) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(OUTPUT_COLUMNS)

    cursor = connection.execute(FREQUENCY_QUERY)
    for row in cursor:
        writer.writerow(row)


def main() -> None:
    ensure_database_exists()

    with sqlite3.connect(DB_PATH) as connection:
        write_frequency_table(connection)


if __name__ == "__main__":
    main()
