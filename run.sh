#!/usr/bin/env bash
# 前台运行博客（供 systemd / launchd 调用，也可手动执行）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -x ".venv/bin/waitress-serve" ]; then
  echo "未找到 .venv，请先运行 ./install.sh" >&2
  exit 1
fi

ENV_HOST="${HOST-}"
ENV_PORT="${PORT-}"
ENV_THREADS="${THREADS-}"
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
if [ -n "${ENV_HOST:-}" ]; then HOST="$ENV_HOST"; fi
if [ -n "${ENV_PORT:-}" ]; then PORT="$ENV_PORT"; fi
if [ -n "${ENV_THREADS:-}" ]; then THREADS="$ENV_THREADS"; fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
THREADS="${THREADS:-4}"

exec .venv/bin/waitress-serve \
  --listen="${HOST}:${PORT}" \
  --threads="${THREADS}" \
  wsgi:app
