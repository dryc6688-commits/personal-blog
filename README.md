# 个人博客（单体版）

当前默认使用 **单体版**：Flask + Jinja + SQLite，一个进程即可运行，不需要 Node、不需要构建、不需要前后端两套部署。

## 一键安装

要求：Python 3.9 或更高版本（Linux / macOS）。

```bash
cd 项目目录
chmod +x install.sh start.sh stop.sh status.sh uninstall.sh run.sh package.sh
./install.sh
```

安装脚本会自动完成：

1. 检查 Python 版本
2. 创建 `.venv` 虚拟环境
3. 安装依赖
4. 生成随机会话密钥 `secret_key`
5. 初始化数据库
6. 后台启动服务

安装完成后访问：

- 前台：http://127.0.0.1:8000
- 首次设置：http://127.0.0.1:8000/setup

首次访问会进入三步引导：

1. 设置后台隐秘路径和二级密码
2. 设置管理员用户名和密码
3. 绑定 Authenticator，并保存一次性临时密钥

完成引导前，站点不可正常使用；完成后按「隐秘路径 → 二级密码 → 管理员密码 → 动态验证码」登录后台。

### 安装选项

```bash
./install.sh --port 9000        # 使用 9000 端口
./install.sh --host 127.0.0.1   # 只允许本机访问
./install.sh --no-start         # 只安装，不启动
sudo ./install.sh --service     # 注册为系统服务（Linux systemd；macOS 用普通用户运行）
```

### 常用命令

```bash
./start.sh     # 后台启动
./stop.sh      # 停止
./status.sh    # 查看状态
```

日志位于 `logs/blog.log`。

### 系统服务（可选）

如果使用 `--service` 安装为系统服务，请用对应命令管理：

```bash
# Linux systemd
sudo systemctl status personal-blog
sudo systemctl restart personal-blog
sudo systemctl stop personal-blog

# macOS launchd
launchctl list | grep com.personal-blog
launchctl unload ~/Library/LaunchAgents/com.personal-blog.plist
launchctl load ~/Library/LaunchAgents/com.personal-blog.plist
```

### 制作分发包

把项目发给别人前，先生成不含个人数据的安装包：

```bash
./package.sh
```

会生成 `dist/personal-blog-YYYYMMDD.tar.gz`，其中不包含：

- `blog.db`
- `secret_key`
- `.env`
- `static/uploads/` 中除 `seed/` 外的上传文件
- `deploy/backups/`
- 已归档的 `backend/`、`frontend/`

对方解压后执行：

```bash
tar -xzf personal-blog-YYYYMMDD.tar.gz
cd personal-blog-YYYYMMDD
./install.sh
```

即可完成部署并进入首次设置向导。

### 手动开发模式

不想用脚本时：

```bash
pip3 install -r requirements.txt
python3 app.py
```

调试模式：

```bash
DEBUG=1 python3 app.py
```

> macOS 的 AirPlay 占用 5000 端口，所以默认使用 8000。

### 反向代理 / HTTPS

生产环境建议用 Nginx 或 Caddy 反向代理到 `127.0.0.1:8000`，并配置 HTTPS。启用 HTTPS 后建议：

```bash
SESSION_COOKIE_SECURE=1 ./start.sh
```

或写入 `.env`（参考 `.env.example`）。


## 从 GitHub 一键安装

本项目已发布到 GitHub：

```
https://github.com/dryc6688-commits/personal-blog
```

一行命令安装：

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh | bash
```

带安装参数：

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
  | bash -s -- --port 9000
```

默认安装到 `~/personal-blog`，可用 `--dir` 指定：

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
  | bash -s -- --dir /opt/personal-blog --port 8000
```

`bootstrap.sh` 会自动克隆仓库、更新已有代码，然后调用 `install.sh`。

### 发布自己的副本

如果你 Fork 或复制了本项目，需要把 `bootstrap.sh` 里的仓库地址改成你自己的：

```bash
REPO_URL="${REPO_URL:-https://github.com/你的用户名/你的仓库.git}"
```

然后提交并推送。README 里的 `dryc6688-commits/personal-blog` 也替换成你的仓库地址即可。

首次上传到 GitHub：

```bash
git init -b main
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/你的仓库.git
git push -u origin main
```

`.gitignore` 已排除数据库、密钥、上传文件和个人配置，不会把敏感数据传到 GitHub。

## 功能

- 文章：图文 / 代码教程 / 视频 / 图文视频混排
- 代码高亮 + 一键复制
- 图片画廊、视频嵌入、灯箱
- 分类筛选（一篇文章可多分类）
- 友链管理（权重排序）
- 音乐播放器（圆盘 / 音乐卡片、音量、进度）
- 弹窗推送（纯图片 / 纯文字 / 图片+文字，手动关闭 / 点击外部关闭 / 倒计时）
- 点赞、打赏、文章基础访问量
- 文章密码、私密入口与私密文章
- 数据统计与埋点
- 用户管理、LOGO、备案信息、富文本编辑器
- 文件上传

## 数据位置

- 数据库：`blog.db`
- 上传文件：`static/uploads/`
- 会话密钥：`secret_key`
- 运行配置（可选）：`.env`
- 日志：`logs/blog.log`

请定期备份 `blog.db`、`secret_key` 和 `static/uploads/`。

## 目录说明

```
app.py            单体版后端
templates/        页面模板
static/           前端资源与上传文件
blog.db           当前数据库
requirements.txt  依赖
backend/          前后端分离版后端（已停止，保留归档）
frontend/         前后端分离版前端（已停止，保留归档）
deploy/           分离版部署脚本 + 本次切换前的数据备份
legacy/           空目录（原单体版文件已恢复到根目录）
```

## 数据备份

本次从分离版切回单体版前的完整备份在：

```
deploy/backups/
```

包含两套数据库和上传文件。确认新版数据无误后可自行清理。

## 维护建议

- 日常写文章只需运行 `./start.sh`
- 不需要启动 Vite / API 两个服务
- 不需要 Node.js
- 修改页面直接改 `templates/` 和 `static/`
- 定期备份 `blog.db` 和 `static/uploads/`

## 安全加固（已启用）

- **SECRET_KEY**：首次启动自动生成到 `secret_key`（权限 600），不再使用公开默认值。生产环境建议改用环境变量 `SECRET_KEY`。
- **密码哈希**：二级密码、管理员密码、私密入口密码、文章密码改为 **PBKDF2-SHA256（60 万次迭代 + 随机盐）**；旧的 SHA-256 哈希会在下次成功登录 / 解锁时自动升级。
- **失败限流**：二级密码、管理员登录、私密入口、文章密码连续失败 **8 次锁定 15 分钟**（进程内计数，重启后清零）。
- **Cookie**：`HttpOnly` + `SameSite=Strict`；HTTPS 环境请设置 `SESSION_COOKIE_SECURE=1`。
- **DEBUG 默认关闭**：开发时可 `DEBUG=1 python3 app.py`。
- 首次部署会强制设置二级密码、管理员账号和 Authenticator，不再使用默认密码。
- 请备份 `secret_key` 文件；删除后所有登录会话会失效（数据不受影响）。

## Authenticator 两步验证

后台 →「设置」→「两步验证（Authenticator）」：

1. 点击「启用 Authenticator」
2. 用 Google Authenticator / Microsoft Authenticator / Authy 扫描二维码
3. 输入 App 显示的 6 位验证码确认绑定

启用后的登录流程：

```
隐秘路径 → 二级密码 → 管理员密码 → Authenticator 动态验证码 → 后台
```

### 一次性临时登录密钥

启用两步验证后，可在设置中点击「生成一次性临时登录密钥」：

- 只显示一次
- 不设有效期
- 使用一次后立即失效
- 在两步验证页面展开「使用一次性临时登录密钥」输入

它用于手机丢失 / Authenticator 不可用时，仍然需要管理员密码。

### 关闭 / 重新绑定

- 关闭两步验证需要输入当前管理员密码
- 「重新绑定 Authenticator」会生成新的密钥，旧绑定失效

### 注意

- TOTP 密钥保存在 `settings` 表中，请保护好 `blog.db`
- 如果同时丢失 Authenticator 和临时密钥，可在数据库中临时关闭：
  ```sql
  UPDATE settings SET value='0' WHERE key='admin_totp_enabled';
  ```
