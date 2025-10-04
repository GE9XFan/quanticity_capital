PYTHON ?= python3
PIP ?= pip3

.PHONY: install lint uw-rest-fetch uw-websocket clean

install:
	$(PIP) install -r requirements.txt

lint:
	PYTHONPATH=src $(PYTHON) -m compileall src

uw-rest-fetch:
	PYTHONPATH=. $(PYTHON) -m src.cli.uw_rest_fetch

uw-websocket:
	PYTHONPATH=. $(PYTHON) -m src.cli.uw_websocket

clean:
	rm -rf __pycache__ .pytest_cache data/unusual_whales/raw logs
