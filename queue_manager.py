# queue_manager.py
# ============================================================
# Очередь отправки с соблюдением rate-limit (2 сообщения/сек)
# ============================================================

import queue
import time
import logging
import threading

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, api_client, send_interval: float = 0.6):
        self.api = api_client
        self.q = queue.Queue()
        self.send_interval = send_interval
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()
        logger.info(f"✅ QueueManager запущен (интервал {send_interval} сек)")

    def enqueue(self, chat_id: str, text: str, tokens: list, types: list):
        """Кладёт задачу в очередь."""
        self.q.put((chat_id, text, tokens, types))
        logger.info(f"📥 В очередь: {len(tokens)} медиа, всего в очереди: {self.q.qsize()}")

    def _loop(self):
        while True:
            try:
                chat_id, text, tokens, types = self.q.get()
                logger.info(f"📤 Отправка из очереди в {chat_id} ({len(tokens)} медиа)")

                ok, link = self.api.send_post(chat_id, text, tokens, types)

                if ok:
                    logger.info(f"✅ Отправлено в {chat_id}: {link or '(ссылка не получена)'}")
                else:
                    logger.error(f"❌ Не удалось отправить в {chat_id}")

                time.sleep(self.send_interval)
            except Exception as e:
                logger.exception(f"❌ Ошибка воркера очереди: {e}")
                time.sleep(1)
