#!/usr/bin/env bash
# 卸载博客运行环境（默认保留 blog.db、secret_key、上传文件）
# 加 --purge 会删除全部数据，请谨慎使用。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PURGE=0
if [ "${1:-}" = "--purge" ]; then
  PURGE=1
fi

echo "==> 停止博客"
./stop.sh || true

if [ "$(uname -s)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.personal-blog.plist"
  if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" >/dev/null 2>&1 || true
    rm -f "$PLIST"
    echo "已移除 launchd 服务。"
  fi
elif command -v systemctl >/dev/null 2>&1 && [ -f /etc/systemd/system/personal-blog.service ]; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      SUDO="sudo"
    fi
  fi
  $SUDO systemctl disable --now personal-blog 2>/dev/null || true
  $SUDO rm -f /etc/systemd/system/personal-blog.service
  $SUDO systemctl daemon-reload 2>/dev/null || true
  echo "已移除 systemd 服务。"
fi

echo "==> 删除虚拟环境与日志"
rm -rf .venv logs blog.pid __pycache__
rm -f setup_token

if [ "$PURGE" = "1" ]; then
  echo
  echo "警告：--purge 将删除数据库、会话密钥和全部上传文件，且不可恢复。"
  printf "如果确认，请输入 PURGE："
  read -r ANSWER
  if [ "$ANSWER" != "PURGE" ]; then
    echo "已取消删除数据。运行环境已卸载。"
    exit 0
  fi
  rm -f blog.db secret_key
  find static/uploads -mindepth 1 -maxdepth 1 ! -name seed -exec rm -rf {} + 2>/dev/null || true
  echo "数据已删除。"
else
  echo "已保留数据：blog.db、secret_key、static/uploads/"
fi

echo "卸载完成。"
