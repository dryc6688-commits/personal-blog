#!/usr/bin/env bash
# GitHub 远程一键安装
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
#     | bash -s -- --dir "$HOME/personal-blog" --host 0.0.0.0 --port 8000 --service
#
# 也可以本地测试：
#   ./bootstrap.sh --repo /path/to/repo --dir /tmp/blog-test --port 8010
set -euo pipefail

# 上传到 GitHub 后，把这里改成你的仓库地址
REPO_URL="${REPO_URL:-https://github.com/dryc6688-commits/personal-blog.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/personal-blog}"
INSTALL_ARGS=()

usage() {
  cat <<EOF
GitHub 远程一键安装

用法：
  curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \\
    | bash -s -- --dir "\$HOME/personal-blog" --host 0.0.0.0 --port 8000 --service

选项：
  --repo URL        指定 Git 仓库地址
  --branch NAME     指定分支，默认 main
  --dir PATH        安装目录，默认 \$HOME/personal-blog
  -h, --help        显示帮助

其余参数会原样传给 install.sh，例如：
  --port 8000
  --host 0.0.0.0
  --service
  --no-start
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      REPO_URL="${2:?--repo 需要参数}"
      shift 2
      ;;
    --repo=*)
      REPO_URL="${1#*=}"
      shift
      ;;
    --branch)
      BRANCH="${2:?--branch 需要参数}"
      shift 2
      ;;
    --branch=*)
      BRANCH="${1#*=}"
      shift
      ;;
    --dir)
      INSTALL_DIR="${2:?--dir 需要参数}"
      shift 2
      ;;
    --dir=*)
      INSTALL_DIR="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [ $# -gt 0 ]; do
        INSTALL_ARGS+=("$1")
        shift
      done
      ;;
    *)
      INSTALL_ARGS+=("$1")
      shift
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "未找到 git，请先安装 git。" >&2
  exit 1
fi

echo "==> 仓库：$REPO_URL"
echo "==> 分支：$BRANCH"
echo "==> 目录：$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "==> 更新已有代码 ..."
  git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH" >/dev/null 2>&1 || true
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
elif [ -e "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]; then
  echo "目录已存在且不是 Git 仓库：$INSTALL_DIR" >&2
  echo "请换一个 --dir，或先备份并移走该目录。" >&2
  exit 1
else
  echo "==> 下载代码 ..."
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

if [ ! -f "$INSTALL_DIR/install.sh" ]; then
  echo "未找到 install.sh，仓库内容可能不完整。" >&2
  exit 1
fi

cd "$INSTALL_DIR"
chmod +x install.sh start.sh stop.sh status.sh uninstall.sh run.sh 2>/dev/null || true

if [ ${#INSTALL_ARGS[@]} -gt 0 ]; then
  exec ./install.sh "${INSTALL_ARGS[@]}"
else
  exec ./install.sh
fi
