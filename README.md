# Cell Population Analysis

This repository loads immune cell count data into SQLite, computes per-sample cell population frequencies, compares miraclib responder and non-responder PBMC samples for melanoma patients, summarizes the requested baseline subset, and serves an interactive local dashboard.

## Run In Codespaces

```bash
make setup
make pipeline
make dashboard
```

The dashboard target starts a local web server and prints the URL. The default local link is [http://localhost:8000/dashboard.html](http://localhost:8000/dashboard.html). In GitHub Codespaces, open the forwarded port shown for the dashboard server.

If your shell does not provide `python3`, override the interpreter:

```bash
make PYTHON=python pipeline
make PYTHON=python dashboard
```

## Generated Outputs

`make pipeline` runs the full workflow without manual intervention and regenerates:

- `cell_counts.db`
- `cell_frequencies.csv`
- `miraclib_response_stats.csv`
- `miraclib_response_boxplot.png`
- `baseline_miraclib_melanoma_pbmc_samples.csv`
- `baseline_miraclib_melanoma_pbmc_summary.csv`
- `dashboard.html`

You can also run individual scripts:

```bash
python load_data.py
python cell_frequency.py
python statistical_analysis.py
python subset_analysis.py
```

Use `python3` instead of `python` if needed.

## Database Schema

The SQLite database is normalized into five tables:

- `projects`: one row per project.
- `subjects`: patient-level metadata, including project, subject id, condition, age, sex, treatment, and response.
- `samples`: sample-level metadata, including sample id, sample type, and time from treatment start.
- `cell_types`: the immune cell population names.
- `cell_counts`: one count per sample and cell type.

This design avoids repeating project and subject metadata for every cell population. It also lets analytics join the exact level they need: project-level summaries, subject response comparisons, sample time-point filters, and cell-type frequency calculations. If the dataset grew to hundreds of projects, thousands of samples, or more immune cell panels, new projects, subjects, samples, and cell types can be inserted without changing the schema. Additional analytics can index or aggregate the normalized tables rather than parsing wide CSV rows repeatedly.

## Code Structure

- `load_data.py` initializes `cell_counts.db` and loads `cell-count.csv`.
- `cell_frequency.py` prints the Part 2 frequency table with `sample`, `total_count`, `population`, `count`, and `percentage`.
- `statistical_analysis.py` filters melanoma PBMC samples treated with miraclib, compares responders and non-responders using Mann-Whitney U tests, reports both unadjusted and Benjamini-Hochberg FDR-adjusted significance, writes the statistics CSV, and creates the boxplot.
- `subset_analysis.py` filters baseline melanoma PBMC samples treated with miraclib and writes the sample-level and summary CSV outputs.
- `dashboard.py` rebuilds outputs when needed, generates `dashboard.html`, and serves it locally.
- `Makefile` provides the required `setup`, `pipeline`, and `dashboard` targets.

## Current Analysis Summary

The response comparison uses PBMC samples from melanoma patients treated with miraclib. In the generated `miraclib_response_stats.csv`, `cd4_t_cell` is significant using the unadjusted Mann-Whitney U p-value at 0.05. After Benjamini-Hochberg FDR correction across the five tested immune cell populations, no population remains significant at 0.05.

The baseline subset contains 656 melanoma PBMC baseline samples treated with miraclib. The generated summary reports 384 samples from `prj1` and 272 from `prj3`; 331 responder subjects and 325 non-responder subjects; 312 female subjects and 344 male subjects.
