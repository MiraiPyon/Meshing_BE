SHELL := /bin/sh
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
PYTHON = $(shell if [ -x "$(VENV_PYTHON)" ]; then printf '%s' "$(VENV_PYTHON)"; else command -v python3 || command -v python; fi)
PIP := $(PYTHON) -m pip
COMPOSE := docker compose --env-file docker/.env -f docker/docker-compose.yml
LINT_PATHS := app tests
PORT ?= 8000

.PHONY: venv install bootstrap-env hooks secret-scan test test-fea test-fea-stress test-stress lint format check ci up down run run-alt

venv:
	/usr/bin/python -m venv $(VENV)

install: venv
	$(VENV_PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

bootstrap-env:
	./scripts/bootstrap-env.sh

hooks:
	chmod +x .githooks/pre-commit scripts/precommit-secret-scan.sh scripts/bootstrap-env.sh
	git config core.hooksPath .githooks

secret-scan:
	./scripts/precommit-secret-scan.sh

test:
	$(PYTHON) -m pytest -q

test-fea:
	$(PYTHON) -m pytest -q tests/test_fea_*.py

test-fea-stress:
	@set -e; \
	for i in 1 2 3 4 5; do \
		echo "[fea-stress] run $$i/5"; \
		$(PYTHON) -m pytest -q tests/test_fea_*.py; \
	done

test-stress:
	@set -e; \
	for i in 1 2 3 4 5; do \
		echo "[stress] run $$i/5"; \
		$(PYTHON) -m pytest -q; \
	done

lint:
	$(PYTHON) -m ruff check $(LINT_PATHS)

format:
	$(PYTHON) -m black .

check: lint test

ci: secret-scan lint test

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

run-alt:
	$(MAKE) run PORT=8001
