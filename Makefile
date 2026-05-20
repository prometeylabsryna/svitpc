.PHONY: help install run migrate makemigrations shell test lint fmt celery worker beat import-sql createsuperuser

PYTHON := python
MANAGE := $(PYTHON) manage.py
SETTINGS := DJANGO_SETTINGS_MODULE=config.settings.develop

help:
	@echo "СвітПК — Makefile команди:"
	@echo "  make install       — встановити залежності (uv sync)"
	@echo "  make run           — запустити dev-сервер"
	@echo "  make migrate       — застосувати міграції"
	@echo "  make mm            — створити міграції"
	@echo "  make shell         — Django shell"
	@echo "  make test          — запустити тести"
	@echo "  make lint          — ruff + mypy + djlint"
	@echo "  make fmt           — ruff format + isort"
	@echo "  make celery        — запустити Celery worker + beat"
	@echo "  make import-sql    — імпорт із OpenCart SQL-бекапу"
	@echo "  make superuser     — створити суперкористувача"

install:
	uv sync --all-extras

run:
	$(SETTINGS) $(MANAGE) runserver 0.0.0.0:8000

migrate:
	$(SETTINGS) $(MANAGE) migrate

mm:
	$(SETTINGS) $(MANAGE) makemigrations

shell:
	$(SETTINGS) $(MANAGE) shell_plus --ipython

test:
	$(SETTINGS) pytest --cov=apps --cov-report=term-missing -x

lint:
	ruff check apps config
	mypy apps config --ignore-missing-imports
	djlint templates --check

fmt:
	ruff check --fix apps config
	ruff format apps config

celery:
	celery -A config worker --beat --loglevel=info

worker:
	celery -A config worker --loglevel=info

beat:
	celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

import-sql:
	$(SETTINGS) $(MANAGE) import_opencart_sql --file data/svitpc_2023-02-28_15-47-34_backup.sql

superuser:
	$(SETTINGS) $(MANAGE) createsuperuser

collectstatic:
	$(SETTINGS) $(MANAGE) collectstatic --noinput

backup-db:
	$(SETTINGS) $(MANAGE) backup_db
