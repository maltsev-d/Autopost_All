import os
import json
import logging
import requests

log = logging.getLogger(__name__)

BUFFER_API_KEYS = {
    "AFS":  os.getenv("BUFFER_API_KEY_AFS"),
    "DSL":  os.getenv("BUFFER_API_KEY_DSL"),
    "JUJU": os.getenv("BUFFER_API_KEY_JUJU"),
}

BUFFER_CHANNEL_IDS = {
    "AFS":  os.getenv("BUFFER_CHANNEL_ID_AFS"),
    "DSL":  os.getenv("BUFFER_CHANNEL_ID_DSL"),
    "JUJU": os.getenv("BUFFER_CHANNEL_ID_JUJU"),
}

TZ_OFFSET = int(os.getenv("TZ_OFFSET", "7"))


def post(page_name: str, text: str, file_url: str, post_datetime) -> tuple[str | None, str | None]:
    """
    Планирует TikTok-пост через Buffer GraphQL.
    Возвращает (buffer_post_id, error_msg).
    """
    api_key    = BUFFER_API_KEYS.get(page_name)
    channel_id = BUFFER_CHANNEL_IDS.get(page_name)

    if not api_key:
        return None, f"BUFFER_API_KEY не найден для {page_name}"
    if not channel_id:
        return None, f"BUFFER_CHANNEL_ID не найден для {page_name}"

    sign   = "+" if TZ_OFFSET >= 0 else "-"
    tz_str = f"{sign}{abs(TZ_OFFSET):02d}:00"
    due_at = post_datetime.strftime(f"%Y-%m-%dT%H:%M:%S{tz_str}")

    safe_text = text.replace("\\", "\\\\").replace('"', '\\"')

    query = f"""mutation CreatePost {{
        createPost(input: {{
            text: "{safe_text}"
            channelId: "{channel_id}"
            schedulingType: automatic
            mode: customScheduled
            dueAt: "{due_at}"
            assets: [{{ video: {{ url: "{file_url}" }} }}]
        }}) {{
            ... on PostActionSuccess {{
                post {{ id }}
            }}
            ... on MutationError {{
                message
            }}
        }}
    }}"""

    try:
        r = requests.post(
            "https://api.buffer.com",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={"query": query},
            timeout=15,
        )
        data = r.json()

        if "errors" in data:
            msg = data["errors"][0].get("message", "Unknown GraphQL error")
            log.error("Buffer GraphQL error: %s", msg)
            return None, msg

        result = data.get("data", {}).get("createPost", {})

        if "post" in result:
            post_id = result["post"]["id"]
            log.info("TikTok запланирован через Buffer: %s → %s", page_name, post_id)
            return post_id, None

        if "message" in result:
            log.error("Buffer mutation error: %s", result["message"])
            return None, result["message"]

        return None, f"Unexpected Buffer response: {result}"

    except requests.RequestException as e:
        return None, f"Request error: {e}"
    except json.JSONDecodeError:
        return None, "Invalid JSON from Buffer"