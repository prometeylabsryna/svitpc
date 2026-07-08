#!/usr/bin/env bash
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

free_host_ports() {
  systemctl stop nginx 2>/dev/null || true
  systemctl disable nginx 2>/dev/null || true
  for svc in $(systemctl list-units --type=service --all 2>/dev/null | grep -oE 'gunicorn[^ ]*' || true); do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
  done
}

if [[ ! -f .env ]]; then
  echo "FATAL: .env not found. Copy .env.docker.example to .env and fill secrets."
  exit 1
fi

free_host_ports

echo "==> Mode: USE_HTTPS=${USE_HTTPS}"
echo "==> Building images"
"${COMPOSE[@]}" build

echo "==> Starting stack"
# НЕ фатально: якщо якийсь контейнер не встиг стати healthy (довгі міграції),
# `up` повертає ненульовий код і set -e вбив би скрипт, лишивши стек неповним
# (саме так nginx одного разу не піднявся і сайт лежав до ручного up -d).
"${COMPOSE[@]}" up -d || echo "WARN: initial 'up -d' returned non-zero (slow healthcheck?) — will retry after backend is healthy."

echo "==> Waiting for backend healthcheck (up to ~16 min: migrations with data backfill)"
HEALTHCHECK='import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/healthz/", timeout=5)'
BACKEND_HEALTHY=false
for _ in $(seq 1 480); do
  if "${COMPOSE[@]}" exec -T backend python -c "$HEALTHCHECK" 2>/dev/null; then
    echo "Backend healthy"
    BACKEND_HEALTHY=true
    break
  fi
  sleep 2
done
if [[ "$BACKEND_HEALTHY" != "true" ]]; then
  echo "WARN: backend did not become healthy in time — check: ${COMPOSE[*]} logs backend"
fi

echo "==> Final 'up -d' (bring up any services skipped by the first attempt)"
"${COMPOSE[@]}" up -d || echo "WARN: final 'up -d' returned non-zero — inspect '${COMPOSE[*]} ps' below."

if curl -sf http://127.0.0.1/healthz/ >/dev/null; then
  echo "HTTP healthz OK"
else
  echo "WARN: HTTP healthz failed - check: ${COMPOSE[*]} logs backend nginx"
fi

if [[ "$USE_HTTPS" == "true" ]] && curl -sfk https://127.0.0.1/healthz/ >/dev/null 2>&1; then
  echo "HTTPS healthz OK"
fi

"${COMPOSE[@]}" ps

# Every service in the stack must be running — a missing container is how the
# site silently went down before (nginx never created after an aborted `up`).
EXPECTED_SERVICES=(backend nginx db redis celery_worker celery_worker_light celery_worker_priority celery_beat)
MISSING=0
for svc in "${EXPECTED_SERVICES[@]}"; do
  if ! "${COMPOSE[@]}" ps "$svc" 2>/dev/null | grep -qE "Up|running"; then
    echo "ERROR: service '$svc' is NOT running — check: ${COMPOSE[*]} logs $svc"
    MISSING=1
  fi
done
if [[ "$MISSING" == "0" ]]; then
  echo "All ${#EXPECTED_SERVICES[@]} services are running."
fi

if [[ -f docker-compose.override.yml ]]; then
  echo "WARN: docker-compose.override.yml is for local dev only."
  echo "      On production rename it (e.g. docker-compose.override.yml.bak) before deploy."
fi
