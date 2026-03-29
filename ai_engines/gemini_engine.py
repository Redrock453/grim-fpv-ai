"""Gemini engine для глубокого анализа ГРІМ-5"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def gemini_calculate(prompt: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"ai": "gemini", "status": "no_key", "response": "Вставь GEMINI_API_KEY в .env"}
    # Реальный вызов Gemini REST (упрощённо)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=15)
            data = r.json()
            return {"ai": "gemini", "status": "ok", "response": data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "OK")}
        except:
            return {"ai": "gemini", "status": "error", "response": "Ошибка вызова"}
