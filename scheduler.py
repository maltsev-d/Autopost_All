import logging
from core.sheets import get_sheet, get_pending_rows, update_row
from core.validator import validate_post
from platforms import facebook, instagram, telegram, youtube, line

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PLATFORM_MAP = {
    "facebook":  facebook.post,
    "instagram": instagram.post,
    "telegram":  telegram.post,
    "youtube":   youtube.post,
    "line":      line.post,
}


def run():
    log.info("Запуск планировщика...")
    sheet   = get_sheet()
    pending = get_pending_rows(sheet)

    if not pending:
        log.info("Нет постов для публикации.")
        return

    log.info("Найдено постов: %d", len(pending))

    for row_index, row in pending:
        platform  = row["platform"]
        page_name = row["page_name"]
        text      = row["text"]
        file_url  = row["file"]
        files     = row["files"]
        post_type = row["type"]

        if platform == "tiktok":
            continue

        poster = PLATFORM_MAP.get(platform)
        if not poster:
            log.warning("Неизвестная платформа: %s — пропускаем", platform)
            update_row(sheet, row_index, status="error", error_msg=f"Неизвестная платформа: {platform}")
            continue

        log.info("Валидация: [%s] [%s] тип=%s", platform, page_name, post_type)
        warnings = validate_post(platform, post_type, file_url, text, files)
        if warnings:
            for w in warnings:
                log.warning("  ⚠ %s", w)
            update_row(sheet, row_index, status="error", error_msg="Валидация: " + " | ".join(warnings))
            log.error("Пост пропущен из-за ошибок валидации.")
            continue

        log.info("Публикация: [%s] [%s] тип=%s", platform, page_name, post_type)
        try:
            post_id = poster(page_name, text, file_url, post_type, files)
            log.info("✅ Опубликовано. post_id=%s", post_id)
            update_row(sheet, row_index, status="posted", post_id=str(post_id))
        except Exception as e:
            log.error("Ошибка публикации: %s", e)
            update_row(sheet, row_index, status="error", error_msg=str(e))

    log.info("Готово.")


if __name__ == "__main__":
    run()