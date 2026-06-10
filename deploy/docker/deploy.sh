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
"${COMPOSE[@]}" up -d

echo "==> Waiting for backend healthcheck"
HEALTHCHECK='import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/healthz/", timeout=5)'
for _ in $(seq 1 45); do
  if "${COMPOSE[@]}" exec -T backend python -c "$HEALTHCHECK" 2>/dev/null; then
    echo "Backend healthy"
    break
  fi
  sleep 2
done

if curl -sf http://127.0.0.1/healthz/ >/dev/null; then
  echo "HTTP healthz OK"
else
  echo "WARN: HTTP healthz failed - check: ${COMPOSE[*]} logs backend nginx"
fi

if [[ "$USE_HTTPS" == "true" ]] && curl -sfk https://127.0.0.1/healthz/ >/dev/null 2>&1; then
  echo "HTTPS healthz OK"
fi

"${COMPOSE[@]}" ps
