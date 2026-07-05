import subprocess
import json
import logging
import requests

log = logging.getLogger(__name__)

TEXT_LIMITS = {
    "instagram": 2200,
    "facebook":  63206,
    "telegram":  1024,
    "tiktok":    2200,
    "youtube":   5000,
    "line":      5000,
}


def _get_video_info(url: str) -> dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", url],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout)
    except Exception as e:
        log.warning(f"ffprobe error: {e}")
        return {}


def validate_video(url: str, platform: str) -> list[str]:
    warnings = []
    info = _get_video_info(url)

    if not info:
        warnings.append("Не удалось получить метаданные видео — проверь что URL публичный и прямой")
        return warnings

    streams  = info.get("streams", [])
    video_st = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_st = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt      = info.get("format", {})

    if not video_st:
        warnings.append("Видео поток не найден")
        return warnings

    codec    = video_st.get("codec_name", "").lower()
    width    = int(video_st.get("width", 0))
    height   = int(video_st.get("height", 0))
    duration = float(fmt.get("duration", 0))
    ratio    = round(width / height, 2) if height else 0

    if platform in ("instagram", "tiktok", "youtube"):
        if codec not in ("h264", "avc"):
            warnings.append(f"Кодек {codec} — нужен H.264")
        if ratio > 0.57:
            warnings.append(f"Разрешение {width}x{height} — нужен вертикальный формат 9:16")
        if not audio_st:
            warnings.append("Аудио поток не найден — рекомендуется для Reels/Shorts")

    if platform == "instagram":
        if duration < 3:
            warnings.append(f"Длина {duration:.1f} сек — минимум 3 сек")
        elif duration > 900:
            warnings.append(f"Длина {duration:.1f} сек — максимум 15 мин")
        if width > 1920 or height > 1920:
            warnings.append(f"Разрешение {width}x{height} — максимум 1920px")

    elif platform == "youtube":
        if duration > 60:
            warnings.append(f"Длина {duration:.1f} сек — YouTube Shorts максимум 60 сек")

    elif platform == "facebook":
        if duration > 14400:
            warnings.append(f"Длина {duration:.1f} сек — максимум 4 часа")
        if width < 120 or height < 120:
            warnings.append(f"Разрешение {width}x{height} — минимум 120x120")

    elif platform == "telegram":
        size_mb = float(fmt.get("size", 0)) / 1024 / 1024
        if size_mb > 2000:
            warnings.append(f"Размер {size_mb:.0f} МБ — лимит Telegram 2 ГБ")

    return warnings


def validate_image(url: str) -> list[str]:
    warnings = []
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        if r.status_code == 405:
            r = requests.get(url, timeout=10, allow_redirects=True, stream=True)
        content_type = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            warnings.append(f"URL недоступен (статус {r.status_code})")
        elif "image" not in content_type:
            warnings.append(f"URL не является изображением (Content-Type: {content_type})")
    except Exception as e:
        warnings.append(f"Не удалось проверить URL: {e}")
    return warnings


def validate_post(platform: str, post_type: str, file_url: str, text: str,
                  files: list[str] | None = None) -> list[str]:
    warnings = []

    limit = TEXT_LIMITS.get(platform)
    if limit and len(text) > limit:
        warnings.append(f"Текст {len(text)} символов — лимит {platform} {limit}")

    if post_type == "carousel":
        urls = files if files else [u.strip() for u in file_url.split(",") if u.strip()]

        if platform == "line" and len(urls) > 4:
            # С текстом занимаем 1 слот, остаётся 4 под медиа
            warnings.append(f"Line carousel: максимум 4 файла (с учётом текста лимит 5 сообщений), передано {len(urls)}")

        if len(urls) < 2:
            warnings.append("Карусель требует минимум 2 файла")
        elif len(urls) > 10:
            warnings.append(f"Карусель поддерживает максимум 10 файлов, передано {len(urls)}")

        for url in urls:
            is_video = any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi"))
            if is_video:
                warnings += validate_video(url, platform)
            else:
                warnings += validate_image(url)

    elif post_type == "video" and file_url:
        warnings += validate_video(file_url, platform)

    elif post_type == "photo" and file_url:
        warnings += validate_image(file_url)

    elif post_type in ("photo", "video") and not file_url:
        warnings.append(f"Тип '{post_type}' но URL файла пустой")

    return warnings