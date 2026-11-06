#!/usr/bin/env bash
# 停止后台运行的博客
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet personal-blog 2>/dev/null; then
  echo "博客当前由 systemd 服务运行。" >&2
  echo "停止服务：sudo systemctl stop personal-blog" >&2
  exit 1
fi
if [ "$(uname -s)" = "Darwin" ] && launchctl list 2>/dev/null | grep -q com.personal-blog; then
  echo "博客当前由 launchd 服务运行。" >&2
  echo "停止服务：launchctl unload ~/Library/LaunchAgents/com.personal-blog.plist" >&2
  exit 1
fi

if [ ! -f blog.pid ]; then
  echo "博客未在后台运行（没有 blog.pid）。"
  exit 0
fi

PID="$(cat blog.pid 2>/dev/null || true)"
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  rm -f blog.pid
  echo "进程不存在，已清理 blog.pid。"
  exit 0
fi

kill "$PID"
for _ in $(seq 1 20); do
  if ! kill -0 "$PID" 2>/dev/null; then
    break
  fi
  sleep 0.2
done
if kill -0 "$PID" 2>/dev/null; then
  echo "普通停止超时，强制结束进程 ${PID}。"
  kill -9 "$PID" 2>/dev/null || true
fi
rm -f blog.pid
echo "博客已停止。"
