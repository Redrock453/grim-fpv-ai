"""GLM (ChatGLM) engine"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def glm_calculate(prompt: str):
    api_key = os.getenv("GLM_API_KEY")  # ← добавь в .env если используешь
    if not api_key:
        return {"ai": "glm", "status": "no_key", "response": "Вставь GLM_API_KEY"}
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # Zhipu GLM
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=15)
            data = r.json()
            return {"ai": "glm", "status": "ok", "response": data["choices"][0]["message"]["content"]}
        except:
            return {"ai": "glm", "status": "error", "response": "Ошибка вызова"}
