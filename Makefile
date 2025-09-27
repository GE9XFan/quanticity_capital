.PHONY: install requirements clean-venv

install requirements:
	python -m pip install -r requirements.txt

clean-venv:
	rm -rf .venv
