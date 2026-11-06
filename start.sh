#!/usr/bin/env bash
# 后台启动博客，PID 写入 blog.pid，日志写入 logs/blog.log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ENV_HOST="${HOST-}"
ENV_PORT="${PORT-}"
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
if [ -n "${ENV_HOST:-}" ]; then HOST="$ENV_HOST"; fi
if [ -n "${ENV_PORT:-}" ]; then PORT="$ENV_PORT"; fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ ! -x ".venv/bin/waitress-serve" ]; then
  echo "未安装依赖，请先运行 ./install.sh" >&2
  exit 1
fi

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet personal-blog 2>/dev/null; then
  echo "博客已由 systemd 服务运行（personal-blog）。"
  echo "如需重启：sudo systemctl restart personal-blog"
  exit 0
fi
if [ "$(uname -s)" = "Darwin" ] && launchctl list 2>/dev/null | grep -q com.personal-blog; then
  echo "博客已由 launchd 服务运行（com.personal-blog）。"
  echo "如需重启：launchctl unload ~/Library/LaunchAgents/com.personal-blog.plist && launchctl load ~/Library/LaunchAgents/com.personal-blog.plist"
  exit 0
fi

if [ -f blog.pid ]; then
  OLD_PID="$(cat blog.pid 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "博客已在运行（PID ${OLD_PID}），地址：http://127.0.0.1:$PORT"
    exit 0
  fi
  rm -f blog.pid
fi

if ! .venv/bin/python - "$HOST" "$PORT" <<'PY'
import socket
import sys

host, port = sys.argv[1], int(sys.argv[2])
family = socket.AF_INET6 if ":" in host else socket.AF_INET
s = socket.socket(family, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port))
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
then
  echo "端口 $PORT 已被占用，请使用 --port 指定其他端口。" >&2
  exit 2
fi

mkdir -p logs
nohup env HOST="$HOST" PORT="$PORT" ./run.sh >> logs/blog.log 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > blog.pid

READY=0
for _ in $(seq 1 60); do
  if ! kill -0 "$NEW_PID" 2>/dev/null; then
    break
  fi
  if .venv/bin/python - "$HOST" "$PORT" <<'PY'
import socket
import sys

host, port = sys.argv[1], int(sys.argv[2])
if host in ("", "0.0.0.0"):
    host = "127.0.0.1"
elif host == "::":
    host = "::1"
try:
    with socket.create_connection((host, port), timeout=0.5):
        raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
  then
    READY=1
    break
  fi
  sleep 0.25
done

if [ "$READY" != "1" ]; then
  rm -f blog.pid
  if kill -0 "$NEW_PID" 2>/dev/null; then
    kill "$NEW_PID" 2>/dev/null || true
  fi
  echo "启动失败或超时，最近日志：" >&2
  tail -n 20 logs/blog.log >&2 || true
  exit 1
fi

echo "博客已启动（PID ${NEW_PID}）"
echo "  前台：http://127.0.0.1:$PORT"
echo "  首次设置：http://127.0.0.1:$PORT/setup"
echo "  日志：$ROOT/logs/blog.log"
