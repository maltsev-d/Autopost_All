import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TZ_OFFSET = int(os.getenv("TZ_OFFSET", "7"))
LOCAL_TZ  = timezone(timedelta(hours=TZ_OFFSET))

DATE_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
]

# Колонки Google Sheets (1-based)
COL = {
    "date":          1,
    "platform":      2,
    "page_name":     3,
    "text":          4,
    "file":          5,
    "type":          6,
    "status":        7,
    "post_id":       8,
    "error_msg":     9,
    "views":         10,
    "likes":         11,
    "comments":      12,
    "shares":        13,
    "saved":         14,
    "stats_updated": 15,
}


def parse_date(date_str: str) -> datetime:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    raise ValueError(f"Не удалось распознать дату: '{date_str}'")


def get_client():
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if not raw:
        raise ValueError("GOOGLE_CREDENTIALS не задан в .env")
    try:
        creds_dict = json.loads(raw)
    except json.JSONDecodeError:
        creds_dict = json.loads(base64.b64decode(raw))
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    client   = get_client()
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID не задан в .env")
    return client.open_by_key(sheet_id).sheet1


def get_pending_rows(sheet):
    """Строки со статусом pending и датой <= сейчас."""
    now  = datetime.now(LOCAL_TZ)
    rows = sheet.get_all_values()
    result = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 7:
            continue
        status = row[COL["status"] - 1].strip().lower()
        if status != "pending":
            continue
        date_str = row[COL["date"] - 1].strip()
        try:
            post_time = parse_date(date_str)
        except ValueError:
            continue
        if post_time <= now:
            file_raw = row[COL["file"] - 1].strip()
            files    = [u.strip() for u in file_raw.split(",") if u.strip()]
            result.append((i, {
                "platform":  row[COL["platform"]  - 1].strip().lower(),
                "page_name": row[COL["page_name"] - 1].strip().upper(),
                "text":      row[COL["text"]      - 1].strip(),
                "file":      file_raw,           # оригинальная строка
                "files":     files,              # список URL (1+ элементов)
                "type":      row[COL["type"]      - 1].strip().lower(),
            }))
    return result


def get_pending_tiktok_rows(sheet):
    """Строки TikTok со статусом pending и датой > сейчас (планируем наперёд через Buffer)."""
    now  = datetime.now(LOCAL_TZ)
    rows = sheet.get_all_values()
    result = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 7:
            continue
        platform = row[COL["platform"] - 1].strip().lower()
        status   = row[COL["status"]   - 1].strip().lower()
        if platform != "tiktok" or status != "pending":
            continue
        date_str = row[COL["date"] - 1].strip()
        try:
            post_time = parse_date(date_str)
        except ValueError:
            continue
        # Для TikTok берём посты в будущем — Buffer сам запланирует
        if post_time > now:
            file_raw = row[COL["file"] - 1].strip()
            result.append((i, {
                "platform":      "tiktok",
                "page_name":     row[COL["page_name"] - 1].strip().upper(),
                "text":          row[COL["text"]      - 1].strip(),
                "file":          file_raw,
                "files":         [u.strip() for u in file_raw.split(",") if u.strip()],
                "type":          row[COL["type"]      - 1].strip().lower(),
                "post_datetime": post_time,
            }))
    return result


def get_stats_rows(sheet, max_age_days: int = 30):
    """
    Строки для обновления статистики:
    - статус posted
    - пост не старше max_age_days дней
    - stats_updated пустой ИЛИ обновлялся более 7 дней назад
    """
    now  = datetime.now(LOCAL_TZ)
    rows = sheet.get_all_values()
    result = []
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (COL["stats_updated"] - len(row))
        status        = row[COL["status"]        - 1].strip().lower()
        post_id       = row[COL["post_id"]       - 1].strip()
        platform      = row[COL["platform"]      - 1].strip().lower()
        page_name     = row[COL["page_name"]     - 1].strip().upper()
        date_str      = row[COL["date"]          - 1].strip()
        stats_updated = row[COL["stats_updated"] - 1].strip()

        if status != "posted" or not post_id:
            continue
        # Telegram и TikTok — статистика недоступна через API
        if platform in ("telegram", "tiktok", "line"):
            continue

        try:
            post_time = parse_date(date_str)
        except ValueError:
            continue
        if (now - post_time).days > max_age_days:
            continue

        if stats_updated:
            try:
                last_dt = datetime.strptime(stats_updated, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
                if (now - last_dt).days < 7:
                    continue
            except ValueError:
                pass

        result.append((i, {
            "platform":  platform,
            "post_id":   post_id,
            "page_name": page_name,
        }))
    return result


def update_row(sheet, row_index: int, status: str, post_id: str = "", error_msg: str = ""):
    sheet.update_cell(row_index, COL["status"],    status)
    sheet.update_cell(row_index, COL["post_id"],   post_id)
    sheet.update_cell(row_index, COL["error_msg"], error_msg)


def update_stats(sheet, row_index: int, stats: dict):
    now = datetime.now(LOCAL_TZ)
    # Пишем только те поля, которые есть в stats (None/отсутствие = оставляем пустым)
    fields = ["views", "likes", "comments", "shares", "saved"]
    for field in fields:
        if field in stats:
            sheet.update_cell(row_index, COL[field], stats[field])
    sheet.update_cell(row_index, COL["stats_updated"], now.strftime("%Y-%m-%d"))