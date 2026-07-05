import os
import logging
import requests

log = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

LINE_TOKENS = {
    "AFS": os.getenv("LINE_TOKEN_AFS"),
    # DSL и JUJU добавить когда понадобится
}


def _headers(page_name: str) -> dict:
    token = LINE_TOKENS.get(page_name)
    if not token:
        raise ValueError(f"LINE_TOKEN_{page_name} не задан в .env")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _text_message(text: str) -> dict:
    return {"type": "text", "text": text}


def _image_message(url: str) -> dict:
    return {
        "type":             "image",
        "originalContentUrl": url,
        "previewImageUrl":    url,
    }


def _video_message(url: str) -> dict:
    return {
        "type":             "video",
        "originalContentUrl": url,
        "previewImageUrl":    url,  # Line требует preview — используем тот же URL
    }


def post(page_name: str, text: str, file_url: str, post_type: str,
         files: list[str] | None = None) -> str:
    """
    Broadcast сообщение в Line Official Account.
    Возвращает requestId из ответа API.
    """
    headers = _headers(page_name)
    messages = []

    if post_type == "text":
        messages.append(_text_message(text))

    elif post_type == "photo":
        if text:
            messages.append(_text_message(text))
        messages.append(_image_message(file_url))

    elif post_type == "video":
        if text:
            messages.append(_text_message(text))
        messages.append(_video_message(file_url))

    elif post_type == "carousel":
        # Несколько фото подряд — до 5 сообщений за один broadcast
        urls = files if files else [u.strip() for u in file_url.split(",") if u.strip()]
        if len(urls) < 2:
            raise ValueError("Карусель требует минимум 2 файла")

        if text:
            messages.append(_text_message(text))

        for url in urls:
            is_video = any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi"))
            messages.append(_video_message(url) if is_video else _image_message(url))

        # Line broadcast принимает максимум 5 сообщений за раз
        if len(messages) > 5:
            log.warning("[Line] Обрезаем до 5 сообщений (лимит API), было %d", len(messages))
            messages = messages[:5]

    else:
        raise ValueError(f"Line не поддерживает тип: {post_type}")

    r = requests.post(
        LINE_API_URL,
        headers=headers,
        json={"messages": messages},
        timeout=15,
    )

    log.info("[Line] %s response: %s %s", page_name, r.status_code, r.text)
    r.raise_for_status()

    # Line возвращает requestId для успешного broadcast
    request_id = r.headers.get("X-Line-Request-Id", "ok")
    return request_id