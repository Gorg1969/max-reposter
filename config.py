# config.py
# ============================================================
# Конфигурация max-reposter
# ============================================================

import os

# ============ ТОКЕН БОТА ============
TOKEN = os.environ.get("MAX_TOKEN") or os.environ.get("MAX_BOT_TOKEN") or os.environ.get("TOKEN")

# ============ API MAX ============
BASE_URL = "https://platform-api2.max.ru"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://maxbot.bothost.tech")

# ============ ГРУППЫ-ИСТОЧНИКИ ============
SOURCE_CHAT_IDS = {
    "-73112487086609",  # ИЗТ-админ
    "-69959827081745",  # ТЯГАЧИ
    "-73112596204049",  # САМОСВАЛЫ
    "-73112639261201",  # ПРИЦЕПЫ
    "-77133991815241",  # СТРОИТЕЛЬНАЯ
    "-73112528570897",  # ЛЕГКИЙ КОММЕРЧЕСКИЙ
    "-73113726634513",  # АВТОБУСЫ
    "-73112356014609",  # КМУ
    "-73112743070225",  # КОММУНАЛЬНАЯ
    "-73113781029393",  # СЕЛЬХОЗ
    "-73112453597713",  # ЛЕСНОЕ
    "-76868172202744"
}

# ============ ЦЕЛЕВОЙ КАНАЛ ============
TARGET_CHANNEL_ID = "-78837970191096"

# ============ ФИЛЬТР ПО ТЕКСТУ ============
TRIGGER_PHRASES = [
    "За покупкой и согласованием скидки обращайтесь",
]

# ============ ЛИМИТЫ ============
MAX_MEDIA_PER_POST = 10
SEND_INTERVAL_SECONDS = 0.6
VIDEO_PROCESS_WAIT = 60

# ============ ДАННЫЕ ============
DATA_DIR = "/app/data"
DEDUP_DB = os.path.join(DATA_DIR, "dedup.db")
ADMIN_DB = os.path.join(DATA_DIR, "admin.db")

# ============ АДМИНКА ============
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "")  # если пусто — авторизация отключена

# ============ ЛОГИРОВАНИЕ ============
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# ============ ХЕЛПЕР ДЛЯ СРАВНЕНИЯ chat_id ============
def _norm(chat_id) -> str:
    """Нормализует chat_id: убирает минус, приводит к строке."""
    return str(chat_id).lstrip("-")

def is_source_chat(chat_id) -> bool:
    """Проверяет, является ли chat_id одним из источников (с учётом знака)."""
    if chat_id is None:
        return False
    s = str(chat_id)
    # Прямое сравнение
    if s in SOURCE_CHAT_IDS:
        return True
    # Сравнение без минуса
    return _norm(s) in {_norm(c) for c in SOURCE_CHAT_IDS}
