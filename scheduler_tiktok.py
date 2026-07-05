import logging
from core.sheets import get_sheet, get_pending_tiktok_rows, update_row
from platforms.tiktok import post as tiktok_post

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def run():
    log.info("Запуск планировщика TikTok...")
    sheet   = get_sheet()
    pending = get_pending_tiktok_rows(sheet)

    if not pending:
        log.info("Нет TikTok постов для планирования.")
        return

    log.info("Найдено TikTok постов: %d", len(pending))

    for row_index, row in pending:
        page_name     = row["page_name"]
        text          = row["text"]
        file_url      = row["file"]
        post_datetime = row["post_datetime"]

        log.info("Планирую TikTok [%s] на %s", page_name, post_datetime)

        post_id, error_msg = tiktok_post(page_name, text, file_url, post_datetime)

        if error_msg:
            log.error("Ошибка TikTok [%s]: %s", page_name, error_msg)
            update_row(sheet, row_index, status="error", error_msg=error_msg)
        else:
            log.info("✅ TikTok запланирован. buffer_post_id=%s", post_id)
            update_row(sheet, row_index, status="posted", post_id=post_id)

    log.info("Готово.")


if __name__ == "__main__":
    run()