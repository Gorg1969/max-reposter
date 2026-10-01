# reposter.py
# ============================================================
# Главная логика: извлечение → фильтр → скачивание → отправка
# с записью в AdminDB
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
    def __init__(self, api, downloader, queue, dedup, admin_db):
        self.api = api
        self.downloader = downloader
        self.queue = queue
        self.dedup = dedup
        self.admin_db = admin_db

    def on_message_created(self, update: dict):
        try:
            msg = update.get("message", {}) or {}
            recipient = msg.get("recipient", {}) or {}
            body = msg.get("body", {}) or {}

            chat_id = str(recipient.get("chat_id", ""))
            if chat_id not in SOURCE_CHAT_IDS:
                return

            # Извлекаем контент
            text, attachments, markup = self._extract_content(msg)

            # Определяем mid
            mid = body.get("mid") or msg.get("link", {}).get("message", {}).get("mid")
            if not mid:
                return

            # Дедуп
            if self.dedup.seen(mid):
                return

            # Чёрный список
            if self.admin_db.blacklist_has(mid):
                logger.info(f"🚫 mid в чёрном списке: {mid}")
                self.dedup.mark(mid)
                return

            # Фильтр по фразе
            if not self._match_trigger(text):
                logger.debug(f"⏭️ Не подходит по фильтру: {text[:80]}")
                return

            logger.info(
                f"🎯 Объявление! mid={mid}, "
                f"text={len(text)} симв., медиа={len(attachments)}"
            )

            # Запись в историю со статусом pending
            self.admin_db.add_repost(
                mid=mid,
                source_chat_id=chat_id,
                target_chat_id=TARGET_CHANNEL_ID,
                text_preview=text,
                media_count=len(attachments),
                status="pending",
            )

            # Скачиваем + загружаем медиа
            tokens, types = self._reupload_media(attachments)

            # Собираем HTML со ссылками
            html_text = build_html_text(text, markup)

            # В очередь (с mid, чтобы потом обновить статус)
            self.queue.enqueue(
                TARGET_CHANNEL_ID, html_text, tokens, types,
                mid=mid, admin_db=self.admin_db
            )

            # Помечаем как обработанное
            self.dedup.mark(mid)

        except Exception as e:
            logger.exception(f"❌ on_message_created: {e}")

    def _extract_content(self, msg: dict):
        link = msg.get("link") or {}
        if link.get("type") == "forward":
            inner = link.get("message") or {}
            return (
                inner.get("text", "") or "",
                inner.get("attachments", []) or [],
                inner.get("markup", []) or [],
            )
        body = msg.get("body") or {}
        return (
            body.get("text", "") or "",
            body.get("attachments", []) or [],
            [],
        )

    def _match_trigger(self, text: str) -> bool:
        if not text:
            return False
        return any(phrase in text for phrase in TRIGGER_PHRASES)

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
                logger.warning(f"⚠️ Нет url в attachment типа {att_type}")
                continue

            if att_type not in ("image", "video"):
                logger.warning(f"⚠️ Неизвестный тип: {att_type}")
                continue

            file_bytes = self.downloader.download(url)
            if not file_bytes:
                logger.error(f"❌ Не удалось скачать {att_type}")
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
