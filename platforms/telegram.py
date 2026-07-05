import os
import logging
import requests

log = logging.getLogger(__name__)

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_URL   = f"https://api.telegram.org/bot{TG_TOKEN}"

TG_CHANNELS = {
    "AFS":  os.getenv("TG_CHANNEL_AFS"),
    "DSL":  os.getenv("TG_CHANNEL_DSL"),
    "JUJU": os.getenv("TG_CHANNEL_JUJU"),
}


def post(page_name: str, text: str, file_url: str, post_type: str,
         files: list[str] | None = None) -> str:
    channel = TG_CHANNELS[page_name]

    if post_type == "text":
        r = requests.post(
            f"{TG_URL}/sendMessage",
            data={"chat_id": channel, "text": text, "parse_mode": "HTML"}
        )
        r.raise_for_status()
        return str(r.json()["result"]["message_id"])

    elif post_type == "photo":
        r = requests.post(
            f"{TG_URL}/sendPhoto",
            data={"chat_id": channel, "photo": file_url, "caption": text, "parse_mode": "HTML"}
        )
        r.raise_for_status()
        return str(r.json()["result"]["message_id"])

    elif post_type == "video":
        r = requests.post(
            f"{TG_URL}/sendVideo",
            data={"chat_id": channel, "video": file_url, "caption": text, "parse_mode": "HTML"}
        )
        r.raise_for_status()
        return str(r.json()["result"]["message_id"])

    elif post_type == "carousel":
        # sendMediaGroup — до 10 фото/видео одним сообщением
        urls = files if files else [u.strip() for u in file_url.split(",") if u.strip()]
        if len(urls) < 2:
            raise ValueError("Карусель требует минимум 2 файла")
        if len(urls) > 10:
            raise ValueError("Карусель поддерживает максимум 10 файлов")

        media = []
        for idx, url in enumerate(urls):
            is_video = any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi"))
            item = {
                "type":  "video" if is_video else "photo",
                "media": url,
            }
            # Подпись только к первому элементу
            if idx == 0 and text:
                item["caption"]    = text
                item["parse_mode"] = "HTML"
            media.append(item)

        import json
        r = requests.post(
            f"{TG_URL}/sendMediaGroup",
            data={"chat_id": channel, "media": json.dumps(media)}
        )
        r.raise_for_status()
        # sendMediaGroup возвращает массив сообщений — берём id первого
        return str(r.json()["result"][0]["message_id"])

    raise ValueError(f"Telegram не поддерживает тип: {post_type}")