# dedup.py
# ============================================================
# Защита от повторной обработки одного и того же сообщения
# ============================================================

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


class Dedup:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen (
                mid TEXT PRIMARY KEY,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def seen(self, mid: str) -> bool:
        """Проверяет, обрабатывали ли уже это сообщение."""
        if not mid:
            return False
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT 1 FROM seen WHERE mid=?", (mid,)).fetchone()
        conn.close()
        return row is not None

    def mark(self, mid: str):
        """Помечает сообщение как обработанное."""
        if not mid:
            return
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT OR IGNORE INTO seen (mid) VALUES (?)", (mid,))
        conn.commit()
        conn.close()

    def cleanup_old(self, days: int = 30):
        """Удаляет старые записи."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM seen WHERE ts < datetime('now', ?)",
            (f"-{days} days",),
        )
        conn.commit()
        conn.close()
