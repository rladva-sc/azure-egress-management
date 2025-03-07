.PHONY: setup test lint format clean docs

# Virtual environment commands
setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .

# Testing commands
test:
	pytest

test-coverage:
	pytest --cov=src tests/

# Linting and formatting
lint:
	flake8 src tests
	black --check src tests

format:
	black src tests
	isort src tests

# Cleaning commands
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .coverage -exec rm -rf {} +

# Documentation
docs:
	cd docs && sphinx-build -b html . _build/html
