#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个人博客 —— Flask + SQLite 单文件后端。

功能：
- 文章（图片 / 代码教程 / 视频）前台展示与后台增删改
- 代码高亮 + 一键复制（前端 highlight.js + 复制按钮）
- 音乐播放器：网易云 / QQ音乐 / 汽水音乐 / 直链音频
- 页脚备案信息（后台可配置）
- 首次启动自动写入 3 篇示例文章与示例音乐
"""

import base64
import hashlib
import hmac
import io
import json
import os
import random
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, date, timedelta

import pyotp
import qrcode
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from markdown import Markdown
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "blog.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "svg",
    "mp4", "webm", "ogg", "mov", "m4v",
    "mp3", "wav", "m4a", "aac", "flac",
}

RESERVED_PATHS = {
    "admin", "login", "api", "static", "post", "friends", "private",
    "uploads", "setup", "favicon.ico", "robots.txt",
}


def load_secret_key():
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    path = os.path.join(BASE_DIR, "secret_key")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                return key
        except OSError:
            pass
    key = secrets.token_hex(32)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


app = Flask(__name__)
app.config["SECRET_KEY"] = load_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512MB

md = Markdown(extensions=["fenced_code", "tables", "nl2br", "sane_lists", "toc"])

DEFAULT_SETTINGS = {
    "site_title": "我的个人博客",
    "site_subtitle": "记录灵感 · 影像 · 代码",
    "site_description": "一个关于生活、摄影与编程的个人小站。",
    "site_logo": "",
    "footer_text": "用代码记录生活",
    "icp": "粤ICP备00000000号-1",
    "police": "粤公网安备 00000000000000号",
    "police_url": "https://beian.mps.gov.cn/",
    "copyright": "© 2026 我的个人博客",
    "music_enabled": "1",
    "player_autoplay": "0",
    "player_style": "vinyl",
    "player_volume": "30",
    "likes_enabled": "1",
    "reward_enabled": "1",
    "reward_title": "赞赏支持",
    "reward_desc": "如果这篇文章对你有帮助，可以请我喝杯咖啡 ☕",
    "popup_enabled": "0",
    "popup_mode": "daily_first",
    "popup_title": "欢迎来到我的博客",
    "popup_content": "",
    "popup_content_mode": "both",
    "popup_image": "",
    "popup_button_text": "",
    "popup_button_url": "",
    "popup_link_target": "_blank",
    "popup_close_mode": "manual",
    "popup_countdown": "0",
    "popup_start": "",
    "popup_end": "",
    "popup_daily_once": "1",
    "private_enabled": "0",
    "private_label": "私密空间",
    "private_desc": "该区域内容仅通过右上角入口访问。",
    "private_password_hash": generate_password_hash("123456", method="pbkdf2:sha256:600000"),
    "admin_secret_path": "console-8f3c2a",
    "admin_gate_password_hash": generate_password_hash("admin2026", method="pbkdf2:sha256:600000"),
    "admin_totp_enabled": "0",
    "admin_totp_secret": "",
    "admin_temp_key_hash": "",
    "admin_temp_key_expires": "",
    "setup_completed": "0",
    "setup_step": "1",
    "admin_password": generate_password_hash("admin123", method="pbkdf2:sha256:600000"),
}

# 版权说明选项（参考 B 站等平台的版权声明）
COPYRIGHT_TYPES = {
    "original": {"label": "原创", "text": "未经作者授权，禁止转载"},
    "reprint": {"label": "转载", "text": "转载请务必注明出处"},
    "cc_by": {"label": "CC BY 4.0", "text": "署名"},
    "cc_by_nc": {"label": "CC BY-NC 4.0", "text": "署名 - 非商业性使用"},
    "cc_by_nc_sa": {"label": "CC BY-NC-SA 4.0", "text": "署名 - 非商业性使用 - 相同方式共享"},
    "public": {"label": "公共领域", "text": "可自由使用，无需署名"},
    "custom": {"label": "自定义", "text": ""},
}


# --------------------------------------------------------------------------
# 数据库
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'image',
    excerpt TEXT DEFAULT '',
    cover TEXT DEFAULT '',
    content TEXT DEFAULT '',
    images TEXT DEFAULT '[]',
    video_url TEXT DEFAULT '',
    video_poster TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    copyright_type TEXT DEFAULT 'original',
    copyright_text TEXT DEFAULT '',
    content_format TEXT DEFAULT 'markdown',
    is_private INTEGER DEFAULT 0,
    published INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT DEFAULT '',
    platform TEXT NOT NULL DEFAULT 'custom',
    ref TEXT DEFAULT '',
    audio_url TEXT DEFAULT '',
    cover TEXT DEFAULT '',
    sort INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS post_categories (
    post_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, category_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    path TEXT DEFAULT '',
    post_id INTEGER,
    category_id INTEGER,
    label TEXT DEFAULT '',
    visitor_id TEXT DEFAULT '',
    ip TEXT DEFAULT '',
    ua TEXT DEFAULT '',
    device TEXT DEFAULT 'pc',
    browser TEXT DEFAULT '',
    os TEXT DEFAULT '',
    referer TEXT DEFAULT '',
    demo INTEGER DEFAULT 0,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analytics_day ON analytics(day);
CREATE INDEX IF NOT EXISTS idx_analytics_event ON analytics(event);
CREATE INDEX IF NOT EXISTS idx_analytics_visitor ON analytics(visitor_id);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS friend_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    logo TEXT DEFAULT '',
    description TEXT DEFAULT '',
    weight INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS post_likes (
    post_id INTEGER NOT NULL,
    visitor_id TEXT NOT NULL,
    created_at TEXT,
    PRIMARY KEY (post_id, visitor_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reward_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'qr',
    image TEXT DEFAULT '',
    url TEXT DEFAULT '',
    note TEXT DEFAULT '',
    sort INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    created_at TEXT
);
"""


def ensure_columns(db):
    """为已有数据库补齐新增字段。"""
    cols = {row[1] for row in db.execute("PRAGMA table_info(posts)").fetchall()}
    additions = {
        "password_hash": "TEXT DEFAULT ''",
        "copyright_type": "TEXT DEFAULT 'original'",
        "copyright_text": "TEXT DEFAULT ''",
        "content_format": "TEXT DEFAULT 'markdown'",
        "base_views": "INTEGER DEFAULT 0",
        "show_views": "INTEGER DEFAULT 1",
        "is_private": "INTEGER DEFAULT 0",
    }
    for name, ddl in additions.items():
        if name not in cols:
            db.execute(f"ALTER TABLE posts ADD COLUMN {name} {ddl}")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    ensure_columns(db)
    # 初始化设置
    for k, v in DEFAULT_SETTINGS.items():
        db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))
    # 首次写入示例内容
    cur = db.execute("SELECT COUNT(*) FROM posts").fetchone()
    if cur[0] == 0:
        seed_posts(db)
    cur = db.execute("SELECT COUNT(*) FROM tracks").fetchone()
    if cur[0] == 0:
        seed_tracks(db)
    seed_categories(db)
    seed_analytics(db)
    seed_users(db)
    seed_friends(db)
    db.commit()
    db.close()


def seed_posts(db):
    now = datetime.now().isoformat(timespec="seconds")
    posts = [
        {
            "title": "秋日随手拍：光影与城市",
            "type": "image",
            "excerpt": "一次午后的散步，把城市的光影收进镜头里。",
            "cover": "/static/uploads/seed/seed-01.jpg",
            "images": [
                "/static/uploads/seed/seed-01.jpg",
                "/static/uploads/seed/seed-02.jpg",
                "/static/uploads/seed/seed-03.jpg",
                "/static/uploads/seed/seed-04.jpg",
            ],
            "content": (
                "这是一篇**图片文章**示例。后台可以上传多张图片，前台会以画廊形式展示。\n\n"
                "> 光线是摄影的语言，城市是它的稿纸。\n\n"
                "点击任意图片可以放大查看。你可以在后台「文章管理」中编辑或删除这篇示例。"
            ),
            "video_url": "",
            "video_poster": "",
        },
        {
            "title": "Python 快速排序：从原理到实现",
            "type": "code",
            "excerpt": "用分治思想理解快速排序，附 Python / JavaScript 实现与复杂度分析。",
            "cover": "",
            "images": [],
            "content": (
                "快速排序（Quicksort）是分治算法的经典代表。它选择一个基准值（pivot），"
                "把数组分成小于和大于基准的两部分，再递归排序。\n\n"
                "## 核心思路\n\n"
                "1. 选择基准元素\n"
                "2. 分区：小于基准放左边，大于基准放右边\n"
                "3. 递归处理左右子数组\n\n"
                "## Python 实现\n\n"
                "```python\n"
                "def quicksort(arr):\n"
                "    if len(arr) <= 1:\n"
                "        return arr\n"
                "    pivot = arr[len(arr) // 2]\n"
                "    left = [x for x in arr if x < pivot]\n"
                "    middle = [x for x in arr if x == pivot]\n"
                "    right = [x for x in arr if x > pivot]\n"
                "    return quicksort(left) + middle + quicksort(right)\n\n"
                "print(quicksort([3, 6, 8, 10, 1, 2, 1]))\n"
                "# [1, 1, 2, 3, 6, 8, 10]\n"
                "```\n\n"
                "## JavaScript 实现\n\n"
                "```javascript\n"
                "function quickSort(arr) {\n"
                "  if (arr.length <= 1) return arr;\n"
                "  const pivot = arr[Math.floor(arr.length / 2)];\n"
                "  const left = arr.filter(x => x < pivot);\n"
                "  const mid = arr.filter(x => x === pivot);\n"
                "  const right = arr.filter(x => x > pivot);\n"
                "  return [...quickSort(left), ...mid, ...quickSort(right)];\n"
                "}\n"
                "```\n\n"
                "## 复杂度\n\n"
                "| 情况 | 时间复杂度 |\n"
                "| --- | --- |\n"
                "| 平均 | O(n log n) |\n"
                "| 最坏 | O(n²) |\n"
                "| 空间 | O(log n) |\n\n"
                "## 运行测试\n\n"
                "```bash\n"
                "python3 -c \"import pytest; pytest test_sort.py -q\"\n"
                "```\n\n"
                "> 每段代码右上角都有「复制」按钮，点击即可一键复制。"
            ),
            "video_url": "",
            "video_poster": "",
        },
        {
            "title": "示例短片：SAMPLE FILM",
            "type": "video",
            "excerpt": "一段 8 秒的示例视频，用于展示视频嵌入效果。",
            "cover": "/static/uploads/seed/seed-01.jpg",
            "images": [],
            "content": (
                "这是一篇**视频文章**示例。后台可以填写视频直链（mp4/webm）"
                "或第三方嵌入地址（如 B 站、YouTube 的 iframe 链接）。\n\n"
                "视频下方同样支持正文、图片与代码块。你可以在后台自由替换这段示例。"
            ),
            "video_url": "/static/uploads/seed/seed-video.mp4",
            "video_poster": "/static/uploads/seed/seed-01.jpg",
        },
    ]
    for p in posts:
        db.execute(
            """INSERT INTO posts(title, type, excerpt, cover, content, images,
                                 video_url, video_poster, published, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (p["title"], p["type"], p["excerpt"], p["cover"], p["content"],
             json.dumps(p["images"], ensure_ascii=False), p["video_url"],
             p["video_poster"], 1, now, now),
        )


def seed_tracks(db):
    now = datetime.now().isoformat(timespec="seconds")
    tracks = [
        ("氛围和弦（本地示例）", "Seed Studio", "custom",
         "", "/static/uploads/seed/seed-ambient.mp3", "/static/uploads/seed/seed-01.jpg", 1),
        ("网易云音乐示例（后台可替换）", "网易云", "netease",
         "186016", "", "/static/uploads/seed/seed-02.jpg", 2),
        ("QQ 音乐示例（后台可替换）", "QQ音乐", "qq",
         "003OUlho2HcRHC", "", "/static/uploads/seed/seed-03.jpg", 3),
        ("汽水音乐示例（后台可替换）", "汽水音乐", "soda",
         "", "", "/static/uploads/seed/seed-04.jpg", 4),
    ]
    for t in tracks:
        db.execute(
            """INSERT INTO tracks(title, artist, platform, ref, audio_url, cover, sort, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (t[0], t[1], t[2], t[3], t[4], t[5], t[6], now),
        )


def seed_categories(db):
    """首次初始化默认分类，并按文章类型归类。"""
    seeded = db.execute("SELECT value FROM settings WHERE key='categories_seeded'").fetchone()
    if seeded:
        return
    if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        defaults = [("摄影", 1), ("代码", 2), ("视频", 3), ("生活", 4)]
        ids = {}
        for name, sort in defaults:
            cur = db.execute(
                "INSERT INTO categories(name, sort, created_at) VALUES(?,?,?)",
                (name, sort, now),
            )
            ids[name] = cur.lastrowid
        assign = {
            "image": ["摄影"],
            "code": ["代码"],
            "video": ["视频"],
            "mixed": ["视频", "代码"],
        }
        for pid, ptype in db.execute("SELECT id, type FROM posts").fetchall():
            for name in assign.get(ptype, []):
                db.execute(
                    "INSERT OR IGNORE INTO post_categories(post_id, category_id) VALUES(?,?)",
                    (pid, ids[name]),
                )
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('categories_seeded', '1')")


def seed_analytics(db):
    """首次启动预置最近 14 天演示统计数据，便于预览图表。"""
    seeded = db.execute("SELECT value FROM settings WHERE key='analytics_seeded'").fetchone()
    if seeded:
        return
    if db.execute("SELECT COUNT(*) FROM analytics").fetchone()[0] == 0:
        random.seed(2026)
        post_ids = [r[0] for r in db.execute("SELECT id FROM posts").fetchall()]
        browsers = ["Chrome", "Safari", "Edge", "Firefox"]
        oses = ["macOS", "iOS", "Windows", "Android", "Linux"]
        events = ["article_click", "category_click", "music_play", "code_copy", "video_play", "image_view"]
        today = date.today()
        for offset in range(13, -1, -1):
            d = today - timedelta(days=offset)
            day = d.isoformat()
            visitors = [uuid.uuid4().hex for _ in range(random.randint(8, 20))]
            for _ in range(random.randint(30, 70)):
                vid = random.choice(visitors)
                device = random.choices(["pc", "mobile", "tablet"], weights=[60, 35, 5])[0]
                browser = random.choices(browsers, weights=[55, 30, 10, 5])[0]
                osname = random.choices(oses, weights=[40, 25, 20, 10, 5])[0]
                pid = random.choice(post_ids) if post_ids and random.random() < 0.65 else None
                path = ("/post/%d" % pid) if pid else "/"
                created = "%sT%02d:%02d:%02d" % (day, random.randint(8, 23), random.randint(0, 59), random.randint(0, 59))
                db.execute(
                    """INSERT INTO analytics(event, path, post_id, category_id, label, visitor_id,
                       ip, ua, device, browser, os, referer, demo, day, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("pageview", path, pid, None, "", vid, "", "", device, browser, osname, "", 1, day, created),
                )
            for _ in range(random.randint(6, 16)):
                ev = random.choice(events)
                vid = random.choice(visitors)
                device = random.choices(["pc", "mobile", "tablet"], weights=[60, 35, 5])[0]
                browser = random.choices(browsers, weights=[55, 30, 10, 5])[0]
                osname = random.choices(oses, weights=[40, 25, 20, 10, 5])[0]
                pid = random.choice(post_ids) if post_ids else None
                created = "%sT%02d:%02d:%02d" % (day, random.randint(8, 23), random.randint(0, 59), random.randint(0, 59))
                db.execute(
                    """INSERT INTO analytics(event, path, post_id, category_id, label, visitor_id,
                       ip, ua, device, browser, os, referer, demo, day, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ev, ("/post/%d" % pid) if pid else "/", pid, None, "", vid, "", "", device, browser, osname, "", 1, day, created),
                )
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('analytics_seeded', '1')")


def seed_users(db):
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        row = db.execute("SELECT value FROM settings WHERE key='admin_password'").fetchone()
        pwd = row[0] if row and row[0] else generate_password_hash("admin123", method="pbkdf2:sha256:600000")
        db.execute(
            "INSERT INTO users(username, password_hash, display_name, created_at) VALUES(?,?,?,?)",
            ("admin", pwd, "管理员", datetime.now().isoformat(timespec="seconds")),
        )


def seed_friends(db):
    if db.execute("SELECT COUNT(*) FROM friend_links").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        links = [
            ("GitHub", "https://github.com", "", "代码与开源项目", 100),
            ("哔哩哔哩", "https://www.bilibili.com", "", "视频与灵感", 80),
            ("示例友链", "https://example.com", "", "在这里添加你的朋友站点", 60),
        ]
        for name, url, logo, desc, weight in links:
            db.execute(
                """INSERT INTO friend_links(name, url, logo, description, weight, enabled, created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (name, url, logo, desc, weight, 1, now),
            )


def detect_device(ua):
    ua_l = (ua or "").lower()
    if "ipad" in ua_l or "tablet" in ua_l or ("android" in ua_l and "mobile" not in ua_l):
        return "tablet"
    if any(k in ua_l for k in ("mobile", "iphone", "ipod", "android", "windows phone")):
        return "mobile"
    return "pc"


def detect_browser(ua):
    ua_l = (ua or "").lower()
    if "edg/" in ua_l or "edgios" in ua_l:
        return "Edge"
    if "chrome" in ua_l or "crios" in ua_l:
        return "Chrome"
    if "firefox" in ua_l or "fxios" in ua_l:
        return "Firefox"
    if "safari" in ua_l:
        return "Safari"
    return "Other"


def detect_os(ua):
    ua_l = (ua or "").lower()
    if "iphone" in ua_l or "ipad" in ua_l or "ipod" in ua_l:
        return "iOS"
    if "android" in ua_l:
        return "Android"
    if "mac os x" in ua_l or "macintosh" in ua_l:
        return "macOS"
    if "windows" in ua_l:
        return "Windows"
    if "linux" in ua_l:
        return "Linux"
    return "Other"


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def get_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    data = dict(DEFAULT_SETTINGS)
    data.update({r["key"]: r["value"] for r in rows})
    return data


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def is_legacy_hash(stored):
    return bool(stored) and ":" not in stored


def verify_password(password, stored):
    if not stored:
        return False
    if ":" in stored:
        try:
            return check_password_hash(stored, password)
        except Exception:
            return False
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored)


# 登录失败限流（进程内）
_RATE_LOCK = threading.Lock()
_RATE_ATTEMPTS = {}
RATE_MAX = 8
RATE_WINDOW = 15 * 60
RATE_LOCK_SECONDS = 15 * 60


def rate_limit_key(scope):
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "unknown"
    return "%s:%s" % (scope, ip)


def rate_locked_seconds(key):
    now = time.time()
    with _RATE_LOCK:
        rec = _RATE_ATTEMPTS.get(key)
        if not rec:
            return 0
        count, first, locked_until = rec
        if locked_until and now < locked_until:
            return int(locked_until - now)
        if now - first > RATE_WINDOW:
            _RATE_ATTEMPTS.pop(key, None)
        return 0


def rate_fail(key):
    now = time.time()
    with _RATE_LOCK:
        rec = _RATE_ATTEMPTS.get(key)
        if not rec or now - rec[1] > RATE_WINDOW:
            rec = (1, now, 0)
        else:
            count = rec[0] + 1
            locked_until = now + RATE_LOCK_SECONDS if count >= RATE_MAX else 0
            rec = (count, rec[1], locked_until)
        _RATE_ATTEMPTS[key] = rec
        return rec


def rate_clear(key):
    with _RATE_LOCK:
        _RATE_ATTEMPTS.pop(key, None)


def rate_locked_text(seconds):
    return "尝试次数过多，请 %d 分钟后再试。" % max(1, seconds // 60)


def safe_next(path):
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return url_for("admin_dashboard")


@app.template_filter("md")
def render_markdown(text):
    if not text:
        return ""
    return md.reset().convert(text)


@app.template_filter("nl2list")
def nl2list(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


@app.template_filter("is_video_file")
def is_video_file(url):
    path = (url or "").lower().split("?")[0].split("#")[0]
    return path.endswith((".mp4", ".webm", ".ogg", ".mov", ".m4v", ".ogv"))


def parse_images(raw):
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_category_counts(db=None):
    """全部分类 + 已发布文章数。"""
    if db is None:
        db = get_db()
    rows = db.execute(
        """SELECT c.id, c.name, c.sort, COUNT(p.id) AS count
           FROM categories c
           LEFT JOIN post_categories pc ON pc.category_id = c.id
           LEFT JOIN posts p ON p.id = pc.post_id AND p.published = 1 AND p.is_private = 0
           GROUP BY c.id
           ORDER BY c.sort, c.id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_post_categories(post_id):
    db = get_db()
    rows = db.execute(
        """SELECT c.id, c.name FROM post_categories pc
           JOIN categories c ON c.id = pc.category_id
           WHERE pc.post_id = ? ORDER BY c.sort, c.id""",
        (post_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def attach_categories(db, posts):
    """给文章 dict 列表批量挂上 categories 字段。"""
    if not posts:
        return
    ids = [p["id"] for p in posts]
    marks = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""SELECT pc.post_id, c.id, c.name FROM post_categories pc
            JOIN categories c ON c.id = pc.category_id
            WHERE pc.post_id IN ({marks}) ORDER BY c.sort, c.id""",
        ids,
    ).fetchall()
    grouped = {}
    for r in rows:
        grouped.setdefault(r["post_id"], []).append({"id": r["id"], "name": r["name"]})
    for p in posts:
        p["categories"] = grouped.get(p["id"], [])


def attach_views(db, posts):
    """给文章挂上 views = 基础访问量 + 真实访问量。"""
    if not posts:
        return
    ids = [p["id"] for p in posts]
    marks = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""SELECT post_id, COUNT(*) AS c FROM analytics
            WHERE event='pageview' AND demo=0 AND post_id IN ({marks})
            GROUP BY post_id""",
        ids,
    ).fetchall()
    real = {r["post_id"]: r["c"] for r in rows}
    for p in posts:
        p["real_views"] = real.get(p["id"], 0)
        p["views"] = (p.get("base_views") or 0) + p["real_views"]


def get_like_count(post_id):
    db = get_db()
    row = db.execute("SELECT COUNT(*) FROM post_likes WHERE post_id = ?", (post_id,)).fetchone()
    return row[0] if row else 0


def is_liked(post_id, visitor_id):
    if not visitor_id:
        return False
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND visitor_id = ?",
        (post_id, visitor_id),
    ).fetchone()
    return bool(row)


def get_friend_links(enabled_only=True):
    db = get_db()
    sql = "SELECT * FROM friend_links"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY weight DESC, id ASC"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_reward_methods(enabled_only=True):
    db = get_db()
    sql = "SELECT * FROM reward_methods"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY sort ASC, id ASC"
    return [dict(r) for r in db.execute(sql).fetchall()]


# 各平台音乐嵌入地址
def build_embed(platform, ref):
    """把歌曲 ID / mid / 完整链接转换为可嵌入的 iframe 地址。"""
    ref = (ref or "").strip()
    if not ref:
        return ""
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    if platform == "netease":
        return f"https://music.163.com/outchain/player?type=2&id={ref}&auto=0&height=66"
    if platform == "qq":
        # ref 可以是歌曲 mid 或数字 songid
        if ref.isdigit():
            return f"https://y.qq.com/iframe/player.html?tiny=0&auto=0&songid={ref}"
        return f"https://y.qq.com/iframe/player.html?tiny=0&auto=0&mid={ref}"
    if platform == "soda":
        # 汽水音乐暂无公开 embed，ref 填 iframe 链接时直接使用
        return ref
    return ""


def build_tracks():
    db = get_db()
    rows = db.execute("SELECT * FROM tracks ORDER BY sort ASC, id ASC").fetchall()
    tracks = []
    for r in rows:
        t = dict(r)
        embed = build_embed(t["platform"], t.get("ref", ""))
        t["embed_url"] = embed
        if t["platform"] in ("custom", "soda") and t.get("audio_url"):
            t["kind"] = "audio"
            t["play_url"] = t["audio_url"]
        elif embed:
            t["kind"] = "embed"
            t["play_url"] = ""
        else:
            t["kind"] = "none"
            t["play_url"] = ""
        tracks.append(t)
    return tracks


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    settings = get_settings()
    tracks = []
    if settings.get("music_enabled", "1") == "1":
        try:
            tracks = build_tracks()
        except Exception:
            tracks = []
    popup_config = {
        "enabled": settings.get("popup_enabled") == "1",
        "mode": settings.get("popup_mode", "daily_first"),
        "title": settings.get("popup_title", ""),
        "content": settings.get("popup_content", ""),
        "content_mode": settings.get("popup_content_mode", "both"),
        "image": settings.get("popup_image", ""),
        "link_url": settings.get("popup_button_url", ""),
        "link_target": settings.get("popup_link_target", "_blank"),
        "close_mode": settings.get("popup_close_mode", "manual"),
        "countdown": int(settings.get("popup_countdown", "0") or 0),
        "start": settings.get("popup_start", ""),
        "end": settings.get("popup_end", ""),
        "daily_once": settings.get("popup_daily_once") == "1",
    }
    return {
        "settings": settings,
        "tracks": tracks,
        "popup_config": popup_config,
        "copyright_types": COPYRIGHT_TYPES,
        "current_year": datetime.now().year,
    }


# --------------------------------------------------------------------------
# 前台
# --------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    category_id = request.args.get("category", type=int)
    active_category = None
    if category_id:
        row = db.execute("SELECT id, name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row:
            active_category = dict(row)
        else:
            category_id = None

    if category_id:
        posts = db.execute(
            """SELECT p.* FROM posts p
               JOIN post_categories pc ON pc.post_id = p.id
               WHERE p.published = 1 AND p.is_private = 0 AND pc.category_id = ?
               ORDER BY p.created_at DESC, p.id DESC""",
            (category_id,),
        ).fetchall()
    else:
        posts = db.execute(
            "SELECT * FROM posts WHERE published = 1 AND is_private = 0 ORDER BY created_at DESC, id DESC"
        ).fetchall()

    items = []
    for p in posts:
        d = dict(p)
        d["image_list"] = parse_images(p["images"])
        items.append(d)
    attach_categories(db, items)
    attach_views(db, items)
    categories = get_category_counts(db)
    return render_template("index.html", posts=items, categories=categories,
                           active_category=active_category, friends=get_friend_links())


@app.route("/friends")
def friends_page():
    return render_template("friends.html", friends=get_friend_links())


@app.route("/private", methods=["GET", "POST"])
def private_home():
    settings = get_settings()
    if settings.get("private_enabled") != "1":
        abort(404)

    next_path = request.args.get("next", "") or request.form.get("next", "")
    if request.method == "POST":
        key = rate_limit_key("private")
        locked = rate_locked_seconds(key)
        if locked:
            flash(rate_locked_text(locked), "error")
            return render_template("private_login.html", next_path=next_path), 429
        pwd = request.form.get("password", "")
        if verify_password(pwd, settings.get("private_password_hash")):
            rate_clear(key)
            if is_legacy_hash(settings.get("private_password_hash")):
                set_setting("private_password_hash", hash_password(pwd))
            session["private_unlocked"] = True
            if next_path.startswith("/") and not next_path.startswith("//"):
                return redirect(next_path)
            return redirect(url_for("private_home"))
        rate_fail(key)
        flash("密码错误，请重试。", "error")

    if not session.get("private_unlocked"):
        return render_template("private_login.html", next_path=next_path)

    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE is_private = 1 AND published = 1 ORDER BY created_at DESC, id DESC"
    ).fetchall()
    items = []
    for p in posts:
        d = dict(p)
        d["image_list"] = parse_images(p["images"])
        items.append(d)
    attach_categories(db, items)
    attach_views(db, items)
    return render_template("private.html", posts=items)


@app.route("/private/logout")
def private_logout():
    session.pop("private_unlocked", None)
    return redirect(url_for("index"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    db = get_db()
    p = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not p:
        abort(404)
    d = dict(p)
    d["image_list"] = parse_images(p["images"])
    d["categories"] = get_post_categories(post_id)
    attach_views(db, [d])
    d["like_count"] = get_like_count(post_id)
    d["liked"] = is_liked(post_id, request.cookies.get("vid"))
    d["reward_methods"] = get_reward_methods()
    d["reward_enabled"] = get_settings().get("reward_enabled") == "1"

    # 私密内容：只能通过右上角私密入口解锁后访问
    if d.get("is_private"):
        if get_settings().get("private_enabled") != "1":
            abort(404)
        if not session.get("private_unlocked"):
            return redirect(url_for("private_home", next=request.path))

    if d.get("password_hash"):
        unlocked = session.get("unlocked_posts", [])
        if post_id not in unlocked:
            if request.method == "POST":
                key = rate_limit_key("post_%s" % post_id)
                locked = rate_locked_seconds(key)
                if locked:
                    flash(rate_locked_text(locked), "error")
                    return render_template("post_locked.html", post=d), 429
                pwd = request.form.get("password", "")
                if verify_password(pwd, d["password_hash"]):
                    rate_clear(key)
                    if is_legacy_hash(d["password_hash"]):
                        db.execute(
                            "UPDATE posts SET password_hash = ? WHERE id = ?",
                            (hash_password(pwd), post_id),
                        )
                        db.commit()
                    session["unlocked_posts"] = list(unlocked) + [post_id]
                    return redirect(url_for("post_detail", post_id=post_id))
                rate_fail(key)
                flash("密码错误，请重试。", "error")
            return render_template("post_locked.html", post=d)

    return render_template("post.html", post=d)


ALLOWED_EVENTS = {
    "pageview", "article_click", "category_click",
    "music_play", "code_copy", "video_play", "image_view", "like_click",
}


@app.route("/api/track", methods=["POST"])
def api_track():
    """前端埋点上报接口。"""
    data = request.get_json(silent=True) or request.form or {}
    event = (data.get("event") or "").strip()
    if event not in ALLOWED_EVENTS:
        return ("", 204)

    ua = request.headers.get("User-Agent", "")
    vid = request.cookies.get("vid") or uuid.uuid4().hex
    now = datetime.now()

    def as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    post_id = as_int(data.get("post_id"))
    category_id = as_int(data.get("category_id"))
    path = (data.get("path") or "")[:500]
    label = (data.get("label") or "")[:200]
    referer = (data.get("referer") or "")[:500]
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

    db = get_db()
    try:
        db.execute(
            """INSERT INTO analytics(event, path, post_id, category_id, label, visitor_id,
               ip, ua, device, browser, os, referer, demo, day, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event, path, post_id, category_id, label, vid, ip, ua,
             detect_device(ua), detect_browser(ua), detect_os(ua), referer, 0,
             now.strftime("%Y-%m-%d"), now.isoformat(timespec="seconds")),
        )
        db.commit()
    except Exception:
        pass

    resp = app.response_class(status=204)
    if not request.cookies.get("vid"):
        resp.set_cookie("vid", vid, max_age=365 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


@app.route("/api/like/<int:post_id>", methods=["POST"])
def api_like(post_id):
    if get_settings().get("likes_enabled") != "1":
        return jsonify({"ok": False, "error": "点赞功能已关闭"}), 403
    db = get_db()
    if not db.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone():
        return jsonify({"ok": False, "error": "文章不存在"}), 404

    vid = request.cookies.get("vid") or uuid.uuid4().hex
    existing = db.execute(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND visitor_id = ?",
        (post_id, vid),
    ).fetchone()
    if existing:
        db.execute(
            "DELETE FROM post_likes WHERE post_id = ? AND visitor_id = ?",
            (post_id, vid),
        )
        liked = False
    else:
        db.execute(
            "INSERT OR IGNORE INTO post_likes(post_id, visitor_id, created_at) VALUES(?,?,?)",
            (post_id, vid, datetime.now().isoformat(timespec="seconds")),
        )
        liked = True
    db.commit()
    count = db.execute(
        "SELECT COUNT(*) FROM post_likes WHERE post_id = ?", (post_id,)
    ).fetchone()[0]
    resp = jsonify({"ok": True, "liked": liked, "count": count})
    if not request.cookies.get("vid"):
        resp.set_cookie("vid", vid, max_age=365 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# --------------------------------------------------------------------------
# 后台上传
# --------------------------------------------------------------------------
@app.route("/admin/upload", methods=["POST"])
@login_required
def admin_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "没有文件"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"ok": False, "error": f"不支持的文件类型: .{ext}"}), 400
    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    f.save(path)
    url = f"/static/uploads/{name}"
    return jsonify({"ok": True, "url": url, "name": f.filename})


# --------------------------------------------------------------------------
# 后台：隐秘入口 + 二级密码
# --------------------------------------------------------------------------
@app.before_request
def first_run_setup():
    if get_settings().get("setup_completed") == "1":
        return
    path = request.path
    if path.startswith("/setup") or path.startswith("/static/"):
        return
    return redirect(url_for("setup_wizard"))


@app.before_request
def hide_admin_without_gate():
    if request.path.startswith("/admin") and not session.get("admin_gate_passed"):
        abort(404)


# --------------------------------------------------------------------------
# 首次部署引导
# --------------------------------------------------------------------------
@app.route("/setup")
def setup_wizard():
    settings = get_settings()
    if settings.get("setup_completed") == "1":
        return redirect(url_for("index"))
    try:
        step = int(settings.get("setup_step", "1"))
    except (TypeError, ValueError):
        step = 1
    if step >= 4:
        return redirect(url_for("index"))

    if step == 3:
        secret = session.get("setup_totp_secret")
        if not secret:
            secret = pyotp.random_base32()
            session["setup_totp_secret"] = secret
        db = get_db()
        row = db.execute("SELECT username FROM users ORDER BY id LIMIT 1").fetchone()
        username = row["username"] if row else "admin"
        issuer = settings.get("site_title") or "Blog"
        uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
        return render_template("setup.html", step=3, secret=secret, qr=_qr_data_uri(uri))

    if step == 2:
        db = get_db()
        row = db.execute("SELECT username FROM users ORDER BY id LIMIT 1").fetchone()
        username = row["username"] if row else "admin"
        return render_template("setup.html", step=2, current_username=username)

    return render_template("setup.html", step=1,
                           current_path=settings.get("admin_secret_path", ""))


@app.route("/setup/step1", methods=["POST"])
def setup_step1():
    settings = get_settings()
    if settings.get("setup_completed") == "1" or settings.get("setup_step") != "1":
        return redirect(url_for("setup_wizard"))
    path = request.form.get("secret_path", "").strip().lstrip("/")
    pwd = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not re.match(r"^[A-Za-z0-9_-]{4,40}$", path):
        flash("隐秘路径只能包含字母、数字、下划线、短横线，长度 4-40。", "error")
        return render_template("setup.html", step=1, current_path=path)
    if path.lower() in RESERVED_PATHS:
        flash("该路径为系统保留路径，请换一个。", "error")
        return render_template("setup.html", step=1, current_path=path)
    if len(pwd) < 8:
        flash("二级密码至少 8 位。", "error")
        return render_template("setup.html", step=1, current_path=path)
    if pwd != confirm:
        flash("两次输入的二级密码不一致。", "error")
        return render_template("setup.html", step=1, current_path=path)
    set_setting("admin_secret_path", path)
    set_setting("admin_gate_password_hash", hash_password(pwd))
    set_setting("setup_step", "2")
    get_db().commit()
    flash("二级密码与隐秘路径已设置。", "ok")
    return redirect(url_for("setup_wizard"))


@app.route("/setup/step2", methods=["POST"])
def setup_step2():
    settings = get_settings()
    if settings.get("setup_completed") == "1" or settings.get("setup_step") != "2":
        return redirect(url_for("setup_wizard"))
    username = request.form.get("username", "").strip()
    pwd = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not re.match(r"^[A-Za-z0-9_.-]{3,30}$", username):
        flash("用户名只能包含字母、数字、下划线、点、短横线，长度 3-30。", "error")
        return render_template("setup.html", step=2, current_username=username)
    if len(pwd) < 8:
        flash("管理员密码至少 8 位。", "error")
        return render_template("setup.html", step=2, current_username=username)
    if pwd != confirm:
        flash("两次输入的管理员密码不一致。", "error")
        return render_template("setup.html", step=2, current_username=username)
    db = get_db()
    current = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if current:
        other = db.execute(
            "SELECT id FROM users WHERE username = ? AND id <> ?",
            (username, current["id"]),
        ).fetchone()
        if other:
            flash("该用户名已被其他用户占用。", "error")
            return render_template("setup.html", step=2, current_username=username)
        db.execute(
            "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
            (username, hash_password(pwd), current["id"]),
        )
    else:
        db.execute(
            "INSERT INTO users(username, password_hash, display_name, created_at) VALUES(?,?,?,?)",
            (username, hash_password(pwd), "管理员", datetime.now().isoformat(timespec="seconds")),
        )
    db.commit()
    set_setting("setup_step", "3")
    flash("管理员账号已设置。", "ok")
    return redirect(url_for("setup_wizard"))


@app.route("/setup/step3", methods=["POST"])
def setup_step3():
    settings = get_settings()
    if settings.get("setup_completed") == "1" or settings.get("setup_step") != "3":
        return redirect(url_for("setup_wizard"))
    secret = session.get("setup_totp_secret")
    code = request.form.get("code", "").strip()
    if not secret:
        flash("绑定已过期，请重新开始。", "error")
        return redirect(url_for("setup_wizard"))
    try:
        ok = pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        ok = False
    if not ok:
        flash("验证码错误，请重试。", "error")
        db = get_db()
        row = db.execute("SELECT username FROM users ORDER BY id LIMIT 1").fetchone()
        username = row["username"] if row else "admin"
        issuer = settings.get("site_title") or "Blog"
        uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
        return render_template("setup.html", step=3, secret=secret, qr=_qr_data_uri(uri))

    set_setting("admin_totp_secret", secret)
    set_setting("admin_totp_enabled", "1")
    temp_key = secrets.token_urlsafe(12)
    set_setting("admin_temp_key_hash", hash_password(temp_key))
    set_setting("admin_temp_key_expires", "")
    set_setting("setup_step", "4")
    set_setting("setup_completed", "1")
    session.pop("setup_totp_secret", None)
    get_db().commit()
    current = get_settings()
    return render_template("setup.html", step=4, temp_key=temp_key,
                           secret_path=current.get("admin_secret_path", ""))


@app.route("/setup/skip2fa", methods=["POST"])
def setup_skip2fa():
    settings = get_settings()
    if settings.get("setup_completed") == "1" or settings.get("setup_step") != "3":
        return redirect(url_for("setup_wizard"))
    set_setting("admin_totp_enabled", "0")
    set_setting("admin_totp_secret", "")
    set_setting("admin_temp_key_hash", "")
    set_setting("admin_temp_key_expires", "")
    set_setting("setup_step", "4")
    set_setting("setup_completed", "1")
    session.pop("setup_totp_secret", None)
    get_db().commit()
    current = get_settings()
    return render_template("setup.html", step=4, temp_key=None,
                           secret_path=current.get("admin_secret_path", ""))


@app.route("/<secret>", methods=["GET", "POST"])
def admin_secret_gate(secret):
    settings = get_settings()
    expected = (settings.get("admin_secret_path") or "").strip().lstrip("/")
    if not expected or secret != expected:
        abort(404)
    if request.method == "POST":
        key = rate_limit_key("admin_gate")
        locked = rate_locked_seconds(key)
        if locked:
            flash(rate_locked_text(locked), "error")
            return render_template("admin_gate.html"), 429
        pwd = request.form.get("password", "")
        if verify_password(pwd, settings.get("admin_gate_password_hash")):
            rate_clear(key)
            if is_legacy_hash(settings.get("admin_gate_password_hash")):
                set_setting("admin_gate_password_hash", hash_password(pwd))
            # 二级密码通过后，清除旧的管理员登录状态，始终重新进入登录页
            session.pop("admin", None)
            session.pop("admin_user", None)
            session.pop("admin_pending", None)
            session["admin_gate_passed"] = True
            return redirect(url_for("admin_login"))
        rate_fail(key)
        flash("二级密码错误，请重试。", "error")
    return render_template("admin_gate.html")


# --------------------------------------------------------------------------
# 后台：登录
# --------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        key = rate_limit_key("admin_login")
        locked = rate_locked_seconds(key)
        if locked:
            flash(rate_locked_text(locked), "error")
            return render_template("admin_login.html"), 429
        username = request.form.get("username", "").strip() or "admin"
        pwd = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        valid = False
        if user:
            valid = verify_password(pwd, user["password_hash"])
            if valid and is_legacy_hash(user["password_hash"]):
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(pwd), user["id"]),
                )
                db.commit()
        elif username == "admin":
            stored = get_settings().get("admin_password")
            valid = verify_password(pwd, stored)
            if valid and is_legacy_hash(stored):
                set_setting("admin_password", hash_password(pwd))
        if valid:
            rate_clear(key)
            nxt = safe_next(request.args.get("next"))
            if get_settings().get("admin_totp_enabled") == "1":
                session.pop("admin", None)
                session.pop("admin_user", None)
                session["admin_pending"] = {
                    "username": username,
                    "next": nxt,
                    "time": time.time(),
                }
                return redirect(url_for("admin_totp"))
            session["admin"] = True
            session["admin_user"] = username
            session.pop("admin_pending", None)
            return redirect(nxt)
        rate_fail(key)
        flash("用户名或密码错误，请重试。", "error")
    return render_template("admin_login.html")


@app.route("/admin/2fa", methods=["GET", "POST"])
def admin_totp():
    pending = session.get("admin_pending")
    if not pending:
        return redirect(url_for("admin_login"))
    try:
        pending_time = float(pending.get("time", 0))
    except (TypeError, ValueError):
        pending_time = 0
    if time.time() - pending_time > 300:
        session.pop("admin_pending", None)
        flash("验证超时，请重新登录。", "error")
        return redirect(url_for("admin_login"))

    settings = get_settings()
    if settings.get("admin_totp_enabled") != "1":
        session["admin"] = True
        session["admin_user"] = pending.get("username", "admin")
        nxt = pending.get("next") or url_for("admin_dashboard")
        session.pop("admin_pending", None)
        return redirect(nxt)

    key = rate_limit_key("admin_2fa")
    if request.method == "POST":
        locked = rate_locked_seconds(key)
        if locked:
            flash(rate_locked_text(locked), "error")
            return render_template("admin_2fa.html", pending=pending), 429
        code = (request.form.get("code") or "").strip()
        temp_key = (request.form.get("temp_key") or "").strip()
        valid = False
        if code:
            secret = settings.get("admin_totp_secret") or ""
            try:
                valid = bool(secret) and pyotp.TOTP(secret).verify(code, valid_window=1)
            except Exception:
                valid = False
        elif temp_key:
            stored = settings.get("admin_temp_key_hash") or ""
            expires = settings.get("admin_temp_key_expires") or ""
            not_expired = True
            if expires:
                try:
                    exp = datetime.fromisoformat(expires)
                except ValueError:
                    exp = None
                not_expired = bool(exp) and datetime.now() <= exp
            if stored and not_expired and verify_password(temp_key, stored):
                valid = True
                set_setting("admin_temp_key_hash", "")
                set_setting("admin_temp_key_expires", "")
        if valid:
            rate_clear(key)
            session["admin"] = True
            session["admin_user"] = pending.get("username", "admin")
            nxt = pending.get("next") or url_for("admin_dashboard")
            session.pop("admin_pending", None)
            return redirect(nxt)
        rate_fail(key)
        flash("验证码或临时密钥错误，请重试。", "error")

    return render_template("admin_2fa.html", pending=pending)


def _qr_data_uri(uri):
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@app.route("/admin/2fa/setup", methods=["GET", "POST"])
@login_required
def admin_totp_setup():
    settings = get_settings()
    if request.method == "POST":
        secret = session.get("totp_setup_secret")
        code = (request.form.get("code") or "").strip()
        if not secret:
            flash("绑定已过期，请重新开始。", "error")
            return redirect(url_for("admin_totp_setup"))
        try:
            ok = pyotp.TOTP(secret).verify(code, valid_window=1)
        except Exception:
            ok = False
        if ok:
            set_setting("admin_totp_secret", secret)
            set_setting("admin_totp_enabled", "1")
            session.pop("totp_setup_secret", None)
            flash("Authenticator 已启用。", "ok")
            return redirect(url_for("admin_settings"))
        flash("验证码错误，请重试。", "error")

    secret = session.get("totp_setup_secret")
    if not secret:
        secret = pyotp.random_base32()
        session["totp_setup_secret"] = secret
    username = session.get("admin_user") or "admin"
    issuer = settings.get("site_title") or "Blog"
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
    return render_template("admin_2fa_setup.html", secret=secret, qr=_qr_data_uri(uri),
                           enabled=settings.get("admin_totp_enabled") == "1")


@app.route("/admin/2fa/temp-key", methods=["POST"])
@login_required
def admin_2fa_temp_key():
    settings = get_settings()
    if settings.get("admin_totp_enabled") != "1":
        flash("请先启用 Authenticator。", "error")
        return redirect(url_for("admin_settings"))
    key = secrets.token_urlsafe(12)
    set_setting("admin_temp_key_hash", hash_password(key))
    set_setting("admin_temp_key_expires", "")
    return render_template("admin_temp_key.html", key=key)


@app.route("/admin/2fa/disable", methods=["POST"])
@login_required
def admin_2fa_disable():
    pwd = request.form.get("password", "")
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (session.get("admin_user"),)
    ).fetchone()
    if not user or not verify_password(pwd, user["password_hash"]):
        flash("管理员密码错误，无法关闭两步验证。", "error")
        return redirect(url_for("admin_settings"))
    set_setting("admin_totp_enabled", "0")
    set_setting("admin_totp_secret", "")
    set_setting("admin_temp_key_hash", "")
    set_setting("admin_temp_key_expires", "")
    session.pop("totp_setup_secret", None)
    flash("两步验证已关闭。", "ok")
    return redirect(url_for("admin_settings"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    session.pop("admin_user", None)
    session.pop("unlocked_posts", None)
    session.pop("admin_gate_passed", None)
    session.pop("admin_pending", None)
    session.pop("totp_setup_secret", None)
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
# 后台：文章
# --------------------------------------------------------------------------
@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM posts ORDER BY created_at DESC, id DESC"
    ).fetchall()
    posts = [dict(r) for r in rows]
    attach_categories(db, posts)
    return render_template("admin_dashboard.html", posts=posts)


@app.route("/admin/posts/new", methods=["GET"])
@login_required
def admin_post_new():
    db = get_db()
    post = {
        "id": None, "title": "", "type": "image", "excerpt": "", "cover": "",
        "content": "", "images": "[]", "video_url": "", "video_poster": "",
        "published": 1, "password_hash": "", "copyright_type": "original",
        "copyright_text": "", "content_format": "html",
        "base_views": 0, "show_views": 1, "is_private": 0,
    }
    return render_template("admin_edit.html", post=post, image_list=[], content_html="",
                           all_categories=get_category_counts(db), selected_cat_ids=[])


@app.route("/admin/posts/<int:post_id>/edit", methods=["GET"])
@login_required
def admin_post_edit(post_id):
    db = get_db()
    p = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not p:
        abort(404)
    post = dict(p)
    if post.get("content_format") == "html":
        content_html = post.get("content") or ""
    else:
        content_html = md.reset().convert(post.get("content") or "")
    selected_cat_ids = [
        r["category_id"] for r in db.execute(
            "SELECT category_id FROM post_categories WHERE post_id = ?", (post_id,)
        ).fetchall()
    ]
    return render_template("admin_edit.html", post=post, image_list=parse_images(p["images"]),
                           content_html=content_html, all_categories=get_category_counts(db),
                           selected_cat_ids=selected_cat_ids)


@app.route("/admin/posts/save", methods=["POST"])
@login_required
def admin_post_save():
    db = get_db()
    post_id = request.form.get("id", "").strip()
    title = request.form.get("title", "").strip() or "无标题"
    ptype = request.form.get("type", "image")
    excerpt = request.form.get("excerpt", "").strip()
    cover = request.form.get("cover", "").strip()
    content = request.form.get("content", "")
    video_url = request.form.get("video_url", "").strip()
    video_poster = request.form.get("video_poster", "").strip()
    published = 1 if request.form.get("published") else 0
    images_raw = request.form.get("images", "")
    images = [x.strip() for x in images_raw.splitlines() if x.strip()]
    copyright_type = request.form.get("copyright_type", "original")
    if copyright_type not in COPYRIGHT_TYPES:
        copyright_type = "original"
    copyright_text = request.form.get("copyright_text", "").strip()
    content_format = "html"
    try:
        base_views = max(0, int(request.form.get("base_views", "0") or "0"))
    except (TypeError, ValueError):
        base_views = 0
    show_views = 1 if request.form.get("show_views") else 0
    is_private = 1 if request.form.get("is_private") else 0

    # 访问密码：勾选后生效；密码留空则沿用旧密码
    protected = bool(request.form.get("protected"))
    new_pwd = request.form.get("post_password", "").strip()
    existing_hash = ""
    if post_id:
        row = db.execute("SELECT password_hash FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row:
            existing_hash = row["password_hash"] or ""
    password_hash = ""
    if protected:
        password_hash = hash_password(new_pwd) if new_pwd else existing_hash
        if not password_hash:
            flash("已勾选访问密码，但未填写密码，本条不会加密。", "error")
    now = datetime.now().isoformat(timespec="seconds")

    if post_id:
        db.execute(
            """UPDATE posts SET title=?, type=?, excerpt=?, cover=?, content=?,
               images=?, video_url=?, video_poster=?, password_hash=?,
               copyright_type=?, copyright_text=?, content_format=?,
               base_views=?, show_views=?, is_private=?, published=?, updated_at=? WHERE id=?""",
            (title, ptype, excerpt, cover, content, json.dumps(images, ensure_ascii=False),
             video_url, video_poster, password_hash, copyright_type, copyright_text,
             content_format, base_views, show_views, is_private, published, now, post_id),
        )
        saved_id = int(post_id)
    else:
        cur = db.execute(
            """INSERT INTO posts(title, type, excerpt, cover, content, images,
               video_url, video_poster, password_hash, copyright_type, copyright_text,
               content_format, base_views, show_views, is_private, published, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title, ptype, excerpt, cover, content,
             json.dumps(images, ensure_ascii=False), video_url, video_poster,
             password_hash, copyright_type, copyright_text, content_format,
             base_views, show_views, is_private, published, now, now),
        )
        saved_id = cur.lastrowid

    # 保存文章分类（多对多，可多选）
    cat_ids = []
    for raw in request.form.getlist("categories"):
        try:
            cat_ids.append(int(raw))
        except (TypeError, ValueError):
            pass
    valid_ids = {r["id"] for r in db.execute("SELECT id FROM categories").fetchall()}
    db.execute("DELETE FROM post_categories WHERE post_id = ?", (saved_id,))
    for cid in set(cat_ids) & valid_ids:
        db.execute(
            "INSERT OR IGNORE INTO post_categories(post_id, category_id) VALUES(?, ?)",
            (saved_id, cid),
        )

    db.commit()
    flash("文章已保存。", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def admin_post_delete(post_id):
    db = get_db()
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    flash("文章已删除。", "ok")
    return redirect(url_for("admin_dashboard"))


# --------------------------------------------------------------------------
# 后台：分类管理
# --------------------------------------------------------------------------
@app.route("/admin/categories", methods=["GET", "POST"])
@login_required
def admin_categories():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("分类名称不能为空。", "error")
        else:
            try:
                row = db.execute("SELECT COALESCE(MAX(sort), 0) AS m FROM categories").fetchone()
                sort = row["m"] + 1
                db.execute(
                    "INSERT INTO categories(name, sort, created_at) VALUES(?,?,?)",
                    (name, sort, datetime.now().isoformat(timespec="seconds")),
                )
                db.commit()
                flash("分类「%s」已添加。" % name, "ok")
            except sqlite3.IntegrityError:
                flash("分类「%s」已存在。" % name, "error")
        return redirect(url_for("admin_categories"))

    categories = get_category_counts(db)
    return render_template("admin_categories.html", categories=categories)


@app.route("/admin/categories/<int:category_id>/rename", methods=["POST"])
@login_required
def admin_category_rename(category_id):
    db = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("分类名称不能为空。", "error")
        return redirect(url_for("admin_categories"))
    try:
        db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        db.commit()
        flash("分类已更新。", "ok")
    except sqlite3.IntegrityError:
        flash("分类「%s」已存在。" % name, "error")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def admin_category_delete(category_id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    flash("分类已删除，文章本身不会被删除。", "ok")
    return redirect(url_for("admin_categories"))


# --------------------------------------------------------------------------
# 后台：数据统计
# --------------------------------------------------------------------------
EVENT_LABELS = {
    "pageview": "页面访问",
    "article_click": "文章点击",
    "category_click": "分类点击",
    "music_play": "音乐播放",
    "code_copy": "代码复制",
    "video_play": "视频播放",
    "image_view": "图片查看",
}


@app.route("/admin/analytics")
@login_required
def admin_analytics():
    db = get_db()
    today = date.today()
    today_str = today.isoformat()
    start14 = (today - timedelta(days=13)).isoformat()
    start30 = (today - timedelta(days=29)).isoformat()

    def scalar(sql, args=()):
        row = db.execute(sql, args).fetchone()
        return (row[0] if row else 0) or 0

    total_pv = scalar("SELECT COUNT(*) FROM analytics WHERE event='pageview'")
    total_uv = scalar("SELECT COUNT(DISTINCT visitor_id) FROM analytics WHERE event='pageview' AND visitor_id <> ''")
    today_pv = scalar("SELECT COUNT(*) FROM analytics WHERE event='pageview' AND day=?", (today_str,))
    today_uv = scalar(
        "SELECT COUNT(DISTINCT visitor_id) FROM analytics WHERE event='pageview' AND day=? AND visitor_id <> ''",
        (today_str,),
    )
    total_clicks = scalar("SELECT COUNT(*) FROM analytics WHERE event<>'pageview'")
    pv30 = scalar("SELECT COUNT(*) FROM analytics WHERE event='pageview' AND day>=?", (start30,))
    click30 = scalar("SELECT COUNT(*) FROM analytics WHERE event<>'pageview' AND day>=?", (start30,))
    avg_pv = round(pv30 / 30, 1)
    avg_click = round(click30 / 30, 1)
    demo_count = scalar("SELECT COUNT(*) FROM analytics WHERE demo=1")

    trend_rows = db.execute(
        """SELECT day,
                  SUM(CASE WHEN event='pageview' THEN 1 ELSE 0 END) AS pv,
                  COUNT(DISTINCT CASE WHEN event='pageview' AND visitor_id <> '' THEN visitor_id END) AS uv
           FROM analytics WHERE day >= ? GROUP BY day""",
        (start14,),
    ).fetchall()
    by_day = {r["day"]: r for r in trend_rows}
    trend = []
    max_val = 1
    for i in range(14):
        d = today - timedelta(days=13 - i)
        ds = d.isoformat()
        r = by_day.get(ds)
        pv = r["pv"] if r else 0
        uv = r["uv"] if r else 0
        max_val = max(max_val, pv, uv)
        trend.append({"day": ds, "label": ds[5:], "pv": pv, "uv": uv})
    for t in trend:
        t["pv_h"] = round(t["pv"] / max_val * 100)
        t["uv_h"] = round(t["uv"] / max_val * 100)

    device_rows = db.execute(
        """SELECT device, COUNT(*) AS pv, COUNT(DISTINCT visitor_id) AS uv
           FROM analytics WHERE event='pageview' GROUP BY device"""
    ).fetchall()
    dmap = {r["device"]: r for r in device_rows}
    devices = []
    for key, label in [("pc", "PC 电脑"), ("mobile", "手机"), ("tablet", "平板")]:
        r = dmap.get(key)
        pv = r["pv"] if r else 0
        uv = r["uv"] if r else 0
        devices.append({
            "key": key, "label": label, "pv": pv, "uv": uv,
            "pct": round(pv / total_pv * 100, 1) if total_pv else 0,
        })

    browsers = [dict(r) for r in db.execute(
        "SELECT browser, COUNT(*) AS c FROM analytics WHERE event='pageview' GROUP BY browser ORDER BY c DESC"
    ).fetchall()]
    oses = [dict(r) for r in db.execute(
        "SELECT os, COUNT(*) AS c FROM analytics WHERE event='pageview' GROUP BY os ORDER BY c DESC"
    ).fetchall()]
    referers = [dict(r) for r in db.execute(
        """SELECT referer, COUNT(*) AS c FROM analytics
           WHERE event='pageview' AND referer <> '' GROUP BY referer ORDER BY c DESC LIMIT 6"""
    ).fetchall()]

    event_rows = db.execute(
        "SELECT event, COUNT(*) AS c FROM analytics GROUP BY event ORDER BY c DESC"
    ).fetchall()
    events = [
        {"key": r["event"], "label": EVENT_LABELS.get(r["event"], r["event"]), "count": r["c"]}
        for r in event_rows
    ]

    top_posts = [dict(r) for r in db.execute(
        """SELECT a.post_id, COALESCE(p.title, '已删除文章') AS title, COUNT(*) AS c
           FROM analytics a LEFT JOIN posts p ON p.id = a.post_id
           WHERE a.post_id IS NOT NULL AND a.event IN ('pageview','article_click')
           GROUP BY a.post_id ORDER BY c DESC LIMIT 8"""
    ).fetchall()]
    top_pages = [dict(r) for r in db.execute(
        "SELECT path, COUNT(*) AS c FROM analytics WHERE event='pageview' GROUP BY path ORDER BY c DESC LIMIT 8"
    ).fetchall()]
    recent = [dict(r) for r in db.execute(
        """SELECT event, path, label, device, browser, visitor_id, created_at
           FROM analytics ORDER BY id DESC LIMIT 15"""
    ).fetchall()]

    return render_template(
        "admin_analytics.html",
        total_pv=total_pv, total_uv=total_uv, today_pv=today_pv, today_uv=today_uv,
        total_clicks=total_clicks, avg_pv=avg_pv, avg_click=avg_click,
        demo_count=demo_count, trend=trend, devices=devices, browsers=browsers,
        oses=oses, referers=referers, events=events, top_posts=top_posts,
        top_pages=top_pages, recent=recent,
    )


@app.route("/admin/analytics/clear-demo", methods=["POST"])
@login_required
def admin_analytics_clear_demo():
    db = get_db()
    db.execute("DELETE FROM analytics WHERE demo = 1")
    db.commit()
    flash("演示统计数据已清空，之后只统计真实访问。", "ok")
    return redirect(url_for("admin_analytics"))


@app.route("/admin/analytics/clear", methods=["POST"])
@login_required
def admin_analytics_clear():
    db = get_db()
    db.execute("DELETE FROM analytics")
    db.commit()
    flash("全部统计数据已清空。", "ok")
    return redirect(url_for("admin_analytics"))


# --------------------------------------------------------------------------
# 后台：用户管理
# --------------------------------------------------------------------------
@app.route("/admin/users")
@login_required
def admin_users():
    db = get_db()
    users = db.execute(
        "SELECT id, username, display_name, created_at FROM users ORDER BY id"
    ).fetchall()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@login_required
def admin_users_add():
    db = get_db()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    display_name = request.form.get("display_name", "").strip()
    if not username or not password:
        flash("用户名和密码不能为空。", "error")
        return redirect(url_for("admin_users"))
    try:
        db.execute(
            "INSERT INTO users(username, password_hash, display_name, created_at) VALUES(?,?,?,?)",
            (username, hash_password(password), display_name, datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        flash("用户已添加。", "ok")
    except sqlite3.IntegrityError:
        flash("用户名已存在。", "error")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/password", methods=["POST"])
@login_required
def admin_user_password(user_id):
    pwd = request.form.get("password", "").strip()
    if not pwd:
        flash("新密码不能为空。", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(pwd), user_id))
        db.commit()
        flash("密码已更新。", "ok")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/update", methods=["POST"])
@login_required
def admin_user_update(user_id):
    db = get_db()
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    if not username:
        flash("用户名不能为空。", "error")
        return redirect(url_for("admin_users"))
    try:
        old = db.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        db.execute(
            "UPDATE users SET username = ?, display_name = ? WHERE id = ?",
            (username, display_name, user_id),
        )
        db.commit()
        if old and session.get("admin_user") == old["username"]:
            session["admin_user"] = username
        flash("用户信息已更新。", "ok")
    except sqlite3.IntegrityError:
        flash("用户名已存在。", "error")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_user_delete(user_id):
    db = get_db()
    row = db.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        flash("用户不存在。", "error")
    elif row["username"] == session.get("admin_user"):
        flash("不能删除当前登录用户。", "error")
    elif db.execute("SELECT COUNT(*) FROM users").fetchone()[0] <= 1:
        flash("至少保留一个用户。", "error")
    else:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash("用户已删除。", "ok")
    return redirect(url_for("admin_users"))


# --------------------------------------------------------------------------
# 后台：友链管理
# --------------------------------------------------------------------------
@app.route("/admin/friends")
@login_required
def admin_friends():
    db = get_db()
    links = [dict(r) for r in db.execute(
        "SELECT * FROM friend_links ORDER BY weight DESC, id ASC"
    ).fetchall()]
    return render_template("admin_friends.html", links=links)


@app.route("/admin/friends/add", methods=["POST"])
@login_required
def admin_friends_add():
    db = get_db()
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if not name or not url:
        flash("名称和链接不能为空。", "error")
        return redirect(url_for("admin_friends"))
    try:
        weight = int(request.form.get("weight", "0") or "0")
    except ValueError:
        weight = 0
    db.execute(
        """INSERT INTO friend_links(name, url, logo, description, weight, enabled, created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (name, url, request.form.get("logo", "").strip(),
         request.form.get("description", "").strip(), weight,
         1 if request.form.get("enabled") else 0,
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    flash("友链已添加。", "ok")
    return redirect(url_for("admin_friends"))


@app.route("/admin/friends/<int:link_id>/update", methods=["POST"])
@login_required
def admin_friends_update(link_id):
    db = get_db()
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if not name or not url:
        flash("名称和链接不能为空。", "error")
        return redirect(url_for("admin_friends"))
    try:
        weight = int(request.form.get("weight", "0") or "0")
    except ValueError:
        weight = 0
    db.execute(
        """UPDATE friend_links SET name=?, url=?, logo=?, description=?,
           weight=?, enabled=? WHERE id=?""",
        (name, url, request.form.get("logo", "").strip(),
         request.form.get("description", "").strip(), weight,
         1 if request.form.get("enabled") else 0, link_id),
    )
    db.commit()
    flash("友链已更新。", "ok")
    return redirect(url_for("admin_friends"))


@app.route("/admin/friends/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_friends_delete(link_id):
    db = get_db()
    db.execute("DELETE FROM friend_links WHERE id = ?", (link_id,))
    db.commit()
    flash("友链已删除。", "ok")
    return redirect(url_for("admin_friends"))


# --------------------------------------------------------------------------
# 后台：弹窗推送
# --------------------------------------------------------------------------
@app.route("/admin/popup", methods=["GET", "POST"])
@login_required
def admin_popup():
    if request.method == "POST":
        for key in [
            "popup_mode", "popup_title", "popup_content", "popup_image",
            "popup_button_url", "popup_link_target", "popup_start", "popup_end",
        ]:
            set_setting(key, request.form.get(key, ""))
        content_mode = request.form.get("popup_content_mode", "both")
        if content_mode not in ("image", "text", "both"):
            content_mode = "both"
        set_setting("popup_content_mode", content_mode)
        close_mode = request.form.get("popup_close_mode", "manual")
        if close_mode not in ("manual", "outside"):
            close_mode = "manual"
        set_setting("popup_close_mode", close_mode)
        if close_mode == "manual":
            # 手动强制关闭模式不允许自动关闭
            countdown = 0
        else:
            try:
                countdown = max(0, min(3600, int(request.form.get("popup_countdown", "0") or "0")))
            except ValueError:
                countdown = 0
        set_setting("popup_countdown", str(countdown))
        set_setting("popup_enabled", "1" if request.form.get("popup_enabled") else "0")
        set_setting("popup_daily_once", "1" if request.form.get("popup_daily_once") else "0")
        flash("弹窗配置已保存。", "ok")
        return redirect(url_for("admin_popup"))
    db = get_db()
    posts = [dict(r) for r in db.execute(
        "SELECT id, title FROM posts ORDER BY created_at DESC, id DESC"
    ).fetchall()]
    return render_template("admin_popup.html", settings=get_settings(), posts=posts)


# --------------------------------------------------------------------------
# 后台：点赞管理
# --------------------------------------------------------------------------
@app.route("/admin/likes", methods=["GET", "POST"])
@login_required
def admin_likes():
    if request.method == "POST":
        set_setting("likes_enabled", "1" if request.form.get("likes_enabled") else "0")
        flash("点赞设置已保存。", "ok")
        return redirect(url_for("admin_likes"))
    db = get_db()
    top = [dict(r) for r in db.execute(
        """SELECT p.id, p.title, COUNT(l.visitor_id) AS likes
           FROM posts p LEFT JOIN post_likes l ON l.post_id = p.id
           GROUP BY p.id ORDER BY likes DESC, p.id DESC LIMIT 12"""
    ).fetchall()]
    return render_template("admin_likes.html", settings=get_settings(), top=top)


# --------------------------------------------------------------------------
# 后台：打赏管理
# --------------------------------------------------------------------------
@app.route("/admin/reward", methods=["GET", "POST"])
@login_required
def admin_reward():
    if request.method == "POST":
        set_setting("reward_enabled", "1" if request.form.get("reward_enabled") else "0")
        set_setting("reward_title", request.form.get("reward_title", "").strip())
        set_setting("reward_desc", request.form.get("reward_desc", "").strip())
        flash("打赏设置已保存。", "ok")
        return redirect(url_for("admin_reward"))
    return render_template(
        "admin_reward.html",
        settings=get_settings(),
        methods=get_reward_methods(enabled_only=False),
    )


@app.route("/admin/reward/add", methods=["POST"])
@login_required
def admin_reward_add():
    db = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("方式名称不能为空。", "error")
        return redirect(url_for("admin_reward"))
    row = db.execute("SELECT COALESCE(MAX(sort), 0) AS m FROM reward_methods").fetchone()
    db.execute(
        """INSERT INTO reward_methods(name, type, image, url, note, sort, enabled, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (name, request.form.get("type", "qr"), request.form.get("image", "").strip(),
         request.form.get("url", "").strip(), request.form.get("note", "").strip(),
         row["m"] + 1, 1 if request.form.get("enabled") else 0,
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    flash("打赏方式已添加。", "ok")
    return redirect(url_for("admin_reward"))


@app.route("/admin/reward/<int:method_id>/delete", methods=["POST"])
@login_required
def admin_reward_delete(method_id):
    db = get_db()
    db.execute("DELETE FROM reward_methods WHERE id = ?", (method_id,))
    db.commit()
    flash("打赏方式已删除。", "ok")
    return redirect(url_for("admin_reward"))


# --------------------------------------------------------------------------
# 后台：私密入口
# --------------------------------------------------------------------------
@app.route("/admin/private", methods=["GET", "POST"])
@login_required
def admin_private():
    if request.method == "POST":
        label = request.form.get("private_label", "").strip() or "私密空间"
        desc = request.form.get("private_desc", "").strip()
        pwd = request.form.get("private_password", "").strip()
        enabled = bool(request.form.get("private_enabled"))
        current = get_settings()
        if pwd:
            set_setting("private_password_hash", hash_password(pwd))
        elif enabled and not current.get("private_password_hash"):
            flash("请先设置私密入口密码。", "error")
            enabled = False
        set_setting("private_label", label)
        set_setting("private_desc", desc)
        set_setting("private_enabled", "1" if enabled else "0")
        flash("私密入口设置已保存。", "ok")
        return redirect(url_for("admin_private"))
    return render_template("admin_private.html", settings=get_settings())


# --------------------------------------------------------------------------
# 后台：站点设置
# --------------------------------------------------------------------------
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    db = get_db()
    if request.method == "POST":
        fields = [
            "site_title", "site_subtitle", "site_description", "site_logo",
            "footer_text", "icp", "police", "police_url", "copyright",
            "music_enabled", "player_autoplay",
        ]
        for key in fields:
            if key in ("music_enabled", "player_autoplay"):
                set_setting(key, "1" if request.form.get(key) else "0")
            else:
                set_setting(key, request.form.get(key, ""))

        # 后台隐秘路径
        new_path = request.form.get("admin_secret_path", "").strip().lstrip("/")
        reserved = RESERVED_PATHS
        if new_path:
            if not re.match(r"^[A-Za-z0-9_-]{4,40}$", new_path):
                flash("隐秘路径只能包含字母、数字、下划线、短横线，长度 4-40。", "error")
            elif new_path.lower() in reserved:
                flash("该路径为系统保留路径，请换一个。", "error")
            else:
                set_setting("admin_secret_path", new_path)

        # 后台二级密码
        new_gate = request.form.get("admin_gate_password", "").strip()
        if new_gate:
            set_setting("admin_gate_password_hash", hash_password(new_gate))

        flash("设置已保存。", "ok")
        return redirect(url_for("admin_settings"))

    settings = get_settings()
    tracks = build_tracks()
    return render_template("admin_settings.html", settings=settings, tracks=tracks)


# --------------------------------------------------------------------------
# 后台：音乐
# --------------------------------------------------------------------------
@app.route("/admin/music", methods=["GET"])
@login_required
def admin_music():
    tracks = build_tracks()
    return render_template("admin_music.html", tracks=tracks, settings=get_settings())


@app.route("/admin/music/settings", methods=["POST"])
@login_required
def admin_music_settings():
    style = request.form.get("player_style", "vinyl")
    if style not in ("vinyl", "card"):
        style = "vinyl"
    set_setting("player_style", style)
    try:
        vol = max(0, min(100, int(request.form.get("player_volume", "80") or "80")))
    except ValueError:
        vol = 80
    set_setting("player_volume", str(vol))
    flash("播放器设置已保存。", "ok")
    return redirect(url_for("admin_music"))


@app.route("/admin/music/add", methods=["POST"])
@login_required
def admin_music_add():
    db = get_db()
    title = request.form.get("title", "").strip() or "未命名曲目"
    artist = request.form.get("artist", "").strip()
    platform = request.form.get("platform", "custom")
    ref = request.form.get("ref", "").strip()
    audio_url = request.form.get("audio_url", "").strip()
    cover = request.form.get("cover", "").strip()
    now = datetime.now().isoformat(timespec="seconds")
    # sort 取最大值 +1
    row = db.execute("SELECT COALESCE(MAX(sort), 0) AS m FROM tracks").fetchone()
    sort = row["m"] + 1
    db.execute(
        """INSERT INTO tracks(title, artist, platform, ref, audio_url, cover, sort, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (title, artist, platform, ref, audio_url, cover, sort, now),
    )
    db.commit()
    flash("曲目已添加。", "ok")
    return redirect(url_for("admin_music"))


@app.route("/admin/music/<int:track_id>/delete", methods=["POST"])
@login_required
def admin_music_delete(track_id):
    db = get_db()
    db.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    db.commit()
    flash("曲目已删除。", "ok")
    return redirect(url_for("admin_music"))


@app.route("/admin/music/<int:track_id>/edit", methods=["GET", "POST"])
@login_required
def admin_music_edit(track_id):
    db = get_db()
    t = db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if not t:
        abort(404)
    if request.method == "POST":
        db.execute(
            """UPDATE tracks SET title=?, artist=?, platform=?, ref=?, audio_url=?, cover=?
               WHERE id=?""",
            (
                request.form.get("title", "").strip() or "未命名曲目",
                request.form.get("artist", "").strip(),
                request.form.get("platform", "custom"),
                request.form.get("ref", "").strip(),
                request.form.get("audio_url", "").strip(),
                request.form.get("cover", "").strip(),
                track_id,
            ),
        )
        db.commit()
        flash("曲目已更新。", "ok")
        return redirect(url_for("admin_music"))
    return render_template("admin_music_edit.html", track=dict(t))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
else:
    init_db()
