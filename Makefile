# SLAC developer tasks. Targets run zero-install (PYTHONPATH=src) where possible.

PY ?= python3
SRC := PYTHONPATH=src

.DEFAULT_GOAL := help

.PHONY: help lint test check new install install-dev hooks clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

lint: ## Lint the bundled example loops
	$(SRC) $(PY) -m slac lint examples/*.slac.md

test: ## Run the test suite (stdlib unittest, zero deps)
	$(SRC) $(PY) -m unittest discover -s tests -v

check: lint test ## Lint + test (what CI runs)

new: ## Scaffold a loop: make new NAME=my_loop
	$(SRC) $(PY) -m slac new $(NAME)

install: ## Install the `slac` CLI into the current environment
	$(PY) -m pip install .

install-dev: ## Editable install with dev extras (pytest, pyyaml, pre-commit)
	$(PY) -m pip install -e ".[dev]"

hooks: ## Install the pre-commit hook
	pre-commit install

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
