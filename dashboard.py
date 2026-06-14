from __future__ import annotations

import argparse
import csv
import errno
import json
import os
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
FREQUENCIES_PATH = ROOT_DIR / "cell_frequencies.csv"
STATS_PATH = ROOT_DIR / "miraclib_response_stats.csv"
BASELINE_SAMPLES_PATH = ROOT_DIR / "baseline_miraclib_melanoma_pbmc_samples.csv"
BASELINE_SUMMARY_PATH = ROOT_DIR / "baseline_miraclib_melanoma_pbmc_summary.csv"
DASHBOARD_PATH = ROOT_DIR / "dashboard.html"
PLOT_PATH = ROOT_DIR / "miraclib_response_boxplot.png"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cell Population Analysis Dashboard</title>
<style>
:root {
    color-scheme: light;
    --bg: #f6f7f3;
    --panel: #ffffff;
    --ink: #17211b;
    --muted: #5d6a61;
    --line: #d9dfd8;
    --accent: #24735b;
    --accent-strong: #155842;
    --accent-soft: #e5f1ec;
    --warn: #ad5a25;
    --warn-soft: #f7e7da;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.5;
}

header {
    border-bottom: 1px solid var(--line);
    background: #fbfcf8;
}

.wrap {
    width: min(1180px, calc(100% - 32px));
    margin: 0 auto;
}

.topbar {
    padding: 28px 0 22px;
}

h1 {
    margin: 0 0 8px;
    font-size: 30px;
    line-height: 1.15;
}

h2 {
    margin: 0;
    font-size: 21px;
}

h3 {
    margin: 0 0 10px;
    font-size: 16px;
}

p {
    margin: 0;
}

.muted {
    color: var(--muted);
}

.metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    padding: 22px 0;
}

.metric {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
}

.metric span {
    display: block;
    color: var(--muted);
    font-size: 13px;
}

.metric strong {
    display: block;
    margin-top: 4px;
    font-size: 27px;
    line-height: 1.1;
}

main {
    padding: 0 0 36px;
}

.panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    margin: 0 0 18px;
    padding: 20px;
}

.section-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
}

.controls {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
}

label {
    display: grid;
    gap: 5px;
    color: var(--muted);
    font-size: 12px;
}

input,
select,
button {
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #fff;
    color: var(--ink);
    font: inherit;
    min-height: 38px;
}

input,
select {
    min-width: 180px;
    padding: 7px 10px;
}

button {
    align-self: end;
    padding: 7px 12px;
    cursor: pointer;
}

button:hover {
    border-color: var(--accent);
}

.grid-two {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
    gap: 18px;
    align-items: start;
}

.plot {
    width: 100%;
    max-height: 520px;
    object-fit: contain;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fff;
}

.sample-bars {
    display: grid;
    gap: 9px;
}

.bar-row {
    display: grid;
    grid-template-columns: 95px 1fr 58px;
    gap: 10px;
    align-items: center;
    font-size: 13px;
}

.bar-track {
    height: 12px;
    border-radius: 999px;
    background: #edf0eb;
    overflow: hidden;
}

.bar-fill {
    height: 100%;
    border-radius: inherit;
    background: var(--accent);
}

.table-wrap {
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 8px;
}

table {
    width: 100%;
    border-collapse: collapse;
    min-width: 640px;
    background: #fff;
}

th,
td {
    padding: 9px 10px;
    border-bottom: 1px solid var(--line);
    text-align: left;
    white-space: nowrap;
    font-size: 13px;
}

th {
    background: #f2f5ef;
    color: #354039;
    font-weight: 700;
}

tbody tr:last-child td {
    border-bottom: 0;
}

.badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 12px;
    font-weight: 700;
}

.badge.yes {
    background: var(--accent-soft);
    color: var(--accent-strong);
}

.badge.no {
    background: var(--warn-soft);
    color: var(--warn);
}

.links {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 16px;
}

a {
    color: var(--accent-strong);
}

@media (max-width: 860px) {
    .metrics,
    .grid-two {
        grid-template-columns: 1fr;
    }

    .section-head {
        display: grid;
    }

    input,
    select {
        min-width: min(100%, 240px);
    }
}
</style>
</head>
<body>
<header>
    <div class="wrap topbar">
        <h1>Cell Population Analysis Dashboard</h1>
        <p class="muted">Miraclib melanoma PBMC response analysis, per-sample cell frequencies, and baseline subset summaries.</p>
    </div>
</header>
<div class="wrap">
    <section class="metrics" aria-label="Analysis metrics">
        <div class="metric"><span>Samples loaded</span><strong id="metricSamples"></strong></div>
        <div class="metric"><span>Frequency rows</span><strong id="metricFrequencies"></strong></div>
        <div class="metric"><span>Baseline subset samples</span><strong id="metricBaseline"></strong></div>
        <div class="metric"><span>FDR significant populations</span><strong id="metricSignificant"></strong></div>
    </section>
</div>
<main class="wrap">
    <section class="panel">
        <div class="section-head">
            <div>
                <h2>Per-Sample Cell Frequencies</h2>
                <p class="muted">Filter by sample id or population. The profile chart uses the first matching sample.</p>
            </div>
            <p class="muted" id="frequencyCount"></p>
        </div>
        <div class="grid-two">
            <div>
                <div class="controls">
                    <label>Sample search<input id="sampleFilter" type="search" placeholder="sample00000"></label>
                    <label>Population<select id="populationFilter"></select></label>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>Sample</th><th>Total count</th><th>Population</th><th>Count</th><th>Percentage</th></tr></thead>
                        <tbody id="frequencyBody"></tbody>
                    </table>
                </div>
            </div>
            <aside>
                <h3 id="sampleProfileTitle"></h3>
                <div class="sample-bars" id="sampleProfile"></div>
            </aside>
        </div>
    </section>
    <section class="panel">
        <div class="section-head">
            <div>
                <h2>Miraclib Response Comparison</h2>
                <p class="muted" id="findingsText"></p>
            </div>
        </div>
        <div class="grid-two">
            <div>
                <img class="plot" src="miraclib_response_boxplot.png" alt="Boxplot comparing responder and non-responder immune cell frequencies">
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Population</th><th>Responder median %</th><th>Non-responder median %</th><th>Adjusted p</th><th>Significant</th></tr></thead>
                    <tbody id="statsBody"></tbody>
                </table>
            </div>
        </div>
    </section>
    <section class="panel">
        <div class="section-head">
            <div>
                <h2>Baseline Miraclib Melanoma PBMC Subset</h2>
                <p class="muted">Baseline samples are filtered to time_from_treatment_start = 0.</p>
            </div>
            <p class="muted" id="baselineCount"></p>
        </div>
        <div class="grid-two">
            <div>
                <div class="controls">
                    <label>Project<select id="projectFilter"></select></label>
                    <label>Response<select id="responseFilter"></select></label>
                    <label>Sex<select id="sexFilter"></select></label>
                    <button id="resetSubset" type="button">Reset</button>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>Project</th><th>Subject</th><th>Response</th><th>Sex</th><th>Sample</th><th>Time</th></tr></thead>
                        <tbody id="baselineBody"></tbody>
                    </table>
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Category</th><th>Value</th><th>Count</th></tr></thead>
                    <tbody id="summaryBody"></tbody>
                </table>
            </div>
        </div>
    </section>
    <section class="panel">
        <div class="section-head">
            <div>
                <h2>Generated Files</h2>
                <p class="muted">These files are regenerated by make pipeline.</p>
            </div>
        </div>
        <div class="links">
            <a href="cell_frequencies.csv">cell_frequencies.csv</a>
            <a href="miraclib_response_stats.csv">miraclib_response_stats.csv</a>
            <a href="miraclib_response_boxplot.png">miraclib_response_boxplot.png</a>
            <a href="baseline_miraclib_melanoma_pbmc_samples.csv">baseline_miraclib_melanoma_pbmc_samples.csv</a>
            <a href="baseline_miraclib_melanoma_pbmc_summary.csv">baseline_miraclib_melanoma_pbmc_summary.csv</a>
        </div>
    </section>
</main>
<script id="dashboard-data" type="application/json">__DATA__</script>
<script>
const data = JSON.parse(document.getElementById("dashboard-data").textContent);
const maxRows = 300;

function byId(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[character]));
}

function unique(values) {
    return [...new Set(values)].filter(Boolean).sort((a, b) => a.localeCompare(b));
}

function number(value) {
    return Number.parseFloat(value);
}

function formatNumber(value) {
    return Number(value).toLocaleString();
}

function formatPct(value) {
    return number(value).toFixed(2);
}

function fillSelect(id, values, label) {
    const select = byId(id);
    select.innerHTML = `<option value="">${escapeHtml(label)}</option>` + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function badge(value) {
    const normalized = String(value).toLowerCase();
    const klass = normalized === "yes" || normalized === "true" ? "yes" : "no";
    return `<span class="badge ${klass}">${escapeHtml(value)}</span>`;
}

function renderMetrics() {
    byId("metricSamples").textContent = formatNumber(data.metadata.sample_count);
    byId("metricFrequencies").textContent = formatNumber(data.metadata.frequency_rows);
    byId("metricBaseline").textContent = formatNumber(data.metadata.baseline_samples);
    byId("metricSignificant").textContent = formatNumber(data.metadata.significant_populations);
}

function renderFrequencyTable() {
    const sampleQuery = byId("sampleFilter").value.trim().toLowerCase();
    const population = byId("populationFilter").value;
    const rows = data.frequencies.filter(row => {
        const matchesSample = !sampleQuery || row.sample.toLowerCase().includes(sampleQuery);
        const matchesPopulation = !population || row.population === population;
        return matchesSample && matchesPopulation;
    });

    byId("frequencyCount").textContent = `${formatNumber(rows.length)} matching rows, showing up to ${maxRows}`;
    byId("frequencyBody").innerHTML = rows.slice(0, maxRows).map(row => `
        <tr>
            <td>${escapeHtml(row.sample)}</td>
            <td>${formatNumber(row.total_count)}</td>
            <td>${escapeHtml(row.population)}</td>
            <td>${formatNumber(row.count)}</td>
            <td>${formatPct(row.percentage)}%</td>
        </tr>
    `).join("");

    renderSampleProfile(sampleQuery);
}

function renderSampleProfile(sampleQuery) {
    const samples = unique(data.frequencies.map(row => row.sample));
    const selected = samples.find(sample => sample.toLowerCase() === sampleQuery) || samples.find(sample => sample.toLowerCase().includes(sampleQuery)) || samples[0];
    const rows = data.frequencies.filter(row => row.sample === selected);

    byId("sampleProfileTitle").textContent = `${selected} profile`;
    byId("sampleProfile").innerHTML = rows.map(row => `
        <div class="bar-row">
            <span>${escapeHtml(row.population)}</span>
            <span class="bar-track"><span class="bar-fill" style="width: ${Math.max(0, Math.min(100, number(row.percentage)))}%"></span></span>
            <strong>${formatPct(row.percentage)}%</strong>
        </div>
    `).join("");
}

function renderStats() {
    const significant = data.stats.filter(row => row.significant_fdr_0_05 === "True");
    byId("findingsText").textContent = significant.length
        ? `${significant.map(row => row.population).join(", ")} differ significantly after FDR correction at 0.05.`
        : "No immune cell populations differ significantly after FDR correction at 0.05.";
    byId("statsBody").innerHTML = data.stats.map(row => `
        <tr>
            <td>${escapeHtml(row.population)}</td>
            <td>${formatPct(row.responders_median_pct)}%</td>
            <td>${formatPct(row.non_responders_median_pct)}%</td>
            <td>${number(row.adjusted_p_value).toPrecision(4)}</td>
            <td>${badge(row.significant_fdr_0_05)}</td>
        </tr>
    `).join("");
}

function renderSubset() {
    const project = byId("projectFilter").value;
    const response = byId("responseFilter").value;
    const sex = byId("sexFilter").value;
    const rows = data.baseline_samples.filter(row => {
        return (!project || row.project === project) && (!response || row.response === response) && (!sex || row.sex === sex);
    });

    byId("baselineCount").textContent = `${formatNumber(rows.length)} matching samples, showing up to ${maxRows}`;
    byId("baselineBody").innerHTML = rows.slice(0, maxRows).map(row => `
        <tr>
            <td>${escapeHtml(row.project)}</td>
            <td>${escapeHtml(row.subject)}</td>
            <td>${badge(row.response)}</td>
            <td>${escapeHtml(row.sex)}</td>
            <td>${escapeHtml(row.sample)}</td>
            <td>${escapeHtml(row.time_from_treatment_start)}</td>
        </tr>
    `).join("");
}

function renderSummary() {
    byId("summaryBody").innerHTML = data.baseline_summary.map(row => `
        <tr>
            <td>${escapeHtml(row.category)}</td>
            <td>${escapeHtml(row.value)}</td>
            <td>${formatNumber(row.count)}</td>
        </tr>
    `).join("");
}

fillSelect("populationFilter", unique(data.frequencies.map(row => row.population)), "All populations");
fillSelect("projectFilter", unique(data.baseline_samples.map(row => row.project)), "All projects");
fillSelect("responseFilter", unique(data.baseline_samples.map(row => row.response)), "All responses");
fillSelect("sexFilter", unique(data.baseline_samples.map(row => row.sex)), "All sex values");

["sampleFilter", "populationFilter"].forEach(id => byId(id).addEventListener("input", renderFrequencyTable));
["projectFilter", "responseFilter", "sexFilter"].forEach(id => byId(id).addEventListener("input", renderSubset));
byId("resetSubset").addEventListener("click", () => {
    byId("projectFilter").value = "";
    byId("responseFilter").value = "";
    byId("sexFilter").value = "";
    renderSubset();
});

renderMetrics();
renderFrequencyTable();
renderStats();
renderSummary();
renderSubset();
</script>
</body>
</html>
"""


def run_pipeline() -> None:
    subprocess.run([sys.executable, "load_data.py"], cwd=ROOT_DIR, check=True)

    with FREQUENCIES_PATH.open("w", newline="") as output_file:
        subprocess.run(
            [sys.executable, "cell_frequency.py"],
            cwd=ROOT_DIR,
            check=True,
            stdout=output_file,
        )

    subprocess.run([sys.executable, "statistical_analysis.py"], cwd=ROOT_DIR, check=True)
    subprocess.run([sys.executable, "subset_analysis.py"], cwd=ROOT_DIR, check=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def total_from_summary(rows: list[dict[str, str]]) -> int:
    for row in rows:
        if row["category"] == "total_baseline_samples":
            return int(row["count"])
    return 0


def build_dashboard() -> None:
    frequencies = read_csv(FREQUENCIES_PATH)
    stats = read_csv(STATS_PATH)
    baseline_samples = read_csv(BASELINE_SAMPLES_PATH)
    baseline_summary = read_csv(BASELINE_SUMMARY_PATH)
    sample_ids = {row["sample"] for row in frequencies}
    significant_populations = [
        row for row in stats if row["significant_fdr_0_05"] == "True"
    ]
    data = {
        "metadata": {
            "sample_count": len(sample_ids),
            "frequency_rows": len(frequencies),
            "baseline_samples": total_from_summary(baseline_summary),
            "significant_populations": len(significant_populations),
        },
        "frequencies": frequencies,
        "stats": stats,
        "baseline_samples": baseline_samples,
        "baseline_summary": baseline_summary,
    }
    payload = json.dumps(data).replace("</", "<\\/")
    DASHBOARD_PATH.write_text(HTML_TEMPLATE.replace("__DATA__", payload), encoding="utf-8")


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def create_server(
    host: str,
    start_port: int,
) -> tuple[ReusableThreadingHTTPServer, int]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT_DIR))

    for port in range(start_port, start_port + 50):
        try:
            return ReusableThreadingHTTPServer((host, port), handler), port
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                continue
            raise

    raise OSError(f"No open port found from {start_port} to {start_port + 49}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--skip-pipeline", action="store_true")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.skip_pipeline:
        run_pipeline()

    build_dashboard()
    print(f"Dashboard file: {DASHBOARD_PATH}", flush=True)

    if args.build_only:
        return

    server, port = create_server(args.host, args.port)
    display_host = "localhost" if args.host == "0.0.0.0" else args.host
    print(f"Dashboard URL: http://{display_host}:{port}/dashboard.html", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
