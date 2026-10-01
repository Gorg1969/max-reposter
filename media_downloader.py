# media_downloader.py
# ============================================================
# Скачивание медиа из входящего сообщения MAX
# ============================================================

import logging
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class MediaDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; MaxReposter/1.0)"
        })

    def download(self, url: str, timeout: int = 60):
        """
        Скачивает файл по URL.
        Возвращает bytes или None.
        """
        if not url:
            return None
        try:
            r = self.session.get(url, timeout=timeout, verify=False)
            if r.status_code != 200:
                logger.error(f"❌ Скачивание: HTTP {r.status_code} для {url[:100]}")
                return None
            logger.info(f"⬇️ Скачано {len(r.content)} байт с {url[:80]}")
            return r.content
        except requests.exceptions.Timeout:
            logger.error(f"❌ Таймаут скачивания: {url[:100]}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания: {e}")
            return None
