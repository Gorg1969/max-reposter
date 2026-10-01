# app.py
# ============================================================
# max-reposter-debug
# Минимальный бот для перехвата JSON вебхуков от MAX
# ============================================================

import os
os.environ['TZ'] = 'Europe/Moscow'
import time
try:
    time.tzset()
except AttributeError:
    pass

import json
import logging
import urllib3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file, redirect

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ КОНФИГ ============
TOKEN = os.environ.get("MAX_TOKEN") or os.environ.get("MAX_BOT_TOKEN") or os.environ.get("TOKEN")
BASE_URL = "https://platform-api2.max.ru"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://maxbot.bothost.tech")
DATA_DIR = "/app/data"
WEBHOOKS_DIR = os.path.join(DATA_DIR, "webhooks")

os.makedirs(WEBHOOKS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

if not TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН! Проверь переменную MAX_TOKEN в Bothost")


# ============================================================
# Сохранение вебхука в файл
# ============================================================

def save_webhook(data: dict) -> str:
    """Сохраняет вебхук в /app/data/webhooks/YYYY-MM-DD_HH-MM-SS_mmm.json"""
    now = datetime.now()
    ts = now.strftime('%Y-%m-%d_%H-%M-%S_%f')[:-3]  # миллисекунды
    filename = f"{ts}.json"
    filepath = os.path.join(WEBHOOKS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 Вебхук сохранён: {filename}")
    return filename


def list_webhooks():
    """Список файлов вебхуков, отсортированный от новых к старым."""
    try:
        files = [f for f in os.listdir(WEBHOOKS_DIR) if f.endswith('.json')]
        files.sort(reverse=True)
        return files
    except Exception as e:
        logger.error(f"❌ list_webhooks: {e}")
        return []


def load_webhook(filename: str):
    """Загружает содержимое одного вебхука."""
    safe = os.path.basename(filename)
    filepath = os.path.join(WEBHOOKS_DIR, safe)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================
# WEBHOOK — принимает события от MAX
# ============================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return webhook()
    return redirect('/debug')


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(silent=True) or {}
        logger.info("=" * 70)
        logger.info(f"📩 WEBHOOK ПОЛУЧЕН")
        logger.info(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info("=" * 70)

        save_webhook(data)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.exception(f"❌ Ошибка обработки вебхука: {e}")
        return jsonify({"ok": False}), 500


# ============================================================
# DEBUG UI — показывает все пойманные вебхуки
# ============================================================

DEBUG_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Webhook Debug — max-reposter</title>
    <style>
        body { font-family: -apple-system, Arial, sans-serif; max-width: 1200px;
               margin: 30px auto; padding: 20px; background: #f5f5f5; color: #333; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        h1 { margin-top: 0; }
        .btn { display: inline-block; padding: 10px 18px; background: #007bff; color: white;
               border-radius: 5px; text-decoration: none; margin-right: 8px; margin-bottom: 8px;
               border: none; cursor: pointer; font-size: 14px; }
        .btn-green { background: #28a745; }
        .btn-gray { background: #6c757d; }
        .btn-red { background: #dc3545; }
        .btn:hover { opacity: 0.9; }
        .count-big { font-size: 42px; font-weight: bold; color: #28a745; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border-bottom: 1px solid #eee; text-align: left;
                 font-size: 13px; vertical-align: top; }
        th { background: #f8f9fa; font-weight: bold; }
        tr:hover { background: #fafafa; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
                 font-size: 11px; font-weight: bold; color: white; }
        .badge-msg { background: #007bff; }
        .badge-other { background: #6c757d; }
        .empty { text-align: center; color: #999; padding: 40px; }
        pre { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px;
              font-size: 12px; line-height: 1.5; overflow-x: auto; max-height: 600px;
              overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
        .hint { color: #666; font-size: 13px; }
        details summary { cursor: pointer; color: #007bff; font-size: 13px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🐛 Webhook Debug</h1>
        <p>Токен MAX: <b>{{ '✅ есть' if token_set else '❌ НЕТ' }}</b></p>
        <p>Поймано вебхуков: <span class="count-big">{{ files|length }}</span></p>
        <p class="hint">Каждый входящий вебхук сохраняется в файл. Здесь можно всё посмотреть и скачать.</p>

        <a href="/debug" class="btn">🔄 Обновить</a>
        <a href="/setup_webhook" class="btn btn-green">🔗 Настроить вебхук</a>
        <a href="/download_all" class="btn btn-gray">📥 Скачать все JSON одним файлом</a>
        <a href="/clear" class="btn btn-red" onclick="return confirm('Удалить все вебхуки?');">🗑️ Очистить</a>
    </div>

    <div class="card">
        <h2>📋 Список пойманных вебхуков</h2>
        {% if files %}
        <table>
            <thead>
                <tr>
                    <th>№</th>
                    <th>Время</th>
                    <th>Тип события</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                {% for f in files %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ f }}</td>
                    <td>
                        {% if f in previews %}
                            {% set p = previews[f] %}
                            {% if p.update_type == 'message_created' %}
                                <span class="badge badge-msg">message_created</span>
                                {% if p.has_media %}
                                    🖼️ медиа: {{ p.media_count }}
                                {% endif %}
                                {% if p.text_preview %}
                                    <div class="hint">{{ p.text_preview }}</div>
                                {% endif %}
                            {% else %}
                                <span class="badge badge-other">{{ p.update_type or '?' }}</span>
                            {% endif %}
                        {% else %}
                            <span class="badge badge-other">?</span>
                        {% endif %}
                    </td>
                    <td>
                        <a href="/view/{{ f }}" class="btn" style="padding:6px 12px;font-size:12px;">👁️ Открыть</a>
                        <a href="/download/{{ f }}" class="btn btn-gray" style="padding:6px 12px;font-size:12px;">📥 Скачать</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty">
            <p style="font-size:48px;margin:0">📭</p>
            <p>Пока ни одного вебхука не поймано.</p>
            <p class="hint">1. Убедись, что бот добавлен в группу.<br>
               2. Отправь в группу текст, фото и видео.<br>
               3. Обнови эту страницу.</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route('/debug')
def debug_page():
    files = list_webhooks()
    previews = {}
    for f in files[:50]:  # превью только для 50 последних
        try:
            data = load_webhook(f)
            if not data:
                continue
            update_type = data.get('update_type', '?')
            msg = data.get('message', {}) or {}
            body = msg.get('body', {}) or {}
            text = (body.get('text') or '').strip()
            attachments = body.get('attachments') or []
            previews[f] = {
                'update_type': update_type,
                'text_preview': text[:80],
                'has_media': len(attachments) > 0,
                'media_count': len(attachments),
            }
        except Exception:
            pass
    return render_template_string(
        DEBUG_PAGE,
        files=files,
        previews=previews,
        token_set=bool(TOKEN),
    )


@app.route('/view/<path:filename>')
def view_webhook(filename):
    data = load_webhook(filename)
    if data is None:
        return "❌ Файл не найден", 404
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{filename}</title>
        <style>
            body {{ font-family: Arial; max-width: 1200px; margin: 30px auto;
                    padding: 20px; background: #f5f5f5; }}
            .card {{ background: white; padding: 20px; border-radius: 8px;
                     box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            pre {{ background: #1e1e1e; color: #d4d4d4; padding: 20px;
                   border-radius: 5px; font-size: 13px; line-height: 1.6;
                   overflow-x: auto; white-space: pre-wrap; word-break: break-all; }}
            .btn {{ display: inline-block; padding: 10px 18px; background: #007bff;
                    color: white; border-radius: 5px; text-decoration: none;
                    margin-right: 8px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📄 {filename}</h1>
            <a href="/debug" class="btn">← Назад</a>
            <a href="/download/{filename}" class="btn">📥 Скачать</a>
            <pre>{pretty}</pre>
        </div>
    </body>
    </html>
    """


@app.route('/download/<path:filename>')
def download_webhook(filename):
    safe = os.path.basename(filename)
    filepath = os.path.join(WEBHOOKS_DIR, safe)
    if not os.path.exists(filepath):
        return "❌ Файл не найден", 404
    return send_file(filepath, as_attachment=True, download_name=safe)


@app.route('/download_all')
def download_all():
    """Все вебхуки одним JSON-файлом."""
    files = list_webhooks()
    bundle = []
    for f in files:
        try:
            data = load_webhook(f)
            bundle.append({'file': f, 'data': data})
        except Exception:
            pass
    out_path = os.path.join(DATA_DIR, 'webhooks_all.json')
    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(bundle, fp, ensure_ascii=False, indent=2)
    return send_file(out_path, as_attachment=True,
                     download_name=f'webhooks_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')


@app.route('/clear')
def clear_webhooks():
    try:
        for f in os.listdir(WEBHOOKS_DIR):
            if f.endswith('.json'):
                os.remove(os.path.join(WEBHOOKS_DIR, f))
        return redirect('/debug')
    except Exception as e:
        logger.error(f"❌ clear: {e}")
        return f"❌ {e}", 500


# ============================================================
# Настройка вебхука
# ============================================================

@app.route('/setup_webhook')
def setup_webhook():
    token = request.args.get('token') or TOKEN
    if not token:
        return "❌ Нет токена", 400

    webhook_url = f"{PUBLIC_URL}/webhook"
    headers = {"Authorization": token, "Content-Type": "application/json"}

    # Удаляем старые подписки
    try:
        r = requests.get(f"{BASE_URL}/subscriptions", headers=headers,
                         timeout=30, verify=False)
        if r.status_code == 200:
            for sub in r.json().get('subscriptions', []):
                old_url = sub.get('url')
                if old_url:
                    requests.delete(f"{BASE_URL}/subscriptions", headers=headers,
                                    params={"url": old_url}, timeout=30, verify=False)
                    logger.info(f"🗑️ Удалена старая подписка: {old_url}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить старые подписки: {e}")

    # Регистрируем новую
    try:
        r = requests.post(
            f"{BASE_URL}/subscriptions",
            headers=headers,
            json={
                "url": webhook_url,
                "update_types": ["message_created", "bot_started", "bot_stopped"],
            },
            timeout=30,
            verify=False,
        )
        if r.status_code == 200:
            logger.info(f"✅ Вебхук зарегистрирован: {webhook_url}")
            return redirect('/debug')
        else:
            logger.error(f"❌ Ошибка: {r.status_code} - {r.text}")
            return f"❌ Ошибка {r.status_code}: {r.text}", 500
    except Exception as e:
        logger.exception(f"❌ setup_webhook: {e}")
        return f"❌ {e}", 500


# ============================================================
# Служебные
# ============================================================

@app.route('/health')
def health():
    return {"status": "ok", "token_set": bool(TOKEN), "webhooks": len(list_webhooks())}


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    logger.info(f"🚀 Запуск max-reposter-debug на порту {port}")
    logger.info(f"   TOKEN: {'✅' if TOKEN else '❌'}")
    logger.info(f"   PUBLIC_URL: {PUBLIC_URL}")
    logger.info(f"   WEBHOOKS_DIR: {WEBHOOKS_DIR}")

    # Автонастройка вебхука при старте
    if TOKEN:
        try:
            webhook_url = f"{PUBLIC_URL}/webhook"
            headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
            r = requests.post(
                f"{BASE_URL}/subscriptions",
                headers=headers,
                json={
                    "url": webhook_url,
                    "update_types": ["message_created", "bot_started", "bot_stopped"],
                },
                timeout=10,
                verify=False,
            )
            if r.status_code == 200:
                logger.info(f"✅ Вебхук настроен при запуске: {webhook_url}")
            else:
                logger.warning(f"⚠️ Не удалось настроить вебхук: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка настройки вебхука при запуске: {e}")

    app.run(host='0.0.0.0', port=port, threaded=True)
