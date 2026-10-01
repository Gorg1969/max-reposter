# auth.py
# ============================================================
# Basic Auth для админки
# ============================================================

from functools import wraps
from flask import request
import logging

from config import ADMIN_USER, ADMIN_PASS

logger = logging.getLogger(__name__)


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Если пароль не задан — авторизация отключена
        if not ADMIN_PASS:
            return f(*args, **kwargs)

        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return (
                "🔒 Требуется авторизация",
                401,
                {"WWW-Authenticate": 'Basic realm="max-reposter Admin"'},
            )
        return f(*args, **kwargs)

    return decorated
