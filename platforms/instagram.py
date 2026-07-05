import os
import time
import logging
import requests
from platforms.facebook import get_page_token

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"

IG_PAGE_IDS = {
    "AFS":  os.getenv("IG_PAGE_ID_AFS"),
    "DSL":  os.getenv("IG_PAGE_ID_DSL"),
    "JUJU": os.getenv("IG_PAGE_ID_JUJU"),
}

FB_PAGE_IDS = {
    "AFS":  os.getenv("FB_PAGE_ID_AFS"),
    "DSL":  os.getenv("FB_PAGE_ID_DSL"),
    "JUJU": os.getenv("FB_PAGE_ID_JUJU"),
}


def _wait_for_container(container_id: str, page_token: str,
                        max_wait: int = 60, interval: int = 5) -> None:
    for _ in range(max_wait // interval):
        r = requests.get(
            f"{GRAPH_URL}/{container_id}",
            params={"fields": "status_code,status", "access_token": page_token}
        )
        if r.status_code != 200:
            break
        data        = r.json()
        status_code = data.get("status_code", "")
        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise ValueError(f"Instagram не смог обработать медиафайл: {data.get('status')}")
        time.sleep(interval)


def _create_single_container(ig_id: str, page_token: str,
                              file_url: str, post_type: str,
                              caption: str = "", is_carousel_item: bool = False) -> str:
    """Создаёт медиа-контейнер. Возвращает container_id."""
    data = {"access_token": page_token}

    if is_carousel_item:
        data["is_carousel_item"] = "true"
    else:
        data["caption"] = caption

    if post_type == "photo":
        data["image_url"]  = file_url
        data["media_type"] = "IMAGE"
    elif post_type in ("video", "carousel_video"):
        data["video_url"]  = file_url
        data["media_type"] = "REELS" if not is_carousel_item else "VIDEO"
    else:
        raise ValueError(f"Instagram не поддерживает тип: {post_type}")

    r = requests.post(f"{GRAPH_URL}/{ig_id}/media", data=data)
    r.raise_for_status()
    return r.json()["id"]


def post(page_name: str, text: str, file_url: str, post_type: str,
         files: list[str] | None = None) -> str:
    ig_id      = IG_PAGE_IDS[page_name]
    fb_page_id = FB_PAGE_IDS[page_name]
    page_token = get_page_token(fb_page_id)

    # ── Карусель ─────────────────────────────────────────────────
    if post_type == "carousel":
        urls = files if files else [u.strip() for u in file_url.split(",") if u.strip()]
        if len(urls) < 2:
            raise ValueError("Карусель требует минимум 2 файла")
        if len(urls) > 10:
            raise ValueError("Карусель поддерживает максимум 10 файлов")

        # Шаг 1 — контейнер для каждого элемента
        children = []
        for url in urls:
            # Определяем тип элемента по расширению
            item_type = "video" if any(url.lower().endswith(ext)
                                       for ext in (".mp4", ".mov", ".avi")) else "photo"
            container_id = _create_single_container(
                ig_id, page_token, url, item_type, is_carousel_item=True
            )
            _wait_for_container(container_id, page_token)
            children.append(container_id)
            log.info("[IG] Карусель элемент загружен: %s", container_id)

        # Шаг 2 — карусельный контейнер
        r = requests.post(
            f"{GRAPH_URL}/{ig_id}/media",
            data={
                "media_type":  "CAROUSEL",
                "children":    ",".join(children),
                "caption":     text,
                "access_token": page_token,
            }
        )
        r.raise_for_status()
        carousel_id = r.json()["id"]
        _wait_for_container(carousel_id, page_token)

        # Шаг 3 — публикация
        r = requests.post(
            f"{GRAPH_URL}/{ig_id}/media_publish",
            data={"creation_id": carousel_id, "access_token": page_token}
        )
        r.raise_for_status()
        return r.json()["id"]

    # ── Фото / видео ─────────────────────────────────────────────
    container_id = _create_single_container(ig_id, page_token, file_url, post_type, caption=text)
    _wait_for_container(container_id, page_token)

    r = requests.post(
        f"{GRAPH_URL}/{ig_id}/media_publish",
        data={"creation_id": container_id, "access_token": page_token}
    )
    r.raise_for_status()
    return r.json()["id"]