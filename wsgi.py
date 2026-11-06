"""WSGI 入口：供 waitress / gunicorn 等生产服务器使用。"""

from app import app

application = app
