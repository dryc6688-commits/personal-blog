#!/usr/bin/env bash
# 个人博客一键安装脚本（macOS / Linux）
# 用法：./install.sh [--port 8000] [--host 0.0.0.0] [--service] [--no-start]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

chmod +x install.sh start.sh stop.sh status.sh uninstall.sh run.sh 2>/dev/null || true

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
DO_START=1
DO_SERVICE=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<EOF
个人博客一键安装脚本

用法：
  ./install.sh [选项]

选项：
  --host HOST       监听地址，默认 0.0.0.0（所有网卡）
  --port PORT       监听端口，默认 8000
  --service         安装为系统服务（Linux systemd / macOS launchd）
  --no-start        安装完成后不自动启动
  -h, --help        显示帮助

示例：
  ./install.sh
  ./install.sh --port 9000
  sudo ./install.sh --port 80 --service

安装完成后访问：
  http://<服务器公网IP>:8000/setup
  （首次访问会进入三步引导：二级密码、管理员账号、Authenticator）
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:?--host 需要参数}"
      shift 2
      ;;
    --host=*)
      HOST="${1#*=}"
      shift
      ;;
    --port)
      PORT="${2:?--port 需要参数}"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    --service)
      DO_SERVICE=1
      shift
      ;;
    --no-start)
      DO_START=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "端口无效：$PORT" >&2
  exit 1
fi
if [ -z "$HOST" ]; then
  echo "监听地址不能为空" >&2
  exit 1
fi

echo "==> 个人博客一键安装"
echo "    项目目录：$ROOT"
echo "    监听地址：$HOST:$PORT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "未找到 ${PYTHON_BIN}，请先安装 Python 3.9 或更高版本。" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Python 版本过低：$("$PYTHON_BIN" --version 2>&1)，需要 3.9 或更高版本。" >&2
  exit 1
fi
echo "[1/5] Python 检查通过：$("$PYTHON_BIN" --version 2>&1)"

# 保存安装时的监听配置，后续 ./start.sh 会自动沿用
"$PYTHON_BIN" - "$HOST" "$PORT" <<'PY'
import os
import sys

host, port = sys.argv[1], sys.argv[2]
path = ".env"
lines = []
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

wanted = {"HOST": host, "PORT": port}
seen = set()
out = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        out.append(line)
        continue
    key = stripped.split("=", 1)[0].strip()
    if key in wanted:
        out.append("%s=%s\n" % (key, wanted[key]))
        seen.add(key)
    else:
        out.append(line)
for key, value in wanted.items():
    if key not in seen:
        out.append("%s=%s\n" % (key, value))
if not any(line.strip().startswith("THREADS=") for line in out):
    out.append("THREADS=4\n")
if not any(line.strip().startswith("# 由 install.sh") for line in out):
    out.insert(0, "# 由 install.sh 生成；可手动修改\n")
with open(path, "w", encoding="utf-8") as f:
    f.writelines(out)
PY


if [ ! -x ".venv/bin/python" ]; then
  echo "[2/5] 创建虚拟环境 .venv ..."
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo "创建虚拟环境失败。" >&2
    echo "Debian/Ubuntu 请先执行：sudo apt install -y python3-venv" >&2
    exit 1
  fi
else
  echo "[2/5] 虚拟环境已存在，跳过创建"
fi

echo "[3/5] 安装依赖 ..."
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip >/dev/null
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt

if [ ! -s secret_key ]; then
  echo "[4/5] 生成会话密钥 secret_key ..."
  .venv/bin/python - <<'PY'
import os
import secrets

key = secrets.token_hex(32)
with open("secret_key", "w", encoding="utf-8") as f:
    f.write(key)
os.chmod("secret_key", 0o600)
PY
else
  echo "[4/5] 会话密钥已存在，保留不变"
fi
chmod 600 secret_key 2>/dev/null || true

echo "[5/5] 初始化数据库 ..."
.venv/bin/python -c "import app" >/dev/null
mkdir -p logs

if [ "$DO_SERVICE" = "1" ]; then
  echo "==> 注册系统服务 ..."
  if [ "$(uname -s)" = "Darwin" ]; then
    if [ "$(id -u)" -eq 0 ]; then
      echo "macOS 请使用普通用户运行 --service，不要加 sudo。" >&2
      exit 1
    fi
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST="$PLIST_DIR/com.personal-blog.plist"
    mkdir -p "$PLIST_DIR" logs
    PLIST_PATH="$PLIST" ROOT_DIR="$ROOT" BLOG_HOST="$HOST" BLOG_PORT="$PORT" \
      .venv/bin/python - <<'PY'
import os
from xml.sax.saxutils import escape

plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.personal-blog</string>
  <key>ProgramArguments</key>
  <array><string>{run}</string></array>
  <key>WorkingDirectory</key><string>{root}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOST</key><string>{host}</string>
    <key>PORT</key><string>{port}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
""".format(
    run=escape(os.path.join(os.environ["ROOT_DIR"], "run.sh")),
    root=escape(os.environ["ROOT_DIR"]),
    host=escape(os.environ["BLOG_HOST"]),
    port=escape(os.environ["BLOG_PORT"]),
    log=escape(os.path.join(os.environ["ROOT_DIR"], "logs", "blog.log")),
)
with open(os.environ["PLIST_PATH"], "w", encoding="utf-8") as f:
    f.write(plist)
PY
    launchctl unload "$PLIST" >/dev/null 2>&1 || true
    launchctl load "$PLIST"
    echo "已注册 launchd 服务：$PLIST"
    echo "查看状态：launchctl list | grep com.personal-blog"
  elif command -v systemctl >/dev/null 2>&1; then
    SERVICE_NAME="personal-blog"
    UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
    RUN_USER="$(id -un)"
    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
      if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
      else
        echo "注册 systemd 服务需要 root 权限，请使用 sudo 运行。" >&2
        exit 1
      fi
    elif [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
      RUN_USER="$SUDO_USER"
      chown -R "$RUN_USER": "$ROOT" 2>/dev/null || true
    fi
    TMP_UNIT="$(mktemp)"
    cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Personal Blog (Flask + SQLite)
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$ROOT
Environment=HOST=$HOST
Environment=PORT=$PORT
ExecStart="$ROOT/run.sh"
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    $SUDO cp "$TMP_UNIT" "$UNIT"
    rm -f "$TMP_UNIT"
    $SUDO chmod 644 "$UNIT"
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME"
    $SUDO systemctl restart "$SERVICE_NAME"
    if ! $SUDO systemctl is-active --quiet "$SERVICE_NAME"; then
      echo "服务启动失败，请查看日志：" >&2
      $SUDO systemctl status "$SERVICE_NAME" --no-pager 2>&1 | tail -n 20 >&2 || true
      exit 1
    fi
    echo "已注册 systemd 服务：${UNIT}（用户：${RUN_USER}）"
    echo "查看状态：sudo systemctl status $SERVICE_NAME"
    echo "查看日志：sudo journalctl -u $SERVICE_NAME -f"
  else
    echo "当前系统没有 systemd，无法注册服务；请改用 ./start.sh 后台启动。" >&2
    exit 1
  fi
  DO_START=0
fi

if [ "$DO_START" = "1" ]; then
  echo "==> 启动博客 ..."
  START_CODE=0
  HOST="$HOST" PORT="$PORT" ./start.sh || START_CODE=$?
  if [ "$START_CODE" -eq 2 ]; then
    echo "端口 $PORT 已被占用，跳过启动。"
    echo "如果博客已经在运行，可直接访问；否则请改用 ./install.sh --port 其他端口。"
  elif [ "$START_CODE" -ne 0 ]; then
    echo "启动失败，请查看 logs/blog.log。" >&2
    exit 1
  fi
else
  echo "==> 已跳过自动启动"
fi

if [ "$HOST" = "0.0.0.0" ] || [ "$HOST" = "::" ]; then
  ACCESS_URL="http://<服务器公网IP>:$PORT"
  LOCAL_URL="http://127.0.0.1:$PORT"
else
  ACCESS_URL="http://$HOST:$PORT"
  LOCAL_URL=""
fi

if [ -n "$LOCAL_URL" ]; then
  cat <<EOF

安装完成。

  服务器访问：${ACCESS_URL}
  首次设置：${ACCESS_URL}/setup
  本机访问：${LOCAL_URL}

首次访问会进入三步引导：
  1. 设置隐秘路径和二级密码
  2. 设置管理员用户名和密码
  3. 绑定 Authenticator，并保存一次性临时密钥

EOF
else
  cat <<EOF

安装完成。

  访问地址：${ACCESS_URL}
  首次设置：${ACCESS_URL}/setup

首次访问会进入三步引导：
  1. 设置隐秘路径和二级密码
  2. 设置管理员用户名和密码
  3. 绑定 Authenticator，并保存一次性临时密钥

EOF
fi

if [ "$DO_SERVICE" = "1" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    cat <<EOF
服务管理（launchd）：
  launchctl list | grep com.personal-blog
  launchctl unload ~/Library/LaunchAgents/com.personal-blog.plist
  launchctl load ~/Library/LaunchAgents/com.personal-blog.plist
EOF
  else
    cat <<EOF
服务管理（systemd）：
  sudo systemctl status personal-blog
  sudo systemctl restart personal-blog
  sudo systemctl stop personal-blog
EOF
  fi
else
  cat <<EOF
常用命令：
  ./start.sh     后台启动
  ./stop.sh      停止
  ./status.sh    查看状态
  ./uninstall.sh 卸载（保留数据）
EOF
fi

cat <<EOF

数据文件：blog.db、secret_key、static/uploads/
请定期备份以上内容。
EOF
