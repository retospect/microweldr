.PHONY: help install install-dev test test-unit test-integration lint format clean build docs

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package in virtual environment
	python -m venv venv && source venv/bin/activate && pip install -e .

install-dev:  ## Install the package with development dependencies
	python -m venv venv && source venv/bin/activate && pip install -e .[validation,dev]

test:  ## Run all tests including examples and code formatting
	pytest

test-unit:  ## Run unit tests only
	pytest tests/unit/

test-integration:  ## Run integration tests only
	pytest tests/integration/

test-examples:  ## Run example file tests only
	pytest tests/integration/test_full_workflow.py::TestExampleFiles -v

test-markdown:  ## Run markdown validation tests
	pytest tests/unit/test_markdown_validation.py -v

test-format:  ## Check code formatting with black
	black --check svg_welder tests

test-coverage:  ## Run tests with coverage report
	pytest --cov=svg_welder --cov-report=html --cov-report=term

lint:  ## Run linting checks
	flake8 svg_welder tests
	mypy svg_welder

format:  ## Format code with black and isort
	black svg_welder tests
	isort svg_welder tests

format-check:  ## Check code formatting
	black --check svg_welder tests
	isort --check-only svg_welder tests

clean:  ## Clean up build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build the package
	poetry build

install-pre-commit:  ## Install pre-commit hooks
	poetry run pre-commit install

run-example:  ## Run with example SVG
	poetry run svg-welder examples/example.svg

run-comprehensive:  ## Run with comprehensive sample
	poetry run svg-welder examples/comprehensive_sample.svg
