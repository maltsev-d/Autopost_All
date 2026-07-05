import os
import json
import time
import logging
import requests
from core.sheets import get_sheet, get_stats_rows, update_stats

log = logging.getLogger(__name__)

GRAPH_URL       = "https://graph.facebook.com/v19.0"
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")

FB_PAGE_IDS = {
    "AFS":  os.getenv("FB_PAGE_ID_AFS"),
    "DSL":  os.getenv("FB_PAGE_ID_DSL"),
    "JUJU": os.getenv("FB_PAGE_ID_JUJU"),
}


# ─── Meta API helper ─────────────────────────────────────────────

def meta_get(url: str, params: dict, retries: int = 3) -> dict:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            log.warning("Meta API attempt %d/%d: %s", attempt, retries, r.text)
        except Exception as e:
            log.warning("Meta API exception attempt %d/%d: %s", attempt, retries, e)
        time.sleep(2 ** (attempt - 1))
    log.error("Meta API не ответил после всех попыток")
    return {}


def get_page_token(page_id: str) -> str:
    data = meta_get(
        f"{GRAPH_URL}/{page_id}",
        {"fields": "access_token", "access_token": FB_ACCESS_TOKEN}
    )
    if "error" in data:
        raise Exception(f"Token error: {data['error']}")
    if "access_token" not in data:
        raise Exception(f"Токен не получен для page_id={page_id}, ответ: {data}")
    return data["access_token"]


# ─── Facebook ────────────────────────────────────────────────────

def _is_fb_video(post_id: str) -> bool:
    """Page Post содержит '_', Reel/Video — чистое число."""
    return "_" not in post_id.strip()


def _fetch_fb_post_stats(post_id: str, token: str) -> dict:
    """Статистика обычного Page Post."""
    result = {}

    data = meta_get(
        f"{GRAPH_URL}/{post_id}",
        {"fields": "likes.summary(true),comments.summary(true)", "access_token": token}
    )
    likes    = data.get("likes",    {}).get("summary", {}).get("total_count")
    comments = data.get("comments", {}).get("summary", {}).get("total_count")
    if likes    is not None: result["likes"]    = likes
    if comments is not None: result["comments"] = comments

    # Охват через /insights (best effort)
    insights = meta_get(
        f"{GRAPH_URL}/{post_id}/insights",
        {"metric": "post_impressions_unique", "access_token": token}
    )
    for item in insights.get("data", []):
        if item.get("name") == "post_impressions_unique":
            vals = item.get("values", [])
            if vals:
                result["views"] = vals[0].get("value")

    return result


def _fetch_fb_video_stats(video_id: str, token: str) -> dict:
    """
    Статистика FB Reel / Video.
    shares — недоступны через Graph API для Reels.
    comments — отдельный запрос, надёжнее чем post_video_social_actions.
    """
    result = {}

    # Просмотры и лайки из video_insights
    data = meta_get(
        f"{GRAPH_URL}/{video_id}",
        {"fields": "video_insights", "access_token": token}
    )
    for item in data.get("video_insights", {}).get("data", []):
        name   = item.get("name")
        values = item.get("values", [])
        value  = values[0].get("value") if values else None
        if value is None:
            continue
        if name == "fb_reels_total_plays":
            result["views"] = value
        elif name == "post_video_likes_by_reaction_type" and isinstance(value, dict):
            result["likes"] = sum(value.values())

    # Комментарии отдельным запросом — надёжнее для видео/Reels
    comments_data = meta_get(
        f"{GRAPH_URL}/{video_id}",
        {"fields": "comments.summary(true)", "access_token": token}
    )
    total = (
        comments_data
        .get("comments", {})
        .get("summary", {})
        .get("total_count")
    )
    if total is not None:
        result["comments"] = total

    return result


def fetch_fb_stats(post_id: str, token: str) -> dict:
    if not isinstance(post_id, str) or not post_id.strip():
        return {}
    post_id = post_id.strip()
    if _is_fb_video(post_id):
        log.info("[FB] Reel/Video -> %s", post_id)
        return _fetch_fb_video_stats(post_id, token)
    log.info("[FB] Page Post -> %s", post_id)
    return _fetch_fb_post_stats(post_id, token)


# ─── Instagram ───────────────────────────────────────────────────

def fetch_ig_stats(post_id: str, token: str) -> dict:
    """
    likes, comments — прямые поля объекта (надёжно для всех типов).
    views:
      IMAGE / CAROUSEL → reach (уникальные аккаунты)
      VIDEO / REELS    → plays, fallback → video_views
    saved — best effort, недоступно для Reels.
    """
    if not post_id.isdigit():
        log.warning("[IG] Некорректный media_id: %s", post_id)
        return {}

    result = {}

    # Лайки, комментарии, тип контента
    data = meta_get(
        f"{GRAPH_URL}/{post_id}",
        {"fields": "like_count,comments_count,media_type", "access_token": token}
    )
    if "like_count"     in data: result["likes"]    = data["like_count"]
    if "comments_count" in data: result["comments"] = data["comments_count"]

    media_type = data.get("media_type", "").upper()  # IMAGE / VIDEO / CAROUSEL_ALBUM
    log.info("[IG] media_type=%s post_id=%s", media_type, post_id)

    is_video = media_type == "VIDEO"

    # Просмотры + saved одним запросом
    if is_video:
        # Reels: метрика views (plays/video_views не поддерживаются)
        ins = meta_get(
            f"{GRAPH_URL}/{post_id}/insights",
            {"metric": "views", "access_token": token}
        )
        for item in ins.get("data", []):
            if item.get("name") == "views":
                val = item.get("values", [{}])[0].get("value")
                if val is not None:
                    result["views"] = val
    else:
        # Фото / карусель — reach + saved одним запросом
        ins = meta_get(
            f"{GRAPH_URL}/{post_id}/insights",
            {"metric": "reach,saved", "access_token": token}
        )
        for item in ins.get("data", []):
            name = item.get("name")
            val  = item.get("values", [{}])[0].get("value")
            if val is None:
                continue
            if name == "reach":
                result["views"] = val
            elif name == "saved":
                result["saved"] = val

    return result

# ─── YouTube ─────────────────────────────────────────────────────

def _get_yt_credentials(page_name: str):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    YOUTUBE_TOKENS = {
        "AFS":  os.getenv("YOUTUBE_TOKEN_AFS"),
        "DSL":  os.getenv("YOUTUBE_TOKEN_DSL"),
        "JUJU": os.getenv("YOUTUBE_TOKEN_JUJU"),
    }

    raw = YOUTUBE_TOKENS.get(page_name)
    if not raw:
        return None

    token_data = json.loads(raw)
    creds = Credentials(
        token=         token_data.get("token"),
        refresh_token= token_data.get("refresh_token"),
        token_uri=     token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=     token_data.get("client_id"),
        client_secret= token_data.get("client_secret"),
        scopes=        token_data.get("scopes"),
    )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def fetch_yt_stats(video_id: str, page_name: str) -> dict:
    """
    Статистика YouTube видео через YouTube Data API v3.
    views, likes, comments — прямые поля statistics объекта.
    """
    from googleapiclient.discovery import build

    result = {}

    creds = _get_yt_credentials(page_name)
    if not creds:
        log.warning("[YT] YOUTUBE_TOKEN не задан для %s", page_name)
        return result

    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        response = youtube.videos().list(
            part="statistics",
            id=video_id,
        ).execute()

        items = response.get("items", [])
        if not items:
            log.warning("[YT] Видео не найдено: %s", video_id)
            return result

        stats = items[0].get("statistics", {})

        if "viewCount"    in stats: result["views"]    = int(stats["viewCount"])
        if "likeCount"    in stats: result["likes"]    = int(stats["likeCount"])
        if "commentCount" in stats: result["comments"] = int(stats["commentCount"])

        log.info("[YT] %s: %s", video_id, result)

    except Exception as e:
        log.error("[YT] Ошибка статистики %s: %s", video_id, e)

    return result

# ─── Основной процесс ────────────────────────────────────────────

def run():
    log.info("Запуск сбора статистики...")
    sheet = get_sheet()
    rows  = get_stats_rows(sheet, max_age_days=30)

    if not rows:
        log.info("Нет постов для обновления.")
        return

    log.info("Найдено постов для обновления: %d", len(rows))

    tokens: dict = {}

    for row_index, row in rows:
        try:
            platform  = row["platform"]
            post_id   = row["post_id"]
            page_name = row["page_name"]

            log.info("->  Строка %d: %s | %s", row_index, platform, post_id)

            if platform in ("facebook", "instagram"):
                if page_name not in tokens:
                    page_id = FB_PAGE_IDS.get(page_name)
                    if not page_id:
                        log.warning("FB_PAGE_ID не найден для %s", page_name)
                        continue
                    tokens[page_name] = get_page_token(page_id)
                token = tokens[page_name]

            stats = {}

            if platform == "facebook":
                stats = fetch_fb_stats(post_id, token)
            elif platform == "instagram":
                stats = fetch_ig_stats(post_id, token)
            elif platform == "youtube":
                stats = fetch_yt_stats(post_id, page_name)
            else:
                log.warning("Неизвестная платформа: %s", platform)
                continue

            if not stats:
                log.warning("Нет статистики для %s", post_id)
                continue

            update_stats(sheet, row_index, stats)
            log.info("OK %s: %s", post_id, stats)

        except Exception as e:
            log.error("Ошибка в строке %d: %s", row_index, e)
            continue

    log.info("Сбор статистики завершён.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()


