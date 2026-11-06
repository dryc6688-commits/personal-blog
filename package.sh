#!/usr/bin/env bash
# 制作可分发的干净安装包（不包含数据库、密钥、上传文件和个人配置）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

NAME="personal-blog-$(date +%Y%m%d)"
DIST="$ROOT/dist"
STAGE="$(mktemp -d)"
DEST="$STAGE/$NAME"
ARCHIVE="$DIST/$NAME.tar.gz"

cleanup() {
  rm -rf "$STAGE"
}
trap cleanup EXIT

mkdir -p "$DEST" "$DIST"

echo "==> 收集程序文件"
cp app.py wsgi.py requirements.txt README.md .gitignore .env.example "$DEST"/
cp install.sh start.sh stop.sh status.sh uninstall.sh run.sh bootstrap.sh backup.sh "$DEST"/
cp -R templates static "$DEST"/

# 只保留示例上传资源，排除真实上传内容
find "$DEST/static/uploads" -mindepth 1 -maxdepth 1 ! -name seed -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -name '*.pyc' -delete 2>/dev/null || true

chmod +x "$DEST"/*.sh
tar -czf "$ARCHIVE" -C "$STAGE" "$NAME"

echo "==> 已生成：$ARCHIVE"
echo "    解压后运行：./install.sh"
