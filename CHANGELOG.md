# 更新记录

## 未发布（优化与安全加固）

### 修复
- **草稿泄露**：未发布（`published=0`）的文章此前可通过 `/post/<id>` 被匿名访问，现仅管理员可预览。
- **Markdown 线程安全**：全局 `Markdown` 实例在 waitress 多线程下会串内容，改为每次渲染新建实例。
- 点赞接口不再接受草稿文章；埋点不再记录不存在或未发布文章的 `post_id`。

### 安全
- 文章 HTML 渲染前经 `nh3` 清洗（移除脚本、事件属性、`javascript:` 链接，限制 `style` 属性），同时保留富文本编辑器产生的排版、视频嵌入、代码块和表格。后台编辑页同样清洗。
- 上传校验文件头与扩展名一致；JPEG/WebP 重新编码以去除 EXIF（含 GPS），并按 EXIF 方向转正。动画 WebP 与 PNG/GIF 不重新编码。
- 管理员会话新增版本号：修改用户密码、关闭两步验证、删除用户后，其他设备上的登录立即失效。
- TOTP 验证码单次有效，防止重放。
- 限流：IPv6 按 /64 聚合；限流表超限时保留最新与已锁定项，而不是整体清空。

### 性能
- SQLite 启用 WAL、`synchronous=NORMAL` 与 10 秒写超时。
- 新增索引 `analytics(event, post_id)` 与 `posts(published, is_private, created_at)`。
- 首页分页（每页 12 篇），列表查询不再读取文章正文。
- `get_settings()` 每个请求只查询一次，写入后自动失效缓存。

### 变更
- 页脚不再默认显示占位备案号；旧版本预置的占位值会在升级时自动清空。
- 同一访客 30 分钟内重复打开同一篇文章只计一次浏览。
- `seed_analytics` 使用独立随机数生成器，不再污染全局随机状态。
- 备份建议改为使用 `./backup.sh`（WAL 模式下直接复制 `blog.db` 可能不完整）。

### 工程
- 新增依赖：`nh3==0.3.7`。
- 新增回归测试 `tests/test_regressions.py`（19 项），运行：`python3 -m unittest discover -s tests -v`。
- `.gitignore` 排除 `blog.db-wal`、`blog.db-shm`。

### 升级注意
- 重新执行安装命令即可，数据库与上传文件会保留。
- 如有旧文章依赖脚本或特殊 CSS，升级后会被清洗掉，请抽查几篇。
- 已知未处理：默认监听明文 HTTP（建议配合 Caddy/Nginx 启用 HTTPS 并设置 `SESSION_COOKIE_SECURE=1`）；`analytics` 表无清理策略（浏览量由该表计算，清理需先做汇总表）；临时登录密钥无有效期；删除文章不会清理其上传文件。
