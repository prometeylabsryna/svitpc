#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z db 5432; do
  sleep 0.5
done
echo "PostgreSQL is ready"

python manage.py compilemessages -l uk -l en 2>/dev/null || true
exec "$@"
