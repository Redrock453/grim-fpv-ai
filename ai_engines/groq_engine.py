"""Groq engine (Llama-3 / Mixtral)"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def groq_calculate(prompt: str):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"ai": "groq", "status": "no_key", "response": "Вставь GROQ_API_KEY в .env"}
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=10)
            data = r.json()
            return {"ai": "groq", "status": "ok", "response": data["choices"][0]["message"]["content"]}
        except:
            return {"ai": "groq", "status": "error", "response": "Ошибка вызова"}
