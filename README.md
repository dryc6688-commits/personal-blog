# 个人博客 · 一键部署版（基于 100% AI 开发）

一个开箱即用的个人博客系统，基于 **Flask + SQLite**。一个进程即可运行，不需要 Node.js、不需要前端构建、不需要单独安装数据库。

自带完整后台、首次设置向导、Authenticator 两步验证和 Linux 一键安装脚本，**懒人一键拉取即可使用**。

---

## 项目特点

- **一条命令部署**：自动创建虚拟环境、安装依赖、生成密钥、初始化数据库并启动。
- **零前端构建**：使用 Jinja 模板和原生静态资源，不需要 Node.js、Vite 或 npm。
- **内置六套主题**：Butterfly、PaperMod、Stack、Fluid、NexT、Blowfish，后台一键切换，无需改代码。
- **首次设置向导**：必须先完成向导设置，无任何默认账号密码；Authenticator 可跳过，安全性大幅提高。
- **推荐服务器**：阿里云、腾讯云的香港轻量云服务器即可，免去备案麻烦。
- **开发说明**：本项目使用 DeepSeek V4.1 Flash 1017 构建，总消耗 338,485,755 Tokens。

## 项目功能

- 图片、文字、视频单独及混排发布
- 代码高亮与一键复制
- 音乐播放器（支持网易云、QQ 音乐等接入）
- 分类筛选、友链管理
- 弹窗推送（纯图、纯文、图文等三种模式，定时、单次、每次多种方案）
- 单篇文章密码、只给特定的人群看
- 私密空间（加密类目 关联后的内容只有得到空间密码才能观看）
- 数据统计、备案信息一键填写
- 富文本编辑器、文字大小粗细颜色均可随意组合
- 点赞功能 浏览量功能 均内置基础数值补充
- 打赏功能（支持V/Q）
- 全设备自适应尺寸展示
- 内置 6 套主题：Butterfly / PaperMod / Stack / Fluid / NexT / Blowfish
- 首页分页（每页 12 篇）、草稿预览、上传图片自动去除 EXIF
---

## 快速开始（Linux 服务器）

### 1. 环境要求

- Linux 服务器（推荐 Ubuntu 22.04 / 24.04、Debian 12、Rocky Linux 9、AlmaLinux 9）
- Python 3.9 或更高版本
- `git`、`curl`
- 如果使用 `--service`，需要 systemd 和 sudo 权限

安装系统依赖：

| 系统 | 命令 |
|---|---|
| Debian / Ubuntu | `sudo apt update && sudo apt install -y git curl python3 python3-venv python3-pip` |
| RHEL / Rocky / AlmaLinux | `sudo dnf install -y git curl python3 python3-pip` |

### 2. 一条命令安装

> 不需要修改命令中的 `--host 0.0.0.0`，它表示监听所有网卡。浏览器访问时，把 `<服务器公网IP>` 换成你的服务器 IP。

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
  | bash -s -- --dir "$HOME/personal-blog" --host 0.0.0.0 --port 8000 --service
```

参数说明：

| 参数 | 作用 |
|---|---|
| `--dir "$HOME/personal-blog"` | 安装目录 |
| `--host 0.0.0.0` | 监听所有网卡，服务器 IP 才能访问 |
| `--port 8000` | 博客监听端口 |
| `--service` | 注册为 systemd 服务，开机自动启动 |

> `--service` 会调用 `sudo systemctl`，安装过程中可能提示输入服务器密码。
> 如果服务器没有 systemd 或不想注册服务，去掉 `--service`，之后用 `./start.sh` 启动即可。

### 3. 开放端口

如果服务器启用了防火墙，需要放行 8000 端口：

```bash
sudo ufw allow 8000/tcp
```

云服务器还需要在控制台的 **安全组 / 防火墙** 中放行 `8000/TCP`。

### 4. 打开首次设置

在浏览器访问：

```
http://<服务器公网IP>:8000/setup
```

把 `<服务器公网IP>` 换成你的服务器公网 IP。

首次访问需要先输入**初始化令牌**。安装完成时终端会输出「首次设置令牌」，也保存在项目根目录的 `setup_token` 文件中（权限 `600`）。完成初始化后该文件会自动删除。

验证令牌后进入三步引导：

1. 设置后台隐秘路径和二级密码
2. 设置管理员用户名和密码
3. 绑定 Authenticator（可跳过），并保存一次性临时登录密钥（丢失Authenticator时可用）

如果暂时不想绑定 Authenticator，在第 3 步点击「暂不绑定，跳过」即可完成设置。之后登录后台，在「设置 → 两步验证」中可以随时启用。

完成引导前，访问任何页面都会跳转到 `/setup`。**部署完成后请立即完成设置**，不要把未初始化完成的实例长期暴露在公网。

完成后登录流程：

```
http(s)://你的域名或服务器IP/你在向导设置的路径
  → 二级密码
  → 管理员账号密码
  →（如果已启用）Authenticator 6 位动态验证码
  → 成功登陆后台
```

---

## 日常管理

如果安装时使用了 `--service`：

```bash
sudo systemctl status personal-blog
sudo systemctl restart personal-blog
sudo systemctl stop personal-blog
sudo systemctl start personal-blog
sudo journalctl -u personal-blog -f
```

如果没有使用系统服务：

```bash
cd ~/personal-blog
./start.sh     # 后台启动
./stop.sh      # 停止
./status.sh    # 查看状态
```

日志位置：

```
~/personal-blog/logs/blog.log
```

---

## 主题切换

后台 →「设置」→「前台主题」：

| 主题 | 风格 |
|---|---|
| **Butterfly 卡片风**（默认） | 圆角卡片、柔和渐变、封面图，视觉更丰富 |
| **PaperMod 极简风** | 留白充足、列表式排版，适合长时间阅读 |
| **Stack 杂志风** | 深色 Hero、大图卡片、杂志式首页 |
| **Fluid 清新风** | 蓝青渐变、轻盈卡片和清爽留白 |
| **NexT 经典风** | 黑白排版、经典博客气质，阅读优先 |
| **Blowfish 暗夜风** | 深色背景、霓虹渐变和彩色卡片，适合夜间浏览 |

选择后保存，刷新前台即可生效。

主题样式位于：

```text
static/themes/butterfly/theme.css
static/themes/paper/theme.css
static/themes/stack/theme.css
static/themes/fluid/theme.css
static/themes/next/theme.css
static/themes/blowfish/theme.css
```

需要自定义颜色或细节时，直接修改对应主题的 CSS 即可，不会影响后台管理页面。

## 更新版本

重新执行同一条安装命令即可。`bootstrap.sh` 会自动拉取最新代码，`install.sh` 会保留数据库和上传文件。

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
  | bash -s -- --dir "$HOME/personal-blog" --host 0.0.0.0 --port 8000 --service
```

> 大版本更新前建议先备份 `blog.db`、`secret_key` 和 `static/uploads/`。

升级后行为变化与注意事项见 [CHANGELOG.md](CHANGELOG.md)，主要有：

- 新增依赖 `nh3`，重新执行安装命令会自动安装。
- 数据库启用 WAL 模式，运行时会多出 `blog.db-wal`、`blog.db-shm`，请用 `./backup.sh` 备份。
- 文章 HTML 渲染前会被清洗；浏览量对同一访客 30 分钟内的重复打开只计一次。

---

## 数据与备份

| 内容 | 位置 |
|---|---|
| 数据库 | `blog.db`（运行时另有 `blog.db-wal`、`blog.db-shm`） |
| 上传文件 | `static/uploads/` |
| 会话密钥 | `secret_key` |
| 运行配置（可选） | `.env` |
| 日志 | `logs/blog.log` |

推荐使用内置备份脚本（通过 SQLite 在线备份接口生成一致的快照；数据库启用了 WAL 模式，直接 `tar` 或 `cp` 运行中的 `blog.db` 可能得到不完整的备份）：

```bash
./backup.sh
```

脚本会备份数据库、`secret_key`、`.env` 和上传文件到 `backups/`，默认保留 14 天。建议加入 cron：

```bash
0 3 * * * /home/你的用户名/personal-blog/backup.sh >> /home/你的用户名/personal-blog/logs/backup.log 2>&1
```

恢复时把文件解压回原目录即可。`secret_key` 丢失会导致所有登录会话失效，但不会影响文章数据。

---

## 反向代理与 HTTPS（推荐）

生产环境建议用 Nginx 或 Caddy 反向代理到 `127.0.0.1:8000`，并配置 HTTPS。

Nginx 示例：

```nginx
server {
    listen 80;
    server_name blog.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

反向代理场景请在 `.env` 中加入：

```bash
TRUST_PROXY=1
```

启用 HTTPS 后同时加入：

```bash
SESSION_COOKIE_SECURE=1
```

然后重启服务：

```bash
sudo systemctl restart personal-blog
```

---

## 安全说明

- 首次初始化需要安装脚本生成的**初始化令牌**，防止未完成设置的站点被他人抢先接管。
- 所有 POST 表单和 AJAX 写操作带 **CSRF 校验**，Cookie 同时启用 `SameSite=Strict`。
- 首次启动自动生成随机 `secret_key`，权限 `600`，不使用公开默认密钥。
- 二级密码、管理员密码、私密入口密码、文章密码使用 **PBKDF2-SHA256（60 万次迭代 + 随机盐）**。
- 二级密码、管理员登录、私密入口、文章密码连续失败 **8 次锁定 15 分钟**，限流按真实 IP 计算，支持可信反向代理。
- 后台入口隐藏，需要先访问隐秘路径并通过二级密码。
- 支持 Authenticator TOTP 两步验证，可在首次向导中跳过，之后在后台随时启用。
- 一次性临时登录密钥不设有效期，只能使用一次，使用后立即失效。
- 管理员会话 **60 分钟无操作自动过期**，最长 **12 小时**。
- 已移除默认管理员密码兜底；历史默认私密密码 `123456` 会强制失效。
- 禁用 SVG 上传；上传时校验文件头与扩展名一致，JPEG/WebP 自动去除 EXIF（含 GPS 位置）。
- 文章 HTML 渲染前经 `nh3` 清洗：移除脚本、事件属性和 `javascript:` 链接，仅保留编辑器产生的排版与视频嵌入。
- 未发布的草稿仅管理员可预览。
- 修改密码、关闭两步验证、删除用户后，其他设备上的管理员登录立即失效。
- TOTP 验证码单次有效，防止被重放。
- 安全响应头：`CSP`、`X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Permissions-Policy`；HTTPS 下自动启用 HSTS。
- 关键操作写入 `logs/audit.log`，便于排查异常登录和设置变更。
- Cookie 默认 `HttpOnly` + `SameSite=Strict`；HTTPS 环境请开启 `SESSION_COOKIE_SECURE=1`。
- 默认关闭 Flask DEBUG 模式。
- `.gitignore` 已排除数据库、密钥、上传文件和个人配置，不会误传到 GitHub。

建议：

1. 部署完成后立即完成 `/setup` 向导。
2. 尽快配置 HTTPS。
3. 定期备份 `blog.db`、`secret_key` 和 `static/uploads/`。
4. 不要公开 `blog.db` 和 `secret_key`。

---

## 手动开发模式

不想用一键脚本时：

```bash
pip3 install -r requirements.txt
python3 app.py
```

调试模式：

```bash
DEBUG=1 python3 app.py
```

默认访问 `http://127.0.0.1:8000`。macOS 的 AirPlay 占用 5000 端口，所以项目默认使用 8000。

运行测试（无需额外依赖）：

```bash
python3 -m unittest discover -s tests -v
```

---

## 常见问题

### 端口被占用

```bash
# 查看占用 8000 端口的进程
sudo lsof -i :8000
```

换一个端口重新安装：

```bash
curl -fsSL https://raw.githubusercontent.com/dryc6688-commits/personal-blog/main/bootstrap.sh \
  | bash -s -- --dir "$HOME/personal-blog" --host 0.0.0.0 --port 9001 --service
```

### 初始化令牌在哪里

安装完成时终端会输出「首次设置令牌」，也保存在：

```bash
cat ~/personal-blog/setup_token
```

完成初始化后文件会自动删除。如果已经完成初始化，就不再需要该令牌。

### 浏览器打不开服务器 IP

依次检查：

1. 安装命令里是否是 `--host 0.0.0.0`
2. 服务器防火墙是否放行端口
3. 云服务器安全组是否放行端口
4. 服务是否正常运行

```bash
sudo systemctl status personal-blog
curl -I http://127.0.0.1:8000
```

### Python 版本过低

```bash
python3 --version
```

需要 3.9 或更高版本。Ubuntu 20.04 等旧系统建议升级系统或使用新版发行版。

### 创建虚拟环境失败

Debian / Ubuntu 安装：

```bash
sudo apt install -y python3-venv
```

### 查看服务日志

```bash
sudo journalctl -u personal-blog -n 100 --no-pager
```

或：

```bash
tail -f ~/personal-blog/logs/blog.log
```

### 忘记 Authenticator，临时密钥也丢失

如果数据库还能访问，可以临时关闭两步验证：

```sql
UPDATE settings SET value='0' WHERE key='admin_totp_enabled';
```

操作前请先备份 `blog.db`。

---

