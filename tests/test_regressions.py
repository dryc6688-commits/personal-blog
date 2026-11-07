"""回归测试：覆盖本次优化修复的问题。运行：python -m unittest discover -s tests -v"""
import io
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as A  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        A.DB_PATH = os.path.join(self.tmp.name, "blog.db")
        A.UPLOAD_DIR = os.path.join(self.tmp.name, "uploads")
        os.makedirs(A.UPLOAD_DIR)
        A.LOG_DIR = self.tmp.name
        A._RATE_ATTEMPTS.clear()
        A.init_db()
        db = sqlite3.connect(A.DB_PATH)
        db.execute("UPDATE settings SET value='1' WHERE key='setup_completed'")
        db.commit()
        db.close()
        A.app.config["TESTING"] = True
        self.c = A.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def sql(self, q, args=()):
        db = sqlite3.connect(A.DB_PATH)
        cur = db.execute(q, args)
        db.commit()
        rows = cur.fetchall()
        db.close()
        return rows

    def login(self, client=None):
        client = client or self.c
        with client.session_transaction() as s:
            now = time.time()
            s.update(admin=True, admin_user="admin", admin_gate_passed=True,
                     login_at=now, last_seen=now, _csrf_token="tok",
                     epoch=self.sql("SELECT value FROM settings WHERE key='session_epoch'")[0][0])

    def add_post(self, title, published, content="body"):
        self.sql("INSERT INTO posts(title,type,content,content_format,published,created_at,updated_at)"
                 " VALUES(?,?,?,?,?,?,?)", (title, "code", content, "html", published, "2026-01-01", "2026-01-01"))
        return self.sql("SELECT max(id) FROM posts")[0][0]


class DraftAndViews(Base):
    def test_draft_hidden_from_anonymous_but_visible_to_admin(self):
        pid = self.add_post("draft-title", 0, "draft-body-text")
        self.assertEqual(self.c.get(f"/post/{pid}").status_code, 404)
        self.login()
        r = self.c.get(f"/post/{pid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("draft-body-text".encode(), r.data)

    def test_published_post_is_public(self):
        pid = self.add_post("pub", 1, "public-body")
        self.assertEqual(self.c.get(f"/post/{pid}").status_code, 200)

    def test_like_on_draft_rejected(self):
        pid = self.add_post("d", 0)
        with self.c.session_transaction() as s:
            s["_csrf_token"] = "tok"
        r = self.c.post(f"/api/like/{pid}", headers={"X-CSRF-Token": "tok"})
        self.assertEqual(r.status_code, 404)

    def test_track_validates_post_and_dedupes_pageview(self):
        pid = self.add_post("p", 1)
        for _ in range(3):
            self.c.post("/api/track", json={"event": "pageview", "post_id": pid, "path": f"/post/{pid}"})
        self.c.post("/api/track", json={"event": "pageview", "post_id": 99999})
        n = self.sql("SELECT COUNT(*) FROM analytics WHERE event='pageview' AND demo=0 AND post_id=?", (pid,))[0][0]
        self.assertEqual(n, 1)
        bogus = self.sql("SELECT post_id FROM analytics WHERE demo=0 AND post_id=99999")
        self.assertEqual(bogus, [])

    def test_pagination(self):
        for i in range(A.POSTS_PER_PAGE + 3):
            self.add_post(f"post-number-{i:02d}", 1)
        total = self.sql("SELECT COUNT(*) FROM posts WHERE published=1 AND is_private=0")[0][0]  # 含 3 篇示例文章
        p1 = self.c.get("/").data.decode()
        p2 = self.c.get("/?page=2").data.decode()
        self.assertEqual(p1.count('class="post-card'), A.POSTS_PER_PAGE)
        self.assertEqual(p2.count('class="post-card'), total - A.POSTS_PER_PAGE)
        self.assertIn("pager", p1)
        self.assertEqual(self.c.get("/?page=999").status_code, 200)
        self.assertEqual(self.c.get("/?page=abc").status_code, 200)


class Markdown(Base):
    def test_thread_safe(self):
        docs = {i: f"## Title{i}\n\n```python\nprint({i})\n```\n\n| a | b |\n|---|---|\n| {i} | x |\n" for i in range(8)}
        bad = []

        def work(i):
            for _ in range(300):
                out = A.render_markdown(docs[i])
                if f"Title{i}" not in out or any(f"Title{j}<" in out for j in docs if j != i):
                    bad.append(i)
                    return
        ts = [threading.Thread(target=work, args=(i,)) for i in docs]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(bad, [])


class Sanitizer(Base):
    def test_strips_dangerous_markup(self):
        out = str(A.clean_html(
            '<p onclick="x()" style="color:red;position:fixed;background:url(http://e/x)">a</p>'
            '<script>alert(1)</script><a href="javascript:alert(1)">l</a>'
            '<img src="x" onerror="alert(1)"><iframe src="javascript:alert(1)"></iframe>'))
        for bad in ("onclick", "<script", "javascript:", "onerror", "position", "url("):
            self.assertNotIn(bad, out)
        self.assertIn("color: red", out)

    def test_keeps_editor_output(self):
        html = ('<p style="text-align: center"><font color="#ff0000" size="5">x</font></p>'
                '<div class="post-video-embed"><iframe src="https://player.bilibili.com/p.html?bvid=1" allowfullscreen></iframe></div>'
                '<p><video class="post-video" controls playsinline src="/static/uploads/a.mp4"></video></p>'
                '<p><img src="/static/uploads/a.jpg" alt=""></p><pre><code class="language-python">x</code></pre>')
        out = str(A.clean_html(html))
        for keep in ("player.bilibili.com", "<video", 'class="post-video"', "/static/uploads/a.jpg",
                     "text-align: center", "language-python", "<font"):
            self.assertIn(keep, out)

    def test_post_page_renders_cleaned(self):
        pid = self.add_post("x", 1, '<p>ok</p><script>alert(1)</script>')
        r = self.c.get(f"/post/{pid}")
        self.assertIn(b"<p>ok</p>", r.data)
        self.assertNotIn(b"alert(1)", r.data)


class Upload(Base):
    def post_file(self, name, data):
        self.login()
        return self.c.post("/admin/upload", data={"file": (io.BytesIO(data), name)},
                           headers={"X-CSRF-Token": "tok"}, content_type="multipart/form-data")

    def test_rejects_disguised_file(self):
        r = self.post_file("evil.png", b"<html><script>alert(1)</script></html>")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(os.listdir(A.UPLOAD_DIR), [])

    def test_rejects_unknown_extension(self):
        self.assertEqual(self.post_file("a.svg", b"<svg/>").status_code, 400)

    def test_jpeg_exif_gps_removed_and_rotated(self):
        from PIL import Image
        im = Image.new("RGB", (40, 20), "red")
        ex = Image.Exif()
        ex[0x0112] = 6
        ex.get_ifd(0x8825)[1] = "N"
        buf = io.BytesIO()
        im.save(buf, "JPEG", exif=ex)
        r = self.post_file("photo.jpg", buf.getvalue())
        self.assertEqual(r.status_code, 200, r.data)
        saved = os.path.join(A.UPLOAD_DIR, r.get_json()["url"].rsplit("/", 1)[-1])
        with Image.open(saved) as out:
            self.assertEqual(len(dict(out.getexif())), 0)
            self.assertEqual(out.size, (20, 40))

    def test_valid_png_and_mp3_accepted(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, "PNG")
        self.assertEqual(self.post_file("a.png", buf.getvalue()).status_code, 200)
        self.assertEqual(self.post_file("a.mp3", b"ID3\x03\x00" + b"\x00" * 40).status_code, 200)


class Security(Base):
    def test_ipv6_rate_key_uses_prefix(self):
        with A.app.test_request_context("/", environ_base={"REMOTE_ADDR": "2001:db8:1:2::1"}):
            k1 = A.rate_limit_key("x")
        with A.app.test_request_context("/", environ_base={"REMOTE_ADDR": "2001:db8:1:2:ffff::9"}):
            k2 = A.rate_limit_key("x")
        with A.app.test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.5"}):
            k3 = A.rate_limit_key("x")
        self.assertEqual(k1, k2)
        self.assertEqual(k3, "x:203.0.113.5")

    def test_totp_code_cannot_be_replayed(self):
        import pyotp
        secret = pyotp.random_base32()
        code = pyotp.TOTP(secret).now()
        with A.app.test_request_context("/"):
            self.assertTrue(A.verify_totp_once(secret, code))
            self.assertFalse(A.verify_totp_once(secret, code))
            self.assertFalse(A.verify_totp_once(secret, "000000" if code != "000000" else "111111"))

    def test_password_change_revokes_other_sessions(self):
        other = A.app.test_client()
        self.login()
        self.login(other)
        self.assertEqual(other.get("/admin").status_code, 200)
        uid = self.sql("SELECT id FROM users LIMIT 1")[0][0]
        r = self.c.post(f"/admin/users/{uid}/password", data={"password": "new-password-1"},
                        headers={"X-CSRF-Token": "tok"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/admin").status_code, 200)      # 当前会话保持登录
        r = other.get("/admin")
        self.assertIn(r.status_code, (302, 404))                    # 其他会话被踢下线
        with other.session_transaction() as s:
            self.assertFalse(s.get("admin"))


class Database(Base):
    def test_wal_indexes_and_placeholders(self):
        db = sqlite3.connect(A.DB_PATH)
        self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        idx = {r[1] for r in db.execute("PRAGMA index_list(analytics)")}
        self.assertIn("idx_analytics_event_post", idx)
        db.close()
        s = {k: v for k, v in self.sql("SELECT key,value FROM settings")}
        self.assertEqual(s["icp"], "")
        self.assertEqual(s["police"], "")

    def test_old_placeholder_icp_cleared_on_upgrade(self):
        self.sql("UPDATE settings SET value='粤ICP备00000000号-1' WHERE key='icp'")
        A.init_db()
        self.assertEqual(self.sql("SELECT value FROM settings WHERE key='icp'")[0][0], "")

    def test_settings_cache_invalidated_by_set_setting(self):
        with A.app.test_request_context("/"):
            self.assertEqual(A.get_settings()["site_title"], "我的个人博客")
            A.set_setting("site_title", "新标题")
            self.assertEqual(A.get_settings()["site_title"], "新标题")


if __name__ == "__main__":
    unittest.main()
