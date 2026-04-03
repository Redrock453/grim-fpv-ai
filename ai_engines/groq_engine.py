"""Groq engine (Llama-3 / Mixtral)"""
import httpx
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def groq_calculate(prompt: str):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"ai": "groq", "status": "no_key", "response": "Set GROQ_API_KEY in .env"}
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=10)
            data = r.json()
            return {"ai": "groq", "status": "ok", "response": data["choices"][0]["message"]["content"]}
        except Exception as e:
            logger.warning("Groq API error: %s", e)
            return {"ai": "groq", "status": "error", "response": "Groq API call failed"}
