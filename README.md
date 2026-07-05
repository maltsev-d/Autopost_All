# Autoposter

Автоматическая публикация контента в Facebook, Instagram, Telegram, TikTok, YouTube Shorts и Line Official Account. Расписание и контент хранятся в Google Sheets, запуск — через GitHub Actions.

---

## Возможности

- Публикация фото, видео, текста и каруселей в FB / IG / TG / TikTok / YouTube / Line
- Управление тремя проектами из одной таблицы (AFS, DSL, JUJU)
- Валидация медиафайлов перед публикацией (кодек, разрешение, длительность)
- Сбор статистики: просмотры, лайки, комментарии, сохранения
- Автозапуск через GitHub Actions (бесплатно, без сервера)

---

## Структура проекта

```
autoposter/
├── core/
│   ├── sheets.py            # Чтение/запись Google Sheets
│   └── validator.py         # Валидация медиа перед публикацией
├── platforms/
│   ├── facebook.py          # Публикация в Facebook (фото/видео/текст/альбом)
│   ├── instagram.py         # Публикация в Instagram (фото/видео/карусель)
│   ├── telegram.py          # Публикация в Telegram (фото/видео/текст/карусель)
│   ├── tiktok.py            # Планирование TikTok через Buffer
│   ├── youtube.py           # Публикация YouTube Shorts
│   └── line.py              # Broadcast в Line Official Account
├── stats/
│   └── stats_collector.py   # Сбор статистики FB + IG + YouTube
├── scheduler.py             # Планировщик FB / IG / TG / YouTube / Line
├── scheduler_tiktok.py      # Планировщик TikTok
├── requirements.txt
├── .env.example
└── .github/workflows/
    ├── post.yml             # Запуск каждые 30 мин (FB/IG/TG/YouTube/Line)
    ├── post_tiktok.yml      # Запуск каждые 30 мин (TikTok)
    └── stats.yml            # Сбор статистики раз в 3 дня
```

---

## Google Sheets — структура таблицы

| Колонка | Описание |
|---|---|
| `date` | Дата и время публикации (`2026-06-10 10:00`) |
| `platform` | `facebook` / `instagram` / `telegram` / `tiktok` / `youtube` / `line` |
| `page_name` | `AFS` / `DSL` / `JUJU` |
| `text` | Текст поста |
| `file` | URL медиафайла (Cloudinary). Для карусели — через запятую: `url1,url2,url3` |
| `type` | `photo` / `video` / `text` / `carousel` |
| `status` | `pending` → `posted` / `error` |
| `post_id` | ID опубликованного поста |
| `error_msg` | Текст ошибки при неудачной публикации |
| `views` | Просмотры / охват |
| `likes` | Лайки |
| `comments` | Комментарии |
| `shares` | Репосты |
| `saved` | Сохранения (только IG фото/карусель) |
| `stats_updated` | Дата последнего обновления статистики |

Шаблон с тестовыми данными: `autoposter_template.xlsx`

---

## Карусели

Тип `carousel` в колонке `type`, несколько URL через запятую в колонке `file`.

| Платформа | Карусель | Особенности |
|---|---|---|
| Instagram | ✅ | 2–10 элементов, фото + видео вперемешку |
| Telegram | ✅ | 2–10 элементов через `sendMediaGroup` |
| Facebook | ✅ | Альбом из фото (только фото, не видео) |
| Line | ✅ | До 4 файлов (5-й слот занимает текст) |
| TikTok | ❌ | Не поддерживается |
| YouTube | ❌ | Не поддерживается |

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/your-username/autoposter.git
cd autoposter
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Создать `.env`

```bash
cp .env.example .env
```

Заполнить все нужные переменные.

### 4. Загрузить шаблон в Google Sheets

- Открыть `autoposter_template.xlsx`
- Импортировать в Google Sheets: **Файл → Импорт**
- Скопировать ID таблицы из URL: `docs.google.com/spreadsheets/d/**SHEET_ID**/edit`

---

## Переменные окружения

```env
# Google
GOOGLE_CREDENTIALS=       # JSON сервисного аккаунта (raw JSON или base64)
GOOGLE_SHEET_ID=

# Meta
FB_ACCESS_TOKEN=
FB_PAGE_ID_AFS=
FB_PAGE_ID_DSL=
FB_PAGE_ID_JUJU=
IG_PAGE_ID_AFS=
IG_PAGE_ID_DSL=
IG_PAGE_ID_JUJU=

# Telegram
TG_BOT_TOKEN=
TG_CHANNEL_AFS=
TG_CHANNEL_DSL=
TG_CHANNEL_JUJU=

# Buffer (TikTok)
BUFFER_API_KEY_AFS=
BUFFER_API_KEY_DSL=
BUFFER_API_KEY_JUJU=
BUFFER_CHANNEL_ID_AFS=
BUFFER_CHANNEL_ID_DSL=
BUFFER_CHANNEL_ID_JUJU=

# YouTube
YOUTUBE_TOKEN_AFS=
YOUTUBE_TOKEN_DSL=
YOUTUBE_TOKEN_JUJU=

# Line Official Account
LINE_TOKEN_AFS=
# LINE_TOKEN_DSL=         # добавить когда понадобится
# LINE_TOKEN_JUJU=        # добавить когда понадобится

# Настройки
TZ_OFFSET=7
```

---

## Настройка YouTube OAuth

YouTube требует OAuth 2.0 авторизацию — делается **один раз локально** для каждого канала.

### Шаг 1 — Google Cloud Console

1. Открыть [console.cloud.google.com](https://console.cloud.google.com)
2. Создать проект или выбрать существующий
3. Включить: **YouTube Data API v3** и **YouTube Analytics API**
4. Перейти в **APIs & Services → OAuth consent screen**
   - User Type: **External**
   - App name: любое без слов Google/YouTube/Bot/Auto (например `ContentScheduler`)
   - Добавить свой email в Test users
5. Перейти в **Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Скачать `client_secrets.json`

### Шаг 2 — Получить токен локально

```bash
pip install google-auth-oauthlib
python get_youtube_token.py
```

Откроется браузер — авторизоваться под нужным Google аккаунтом. Скрипт выведет готовую строку для `.env`:

```
YOUTUBE_TOKEN_AFS={"token": "ya29.xxx", "refresh_token": "1//xxx", ...}
```

### Шаг 3 — Добавить в .env и GitHub Secrets

Скопировать строку в `.env` и добавить как GitHub Secret `YOUTUBE_TOKEN_AFS`.

> `refresh_token` не протухает. `access_token` обновляется автоматически — повторная авторизация не нужна.

---

## Настройка Line Official Account

1. Открыть [developers.line.biz](https://developers.line.biz)
2. Создать провайдера и канал типа **Messaging API**
3. В настройках канала → **Basic settings → Channel access token** → **Issue**
4. Скопировать токен в `.env` как `LINE_TOKEN_AFS`

> Line broadcast работает только если у Official Account есть подписчики. Статистика через API недоступна.

---

## Настройка GitHub Actions

Все переменные из `.env` добавить как **GitHub Secrets**:

**Settings → Secrets and variables → Actions → New repository secret**

| Workflow | Расписание | Что делает |
|---|---|---|
| `post.yml` | каждые 30 мин | FB / IG / TG / YouTube / Line |
| `post_tiktok.yml` | каждые 30 мин | TikTok через Buffer |
| `stats.yml` | пн / чт / вс в 03:00 UTC | Статистика за 30 дней |

Ручной запуск: **Actions → выбрать workflow → Run workflow**

---

## Как добавить пост

1. Открыть Google Sheets
2. Добавить строку, заполнить поля
3. Поставить `status = pending`
4. Дождаться ближайшего запуска планировщика (до 30 мин)

Для карусели в поле `file` вписать URL через запятую: `url1,url2,url3`

Для TikTok дата должна быть **в будущем** — Buffer запланирует публикацию сам.

---

## Статистика

| Платформа | views | likes | comments | saved |
|---|---|---|---|---|
| FB пост (фото/текст/альбом) | охват | ✅ | ✅ | — |
| FB Reel / видео | воспроизведения | ✅ | ✅ | — |
| IG фото / карусель | охват (reach) | ✅ | ✅ | ✅ |
| IG Reels | воспроизведения | ✅ | ✅ | — |
| YouTube Shorts | ✅ | ✅ | ✅ | — |
| Telegram | — | — | — | — |
| TikTok | — | — | — | — |
| Line | — | — | — | — |

---

## Требования к аккаунтам

**Meta (FB / IG):** System User Token с правами `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `read_insights`. Instagram — профессиональный аккаунт (Business или Creator).

**Telegram:** Бот должен быть администратором канала.

**TikTok:** Отдельный Buffer аккаунт на каждый проект с подключённым TikTok.

**YouTube:** Google аккаунт с YouTube каналом, OAuth Desktop App авторизация (один раз локально).

**Line:** Канал типа Messaging API в Line Developers Console, Long-lived Channel Access Token.

---

## Локальный запуск

```bash
python scheduler.py             # FB / IG / TG / YouTube / Line
python scheduler_tiktok.py      # TikTok
python -m stats.stats_collector # Статистика
python get_youtube_token.py     # YouTube OAuth (один раз)
```