"""
Запускать один раз локально для получения token.json.
Требует: pip install google-auth-oauthlib

Использование:
  1. Положи client_secrets.json в ту же папку что и этот скрипт
  2. Запусти: python get_youtube_token.py
  3. Браузер откроется автоматически — авторизуйся под нужным Google аккаунтом
  4. После авторизации в папке появится youtube_token.json
  5. Содержимое youtube_token.json скопируй в .env как YOUTUBE_TOKEN_AFS= (или DSL/JUJU)
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secrets.json",
        scopes=SCOPES,
    )

    # Открывает браузер для авторизации
    creds = flow.run_local_server(port=0)

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes),
    }

    with open("youtube_token.json", "w") as f:
        json.dump(token_data, f, indent=2)

    print("\n✅ Готово! Файл youtube_token.json создан.")
    print("\nСкопируй его содержимое в .env:")
    print(f"YOUTUBE_TOKEN_AFS={json.dumps(token_data)}")

if __name__ == "__main__":
    main()