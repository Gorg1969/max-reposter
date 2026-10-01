# admin_db.py
# ============================================================
# БД для истории пересылок и настроек
# ============================================================

import os
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AdminDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # История пересылок
        c.execute("""
            CREATE TABLE IF NOT EXISTS reposted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mid TEXT UNIQUE,
                source_chat_id TEXT,
                target_chat_id TEXT,
                target_post_link TEXT,
                text_preview TEXT,
                media_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Настройки (key-value)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Черный список mid (пропущенные сообщения)
        c.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                mid TEXT PRIMARY KEY,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info("✅ AdminDB инициализирована")

    # ============================================================
    # История
    # ============================================================
    def add_repost(self, mid, source_chat_id, target_chat_id,
                   text_preview, media_count, status="pending"):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO reposted
                (mid, source_chat_id, target_chat_id, text_preview, media_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, source_chat_id, target_chat_id,
                  (text_preview or "")[:300], media_count, status))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ add_repost: {e}")
            return False

    def update_repost(self, mid, status, post_link=None, error=None):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                UPDATE reposted
                SET status = ?, target_post_link = COALESCE(?, target_post_link),
                    error = ?, created_at = created_at
                WHERE mid = ?
            """, (status, post_link, error, mid))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ update_repost: {e}")
            return False

    def get_reposts(self, limit=100, status=None, source_chat_id=None):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            query = "SELECT * FROM reposted WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if source_chat_id:
                query += " AND source_chat_id = ?"
                params.append(source_chat_id)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            rows = c.execute(query, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"❌ get_reposts: {e}")
            return []

    def get_stats(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute("SELECT COUNT(*) FROM reposted")
            total = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM reposted WHERE status='success'")
            success = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM reposted WHERE status='error'")
            errors = c.fetchone()[0]

            c.execute("""
                SELECT COUNT(*) FROM reposted
                WHERE status='success'
                  AND DATE(created_at) = DATE('now', 'localtime')
            """)
            today = c.fetchone()[0]

            conn.close()
            return {
                "total": total,
                "success": success,
                "errors": errors,
                "today": today,
            }
        except Exception as e:
            logger.error(f"❌ get_stats: {e}")
            return {"total": 0, "success": 0, "errors": 0, "today": 0}

    def delete_repost(self, mid):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM reposted WHERE mid = ?", (mid,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ delete_repost: {e}")
            return False

    # ============================================================
    # Настройки
    # ============================================================
    def get_setting(self, key, default=None):
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            conn.close()
            return row[0] if row else default
        except Exception as e:
            logger.error(f"❌ get_setting: {e}")
            return default

    def set_setting(self, key, value):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ set_setting: {e}")
            return False

    # ============================================================
    # Черный список
    # ============================================================
    def blacklist_add(self, mid, reason=""):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR IGNORE INTO blacklist (mid, reason) VALUES (?, ?)
            """, (mid, reason))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ blacklist_add: {e}")
            return False

    def blacklist_has(self, mid):
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT 1 FROM blacklist WHERE mid = ?", (mid,)).fetchone()
            conn.close()
            return row is not None
        except Exception as e:
            logger.error(f"❌ blacklist_has: {e}")
            return False

    # ============================================================
    # Очистка старых записей
    # ============================================================
    def cleanup_old(self, days: int = 90):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "DELETE FROM reposted WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ cleanup_old: {e}")
