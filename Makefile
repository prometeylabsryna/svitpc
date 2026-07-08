.PHONY: help install run migrate makemigrations shell test lint fmt celery worker beat import-sql createsuperuser

MANAGE := uv run manage.py
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
	@echo "  make celery        — Celery worker (brain/catalog) + beat"
	@echo "  make worker-priority — окремий worker для ТТН (priority queue)"
	@echo "  make import-sql    — імпорт із OpenCart SQL-бекапу"
	@echo "  make import-prices — імпорт прейскуранта сервісного центру"
	@echo "  make superuser     — створити суперкористувача"
	@echo "  make translate-en  — перекласти каталог/сторінки на англійську (Google)"
	@echo "  make fix-catalog-uk — замінити російські назви атрибутів/фільтрів на українські"
	@echo "  make dedupe-filters  — об'єднати дублікати груп/значень фільтрів OpenCart"
	@echo "  make rebuild-search  — перебудувати FTS-індекс пошуку товарів"
	@echo "  make docker-populate — наповнити prod (OpenCart + Brain + довідники)"
	@echo "  make backfill-i18n   — скопіювати legacy-дані в modeltranslation *_uk"
	@echo "  make test-sms      — перевірити SMS_API_KEY (TurboSMS ping)"
	@echo "  make test-sms-send PHONE=+380... — надіслати тестове SMS"
	@echo "  make test-vchasnokasa — перевірити токен Вчасно.Каса"
	@echo "  make test-vchasnokasa-order ID=12 — фіскалізувати замовлення"

install:
	uv sync --all-extras

run:
	$(SETTINGS) $(MANAGE) runserver 0.0.0.0:8001

migrate:
	$(SETTINGS) $(MANAGE) migrate

mm:
	$(SETTINGS) $(MANAGE) makemigrations

shell:
	$(SETTINGS) $(MANAGE) shell_plus --ipython

test:
	DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest --cov=apps --cov-report=term-missing -x

test-sms:
	$(SETTINGS) $(MANAGE) test_sms --ping-only

test-sms-send:
	@test -n "$(PHONE)" || (echo "Вкажіть PHONE=+380..." && exit 1)
	$(SETTINGS) $(MANAGE) test_sms "$(PHONE)"

test-vchasnokasa:
	$(SETTINGS) $(MANAGE) test_vchasnokasa --ping

test-vchasnokasa-order:
	@test -n "$(ID)" || (echo "Вкажіть ID=номер_замовлення" && exit 1)
	$(SETTINGS) $(MANAGE) test_vchasnokasa --order-id $(ID)

lint:
	ruff check apps config
	mypy apps config --ignore-missing-imports
	djlint templates --check

fmt:
	ruff check --fix apps config
	ruff format apps config

celery:
	celery -A config worker --beat --loglevel=info -Q celery

worker:
	celery -A config worker --loglevel=info -Q celery

worker-priority:
	celery -A config worker --loglevel=info -Q priority -c 1

beat:
	celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

import-sql:
	$(SETTINGS) $(MANAGE) import_opencart_sql --file data/svitpc_2023-02-28_15-47-34_backup.sql

import-prices:
	$(SETTINGS) $(MANAGE) import_service_prices

superuser:
	$(SETTINGS) $(MANAGE) createsuperuser

collectstatic:
	python3 scripts/build_css_bundle.py
	$(SETTINGS) $(MANAGE) collectstatic --noinput

assets:
	python3 scripts/optimize_static_images.py
	python3 scripts/build_css_bundle.py

docker-build:
	docker compose -f docker-compose.yml -f docker-compose.http.yml build

docker-up:
	docker compose -f docker-compose.yml -f docker-compose.http.yml up -d

docker-logs:
	docker compose -f docker-compose.yml -f docker-compose.http.yml logs -f --tail=100

docker-deploy:
	bash deploy/docker/deploy.sh

docker-populate:
	bash deploy/docker/populate.sh

export-requirements:
	uv export --no-dev --no-hashes --no-editable --no-emit-project -o requirements.txt

backup-db:
	$(SETTINGS) $(MANAGE) backup_db

translate-en:
	$(SETTINGS) $(MANAGE) translate_to_english --what=all

fix-catalog-uk:
	$(SETTINGS) $(MANAGE) fix_russian_catalog --what=all

dedupe-filters:
	$(SETTINGS) $(MANAGE) dedupe_catalog_filters

backfill-i18n:
	$(SETTINGS) $(MANAGE) backfill_modeltranslation_uk

rebuild-search:
	$(SETTINGS) $(MANAGE) rebuild_product_search_vectors

populate-site:
	$(SETTINGS) $(MANAGE) populate_site
