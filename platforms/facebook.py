import os
import time
import logging
import requests

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"
FB_TOKEN  = os.getenv("FB_ACCESS_TOKEN")

FB_PAGE_IDS = {
    "AFS":  os.getenv("FB_PAGE_ID_AFS"),
    "DSL":  os.getenv("FB_PAGE_ID_DSL"),
    "JUJU": os.getenv("FB_PAGE_ID_JUJU"),
}

_page_tokens: dict = {}


def get_page_token(page_id: str) -> str:
    if page_id in _page_tokens:
        return _page_tokens[page_id]
    r = requests.get(
        f"{GRAPH_URL}/{page_id}",
        params={"fields": "access_token", "access_token": FB_TOKEN}
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise ValueError(f"Не удалось получить Page Token для page_id={page_id}")
    _page_tokens[page_id] = token
    return token


def post(page_name: str, text: str, file_url: str, post_type: str,
         files: list[str] | None = None) -> str:
    page_id    = FB_PAGE_IDS[page_name]
    page_token = get_page_token(page_id)

    if post_type == "text":
        r = requests.post(
            f"{GRAPH_URL}/{page_id}/feed",
            data={"message": text, "access_token": page_token}
        )
        r.raise_for_status()
        return r.json()["id"]

    elif post_type == "photo":
        r = requests.post(
            f"{GRAPH_URL}/{page_id}/photos",
            data={"url": file_url, "published": "false", "access_token": page_token}
        )
        r.raise_for_status()
        photo_id = r.json()["id"]
        r = requests.post(
            f"{GRAPH_URL}/{page_id}/feed",
            data={
                "message":        text,
                "attached_media": f'[{{"media_fbid":"{photo_id}"}}]',
                "access_token":   page_token,
            }
        )
        r.raise_for_status()
        return r.json()["id"]

    elif post_type == "carousel":
        # FB альбом — несколько фото одним постом
        urls = files if files else [u.strip() for u in file_url.split(",") if u.strip()]
        if len(urls) < 2:
            raise ValueError("Альбом требует минимум 2 фото")
        if len(urls) > 10:
            raise ValueError("Альбом поддерживает максимум 10 фото")

        # Шаг 1 — загружаем каждое фото как unpublished
        photo_ids = []
        for url in urls:
            r = requests.post(
                f"{GRAPH_URL}/{page_id}/photos",
                data={"url": url, "published": "false", "access_token": page_token}
            )
            r.raise_for_status()
            photo_ids.append(r.json()["id"])
            log.info("[FB] Альбом фото загружено: %s", r.json()["id"])

        # Шаг 2 — публикуем пост с прикреплёнными фото
        attached = str([{"media_fbid": pid} for pid in photo_ids]).replace("'", '"')
        r = requests.post(
            f"{GRAPH_URL}/{page_id}/feed",
            data={
                "message":        text,
                "attached_media": attached,
                "access_token":   page_token,
            }
        )
        r.raise_for_status()
        return r.json()["id"]

    elif post_type == "video":
        r = requests.post(
            f"{GRAPH_URL}/{page_id}/videos",
            data={"description": text, "file_url": file_url, "access_token": page_token}
        )
        log.info("FB video response: %s %s", r.status_code, r.text)
        r.raise_for_status()
        video_id = r.json()["id"]

        start = time.time()
        while True:
            check  = requests.get(
                f"{GRAPH_URL}/{video_id}",
                params={"fields": "status", "access_token": page_token}
            )
            status = check.json().get("status", {}).get("video_status")
            log.info("[FB video] %s → %s", video_id, status)
            if status == "ready":
                return video_id
            if status == "failed":
                log.warning("FB video upload failed: %s", video_id)
                return None
            if time.time() - start > 90:
                log.warning("FB video wait timeout: %s", video_id)
                return None
            time.sleep(3)

    raise ValueError(f"Неизвестный тип поста: {post_type}")