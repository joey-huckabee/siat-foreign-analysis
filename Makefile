.DEFAULT_GOAL := help
POETRY ?= poetry
RUN := $(POETRY) run
PKG := siat_foreign_analysis
TESTS := tests

.PHONY: help install hooks format lint types test cov dead check run clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime + dev dependencies
	$(POETRY) install --with dev

hooks: ## Install the pre-commit git hooks
	$(RUN) pre-commit install

format: ## Auto-format the codebase
	$(RUN) black .
	$(RUN) isort .
	$(RUN) ruff check --fix .

lint: ## Run the linters without modifying files
	$(RUN) black --check --diff .
	$(RUN) isort --check-only --diff .
	$(RUN) ruff check .
	$(RUN) pylint $(PKG) $(TESTS)

types: ## Run mypy
	$(RUN) mypy --config-file mypy.ini

test: ## Run the test suite
	$(RUN) pytest

cov: test ## Alias for test (coverage is always on)

dead: ## Look for unused code
	$(RUN) vulture

check: lint types test dead ## Everything CI runs

run: ## Score the documents in input/ into output/
	$(RUN) siat-foreign-analysis

clean: ## Remove build and cache artifacts
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
