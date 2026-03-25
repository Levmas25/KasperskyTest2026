#!/bin/sh
set -eu

exec rq worker \
    --url "redis://${REDIS_HOST:-redis}:${REDIS_PORT:-6379}/${REDIS_DB:-0}" \
    "${REPORT_QUEUE_NAME:-reports}"
