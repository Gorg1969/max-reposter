# app.py
# ============================================================
# max-reposter — Flask-сервер + webhook MAX
# ============================================================

import os
os.environ["TZ"] = "Europe/Moscow"
import time
try:
    time.tzset()
except AttributeError:
    pass

import json
import logging
import urllib3
from datetime import datetime

from flask import Flask, request, jsonify, redirect, render_template_string

import requests

from config import (
    TOKEN, BASE_URL, PUBLIC_URL, DATA_DIR,
    SOURCE_CHAT_IDS, TARGET_CHANNEL_ID, TRIGGER_PHRASES,
    DEDUP_DB, LOG_LEVEL, SEND_INTERVAL_SECONDS,
)
from api_client import APIClient
from dedup import Dedup
from media_downloader import MediaDownloader
from queue_manager import QueueManager
from reposter import Reposter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

if not TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН! Проверь MAX_TOKEN в Bothost")

# ============================================================
# Инициализация
# ============================================================
os.makedirs(DATA_DIR, exist_ok=True)

api = APIClient(token=TOKEN, base_url=BASE_URL)
dedup = Dedup(DEDUP_DB)
downloader = MediaDownloader()
queue = QueueManager(api, send_interval=SEND_INTERVAL_SECONDS)
reposter = Reposter(api, downloader, queue, dedup)


# ============================================================
# WEBHOOK
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return webhook()
    return redirect("/debug")


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True) or {}
        update_type = data.get("update_type")

        if update_type == "message_created":
            reposter.on_message_created(data)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.exception(f"❌ webhook: {e}")
        return jsonify({"ok": False}), 500


# ============================================================
# DEBUG UI
# ============================================================

DEBUG_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>max-reposter — статус</title>
    <style>
        body { font-family: Arial; max-width: 1200px; margin: 30px auto; padding: 20px; background: #f5f5f5; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        h1 { margin-top: 0; }
        .btn { display: inline-block; padding: 10px 18px; background: #007bff; color: white; border-radius: 5px; text-decoration: none; margin-right: 8px; margin-bottom: 8px; }
        .btn-green { background: #28a745; }
        .btn:hover { opacity: 0.9; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; color: white; background: #28a745; }
        .badge-red { background: #dc3545; }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; }
        .list { columns: 2; column-gap: 30px; }
        .list code { display: block; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🤖 max-reposter</h1>
        <p>Токен MAX: <b>{{ '✅ есть' if token_set else '❌ НЕТ' }}</b></p>
        <p>В очереди на отправку: <b>{{ queue_size }}</b></p>
        <p>Обработано сообщений (dedup): <b>{{ dedup_count }}</b></p>
    </div>

    <div class="card">
        <h2>📥 Группы-источники ({{ source_count }})</h2>
        <div class="list">
            {% for cid in sources %}
            <code>{{ cid }}</code>
            {% endfor %}
        </div>
    </div>

    <div class="card">
        <h2>📤 Целевой канал</h2>
        <code>{{ target }}</code>
    </div>

    <div class="card">
        <h2>🔎 Фильтр по фразам</h2>
        {% for p in triggers %}
        <code>{{ p }}</code>
        {% endfor %}
    </div>

    <div class="card">
        <h2>⚙️ Действия</h2>
        <a href="/setup_webhook" class="btn btn-green">🔗 Настроить вебхук</a>
        <a href="/debug" class="btn">🔄 Обновить</a>
    </div>
</body>
</html>
"""


@app.route("/debug")
def debug_page():
    try:
        dedup_count = 0
        import sqlite3
        conn = sqlite3.connect(DEDUP_DB)
        dedup_count = conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        conn.close()
    except Exception:
        dedup_count = 0

    return render_template_string(
        DEBUG_PAGE,
        token_set=bool(TOKEN),
        source_count=len(SOURCE_CHAT_IDS),
        sources=sorted(SOURCE_CHAT_IDS),
        target=TARGET_CHANNEL_ID,
        triggers=TRIGGER_PHRASES,
        queue_size=queue.q.qsize(),
        dedup_count=dedup_count,
    )


# ============================================================
# Настройка вебхука
# ============================================================

@app.route("/setup_webhook")
def setup_webhook():
    webhook_url = f"{PUBLIC_URL}/webhook"
    ok = api.setup_webhook(webhook_url)
    if ok:
        return redirect("/debug")
    return f"❌ Не удалось настроить вебхук. Проверь логи.", 500


# ============================================================
# Health-check
# ============================================================

@app.route("/health")
def health():
    return {
        "status": "ok",
        "token_set": bool(TOKEN),
        "sources": len(SOURCE_CHAT_IDS),
        "target": TARGET_CHANNEL_ID,
        "queue": queue.q.qsize(),
    }


# ============================================================
# Запуск
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    logger.info(f"🚀 Запуск max-reposter на порту {port}")
    logger.info(f"   Токен: {'✅' if TOKEN else '❌'}")
    logger.info(f"   Групп-источников: {len(SOURCE_CHAT_IDS)}")
    logger.info(f"   Целевой канал: {TARGET_CHANNEL_ID}")
    logger.info(f"   Фильтров: {len(TRIGGER_PHRASES)}")

    # Автонастройка вебхука
    if TOKEN:
        try:
            api.setup_webhook(f"{PUBLIC_URL}/webhook")
        except Exception as e:
            logger.warning(f"⚠️
