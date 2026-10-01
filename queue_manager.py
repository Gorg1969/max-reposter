# queue_manager.py
# ============================================================
# Очередь отправки + rate-limit
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

    def enqueue(self, chat_id, text, tokens, types, mid=None, admin_db=None):
        self.q.put({
            "chat_id": chat_id,
            "text": text,
            "tokens": tokens,
            "types": types,
            "mid": mid,
            "admin_db": admin_db,
        })
        logger.info(f"📥 В очередь: {len(tokens)} медиа, всего: {self.q.qsize()}")

    def _loop(self):
        while True:
            try:
                task = self.q.get()
                chat_id = task["chat_id"]
                text = task["text"]
                tokens = task["tokens"]
                types = task["types"]
                mid = task.get("mid")
                admin_db = task.get("admin_db")

                logger.info(f"📤 Отправка в {chat_id} ({len(tokens)} медиа)")

                ok, link = self.api.send_post(chat_id, text, tokens, types)

                if admin_db and mid:
                    if ok:
                        admin_db.update_repost(mid, "success", post_link=link)
                    else:
                        admin_db.update_repost(mid, "error", error="send_post failed")

                if ok:
                    logger.info(f"✅ Отправлено: {link or '(без ссылки)'}")
                else:
                    logger.error(f"❌ Не удалось отправить в {chat_id}")

                time.sleep(self.send_interval)
            except Exception as e:
                logger.exception(f"❌ Ошибка воркера: {e}")
                time.sleep(1)
