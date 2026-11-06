#!/usr/bin/env bash
# 查看博客运行状态
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUNNING=0

if [ -f blog.pid ]; then
  PID="$(cat blog.pid 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "后台进程：运行中（PID ${PID}）"
    RUNNING=1
  else
    echo "后台进程：未运行（blog.pid 已失效）"
  fi
else
  echo "后台进程：未运行"
fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^personal-blog\.service'; then
  if systemctl is-active --quiet personal-blog 2>/dev/null; then
    echo "systemd 服务：运行中"
    RUNNING=1
  else
    echo "systemd 服务：未运行"
  fi
fi

if [ "$(uname -s)" = "Darwin" ] && [ -f "$HOME/Library/LaunchAgents/com.personal-blog.plist" ]; then
  if launchctl list 2>/dev/null | grep -q com.personal-blog; then
    echo "launchd 服务：运行中"
    RUNNING=1
  else
    echo "launchd 服务：未运行"
  fi
fi

if [ "$RUNNING" = "1" ]; then
  exit 0
fi
exit 3
