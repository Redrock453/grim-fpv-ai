"""GLM (ChatGLM) engine"""
import httpx
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def glm_calculate(prompt: str):
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        return {"ai": "glm", "status": "no_key", "response": "Set GLM_API_KEY in .env"}
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=15)
            data = r.json()
            return {"ai": "glm", "status": "ok", "response": data["choices"][0]["message"]["content"]}
        except Exception as e:
            logger.warning("GLM API error: %s", e)
            return {"ai": "glm", "status": "error", "response": "GLM API call failed"}
