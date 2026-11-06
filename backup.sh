#!/usr/bin/env bash
# 备份博客数据库、会话密钥、配置和上传文件
# 建议加入 cron：0 3 * * * /path/to/personal-blog/backup.sh >> /path/to/personal-blog/logs/backup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

if [ ! -f blog.db ]; then
  echo "未找到 blog.db，无法备份。" >&2
  exit 1
fi

PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

DB_OUT="$BACKUP_DIR/blog_$TS.db"
"$PYTHON" - "$ROOT/blog.db" "$DB_OUT" <<'PY'
import sqlite3
import sys

src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
try:
    with dst:
        src.backup(dst)
finally:
    dst.close()
    src.close()
PY

if [ -f secret_key ]; then
  cp secret_key "$BACKUP_DIR/secret_key_$TS"
fi
if [ -f .env ]; then
  cp .env "$BACKUP_DIR/env_$TS"
fi

if [ -d static/uploads ]; then
  tar -czf "$BACKUP_DIR/uploads_$TS.tar.gz" -C static uploads
fi

chmod 600 "$BACKUP_DIR"/* 2>/dev/null || true
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true

echo "备份完成：$BACKUP_DIR"
ls -1 "$BACKUP_DIR" | tail -n 10
