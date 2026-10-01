# html_builder.py
# ============================================================
# Сборка HTML-текста со кликабельными ссылками
# ============================================================

import logging
import html as html_lib

logger = logging.getLogger(__name__)


def build_html_text(text: str, markup: list) -> str:
    """
    Собирает HTML-текст с сохранением ссылок из markup.

    MAX передаёт в markup список элементов с полями:
      - from, length — позиция в тексте
      - type: "link" | "user_mention" | "strong" | "emphasized" | "underline"
      - url — для type="link"
      - user_id — для type="user_mention"
    """
    if not text:
        return ""

    if not markup:
        # Нет разметки — просто экранируем и возвращаем
        return html_lib.escape(text)

    # Сортируем markup по позиции
    items = sorted(markup, key=lambda m: m.get("from", 0))

    # Разбираем текст на куски с разметкой
    result = []
    pos = 0

    for item in items:
        start = item.get("from", 0)
        length = item.get("length", 0)
        end = start + length

        if start < pos or end > len(text):
            continue  # некорректный markup — пропускаем

        # Текст до разметки
        if start > pos:
            result.append(html_lib.escape(text[pos:start]))

        chunk = text[start:end]
        mtype = item.get("type")

        if mtype == "link":
            url = item.get("url", "")
            if url:
                result.append(f'<a href="{html_lib.escape(url)}">{html_lib.escape(chunk)}</a>')
            else:
                result.append(html_lib.escape(chunk))
        elif mtype == "user_mention":
            # Оставляем как обычный текст (упоминание)
            result.append(html_lib.escape(chunk))
        elif mtype == "strong":
            result.append(f"<b>{html_lib.escape(chunk)}</b>")
        elif mtype == "emphasized":
            result.append(f"<i>{html_lib.escape(chunk)}</i>")
        elif mtype == "underline":
            result.append(f"<u>{html_lib.escape(chunk)}</u>")
        else:
            result.append(html_lib.escape(chunk))

        pos = end

    # Остаток текста
    if pos < len(text):
        result.append(html_lib.escape(text[pos:]))

    return "".join(result)
