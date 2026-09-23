#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    alembic upgrade head
fi

if [ -n "${ADMIN_EMAIL:-}" ] || [ -n "${ADMIN_PASSWORD:-}" ]; then
    python -m flask --app app create-admin
fi

exec "$@"
