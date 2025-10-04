PYTHON ?= python3
PIP ?= pip3

.PHONY: install lint uw-rest-fetch clean

install:
	$(PIP) install -r requirements.txt

lint:
	PYTHONPATH=src $(PYTHON) -m compileall src

uw-rest-fetch:
	PYTHONPATH=. $(PYTHON) -m src.cli.uw_rest_fetch

clean:
	rm -rf __pycache__ .pytest_cache data/unusual_whales/raw logs
