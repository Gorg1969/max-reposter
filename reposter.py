# reposter.py
# ============================================================
# Главная логика: извлечение контента → фильтр → скачивание → отправка
# ============================================================

import logging

from config import (
    SOURCE_CHAT_IDS,
    TARGET_CHANNEL_ID,
    TRIGGER_PHRASES,
    MAX_MEDIA_PER_POST,
)
from html_builder import build_html_text

logger = logging.getLogger(__name__)


class Reposter:
    def __init__(self, api, downloader, queue, dedup):
        self.api = api
        self.downloader = downloader
        self.queue = queue
        self.dedup = dedup

    # ============================================================
    # Обработка входящего вебхука
    # ============================================================
    def on_message_created(self, update: dict):
        try:
            msg = update.get("message", {}) or {}
            recipient = msg.get("recipient", {}) or {}
            body = msg.get("body", {}) or {}

            chat_id = str(recipient.get("chat_id", ""))
            if chat_id not in SOURCE_CHAT_IDS:
                return  # не наша группа

            # Извлекаем контент
            text, attachments, markup = self._extract_content(msg)

            # Дедуп
            mid = body.get("mid") or msg.get("link", {}).get("message", {}).get("mid")
            if not mid or self.dedup.seen(mid):
                return

            # Фильтр по фразе
            if not self._match_trigger(text):
                logger.debug(f"⏭️ Не подходит по фильтру: {text[:80]}")
                return

            logger.info(
                f"🎯 Найдено объявление! mid={mid}, "
                f"text={len(text)} симв., медиа={len(attachments)}"
            )

            # Скачиваем + загружаем медиа
            tokens, types = self._reupload_media(attachments)

            # Собираем HTML со ссылками
            html_text = build_html_text(text, markup)

            # В очередь
            self.queue.enqueue(TARGET_CHANNEL_ID, html_text, tokens, types)

            # Помечаем как обработанное
            self.dedup.mark(mid)

        except Exception as e:
            logger.exception(f"❌ on_message_created: {e}")

    # ============================================================
    # Извлечение текста / медиа / markup
    # ============================================================
    def _extract_content(self, msg: dict):
        """
        Если сообщение — пересылка (link.type == "forward"),
        берём данные из link.message. Иначе — из body.
        """
        link = msg.get("link") or {}

        if link.get("type") == "forward":
            inner = link.get("message") or {}
            text = inner.get("text", "") or ""
            attachments = inner.get("attachments", []) or []
            markup = inner.get("markup", []) or []
            return text, attachments, markup

        body = msg.get("body") or {}
        text = body.get("text", "") or ""
        attachments = body.get("attachments", []) or []
        return text, attachments, []

    # ============================================================
    # Проверка фильтра по фразе
    # ============================================================
    def _match_trigger(self, text: str) -> bool:
        if not text:
            return False
        return any(phrase in text for phrase in TRIGGER_PHRASES)

    # ============================================================
    # Скачивание + загрузка медиа заново
    # ============================================================
    def _reupload_media(self, attachments: list):
        tokens = []
        types = []

        if not attachments:
            return tokens, types

        for att in attachments[:MAX_MEDIA_PER_POST]:
            att_type = att.get("type")
            payload = att.get("payload") or {}
            url = payload.get("url")

            if not url:
                logger.warning(f"⚠️ Нет url в attachment типа {att_type}, пропускаем")
                continue

            # MAX понимает типы: image / video
            if att_type not in ("image", "video"):
                logger.warning(f"⚠️ Неизвестный тип вложения: {att_type}")
                continue

            file_bytes = self.downloader.download(url)
            if not file_bytes:
                logger.error(f"❌ Не удалось скачать {att_type}: {url[:80]}")
                continue

            token = self.api.upload_file(
                file_bytes,
                filename=f"{att_type}.bin",
                file_type=att_type,
            )
            if token:
                tokens.append(token)
                types.append(att_type)
                logger.info(f"✅ Медиа перезагружено: {att_type}")
            else:
                logger.error(f"❌ Не удалось перезагрузить {att_type}")

        return tokens, types
