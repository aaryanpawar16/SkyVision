#!/usr/bin/env bash
set -euo pipefail

# Bring up the full stack and wait for services to be healthy.

COMPOSE=${COMPOSE:-"docker compose"}   # supports both Docker Compose v2+ and legacy
API_URL=${API_URL:-"http://localhost:8000"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-3306}

echo "→ Starting services with Docker Compose…"
$COMPOSE up -d

echo "→ Waiting for MariaDB on ${DB_HOST}:${DB_PORT}…"
# Simple TCP wait
for i in {1..60}; do
  (echo > /dev/tcp/${DB_HOST}/${DB_PORT}) >/dev/null 2>&1 && break
  sleep 1
  if [[ $i -eq 60 ]]; then
    echo "✖ Timed out waiting for MariaDB."
    exit 1
  fi
done
echo "✔ MariaDB is reachable."

echo "→ Waiting for API health at ${API_URL}/healthz…"
for i in {1..60}; do
  if curl -fsS "${API_URL}/healthz" >/dev/null 2>&1; then
    echo "✔ API is healthy."
    break
  fi
  sleep 1
  if [[ $i -eq 60 ]]; then
    echo "✖ Timed out waiting for API."
    exit 1
  fi
done

echo "→ Services are up. Follow logs with:"
echo "   $COMPOSE logs -f"
