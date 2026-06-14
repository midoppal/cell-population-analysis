from __future__ import annotations

import csv
import os
import sqlite3
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "cell-population-analysis-matplotlib"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu

from cell_frequency import ensure_database_exists
from load_data import DB_PATH


PLOT_PATH = ROOT_DIR / "miraclib_response_boxplot.png"
STATS_PATH = ROOT_DIR / "miraclib_response_stats.csv"
ALPHA = 0.05


ANALYSIS_QUERY = """
WITH sample_totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample_id
)
SELECT
    samples.sample_code AS sample,
    subjects.response,
    cell_types.name AS population,
    cell_counts.count,
    sample_totals.total_count,
    cell_counts.count * 100.0 / sample_totals.total_count AS percentage
FROM cell_counts
JOIN sample_totals
    ON sample_totals.sample_id = cell_counts.sample_id
JOIN samples
    ON samples.id = cell_counts.sample_id
JOIN subjects
    ON subjects.id = samples.subject_id
JOIN cell_types
    ON cell_types.id = cell_counts.cell_type_id
WHERE subjects.condition = 'melanoma'
    AND subjects.treatment = 'miraclib'
    AND subjects.response IN ('yes', 'no')
    AND samples.sample_type = 'PBMC'
ORDER BY cell_types.id, subjects.response, samples.sample_code;
"""


def fetch_analysis_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(ANALYSIS_QUERY).fetchall()
    return [dict(row) for row in rows]


def median(values: list[float]) -> float:
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    count = len(p_values)
    ranked = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * count
    running_min = 1.0

    for rank, (index, p_value) in reversed(list(enumerate(ranked, start=1))):
        running_min = min(running_min, p_value * count / rank)
        adjusted[index] = min(running_min, 1.0)

    return adjusted


def group_percentages(
    rows: list[dict[str, object]],
) -> dict[str, dict[str, list[float]]]:
    grouped: dict[str, dict[str, list[float]]] = {}

    for row in rows:
        population = str(row["population"])
        response = str(row["response"])
        percentage = float(row["percentage"])
        grouped.setdefault(population, {"yes": [], "no": []})[response].append(percentage)

    return grouped


def compute_statistics(
    grouped: dict[str, dict[str, list[float]]],
) -> list[dict[str, object]]:
    stats_rows: list[dict[str, object]] = []
    p_values: list[float] = []

    for population, responses in grouped.items():
        responder_values = responses["yes"]
        non_responder_values = responses["no"]
        test = mannwhitneyu(
            responder_values,
            non_responder_values,
            alternative="two-sided",
        )
        p_value = float(test.pvalue)
        p_values.append(p_value)
        stats_rows.append(
            {
                "population": population,
                "responders_n": len(responder_values),
                "non_responders_n": len(non_responder_values),
                "responders_mean_pct": mean(responder_values),
                "non_responders_mean_pct": mean(non_responder_values),
                "responders_median_pct": median(responder_values),
                "non_responders_median_pct": median(non_responder_values),
                "median_difference_pct": median(responder_values)
                - median(non_responder_values),
                "mann_whitney_u": float(test.statistic),
                "p_value": p_value,
                "significant_unadjusted_0_05": p_value < ALPHA,
            }
        )

    adjusted_p_values = benjamini_hochberg(p_values)
    for row, adjusted_p_value in zip(stats_rows, adjusted_p_values):
        row["adjusted_p_value"] = adjusted_p_value
        row["significant_fdr_0_05"] = adjusted_p_value < ALPHA

    return stats_rows


def write_statistics(stats_rows: list[dict[str, object]]) -> None:
    columns = (
        "population",
        "responders_n",
        "non_responders_n",
        "responders_mean_pct",
        "non_responders_mean_pct",
        "responders_median_pct",
        "non_responders_median_pct",
        "median_difference_pct",
        "mann_whitney_u",
        "p_value",
        "significant_unadjusted_0_05",
        "adjusted_p_value",
        "significant_fdr_0_05",
    )

    with STATS_PATH.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        for row in stats_rows:
            writer.writerow(
                {
                    column: round(row[column], 6)
                    if isinstance(row[column], float)
                    else row[column]
                    for column in columns
                }
            )


def create_boxplot(grouped: dict[str, dict[str, list[float]]]) -> None:
    populations = list(grouped.keys())
    positions: list[float] = []
    values: list[list[float]] = []
    colors: list[str] = []

    for index, population in enumerate(populations, start=1):
        positions.extend([index - 0.18, index + 0.18])
        values.extend([grouped[population]["yes"], grouped[population]["no"]])
        colors.extend(["#4C78A8", "#F58518"])

    fig, ax = plt.subplots(figsize=(11, 6))
    boxplot = ax.boxplot(
        values,
        positions=positions,
        widths=0.28,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(boxplot["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_title("Melanoma PBMC Relative Frequencies by Miraclib Response")
    ax.set_ylabel("Relative frequency (%)")
    ax.set_xlabel("Immune cell population")
    ax.set_xticks(range(1, len(populations) + 1))
    ax.set_xticklabels(populations, rotation=25, ha="right")
    ax.legend(
        handles=[
            plt.Rectangle((0, 0), 1, 1, color="#4C78A8", alpha=0.75),
            plt.Rectangle((0, 0), 1, 1, color="#F58518", alpha=0.75),
        ],
        labels=["Responders", "Non-responders"],
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=150)
    plt.close(fig)


def print_summary(stats_rows: list[dict[str, object]]) -> None:
    print(f"Saved boxplot: {PLOT_PATH}")
    print(f"Saved statistics: {STATS_PATH}")
    print()
    print(
        "population,responders_median_pct,non_responders_median_pct,"
        "median_difference_pct,p_value,significant_unadjusted_0_05,"
        "adjusted_p_value,significant_fdr_0_05"
    )

    for row in stats_rows:
        print(
            f"{row['population']},"
            f"{row['responders_median_pct']:.3f},"
            f"{row['non_responders_median_pct']:.3f},"
            f"{row['median_difference_pct']:.3f},"
            f"{row['p_value']:.6g},"
            f"{row['significant_unadjusted_0_05']},"
            f"{row['adjusted_p_value']:.6g},"
            f"{row['significant_fdr_0_05']}"
        )

    unadjusted_significant = [
        str(row["population"])
        for row in stats_rows
        if row["significant_unadjusted_0_05"]
    ]
    fdr_significant = [
        str(row["population"])
        for row in stats_rows
        if row["significant_fdr_0_05"]
    ]

    print()
    print("conclusion_type,populations")
    print(
        "unadjusted_p_lt_0_05,"
        f"{';'.join(unadjusted_significant) if unadjusted_significant else 'none'}"
    )
    print(
        "fdr_adjusted_p_lt_0_05,"
        f"{';'.join(fdr_significant) if fdr_significant else 'none'}"
    )


def main() -> None:
    ensure_database_exists()

    with sqlite3.connect(DB_PATH) as connection:
        rows = fetch_analysis_rows(connection)

    grouped = group_percentages(rows)
    stats_rows = compute_statistics(grouped)
    write_statistics(stats_rows)
    create_boxplot(grouped)
    print_summary(stats_rows)


if __name__ == "__main__":
    main()
