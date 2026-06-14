PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: setup pipeline dashboard

setup:
	$(PIP) install -r requirements.txt

pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) cell_frequency.py > cell_frequencies.csv
	$(PYTHON) statistical_analysis.py
	$(PYTHON) subset_analysis.py
	$(PYTHON) dashboard.py --build-only --skip-pipeline

dashboard:
	$(PYTHON) dashboard.py
