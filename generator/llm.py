import requests

URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"

def ask_llm(prompt: str):
    res = requests.post(URL, json={
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 400  # КРИТИЧНО: ограничение длины
        }
    })

    data = res.json()

    # DEBUG SAFETY (ВАЖНО)
    if "message" in data and "content" in data["message"]:
        return data["message"]["content"]

    # fallback если Ollama вернул ошибку
    if "error" in data:
        raise Exception(f"Ollama error: {data['error']}")

    # если вообще непонятный ответ
    raise Exception(f"Unexpected Ollama response: {data}")