from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
CSV_PATH = ROOT_DIR / "cell-count.csv"
DB_PATH = ROOT_DIR / "cell_counts.db"

CELL_COUNT_COLUMNS = (
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
)


SCHEMA = """
DROP TABLE IF EXISTS cell_counts;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS cell_types;
DROP TABLE IF EXISTS projects;

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    subject_code TEXT NOT NULL,
    condition TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0),
    sex TEXT NOT NULL,
    treatment TEXT NOT NULL,
    response TEXT,
    UNIQUE (project_id, subject_code),
    FOREIGN KEY (project_id) REFERENCES projects (id)
);

CREATE TABLE samples (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER NOT NULL,
    sample_code TEXT NOT NULL UNIQUE,
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects (id)
);

CREATE TABLE cell_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE cell_counts (
    sample_id INTEGER NOT NULL,
    cell_type_id INTEGER NOT NULL,
    count INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample_id, cell_type_id),
    FOREIGN KEY (sample_id) REFERENCES samples (id),
    FOREIGN KEY (cell_type_id) REFERENCES cell_types (id)
);
"""


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)


def insert_project(
    cursor: sqlite3.Cursor,
    cache: dict[str, int],
    project_name: str,
) -> int:
    if project_name not in cache:
        cursor.execute(
            "INSERT INTO projects (name) VALUES (?) "
            "ON CONFLICT(name) DO NOTHING",
            (project_name,),
        )
        cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
        cache[project_name] = int(cursor.fetchone()[0])
    return cache[project_name]


def insert_subject(
    cursor: sqlite3.Cursor,
    cache: dict[tuple[int, str], int],
    row: dict[str, str],
    project_id: int,
) -> int:
    key = (project_id, row["subject"])
    if key not in cache:
        cursor.execute(
            """
            INSERT INTO subjects (
                project_id, subject_code, condition, age, sex, treatment, response
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, subject_code) DO NOTHING
            """,
            (
                project_id,
                row["subject"],
                row["condition"],
                int(row["age"]),
                row["sex"],
                row["treatment"],
                row["response"] or None,
            ),
        )
        cursor.execute(
            """
            SELECT id
            FROM subjects
            WHERE project_id = ? AND subject_code = ?
            """,
            key,
        )
        cache[key] = int(cursor.fetchone()[0])
    return cache[key]


def load_data(connection: sqlite3.Connection) -> tuple[int, int]:
    project_ids: dict[str, int] = {}
    subject_ids: dict[tuple[int, str], int] = {}
    cell_type_ids: dict[str, int] = {}
    sample_count = 0
    cell_count_records = 0

    cursor = connection.cursor()

    for cell_type in CELL_COUNT_COLUMNS:
        cursor.execute("INSERT INTO cell_types (name) VALUES (?)", (cell_type,))
        cell_type_ids[cell_type] = int(cursor.lastrowid)

    with CSV_PATH.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            project_id = insert_project(cursor, project_ids, row["project"])
            subject_id = insert_subject(cursor, subject_ids, row, project_id)

            cursor.execute(
                """
                INSERT INTO samples (
                    subject_id, sample_code, sample_type, time_from_treatment_start
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    subject_id,
                    row["sample"],
                    row["sample_type"],
                    int(row["time_from_treatment_start"]),
                ),
            )
            sample_id = int(cursor.lastrowid)
            sample_count += 1

            cursor.executemany(
                """
                INSERT INTO cell_counts (sample_id, cell_type_id, count)
                VALUES (?, ?, ?)
                """,
                (
                    (sample_id, cell_type_ids[cell_type], int(row[cell_type]))
                    for cell_type in CELL_COUNT_COLUMNS
                ),
            )
            cell_count_records += len(CELL_COUNT_COLUMNS)

    return sample_count, cell_count_records


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing source CSV: {CSV_PATH}")

    with sqlite3.connect(DB_PATH) as connection:
        initialize_database(connection)
        sample_count, cell_count_records = load_data(connection)

    print(f"Created {DB_PATH}")
    print(f"Loaded {sample_count} samples")
    print(f"Loaded {cell_count_records} cell count records")


if __name__ == "__main__":
    main()
