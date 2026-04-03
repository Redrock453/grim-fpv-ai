"""Gemini AI engine для глубокого анализа ГРІМ-5"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()


async def gemini_calculate(prompt: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"ai": "gemini", "status": "no_key", "response": "Set GEMINI_API_KEY in .env"}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=15)
            data = r.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "OK")
            return {"ai": "gemini", "status": "ok", "response": text}
        except Exception:
            return {"ai": "gemini", "status": "error", "response": "Gemini API call failed"}
