SHELL := /bin/sh
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
COMPOSE := docker compose --env-file .env -f docker/docker-compose.yml

.PHONY: venv install bootstrap-env hooks secret-scan test lint format check ci up down run

venv:
	/usr/bin/python -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt -r requirements-dev.txt

bootstrap-env:
	./scripts/bootstrap-env.sh

hooks:
	chmod +x .githooks/pre-commit scripts/precommit-secret-scan.sh scripts/bootstrap-env.sh
	git config core.hooksPath .githooks

secret-scan:
	./scripts/precommit-secret-scan.sh

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m black .

check: lint test

ci: secret-scan lint test

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
