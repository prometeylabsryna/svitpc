#!/usr/bin/env bash
# Наповнення production-сайту даними (OpenCart SQL + Brain + довідники).
#
# Перед запуском:
#   1. .env — BRAIN_*, KANCMASTER_*, NOVA_POSHTA_API_KEY
#   2. data/svitpc_2023-02-28_15-47-34_backup.sql
#   3. (опційно) ТЗ/Прейскурант цен .xlsx
#
#   bash deploy/docker/populate.sh
#   bash deploy/docker/populate.sh --dry-run
#   bash deploy/docker/populate.sh --skip-import --full-brain

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

USE_HTTPS="${USE_HTTPS:-false}"
if [[ -f .env ]]; then
  val=$(grep -E '^USE_HTTPS=' .env | tail -1 | cut -d= -f2- | tr -d ' "')
  if [[ -n "${val:-}" ]]; then
    USE_HTTPS="$val"
  fi
fi

if [[ "$USE_HTTPS" == "true" ]]; then
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
else
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.http.yml)
fi

DEFAULT_SQL="data/svitpc_2023-02-28_15-47-34_backup.sql"
DEFAULT_PRICES="ТЗ/Прейскурант цен .xlsx"

if [[ ! -f .env ]]; then
  echo "FATAL: .env not found. Copy .env.docker.example → .env"
  exit 1
fi

mkdir -p data logs backups

echo "==> Compose: ${COMPOSE[*]}"

if [[ ! -f apps/core/management/commands/populate_site.py ]]; then
  echo "FATAL: populate_site.py missing — run: git pull origin main"
  exit 1
fi

echo "==> Rebuild backend (pick up latest management commands)"
"${COMPOSE[@]}" build backend
"${COMPOSE[@]}" up -d db redis backend

echo "==> Waiting for backend"
HEALTHCHECK='import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/healthz/", timeout=5)'
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T backend python -c "$HEALTHCHECK" 2>/dev/null; then
    echo "Backend healthy"
    break
  fi
  sleep 3
done

SKIP_IMPORT=false
for a in "$@"; do
  [[ "$a" == "--skip-import" ]] && SKIP_IMPORT=true
done

if [[ "$SKIP_IMPORT" == false ]]; then
  if [[ ! -f "$DEFAULT_SQL" ]]; then
    echo "FATAL: SQL backup not found: $ROOT/$DEFAULT_SQL"
    echo "  scp backup: scp backup.sql root@SERVER:/var/www/svitpc/data/svitpc_2023-02-28_15-47-34_backup.sql"
    echo "  Or: bash deploy/docker/populate.sh --skip-import"
    exit 1
  fi
  echo "==> SQL backup: $DEFAULT_SQL ($(du -h "$DEFAULT_SQL" | cut -f1))"
fi

if [[ -f "$DEFAULT_PRICES" ]]; then
  echo "==> Service prices workbook found"
else
  echo "WARN: $DEFAULT_PRICES not found — service prices step will be skipped"
fi

echo "==> Pausing Celery (free RAM for import)"
"${COMPOSE[@]}" stop celery_worker celery_beat 2>/dev/null || true

echo "==> populate_site $*"
"${COMPOSE[@]}" exec -T backend python manage.py populate_site "$@"

echo "==> Restarting Celery"
"${COMPOSE[@]}" up -d celery_worker celery_beat

echo "==> Catalog summary:"
"${COMPOSE[@]}" exec -T backend python manage.py shell -c \
  "from apps.catalog.models import Product, Category; print('products', Product.objects.count()); print('categories', Category.objects.count())"
