# app.py
# ============================================================
# max-reposter — Flask + webhook MAX + админка + команды бота
# v4: добавлены эндпоинты /test_subs и /test_me, логирование RAW
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
    DEDUP_DB, ADMIN_DB, LOG_LEVEL, SEND_INTERVAL_SECONDS,
    ADMIN_USER, ADMIN_PASS,
)
from api_client import APIClient
from dedup import Dedup
from media_downloader import MediaDownloader
from queue_manager import QueueManager
from reposter import Reposter
from admin_db import AdminDB
from auth import require_admin
from admin_templates import (
    admin_index_html, admin_repost_detail_html,
    admin_settings_html, admin_blacklist_html,
)

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

if not ADMIN_PASS:
    logger.warning("⚠️ ADMIN_PASS не задан — админка открыта без пароля!")

# ============================================================
# Инициализация
# ============================================================
os.makedirs(DATA_DIR, exist_ok=True)

api = APIClient(token=TOKEN, base_url=BASE_URL)
dedup = Dedup(DEDUP_DB)
admin_db = AdminDB(ADMIN_DB)
downloader = MediaDownloader()
queue = QueueManager(api, send_interval=SEND_INTERVAL_SECONDS)
reposter = Reposter(api, downloader, queue, dedup, admin_db)


# ============================================================
# КОМАНДЫ БОТА
# ============================================================

def handle_bot_command(dialog_chat_id: int, user_id: int, text: str) -> bool:
    cmd = (text or "").strip().lower()

    def reply(msg):
        return api.send_post(dialog_chat_id, msg, [], [])

    if cmd == "/start":
        stats = admin_db.get_stats()
        reply(
            "🤖 **max-reposter**\n\n"
            "Бот слушает 11 групп и пересылает объявления в канал.\n\n"
            f"📊 Всего пересылок: **{stats['total']}**\n"
            f"✅ Успешно: **{stats['success']}**\n"
            f"❌ Ошибок: **{stats['errors']}**\n"
            f"📅 Сегодня: **{stats['today']}**\n\n"
            "🔗 **Админка:**\n"
            f"{PUBLIC_URL}/admin\n\n"
            "**Команды:**\n"
            "/status — статистика\n"
            "/myid — ваш user_id\n"
            "/webhook — статус вебхука\n"
            "/help — справка"
        )
        return True

    if cmd == "/status":
        stats = admin_db.get_stats()
        reply(
            f"📊 **Статус:**\n\n"
            f"📦 Всего: {stats['total']}\n"
            f"✅ Успешно: {stats['success']}\n"
            f"❌ Ошибок: {stats['errors']}\n"
            f"📅 Сегодня: {stats['today']}\n"
            f"📥 В очереди: {queue.q.qsize()}"
        )
        return True

    if cmd == "/myid":
        reply(f"🆔 **Ваш user_id:** `{user_id}`\n💬 **chat_id диалога:** `{dialog_chat_id}`")
        return True

    if cmd == "/webhook":
        reply(
            f"🔗 **Webhook URL:**\n{PUBLIC_URL}/webhook\n\n"
            f"Перерегистрация:\n{PUBLIC_URL}/setup_webhook\n\n"
            f"Отладка:\n{PUBLIC_URL}/test_subs\n{PUBLIC_URL}/test_me"
        )
        return True

    if cmd == "/help":
        reply(
            "🆘 **Справка**\n\n"
            "/start — главное меню\n"
            "/status — статистика\n"
            "/myid — ваш user_id\n"
            "/webhook — статус вебхука\n\n"
            f"🌐 Админка: {PUBLIC_URL}/admin"
        )
        return True

    return False


# ============================================================
# WEBHOOK
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return webhook()
    return redirect("/admin")


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True) or {}
        logger.info(f"RAW: {json.dumps(data, ensure_ascii=False)}")

        update_type = data.get("update_type")

        # -------- bot_added / bot_removed --------
        if update_type in ("bot_added", "bot_removed"):
            logger.info(f"🤖 {update_type}: {json.dumps(data, ensure_ascii=False)}")
            return jsonify({"ok": True}), 200

        if update_type == "message_created":
            msg = data.get("message", {}) or {}
            recipient = msg.get("recipient", {}) or {}
            sender = msg.get("sender", {}) or {}
            body = msg.get("body", {}) or {}

            chat_id = recipient.get("chat_id")
            chat_type = recipient.get("chat_type", "")
            user_id = sender.get("user_id")
            text = (body.get("text") or "").strip()

            logger.info("=" * 70)
            logger.info(f"📩 WEBHOOK message_created")
            logger.info(f"    chat_type = {chat_type}")
            logger.info(f"    chat_id   = {chat_id}")
            logger.info(f"    user_id   = {user_id}")
            logger.info(f"    text      = {text[:200]}")

            # ============ ЛИЧНЫЙ ДИАЛОГ ============
            if chat_type == "dialog":
                logger.info(f"🤖 ЛИЧНЫЙ ДИАЛОГ, команда='{text}'")
                if handle_bot_command(chat_id, user_id, text):
                    logger.info(f"    ✅ команда обработана")
                else:
                    logger.info(f"    ⚠️ команда не распознана")
                logger.info("=" * 70)
                return jsonify({"ok": True}), 200

            # ============ ГРУППА-ИСТОЧНИК ============
            chat_id_str = str(chat_id)
            in_sources = chat_id_str in SOURCE_CHAT_IDS
            logger.info(f"    in_sources = {in_sources}")
            logger.info(f"    SOURCE_CHAT_IDS = {sorted(SOURCE_CHAT_IDS)}")

            if in_sources:
                logger.info(f"📨 Передаю в reposter...")
                reposter.on_message_created(data)
            else:
                logger.info(f"    ⏭️ не из источников")

            logger.info("=" * 70)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.exception(f"❌ webhook: {e}")
        return jsonify({"ok": False}), 500


# ============================================================
# АДМИНКА
# ============================================================

@app.route("/admin")
@require_admin
def admin_page():
    status = request.args.get("status")
    recent = admin_db.get_reposts(limit=100, status=status)
    stats = admin_db.get_stats()

    import sqlite3
    try:
        conn = sqlite3.connect(ADMIN_DB)
        bl_count = conn.execute("SELECT COUNT(*) FROM blacklist").fetchone()[0]
        conn.close()
    except Exception:
        bl_count = 0

    return admin_index_html(
        stats=stats,
        recent=recent,
        sources=SOURCE_CHAT_IDS,
        target=TARGET_CHANNEL_ID,
        triggers=TRIGGER_PHRASES,
        blacklist_count=bl_count,
    )


@app.route("/admin/repost/<path:mid>")
@require_admin
def admin_repost_detail(mid):
    import sqlite3
    conn = sqlite3.connect(ADMIN_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM reposted WHERE mid = ?", (mid,)).fetchone()
    conn.close()
    if not row:
        return "❌ Не найдено", 404
    return admin_repost_detail_html(dict(row))


@app.route("/admin/settings")
@require_admin
def admin_settings():
    return admin_settings_html(
        sources=SOURCE_CHAT_IDS,
        target=TARGET_CHANNEL_ID,
        triggers=TRIGGER_PHRASES,
    )


@app.route("/admin/blacklist")
@require_admin
def admin_blacklist():
    import sqlite3
    conn = sqlite3.connect(ADMIN_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM blacklist ORDER BY created_at DESC").fetchall()
    conn.close()
    return admin_blacklist_html([dict(r) for r in rows])


@app.route("/admin/blacklist/add/<path:mid>")
@require_admin
def admin_blacklist_add(mid):
    admin_db.blacklist_add(mid, reason="manual")
    return redirect("/admin")


@app.route("/admin/blacklist/remove/<path:mid>")
@require_admin
def admin_blacklist_remove(mid):
    import sqlite3
    conn = sqlite3.connect(ADMIN_DB)
    conn.execute("DELETE FROM blacklist WHERE mid = ?", (mid,))
    conn.commit()
    conn.close()
    return redirect("/admin/blacklist")


@app.route("/admin/delete/<path:mid>")
@require_admin
def admin_delete(mid):
    admin_db.delete_repost(mid)
    return redirect("/admin")


@app.route("/admin/cleanup_history")
@require_admin
def admin_cleanup_history():
    admin_db.cleanup_old(days=90)
    return redirect("/admin/settings")


# ============================================================
# Настройка вебхука
# ============================================================

@app.route("/setup_webhook")
def setup_webhook():
    webhook_url = f"{PUBLIC_URL}/webhook"
    ok = api.setup_webhook(webhook_url)
    if ok:
        return redirect("/admin")
    return "❌ Не удалось настроить вебхук. Проверь логи.", 500


# ============================================================
# Debug / Health
# ============================================================

@app.route("/debug")
def debug_page():
    import sqlite3
    try:
        conn = sqlite3.connect(DEDUP_DB)
        dedup_count = conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        conn.close()
    except Exception:
        dedup_count = 0

    stats = admin_db.get_stats()

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Debug</title>
    <style>body{{font-family:Arial;max-width:800px;margin:30px auto;padding:20px;background:#f5f5f5}}
    .card{{background:white;padding:20px;border-radius:8px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
    .btn{{display:inline-block;padding:10px 18px;background:#007bff;color:white;border-radius:5px;text-decoration:none;margin-right:8px}}
    code{{background:#f0f0f0;padding:2px 6px;border-radius:3px}}</style>
    </head><body>
    <div class="card">
        <h1>🐛 Debug</h1>
        <p>Токен: <b>{'✅' if TOKEN else '❌'}</b></p>
        <p>Обработано (dedup): <b>{dedup_count}</b></p>
        <p>Всего пересылок: <b>{stats['total']}</b></p>
        <p>Успешных: <b>{stats['success']}</b>, ошибок: <b>{stats['errors']}</b></p>
        <p>В очереди: <b>{queue.q.qsize()}</b></p>
        <a href="/admin" class="btn">⚙️ Админка</a>
        <a href="/setup_webhook" class="btn">🔗 Вебхук</a>
        <a href="/test_subs" class="btn">📋 Подписки</a>
        <a href="/test_me" class="btn">🤖 Мой бот</a>
        <a href="/debug" class="btn">🔄 Обновить</a>
    </div>
    </body></html>
    """


@app.route("/health")
def health():
    stats = admin_db.get_stats()
    return {
        "status": "ok",
        "token_set": bool(TOKEN),
        "sources": len(SOURCE_CHAT_IDS),
        "target": TARGET_CHANNEL_ID,
        "queue": queue.q.qsize(),
        "stats": stats,
    }


# ============================================================
# ОТЛАДКА: подписки и инфо о боте
# ============================================================

@app.route("/test_subs")
def test_subs():
    """Сырой ответ MAX на GET /subscriptions."""
    return jsonify(api.get_subscriptions_raw())


@app.route("/test_me")
def test_me():
    """Сырой ответ MAX на GET /me."""
    return jsonify(api.get_me_raw())


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
    logger.info(f"   Админ: {ADMIN_USER}, пароль: {'✅' if ADMIN_PASS else '❌'}")

    # Автоперерегистрация вебхука при старте ОТКЛЮЧЕНА —
    # чтобы не создавать гонки. Регистрируйте вручную через /setup_webhook.

    app.run(host="0.0.0.0", port=port, threaded=True)
