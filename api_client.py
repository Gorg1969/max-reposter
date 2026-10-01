# api_client.py
# ============================================================
# APIClient для MAX API
# v3: добавлены отладочные методы get_subscriptions_raw / get_me_raw
# ============================================================

import json
import time
import base64
import logging
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url

    # ============================================================
    # Загрузка файла (фото / видео)
    # ============================================================
    def upload_file(self, file_bytes: bytes, filename: str = "file.bin",
                    file_type: str = "image"):
        if not self.token:
            logger.error("❌ upload_file: нет токена")
            return None

        try:
            logger.info(f"📤 Шаг 1: /uploads для {file_type} {filename} ({len(file_bytes)} байт)")
            r = requests.post(
                f"{self.base_url}/uploads",
                headers={"Authorization": self.token},
                params={"type": file_type},
                timeout=30,
                verify=False,
            )
            logger.info(f"📨 Шаг 1: HTTP {r.status_code}")

            if r.status_code != 200:
                logger.error(f"❌ Шаг 1: {r.status_code} - {r.text[:300]}")
                return None

            data = r.json()
            upload_url = data.get("url")
            if not upload_url:
                logger.error(f"❌ Шаг 1: нет url в ответе: {data}")
                return None

            # ========== ВИДЕО ==========
            if file_type == "video":
                token_from_step1 = data.get("token")
                logger.info(
                    f"🎬 Видео: токен из Шага 1: "
                    f"{str(token_from_step1)[:30] + '...' if token_from_step1 else 'НЕТ'}"
                )

                logger.info(f"📤 Шаг 2: загрузка видео (multipart) на {upload_url[:100]}")
                ur = requests.post(
                    upload_url,
                    files={"data": (filename, file_bytes, "application/octet-stream")},
                    headers={"Content-Length": str(len(file_bytes))},
                    timeout=600,
                    verify=False,
                )
                logger.info(f"📨 Шаг 2 (multipart): HTTP {ur.status_code}")

                if ur.status_code not in (200, 201, 204):
                    logger.error(f"❌ Шаг 2 (multipart): {ur.status_code} - {ur.text[:300]}")

                if token_from_step1:
                    logger.info(f"✅ Токен видео (из Шага 1): {str(token_from_step1)[:30]}...")
                    return token_from_step1

                try:
                    result = ur.json()
                    logger.info(
                        f"📨 Ответ загрузки видео: "
                        f"{json.dumps(result, ensure_ascii=False)[:500]}"
                    )
                    token = result.get("token")
                    if not token and isinstance(result, dict):
                        for key in ("videos", "video", "data", "payload"):
                            if token:
                                break
                            val = result.get(key)
                            if isinstance(val, dict):
                                if "token" in val:
                                    token = val["token"]
                                else:
                                    for v in val.values():
                                        if isinstance(v, dict) and "token" in v:
                                            token = v["token"]
                                            break
                    if token:
                        logger.info(f"✅ Токен видео (из Шага 2): {str(token)[:30]}...")
                    else:
                        logger.error("❌ Токен видео не найден в ответе Шага 2")
                    return token
                except Exception as je:
                    logger.error(f"❌ Ошибка парсинга ответа видео: {je}")
                    logger.error(f"   Тело: {ur.text[:500]}")
                    return None

            # ========== IMAGE ==========
            logger.info(f"📤 Шаг 2: загрузка на {upload_url[:100]}")
            ur = requests.post(
                upload_url,
                files={"data": (filename, file_bytes)},
                timeout=300,
                verify=False,
            )
            logger.info(f"📨 Шаг 2: HTTP {ur.status_code}")

            if ur.status_code != 200:
                logger.error(f"❌ Шаг 2: {ur.status_code} - {ur.text[:200]}")
                return None

            result = ur.json()
            logger.info(f"📨 Ответ загрузки: {json.dumps(result, ensure_ascii=False)[:500]}")

            token = result.get("token")
            if not token and isinstance(result, dict):
                for key in ("photos", "videos", "data", "payload"):
                    if token:
                        break
                    val = result.get(key)
                    if isinstance(val, dict):
                        if "token" in val:
                            token = val["token"]
                        else:
                            for v in val.values():
                                if isinstance(v, dict) and "token" in v:
                                    token = v["token"]
                                    break

            if token:
                logger.info(f"✅ Токен: {str(token)[:30]}...")
            else:
                logger.error("❌ Токен не найден в ответе")
            return token

        except Exception as e:
            logger.exception(f"❌ upload_file упал: {e}")
            return None

    # ============================================================
    # Отправка поста
    # ============================================================
    def send_post(self, chat_id, text, media_tokens, media_types=None,
                  retry_not_ready=True, max_retries=12):
        """
        Отправляет пост с медиа.
        chat_id передаётся КАК ЕСТЬ — без добавления минуса.
        """
        if not self.token:
            return False, None

        try:
            if media_types is None:
                media_types = ["image"] * len(media_tokens)
            if len(media_types) < len(media_tokens):
                media_types = media_types + ["image"] * (len(media_tokens) - len(media_types))

            attachments = []
            for i, token in enumerate(media_tokens[:10]):
                mtype = media_types[i] if i < len(media_types) else "image"
                attachments.append({"type": mtype, "payload": {"token": token}})

            payload = {"text": text, "format": "markdown"}
            if attachments:
                payload["attachments"] = attachments

            chat_id_str = str(chat_id)
            has_video = "video" in media_types

            for attempt in range(1, max_retries + 1):
                logger.info(
                    f"📤 Отправка в {chat_id_str} "
                    f"(попытка {attempt}/{max_retries}), "
                    f"медиа: {len(attachments)} ({media_types})"
                )

                r = requests.post(
                    f"{self.base_url}/messages",
                    headers={
                        "Authorization": self.token,
                        "Content-Type": "application/json",
                    },
                    params={"chat_id": chat_id_str},
                    json=payload,
                    timeout=120,
                    verify=False,
                )

                logger.info(f"📨 Ответ: {r.status_code}")

                if r.status_code == 200:
                    post_link = None
                    try:
                        result = r.json()
                        seq = None
                        if isinstance(result, dict):
                            if "message" in result and isinstance(result["message"], dict):
                                msg = result["message"]
                                if "body" in msg and isinstance(msg["body"], dict):
                                    seq = msg["body"].get("seq")
                            if not seq and "seq" in result:
                                seq = result["seq"]
                        if seq:
                            seq_bytes = int(seq).to_bytes(8, byteorder="big")
                            encoded = base64.urlsafe_b64encode(seq_bytes).decode("utf-8").rstrip("=")
                            post_link = f"https://max.ru/c/{chat_id_str}/{encoded}"
                            logger.info(f"🔗 Ссылка: {post_link}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось получить ссылку: {e}")
                    return True, post_link

                error_text = r.text.lower()
                if "attachment.not.ready" in error_text or "not.processed" in error_text:
                    if retry_not_ready and attempt < max_retries:
                        if has_video:
                            wait = min(5 * (2 ** (attempt - 1)), 180)
                        else:
                            wait = min(3 * attempt, 30)
                        logger.warning(f"⚠️ Медиа ещё не обработано, ждём {wait} сек...")
                        time.sleep(wait)
                        continue

                logger.error(f"❌ send_post: {r.status_code} - {r.text[:300]}")
                return False, None

            return False, None

        except Exception as e:
            logger.exception(f"❌ send_post: {e}")
            return False, None

    # ============================================================
    # Настройка вебхука
    # ============================================================
    def setup_webhook(self, webhook_url: str) -> bool:
        if not self.token:
            return False

        headers = {"Authorization": self.token, "Content-Type": "application/json"}

        try:
            r = requests.get(
                f"{self.base_url}/subscriptions",
                headers=headers, timeout=30, verify=False,
            )
            if r.status_code == 200:
                for sub in r.json().get("subscriptions", []):
                    old_url = sub.get("url")
                    if old_url:
                        requests.delete(
                            f"{self.base_url}/subscriptions",
                            headers=headers,
                            params={"url": old_url},
                            timeout=30, verify=False,
                        )
                        logger.info(f"🗑️ Удалена старая подписка: {old_url}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить старые подписки: {e}")

        try:
            r = requests.post(
                f"{self.base_url}/subscriptions",
                headers=headers,
                json={
                    "url": webhook_url,
                    "update_types": [
                        "message_created",
                        "message_callback",
                        "bot_started",
                        "bot_stopped",
                        "bot_added",
                        "bot_removed",
                    ],
                },
                timeout=30,
                verify=False,
            )
            logger.info(f"📨 SUBSCRIBE RESPONSE: {r.status_code} {r.text[:500]}")
            if r.status_code == 200:
                logger.info(f"✅ Вебхук зарегистрирован: {webhook_url}")
                return True
            logger.error(f"❌ Ошибка регистрации вебхука: {r.status_code} - {r.text}")
            return False
        except Exception as e:
            logger.exception(f"❌ setup_webhook: {e}")
            return False

    # ============================================================
    # ОТЛАДКА
    # ============================================================
    def get_subscriptions_raw(self):
        if not self.token:
            return {"error": "no token"}
        try:
            r = requests.get(
                f"{self.base_url}/subscriptions",
                headers={"Authorization": self.token},
                timeout=30, verify=False,
            )
            return {"status": r.status_code, "body": r.text}
        except Exception as e:
            return {"error": str(e)}

    def get_me_raw(self):
        if not self.token:
            return {"error": "no token"}
        try:
            r = requests.get(
                f"{self.base_url}/me",
                headers={"Authorization": self.token},
                timeout=30, verify=False,
            )
            return {"status": r.status_code, "body": r.text}
        except Exception as e:
            return {"error": str(e)}
