"""Gemini AI engine для глубокого анализа ГРІМ-5"""
import httpx
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def gemini_calculate(prompt: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"ai": "gemini", "status": "no_key", "response": "Set GEMINI_API_KEY in .env"}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=15)
            data = r.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "OK")
            return {"ai": "gemini", "status": "ok", "response": text}
        except Exception as e:
            logger.warning("Gemini API error: %s", e)
            return {"ai": "gemini", "status": "error", "response": "Gemini API call failed"}
