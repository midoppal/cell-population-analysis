from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from cell_frequency import ensure_database_exists
from load_data import DB_PATH


ROOT_DIR = Path(__file__).resolve().parent
SAMPLES_PATH = ROOT_DIR / "baseline_miraclib_melanoma_pbmc_samples.csv"
SUMMARY_PATH = ROOT_DIR / "baseline_miraclib_melanoma_pbmc_summary.csv"


BASELINE_QUERY = """
SELECT
    projects.name AS project,
    subjects.subject_code AS subject,
    subjects.response,
    subjects.sex,
    samples.sample_code AS sample,
    samples.sample_type,
    samples.time_from_treatment_start
FROM samples
JOIN subjects
    ON subjects.id = samples.subject_id
JOIN projects
    ON projects.id = subjects.project_id
WHERE subjects.condition = 'melanoma'
    AND subjects.treatment = 'miraclib'
    AND samples.sample_type = 'PBMC'
    AND samples.time_from_treatment_start = 0
ORDER BY projects.name, subjects.subject_code, samples.sample_code;
"""


def fetch_baseline_samples(connection: sqlite3.Connection) -> list[dict[str, object]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(BASELINE_QUERY).fetchall()
    return [dict(row) for row in rows]


def count_samples_by_project(
    rows: list[dict[str, object]],
) -> list[tuple[str, str, int]]:
    counts: dict[str, int] = {}

    for row in rows:
        project = str(row["project"])
        counts[project] = counts.get(project, 0) + 1

    return [
        ("samples_by_project", project, counts[project])
        for project in sorted(counts)
    ]


def count_subjects_by_field(
    rows: list[dict[str, object]],
    field: str,
    category: str,
) -> list[tuple[str, str, int]]:
    subjects_by_value: dict[str, set[tuple[str, str]]] = {}

    for row in rows:
        value = str(row[field])
        subject_key = (str(row["project"]), str(row["subject"]))
        subjects_by_value.setdefault(value, set()).add(subject_key)

    return [
        (category, value, len(subjects_by_value[value]))
        for value in sorted(subjects_by_value)
    ]


def build_summary(rows: list[dict[str, object]]) -> list[tuple[str, str, int]]:
    return (
        [("total_baseline_samples", "all", len(rows))]
        + count_samples_by_project(rows)
        + count_subjects_by_field(rows, "response", "subjects_by_response")
        + count_subjects_by_field(rows, "sex", "subjects_by_sex")
    )


def write_samples(rows: list[dict[str, object]]) -> None:
    columns = (
        "project",
        "subject",
        "response",
        "sex",
        "sample",
        "sample_type",
        "time_from_treatment_start",
    )

    with SAMPLES_PATH.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(summary_rows: list[tuple[str, str, int]]) -> None:
    with SUMMARY_PATH.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("category", "value", "count"))
        writer.writerows(summary_rows)


def print_summary(summary_rows: list[tuple[str, str, int]]) -> None:
    print(f"Saved baseline samples: {SAMPLES_PATH}")
    print(f"Saved subset summary: {SUMMARY_PATH}")
    print()
    print("category,value,count")

    for category, value, count in summary_rows:
        print(f"{category},{value},{count}")


def main() -> None:
    ensure_database_exists()

    with sqlite3.connect(DB_PATH) as connection:
        rows = fetch_baseline_samples(connection)

    summary_rows = build_summary(rows)
    write_samples(rows)
    write_summary(summary_rows)
    print_summary(summary_rows)


if __name__ == "__main__":
    main()
