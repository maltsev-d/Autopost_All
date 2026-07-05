import os
import json
import logging
import tempfile
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

YOUTUBE_TOKENS = {
    "AFS":  os.getenv("YOUTUBE_TOKEN_AFS"),
    "DSL":  os.getenv("YOUTUBE_TOKEN_DSL"),
    "JUJU": os.getenv("YOUTUBE_TOKEN_JUJU"),
}


def _get_credentials(page_name: str) -> Credentials:
    """Загружает credentials из .env, обновляет access_token если протух."""
    raw = YOUTUBE_TOKENS.get(page_name)
    if not raw:
        raise ValueError(f"YOUTUBE_TOKEN_{page_name} не задан в .env")

    token_data = json.loads(raw)

    creds = Credentials(
        token=         token_data.get("token"),
        refresh_token= token_data.get("refresh_token"),
        token_uri=     token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=     token_data.get("client_id"),
        client_secret= token_data.get("client_secret"),
        scopes=        token_data.get("scopes", SCOPES),
    )

    # Автообновление access_token через refresh_token
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            log.info("[YT] Обновляю access_token для %s...", page_name)
            creds.refresh(Request())
        else:
            raise ValueError(f"YouTube credentials невалидны для {page_name}")

    return creds


def _download_video(url: str) -> str:
    """Скачивает видео из Cloudinary во временный файл. Возвращает путь."""
    log.info("[YT] Скачиваю видео: %s", url)
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()

    suffix = ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in r.iter_content(chunk_size=1024 * 1024):
        tmp.write(chunk)
    tmp.close()

    log.info("[YT] Видео скачано: %s", tmp.name)
    return tmp.name


def post(page_name: str, text: str, file_url: str, post_type: str) -> str:
    """
    Публикует YouTube Short.
    Возвращает video_id опубликованного видео.

    Shorts = видео до 60 сек с вертикальным соотношением сторон (9:16).
    YouTube автоматически определяет Shorts — отдельного эндпоинта нет.

    Требует: youtube.upload scope.
    """
    if post_type != "video":
        raise ValueError(f"YouTube поддерживает только video, получен тип: {post_type}")

    creds   = _get_credentials(page_name)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # Скачиваем видео локально — YouTube API требует файл, не URL
    tmp_path = _download_video(file_url)

    try:
        body = {
            "snippet": {
                "title":       text[:100],   # YouTube лимит заголовка — 100 символов
                "description": text,
                "tags":        ["Shorts"],
                "categoryId":  "22",         # People & Blogs (универсальная категория)
            },
            "status": {
                "privacyStatus":          "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            tmp_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5 MB чанки
        )

        log.info("[YT] Загружаю видео для %s...", page_name)

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("[YT] Загрузка: %d%%", int(status.progress() * 100))

        video_id = response["id"]
        log.info("[YT] Опубликовано: https://youtube.com/shorts/%s", video_id)
        return video_id

    finally:
        # Удаляем временный файл в любом случае
        import os as _os
        try:
            _os.remove(tmp_path)
        except Exception:
            pass